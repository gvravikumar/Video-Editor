"""
Test script for State Persistence & Resume functionality
Run this to verify that task state is properly saved and can be resumed.
"""

import requests
import time
import json
import sys

BASE_URL = "http://localhost:8000"


def test_state_persistence():
    """Test the complete state persistence workflow."""
    
    print("=" * 60)
    print("STATE PERSISTENCE & RESUME TEST")
    print("=" * 60)
    
    # Step 1: Check if server is running
    print("\n1. Checking server status...")
    try:
        response = requests.get(f"{BASE_URL}/system/info")
        if response.status_code == 200:
            print("   ✓ Server is running")
            info = response.json()
            print(f"   Device: {info['device_name']}")
        else:
            print("   ✗ Server returned error")
            return False
    except Exception as e:
        print(f"   ✗ Server not accessible: {e}")
        print("   Please start the server with: python app.py")
        return False
    
    # Step 2: List existing tasks
    print("\n2. Listing all existing tasks...")
    response = requests.get(f"{BASE_URL}/ai/tasks")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Found {data['total']} existing tasks")
        if data['total'] > 0:
            for task in data['tasks'][:3]:  # Show first 3
                print(f"     - {task['task_id'][:8]}... | {task['status']} | {task['percentage']}%")
    
    # Step 3: List resumable tasks
    print("\n3. Checking for resumable tasks...")
    response = requests.get(f"{BASE_URL}/ai/tasks/resumable")
    if response.status_code == 200:
        data = response.json()
        resumable_count = data['total']
        print(f"   ✓ Found {resumable_count} resumable task(s)")
        
        if resumable_count > 0:
            print("\n   Resumable tasks:")
            for task in data['tasks']:
                print(f"     - Task: {task['task_id'][:8]}...")
                print(f"       Status: {task['status']}")
                print(f"       Progress: {task['percentage']}%")
                print(f"       Last checkpoint: {task['last_checkpoint']}")
                print(f"       File: {task['filename']}")
                
                # Ask if user wants to resume
                print(f"\n   Would you like to resume this task? (y/n)")
                choice = input("   > ").strip().lower()
                
                if choice == 'y':
                    test_resume_task(task['task_id'])
                    return True
    
    # Step 4: Check for uploaded videos
    print("\n4. Checking for uploaded videos...")
    response = requests.get(f"{BASE_URL}/uploads/list")
    if response.status_code == 200:
        data = response.json()
        video_count = len(data.get('files', []))
        print(f"   ✓ Found {video_count} uploaded video(s)")
        
        if video_count == 0:
            print("\n   No videos found to test with.")
            print("   Please upload a video through the web interface first.")
            return False
        
        # Use first video for testing
        video = data['files'][0]
        filename = video['filename']
        print(f"\n   Using video: {filename}")
        print(f"   Size: {video['size_mb']} MB")
        
        # Ask if user wants to start a new task
        print(f"\n   Start a new AI processing task with this video? (y/n)")
        choice = input("   > ").strip().lower()
        
        if choice == 'y':
            test_start_and_interrupt(filename)
            return True
    
    print("\n   Test complete - no actions taken.")
    return True


def test_start_and_interrupt(filename):
    """Start a task and demonstrate interruption/resume."""
    print("\n" + "=" * 60)
    print("TESTING: Start Task → Interrupt → Resume")
    print("=" * 60)
    
    # Start task
    print(f"\n1. Starting AI pipeline for {filename}...")
    response = requests.post(
        f"{BASE_URL}/ai/start",
        json={"filename": filename, "fps": 2}
    )
    
    if response.status_code != 200:
        print(f"   ✗ Failed to start task: {response.text}")
        return False
    
    data = response.json()
    task_id = data['task_id']
    print(f"   ✓ Task started: {task_id[:8]}...")
    
    # Monitor progress for 30 seconds
    print("\n2. Monitoring progress for 30 seconds...")
    print("   (In real scenario, page reload would happen here)")
    
    for i in range(6):  # 6 * 5 = 30 seconds
        time.sleep(5)
        response = requests.get(f"{BASE_URL}/ai/status/{task_id}")
        if response.status_code == 200:
            status = response.json()
            print(f"   [{i*5}s] {status['percentage']}% - {status['step_message']}")
            
            if status['status'] in ['completed', 'error']:
                print(f"   Task finished early: {status['status']}")
                return True
    
    # Simulate interruption - check current status
    print("\n3. Checking task state (simulating interruption)...")
    response = requests.get(f"{BASE_URL}/ai/status/{task_id}")
    if response.status_code == 200:
        status = response.json()
        print(f"   Current state:")
        print(f"     Status: {status['status']}")
        print(f"     Progress: {status['percentage']}%")
        print(f"     Last checkpoint: {status.get('last_checkpoint', 'None')}")
        
        print("\n   💡 In real usage:")
        print("   - User would refresh the page now")
        print("   - Server might restart")
        print("   - Task state is saved in state/{task_id}.json")
        print("   - Task can be resumed from last checkpoint")
        
        # Check state file
        print(f"\n4. State file saved at: state/{task_id}.json")
        print("   You can inspect it with:")
        print(f"   cat state/{task_id}.json | jq")
        
        # Ask about resuming
        print("\n   Would you like to test resuming this task? (y/n)")
        choice = input("   > ").strip().lower()
        
        if choice == 'y':
            test_resume_task(task_id)
    
    return True


def test_resume_task(task_id):
    """Test resuming an interrupted task."""
    print("\n" + "=" * 60)
    print(f"TESTING: Resume Task {task_id[:8]}...")
    print("=" * 60)
    
    print("\n1. Attempting to resume task...")
    response = requests.post(f"{BASE_URL}/ai/resume/{task_id}")
    
    if response.status_code != 200:
        print(f"   ✗ Failed to resume: {response.text}")
        return False
    
    data = response.json()
    print(f"   ✓ Task resumed successfully")
    print(f"   Last checkpoint: {data.get('last_checkpoint', 'unknown')}")
    
    # Monitor resumed task
    print("\n2. Monitoring resumed task...")
    print("   (Press Ctrl+C to stop monitoring)")
    
    try:
        while True:
            time.sleep(3)
            response = requests.get(f"{BASE_URL}/ai/status/{task_id}")
            if response.status_code == 200:
                status = response.json()
                print(f"   {status['percentage']}% - {status['step_message']}")
                
                if status['status'] == 'completed':
                    print("\n   ✓ Task completed successfully!")
                    
                    # Show results
                    response = requests.get(f"{BASE_URL}/ai/results/{task_id}")
                    if response.status_code == 200:
                        results = response.json()
                        print(f"\n   Results:")
                        print(f"     Frames: {results['frame_count']}")
                        print(f"     Moments: {results['moment_count']}")
                        print(f"     Shorts: {results['short_count']}")
                    break
                
                elif status['status'] == 'error':
                    print(f"\n   ✗ Task failed: {status.get('error', 'Unknown error')}")
                    break
    
    except KeyboardInterrupt:
        print("\n\n   Monitoring stopped (task still running in background)")
    
    return True


def test_api_endpoints():
    """Quick test of all new API endpoints."""
    print("\n" + "=" * 60)
    print("TESTING: API Endpoints")
    print("=" * 60)
    
    endpoints = [
        ("GET", "/ai/tasks", "List all tasks"),
        ("GET", "/ai/tasks/resumable", "List resumable tasks"),
        ("GET", "/system/info", "System info"),
    ]
    
    for method, endpoint, description in endpoints:
        print(f"\n{method} {endpoint}")
        print(f"  {description}...")
        
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            if response.status_code == 200:
                print(f"  ✓ Success")
                data = response.json()
                print(f"  Response keys: {list(data.keys())}")
            else:
                print(f"  ✗ Failed: {response.status_code}")
        except Exception as e:
            print(f"  ✗ Error: {e}")


if __name__ == "__main__":
    print("\n🧪 State Persistence Test Suite\n")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "api":
            test_api_endpoints()
        elif sys.argv[1] == "resume":
            if len(sys.argv) > 2:
                test_resume_task(sys.argv[2])
            else:
                print("Usage: python test_state_persistence.py resume <task_id>")
        else:
            print("Usage: python test_state_persistence.py [api|resume <task_id>]")
    else:
        # Run full interactive test
        try:
            test_state_persistence()
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60 + "\n")
