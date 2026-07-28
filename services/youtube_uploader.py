"""
YouTube uploader (YouTube Data API v3).

Publishes a generated short via `videos.insert`. A vertical (9:16) video <= 3 min
is automatically treated as a **Short** by YouTube (no separate Shorts API), so our
1080x1920, 15-60s clips upload as Shorts. Adding #Shorts in the title/description
(our metadata already does) helps discovery.

Design goals:
- **Fail-safe**: all heavy imports (googleapiclient, google-auth) are lazy, so the
  Flask app runs fine without the libraries installed. `status()` reports exactly
  what's missing and how to fix it.
- **Secure**: the OAuth token is stored via services.secure_store (OS keychain or
  encrypted file). Tokens are never logged.
- **No API keys**: uploading acts on behalf of a Google account, so OAuth 2.0 is
  required. The user signs in once (browser), we keep a refresh token.

Setup the user must do once (documented in AGENTS.md/README):
  1. Google Cloud Console -> new project -> enable "YouTube Data API v3".
  2. Configure OAuth consent screen (External, add yourself as a Test user).
  3. Create OAuth client ID of type **Desktop app**; download the JSON.
  4. Save it as `youtube_client_secret.json` in the project root (gitignored).
Then click "Connect Google" in the app.
"""

import os
import json
import logging
import datetime

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRET_PATH = os.path.join(_BASE, "youtube_client_secret.json")
TOKEN_SECRET_NAME = "youtube_oauth_token"  # key in secure_store
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]

VALID_PRIVACY = {"private", "unlisted", "public"}
DEFAULT_PRIVACY = "private"


# ------------------------------------------------------------------ dependencies
def _deps_available():
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
        import google.oauth2.credentials  # noqa: F401
        return True
    except Exception:
        return False


def _watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


# ------------------------------------------------------------------ credentials
def _load_credentials():
    """Return valid google Credentials from the stored token, refreshing if needed."""
    from services import secure_store
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    raw = secure_store.get_secret(TOKEN_SECRET_NAME)
    if not raw:
        return None
    info = json.loads(raw)
    creds = Credentials.from_authorized_user_info(info, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_credentials(creds)
        except Exception as e:
            logger.warning("Token refresh failed: %s", e)
            return None
    return creds


def _save_credentials(creds) -> None:
    from services import secure_store
    secure_store.set_secret(TOKEN_SECRET_NAME, creds.to_json())


def _build_service(creds):
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


# ------------------------------------------------------------------ public API
def status() -> dict:
    """
    Report the integration state so the UI can decide what to show.
    Never raises; always returns a dict.
    """
    if not _deps_available():
        return {
            "available": False,
            "configured": False,
            "connected": False,
            "reason": "libraries_missing",
            "message": "YouTube libraries not installed.",
            "fix": "pip install google-api-python-client google-auth-oauthlib google-auth-httplib2",
        }

    configured = os.path.exists(CLIENT_SECRET_PATH)
    if not configured:
        return {
            "available": True,
            "configured": False,
            "connected": False,
            "reason": "missing_client_secret",
            "message": "OAuth client secret not found.",
            "fix": f"Create a Desktop-app OAuth client in Google Cloud (YouTube Data API v3) "
                   f"and save it as {os.path.basename(CLIENT_SECRET_PATH)} in the project root.",
        }

    try:
        from services import secure_store
        store_backend = secure_store.backend_name()
        creds = _load_credentials()
    except Exception as e:
        return {"available": True, "configured": True, "connected": False,
                "reason": "error", "message": str(e)}

    if not creds or not creds.valid:
        return {
            "available": True, "configured": True, "connected": False,
            "reason": "not_connected",
            "message": "Not connected to a YouTube account yet.",
            "token_backend": store_backend,
        }

    channel = None
    try:
        svc = _build_service(creds)
        resp = svc.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            channel = items[0]["snippet"]["title"]
    except Exception as e:
        logger.warning("channels.list failed: %s", e)

    return {
        "available": True, "configured": True, "connected": True,
        "channel": channel,
        "token_backend": store_backend,
    }


def connect(open_browser: bool = True) -> dict:
    """
    Run the OAuth installed-app flow (Google sign-in in the browser) and store the
    token securely. Blocking; intended for localhost single-user.
    """
    if not _deps_available():
        raise RuntimeError("YouTube libraries not installed.")
    if not os.path.exists(CLIENT_SECRET_PATH):
        raise RuntimeError(
            f"Missing {os.path.basename(CLIENT_SECRET_PATH)}. Create a Desktop-app "
            "OAuth client (YouTube Data API v3) and save the JSON to the project root."
        )
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    # port=0 -> pick a free loopback port; works with Desktop-app OAuth clients.
    creds = flow.run_local_server(port=0, open_browser=open_browser,
                                  authorization_prompt_message="",
                                  success_message="Connected! You can close this tab and return to the app.")
    _save_credentials(creds)
    st = status()
    logger.info("Connected to YouTube channel: %s", st.get("channel"))
    return st


def disconnect() -> None:
    """Forget the stored token."""
    from services import secure_store
    secure_store.delete_secret(TOKEN_SECRET_NAME)


def upload(video_path: str, title: str, description: str, tags=None,
           privacy: str = DEFAULT_PRIVACY, made_for_kids: bool = False,
           progress_callback=None) -> dict:
    """
    Upload one video (resumable). Returns {video_id, url, privacy, uploaded_at}.
    Raises RuntimeError on any hard failure.
    """
    if not _deps_available():
        raise RuntimeError("YouTube libraries not installed.")
    if not os.path.exists(video_path):
        raise RuntimeError(f"Video not found: {video_path}")
    if privacy not in VALID_PRIVACY:
        privacy = DEFAULT_PRIVACY

    creds = _load_credentials()
    if not creds or not creds.valid:
        raise RuntimeError("Not connected to YouTube. Click 'Connect Google' first.")

    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    svc = _build_service(creds)
    # YouTube truncates tags list total length; keep it reasonable.
    clean_tags = [t.lstrip("#") for t in (tags or []) if isinstance(t, str) and t.strip()]

    body = {
        "snippet": {
            "title": (title or "Gameplay Short")[:100],
            "description": (description or "")[:5000],
            "tags": clean_tags[:30],
            "categoryId": "20",  # Gaming
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    media = MediaFileUpload(video_path, chunksize=1024 * 1024, resumable=True,
                            mimetype="video/mp4")
    request = svc.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            gstatus, response = request.next_chunk()
            if gstatus and progress_callback:
                progress_callback(int(gstatus.progress() * 100))
    except HttpError as e:
        raise RuntimeError(f"YouTube upload failed: {e}") from e

    video_id = response["id"]
    return {
        "video_id": video_id,
        "url": _watch_url(video_id),
        "privacy": privacy,
        "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
