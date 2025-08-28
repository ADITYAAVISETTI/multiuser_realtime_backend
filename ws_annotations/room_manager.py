"""
Room Manager for WebSocket connections
Provides a centralized way to manage room connections across consumer instances
"""
import asyncio
from typing import Dict, List, Set


class RoomManager:
    """Singleton class to manage room connections"""
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rooms: Dict[str, List[str]] = {}
            cls._instance.user_channels: Dict[str, Set[str]] = {}
        return cls._instance
    
    async def add_user_to_room(self, room_id: str, username: str, channel_name: str) -> List[str]:
        """Add a user to a room and return the list of all users"""
        async with self._lock:
            # Initialize room if it doesn't exist
            if room_id not in self.rooms:
                self.rooms[room_id] = []
            
            # Add user if not already in room
            if username not in self.rooms[room_id]:
                self.rooms[room_id].append(username)
            
            # Track user's channel
            if username not in self.user_channels:
                self.user_channels[username] = set()
            self.user_channels[username].add(channel_name)
            
            return self.rooms[room_id].copy()
    
    async def remove_user_from_room(self, room_id: str, username: str, channel_name: str) -> List[str]:
        """Remove a user from a room and return the list of remaining users"""
        async with self._lock:
            if room_id in self.rooms and username in self.rooms[room_id]:
                self.rooms[room_id].remove(username)
                
                # Clean up empty rooms
                if not self.rooms[room_id]:
                    del self.rooms[room_id]
            
            # Remove channel tracking
            if username in self.user_channels:
                self.user_channels[username].discard(channel_name)
                if not self.user_channels[username]:
                    del self.user_channels[username]
            
            return self.rooms.get(room_id, []).copy()
    
    async def get_users_in_room(self, room_id: str) -> List[str]:
        """Get list of users in a room"""
        async with self._lock:
            return self.rooms.get(room_id, []).copy()
    
    async def get_all_rooms(self) -> Dict[str, List[str]]:
        """Get all rooms and their users"""
        async with self._lock:
            return {room_id: users.copy() for room_id, users in self.rooms.items()}


# Global room manager instance
room_manager = RoomManager()