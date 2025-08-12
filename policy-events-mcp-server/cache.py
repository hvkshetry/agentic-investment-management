"""
Simple in-memory cache for event deduplication.
In production, this would use Redis for persistence across restarts.
"""
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
import json
import os
from pathlib import Path


class EventCache:
    """
    Cache for tracking seen events to prevent duplicates.
    Uses in-memory storage with optional file persistence.
    """
    
    def __init__(self, cache_dir: Optional[str] = None, ttl_hours: int = 24):
        """
        Initialize event cache.
        
        Args:
            cache_dir: Directory for cache persistence (optional)
            ttl_hours: Time-to-live for cached events in hours
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".policy_events_cache"
        self.ttl = timedelta(hours=ttl_hours)
        self.events: Dict[str, Dict[str, datetime]] = {}
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing cache
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from disk if it exists"""
        cache_file = self.cache_dir / "event_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    # Convert string timestamps back to datetime
                    for event_type, events in data.items():
                        self.events[event_type] = {
                            event_id: datetime.fromisoformat(timestamp)
                            for event_id, timestamp in events.items()
                        }
                    # Clean expired entries
                    self._clean_expired()
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Warning: Could not load cache: {e}")
                self.events = {}
    
    def _save_cache(self):
        """Save cache to disk"""
        cache_file = self.cache_dir / "event_cache.json"
        try:
            # Convert datetime to string for JSON serialization
            data = {}
            for event_type, events in self.events.items():
                data[event_type] = {
                    event_id: timestamp.isoformat()
                    for event_id, timestamp in events.items()
                }
            
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")
    
    def _clean_expired(self):
        """Remove expired entries from cache"""
        now = datetime.now()
        for event_type in list(self.events.keys()):
            events = self.events[event_type]
            expired = [
                event_id for event_id, timestamp in events.items()
                if now - timestamp > self.ttl
            ]
            for event_id in expired:
                del events[event_id]
            
            # Remove empty event types
            if not events:
                del self.events[event_type]
    
    def is_duplicate(self, event_type: str, event_id: str) -> bool:
        """
        Check if an event has been seen recently.
        
        Args:
            event_type: Type of event (bill, hearing, rule, trade, nomination, rin)
            event_id: Unique identifier for the event
        
        Returns:
            True if event is a duplicate (seen within TTL), False otherwise
        """
        # Clean expired entries periodically
        if len(self.events) > 0 and datetime.now().minute % 5 == 0:
            self._clean_expired()
        
        if event_type not in self.events:
            return False
        
        if event_id not in self.events[event_type]:
            return False
        
        # Check if event is within TTL
        timestamp = self.events[event_type][event_id]
        if datetime.now() - timestamp > self.ttl:
            # Expired, remove it
            del self.events[event_type][event_id]
            return False
        
        return True
    
    def add_event(self, event_type: str, event_id: str, timestamp: Optional[datetime] = None):
        """
        Add an event to the cache.
        
        Args:
            event_type: Type of event
            event_id: Unique identifier for the event
            timestamp: Event timestamp (defaults to now)
        """
        if event_type not in self.events:
            self.events[event_type] = {}
        
        self.events[event_type][event_id] = timestamp or datetime.now()
        
        # Save to disk periodically
        if len(self.events[event_type]) % 10 == 0:
            self._save_cache()
    
    def clear(self, event_type: Optional[str] = None):
        """
        Clear cache for a specific event type or all events.
        
        Args:
            event_type: Type to clear, or None to clear all
        """
        if event_type:
            if event_type in self.events:
                del self.events[event_type]
        else:
            self.events.clear()
        
        self._save_cache()
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about cached events"""
        self._clean_expired()
        stats = {
            event_type: len(events)
            for event_type, events in self.events.items()
        }
        stats['total'] = sum(stats.values())
        return stats


class RateLimiter:
    """
    Simple rate limiter for API calls.
    Tracks API usage to stay within limits.
    """
    
    def __init__(self):
        self.congress_calls: List[datetime] = []
        self.govinfo_calls: List[datetime] = []
        self.congress_limit = 5000  # per hour
        self.govinfo_limit = 1000  # per hour (estimated)
    
    def can_call_congress(self) -> bool:
        """Check if we can make a Congress API call"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Remove old calls
        self.congress_calls = [
            call for call in self.congress_calls
            if call > hour_ago
        ]
        
        return len(self.congress_calls) < self.congress_limit
    
    def record_congress_call(self):
        """Record a Congress API call"""
        self.congress_calls.append(datetime.now())
    
    def can_call_govinfo(self) -> bool:
        """Check if we can make a GovInfo API call"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Remove old calls
        self.govinfo_calls = [
            call for call in self.govinfo_calls
            if call > hour_ago
        ]
        
        return len(self.govinfo_calls) < self.govinfo_limit
    
    def record_govinfo_call(self):
        """Record a GovInfo API call"""
        self.govinfo_calls.append(datetime.now())
    
    def get_remaining(self) -> Dict[str, int]:
        """Get remaining API calls for each service"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        congress_recent = len([
            call for call in self.congress_calls
            if call > hour_ago
        ])
        
        govinfo_recent = len([
            call for call in self.govinfo_calls
            if call > hour_ago
        ])
        
        return {
            'congress': self.congress_limit - congress_recent,
            'govinfo': self.govinfo_limit - govinfo_recent
        }