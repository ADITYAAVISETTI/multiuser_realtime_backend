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
            # Changed: rooms now store user info dicts with id and username
            cls._instance.rooms: Dict[str, List[Dict[str, str]]] = {}
            # Changed: user_channels now keyed by user_id instead of username
            cls._instance.user_channels: Dict[str, Set[str]] = {}
        return cls._instance
    
    async def add_user_to_room(self, room_id: str, user_id: str, username: str, channel_name: str) -> List[str]:
        """Add a user to a room and return the list of all users (usernames for display)"""
        async with self._lock:
            # Initialize room if it doesn't exist
            if room_id not in self.rooms:
                self.rooms[room_id] = []
            
            # Check if user ID already exists in room
            user_exists = any(user['id'] == str(user_id) for user in self.rooms[room_id])
            
            if not user_exists:
                # Add new user with both ID and username
                self.rooms[room_id].append({
                    'id': str(user_id),
                    'username': username
                })
                print(f"[RoomManager] Added user to room: {username} (ID: {user_id})")
            else:
                print(f"[RoomManager] User already exists: {username} (ID: {user_id})")
            
            # Track user's channel by user ID
            if str(user_id) not in self.user_channels:
                self.user_channels[str(user_id)] = set()
            self.user_channels[str(user_id)].add(channel_name)
            
            # Debug: Print current room state
            print(f"[RoomManager] Room {room_id} users: {self.rooms[room_id]}")
            display_names = self._get_display_usernames(self.rooms[room_id])
            print(f"[RoomManager] Display names: {display_names}")
            
            # Return list of usernames for display (showing username + id for duplicates)
            return display_names
    
    async def remove_user_from_room(self, room_id: str, user_id: str, username: str, channel_name: str) -> List[str]:
        """Remove a user from a room and return the list of remaining users"""
        async with self._lock:
            if room_id in self.rooms:
                # Remove user by ID
                self.rooms[room_id] = [user for user in self.rooms[room_id] if user['id'] != str(user_id)]
                
                # Clean up empty rooms
                if not self.rooms[room_id]:
                    del self.rooms[room_id]
            
            # Remove channel tracking by user ID
            if str(user_id) in self.user_channels:
                self.user_channels[str(user_id)].discard(channel_name)
                if not self.user_channels[str(user_id)]:
                    del self.user_channels[str(user_id)]
            
            # Return display usernames
            return self._get_display_usernames(self.rooms.get(room_id, []))
    
    async def get_users_in_room(self, room_id: str) -> List[str]:
        """Get list of users in a room (returns display usernames)"""
        async with self._lock:
            users = self.rooms.get(room_id, [])
            return self._get_display_usernames(users)
    
    async def get_all_rooms(self) -> Dict[str, List[str]]:
        """Get all rooms and their users"""
        async with self._lock:
            return {room_id: self._get_display_usernames(users) for room_id, users in self.rooms.items()}
    
    def _get_display_usernames(self, users: List[Dict[str, str]]) -> List[str]:
        """Convert user dicts to display names, showing ID suffix for duplicate usernames"""
        # Count occurrences of each username
        username_counts = {}
        for user in users:
            username = user['username']
            username_counts[username] = username_counts.get(username, 0) + 1
        
        # Build display names
        display_names = []
        for user in users:
            username = user['username']
            if username_counts[username] > 1:
                # Show username with ID suffix for duplicates
                display_names.append(f"{username} (ID: {user['id']})")
            else:
                # Show just username if unique
                display_names.append(username)
        
        return display_names

    async def get_display_username_for_user(self, room_id: str, user_id: str, username: str) -> str:
        """Get the display username for a specific user (with ID suffix if there are duplicates)"""
        async with self._lock:
            users = self.rooms.get(room_id, [])
            
            # Count occurrences of this username in the room
            username_count = sum(1 for user in users if user['username'] == username)
            
            if username_count > 1:
                # Multiple users with same username, return with ID suffix
                return f"{username} (ID: {user_id})"
            else:
                # Unique username, return as-is
                return username


# Global room manager instance
room_manager = RoomManager()