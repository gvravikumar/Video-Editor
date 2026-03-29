"""
State Manager Service
Provides persistent task state management with checkpoint/resume capability.
Allows recovery from server restarts, page reloads, and failures.
"""

import os
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages persistent state for long-running video processing tasks.
    
    Features:
    - Automatic state persistence to disk
    - Checkpoint-based progress tracking
    - Resume capability after interruptions
    - Atomic writes to prevent corruption
    - Thread-safe operations
    """
    
    def __init__(self, state_dir: str):
        """
        Initialize the state manager.
        
        Args:
            state_dir: Directory to store state files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self._in_memory_cache: Dict[str, Dict[str, Any]] = {}
        
        # Load existing states on initialization
        self._load_all_states()
        
        logger.info(f"StateManager initialized with state_dir: {self.state_dir}")
    
    def _get_state_file(self, task_id: str) -> Path:
        """Get the path to a task's state file."""
        return self.state_dir / f"{task_id}.json"
    
    def _load_all_states(self):
        """Load all existing task states from disk into memory."""
        try:
            state_files = list(self.state_dir.glob("*.json"))
            logger.info(f"Loading {len(state_files)} existing task states...")
            
            for state_file in state_files:
                try:
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                        task_id = state_file.stem
                        self._in_memory_cache[task_id] = state
                        
                        # Mark interrupted tasks as resumable
                        if state.get('status') in ['processing', 'extracting_frames', 
                                                   'analyzing_frames', 'generating_story',
                                                   'generating_shorts', 'generating_metadata']:
                            state['status'] = 'interrupted'
                            state['resumable'] = True
                            state['interrupted_at'] = datetime.now().isoformat()
                            self._save_state_to_disk(task_id, state)
                            logger.info(f"Task {task_id} marked as interrupted (was {state.get('step', 'unknown')})")
                        
                except Exception as e:
                    logger.error(f"Error loading state from {state_file}: {e}")
            
            logger.info(f"Loaded {len(self._in_memory_cache)} task states successfully")
            
        except Exception as e:
            logger.error(f"Error loading task states: {e}")
    
    def _save_state_to_disk(self, task_id: str, state: Dict[str, Any]):
        """
        Save task state to disk atomically.
        Uses a temporary file and atomic rename to prevent corruption.
        """
        state_file = self._get_state_file(task_id)
        temp_file = state_file.with_suffix('.tmp')
        
        try:
            # Write to temporary file
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            # Atomic rename (safe even if interrupted)
            temp_file.replace(state_file)
            
        except Exception as e:
            logger.error(f"Error saving state for task {task_id}: {e}")
            if temp_file.exists():
                temp_file.unlink()
    
    def create_task(self, task_id: str, task_type: str, **kwargs) -> Dict[str, Any]:
        """
        Create a new task with initial state.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task (e.g., 'ai_pipeline', 'video_processing')
            **kwargs: Additional task metadata
        
        Returns:
            The created task state
        """
        with self.lock:
            state = {
                'task_id': task_id,
                'type': task_type,
                'status': 'queued',
                'percentage': 0,
                'step': 'initializing',
                'step_message': 'Task created',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'checkpoints': [],
                'resumable': False,
                **kwargs
            }
            
            self._in_memory_cache[task_id] = state
            self._save_state_to_disk(task_id, state)
            
            logger.info(f"Created task {task_id} of type {task_type}")
            return state.copy()
    
    def update_task(self, task_id: str, **updates) -> Optional[Dict[str, Any]]:
        """
        Update task state with new information.
        
        Args:
            task_id: Task identifier
            **updates: Fields to update
        
        Returns:
            Updated task state or None if task not found
        """
        with self.lock:
            if task_id not in self._in_memory_cache:
                logger.warning(f"Task {task_id} not found for update")
                return None
            
            state = self._in_memory_cache[task_id]
            state.update(updates)
            state['updated_at'] = datetime.now().isoformat()
            
            # Save to disk
            self._save_state_to_disk(task_id, state)
            
            return state.copy()
    
    def add_checkpoint(self, task_id: str, checkpoint_name: str, data: Dict[str, Any] = None):
        """
        Add a checkpoint to the task's progress.
        Checkpoints allow resuming from specific points.
        
        Args:
            checkpoint_name: Name of the checkpoint (e.g., 'frames_extracted', 'analysis_complete')
            data: Optional data to store with checkpoint
        """
        with self.lock:
            if task_id not in self._in_memory_cache:
                logger.warning(f"Task {task_id} not found for checkpoint")
                return
            
            state = self._in_memory_cache[task_id]
            checkpoint = {
                'name': checkpoint_name,
                'timestamp': datetime.now().isoformat(),
                'data': data or {}
            }
            
            if 'checkpoints' not in state:
                state['checkpoints'] = []
            
            state['checkpoints'].append(checkpoint)
            state['last_checkpoint'] = checkpoint_name
            state['updated_at'] = datetime.now().isoformat()
            
            self._save_state_to_disk(task_id, state)
            
            logger.info(f"Task {task_id} checkpoint: {checkpoint_name}")
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a task."""
        with self.lock:
            return self._in_memory_cache.get(task_id, None)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all tasks."""
        with self.lock:
            return self._in_memory_cache.copy()
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all tasks with a specific status."""
        with self.lock:
            return [
                task.copy() 
                for task in self._in_memory_cache.values() 
                if task.get('status') == status
            ]
    
    def get_resumable_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks that can be resumed."""
        with self.lock:
            return [
                task.copy() 
                for task in self._in_memory_cache.values() 
                if task.get('resumable', False) or task.get('status') == 'interrupted'
            ]
    
    def remove_checkpoint(self, task_id: str, checkpoint_name: str):
        """Remove a specific checkpoint so that stage can be re-run."""
        with self.lock:
            state = self._in_memory_cache.get(task_id)
            if not state:
                return
            state['checkpoints'] = [
                cp for cp in state.get('checkpoints', [])
                if cp['name'] != checkpoint_name
            ]
            if state.get('last_checkpoint') == checkpoint_name:
                remaining = state['checkpoints']
                state['last_checkpoint'] = remaining[-1]['name'] if remaining else None
            state['updated_at'] = datetime.now().isoformat()
            self._save_state_to_disk(task_id, state)
            logger.info(f"Task {task_id}: removed checkpoint '{checkpoint_name}'")

    def has_checkpoint(self, task_id: str, checkpoint_name: str) -> bool:
        """Check if a task has reached a specific checkpoint."""
        with self.lock:
            state = self._in_memory_cache.get(task_id)
            if not state:
                return False
            
            checkpoints = state.get('checkpoints', [])
            return any(cp['name'] == checkpoint_name for cp in checkpoints)
    
    def get_last_checkpoint(self, task_id: str) -> Optional[str]:
        """Get the name of the last checkpoint for a task."""
        with self.lock:
            state = self._in_memory_cache.get(task_id)
            if not state:
                return None
            
            return state.get('last_checkpoint')
    
    def mark_completed(self, task_id: str, result: Dict[str, Any] = None):
        """Mark a task as completed."""
        updates = {
            'status': 'completed',
            'percentage': 100,
            'step': 'done',
            'step_message': 'Task completed successfully',
            'completed_at': datetime.now().isoformat(),
            'resumable': False
        }
        
        if result:
            updates['result'] = result
        
        self.update_task(task_id, **updates)
        logger.info(f"Task {task_id} marked as completed")
    
    def mark_error(self, task_id: str, error: str):
        """Mark a task as failed with error."""
        self.update_task(
            task_id,
            status='error',
            error=error,
            error_at=datetime.now().isoformat(),
            resumable=False
        )
        logger.error(f"Task {task_id} failed: {error}")
    
    def clear_all_tasks(self):
        """Delete all task states from memory and disk (used by cache clear)."""
        with self.lock:
            task_ids = list(self._in_memory_cache.keys())
            for task_id in task_ids:
                state_file = self._get_state_file(task_id)
                if state_file.exists():
                    state_file.unlink()
            self._in_memory_cache.clear()
            logger.info("All task states cleared")

    def delete_task(self, task_id: str):
        """Delete a task and its state file."""
        with self.lock:
            if task_id in self._in_memory_cache:
                del self._in_memory_cache[task_id]
            
            state_file = self._get_state_file(task_id)
            if state_file.exists():
                state_file.unlink()
            
            logger.info(f"Task {task_id} deleted")
    
    def cleanup_old_tasks(self, max_age_days: int = 7):
        """
        Clean up old completed/error tasks older than max_age_days.
        
        Args:
            max_age_days: Maximum age in days for task retention
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        tasks_to_delete = []
        
        with self.lock:
            for task_id, state in self._in_memory_cache.items():
                if state.get('status') in ['completed', 'error']:
                    updated_at = state.get('updated_at', state.get('created_at', ''))
                    try:
                        task_date = datetime.fromisoformat(updated_at)
                        if task_date < cutoff_date:
                            tasks_to_delete.append(task_id)
                    except:
                        pass
        
        for task_id in tasks_to_delete:
            self.delete_task(task_id)
        
        if tasks_to_delete:
            logger.info(f"Cleaned up {len(tasks_to_delete)} old tasks")


# Global state manager instance (will be initialized by app.py)
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        raise RuntimeError("StateManager not initialized. Call init_state_manager() first.")
    return _state_manager


def init_state_manager(state_dir: str) -> StateManager:
    """Initialize the global state manager."""
    global _state_manager
    _state_manager = StateManager(state_dir)
    return _state_manager
