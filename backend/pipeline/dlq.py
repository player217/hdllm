"""
Dead Letter Queue Implementation
Author: Claude Code
Date: 2025-01-27
Description: Phase 2B-2 - Dead letter queue for failed tasks
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DLQEntry:
    """Dead letter queue entry"""
    task_id: str
    payload: Dict[str, Any]
    error: str
    attempt: int
    timestamp: float
    error_type: str = "unknown"
    stack_trace: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(asdict(self), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'DLQEntry':
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls(**data)


class DeadLetterQueue:
    """
    File-based dead letter queue for failed tasks
    Stores failed tasks in JSONL format for easy replay
    """
    
    def __init__(self, path: str = "data/dlq.jsonl", max_size_mb: int = 100):
        """
        Initialize DLQ
        
        Args:
            path: Path to DLQ file
            max_size_mb: Maximum size of DLQ file in MB before rotation
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = threading.Lock()
        self.stats = {
            "total_pushed": 0,
            "total_popped": 0,
            "current_size": 0
        }
        
        # Initialize file if it doesn't exist
        if not self.path.exists():
            self.path.touch()
        
        self._update_stats()
        logger.info(f"📝 DLQ initialized at {self.path}")
    
    def push(self, entry: DLQEntry) -> bool:
        """
        Push failed task to DLQ
        
        Args:
            entry: DLQ entry to store
            
        Returns:
            Success status
        """
        try:
            with self._lock:
                # Check if rotation needed
                if self.path.stat().st_size >= self.max_size_bytes:
                    self._rotate()
                
                # Write entry
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
                
                self.stats["total_pushed"] += 1
                self._update_stats()
                
                logger.warning(f"☠️ Task {entry.task_id} sent to DLQ after {entry.attempt} attempts: {entry.error}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to push to DLQ: {e}")
            return False
    
    def pop(self, count: int = 1) -> List[DLQEntry]:
        """
        Pop entries from DLQ (FIFO)
        
        Args:
            count: Number of entries to pop
            
        Returns:
            List of DLQ entries
        """
        entries = []
        
        try:
            with self._lock:
                # Read all lines
                with self.path.open("r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                # Extract requested count
                if lines:
                    popped_lines = lines[:count]
                    remaining_lines = lines[count:]
                    
                    # Parse entries
                    for line in popped_lines:
                        if line.strip():
                            try:
                                entries.append(DLQEntry.from_json(line.strip()))
                            except Exception as e:
                                logger.error(f"Failed to parse DLQ entry: {e}")
                    
                    # Write back remaining lines
                    with self.path.open("w", encoding="utf-8") as f:
                        f.writelines(remaining_lines)
                    
                    self.stats["total_popped"] += len(entries)
                    self._update_stats()
                    
        except Exception as e:
            logger.error(f"❌ Failed to pop from DLQ: {e}")
        
        return entries
    
    def peek(self, count: int = 10) -> List[DLQEntry]:
        """
        Peek at DLQ entries without removing them
        
        Args:
            count: Number of entries to peek
            
        Returns:
            List of DLQ entries
        """
        entries = []
        
        try:
            with self._lock:
                with self.path.open("r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        if i >= count:
                            break
                        if line.strip():
                            try:
                                entries.append(DLQEntry.from_json(line.strip()))
                            except Exception as e:
                                logger.error(f"Failed to parse DLQ entry: {e}")
                                
        except Exception as e:
            logger.error(f"❌ Failed to peek DLQ: {e}")
        
        return entries
    
    def filter_entries(self, 
                      task_type: Optional[str] = None,
                      max_age_hours: Optional[int] = None,
                      error_type: Optional[str] = None) -> List[DLQEntry]:
        """
        Filter DLQ entries based on criteria
        
        Args:
            task_type: Filter by task ID pattern
            max_age_hours: Maximum age of entries in hours
            error_type: Filter by error type
            
        Returns:
            Filtered list of DLQ entries
        """
        filtered = []
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600 if max_age_hours else None
        
        try:
            with self._lock:
                with self.path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            try:
                                entry = DLQEntry.from_json(line.strip())
                                
                                # Apply filters
                                if task_type and task_type not in entry.task_id:
                                    continue
                                    
                                if max_age_seconds and (current_time - entry.timestamp) > max_age_seconds:
                                    continue
                                    
                                if error_type and entry.error_type != error_type:
                                    continue
                                
                                filtered.append(entry)
                                
                            except Exception as e:
                                logger.error(f"Failed to parse DLQ entry: {e}")
                                
        except Exception as e:
            logger.error(f"❌ Failed to filter DLQ: {e}")
        
        return filtered
    
    def clear(self) -> int:
        """
        Clear all entries from DLQ
        
        Returns:
            Number of entries cleared
        """
        count = 0
        
        try:
            with self._lock:
                # Count entries before clearing
                with self.path.open("r", encoding="utf-8") as f:
                    count = sum(1 for line in f if line.strip())
                
                # Clear file
                self.path.write_text("")
                self._update_stats()
                
                logger.info(f"🧹 Cleared {count} entries from DLQ")
                
        except Exception as e:
            logger.error(f"❌ Failed to clear DLQ: {e}")
        
        return count
    
    def _rotate(self):
        """Rotate DLQ file when it gets too large"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_path = self.path.parent / f"{self.path.stem}_{timestamp}{self.path.suffix}"
        
        try:
            self.path.rename(rotated_path)
            self.path.touch()
            logger.info(f"📁 Rotated DLQ to {rotated_path}")
        except Exception as e:
            logger.error(f"❌ Failed to rotate DLQ: {e}")
    
    def _update_stats(self):
        """Update statistics"""
        try:
            self.stats["current_size"] = self.path.stat().st_size
        except:
            self.stats["current_size"] = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics"""
        entry_count = 0
        try:
            with self.path.open("r", encoding="utf-8") as f:
                entry_count = sum(1 for line in f if line.strip())
        except:
            pass
        
        return {
            **self.stats,
            "entry_count": entry_count,
            "size_mb": self.stats["current_size"] / (1024 * 1024),
            "file_path": str(self.path)
        }