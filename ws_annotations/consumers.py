import json
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from datetime import datetime
from .room_manager import room_manager


class AnnotationRoomConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling real-time annotation room connections
    Optimized for 10-15 concurrent users with rate limiting
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'annotation_room_{self.room_id}'
        self.username = None
        self.user_id = None  # Add user ID tracking
        self.active_drawings = {}  # Track active drawings by this user
        
        # Rate limiting timestamps
        self.last_cursor_update = 0
        self.last_drawing_update = 0
        self.last_chat_message = 0
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        print(f"WebSocket connected to room {self.room_id}")
    
    def is_rate_limited(self, message_type: str) -> bool:
        """Check if message should be rate limited for performance optimization"""
        current_time = time.time()
        
        if message_type == 'cursor_move':
            rate_limit = getattr(settings, 'RATE_LIMIT_CURSOR_UPDATES', 20)  # 20 updates per second
            if current_time - self.last_cursor_update < (1.0 / rate_limit):
                return True
            self.last_cursor_update = current_time
            
        elif message_type == 'drawing_update':
            rate_limit = getattr(settings, 'RATE_LIMIT_DRAWING_UPDATES', 10)  # 10 updates per second
            if current_time - self.last_drawing_update < (1.0 / rate_limit):
                return True
            self.last_drawing_update = current_time
            
        elif message_type == 'chat':
            rate_limit = getattr(settings, 'RATE_LIMIT_CHAT_MESSAGES', 5)  # 5 messages per second
            if current_time - self.last_chat_message < (1.0 / rate_limit):
                return True
            self.last_chat_message = current_time
            
        return False
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        print(f"WebSocket disconnecting from room {self.room_id}, user: {self.username} (ID: {self.user_id})")
        
        # Remove user from room connections using user ID
        if self.user_id:
            users = await room_manager.remove_user_from_room(self.room_id, self.user_id, self.username, self.channel_name)
            
            # Notify other users about the disconnection (includes drawing cleanup)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'username': self.username,
                    'users': users
                }
            )
            
            # Also send explicit drawing cleanup message
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'clear_drawings',
                    'username': self.username,
                    'sender_channel': self.channel_name
                }
            )
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            print(f"Received message: {data}")
            
            if message_type == 'join':
                await self.handle_join(data)
            elif message_type == 'leave':
                await self.handle_leave(data)
            elif message_type == 'ping':
                await self.handle_ping(data)
            elif message_type == 'cursor_move':
                await self.handle_cursor_move(data)
            elif message_type == 'chat':
                await self.handle_chat_message(data)
            # NEW: Drawing-related message types
            elif message_type == 'drawing_start':
                await self.handle_drawing_start(data)
            elif message_type == 'drawing_update':
                await self.handle_drawing_update(data)
            elif message_type == 'drawing_end':
                await self.handle_drawing_end(data)
            elif message_type == 'geometry_select':
                await self.handle_geometry_select(data)
            elif message_type == 'add_icon_click':
                await self.handle_add_icon_click(data)
            elif message_type == 'clear_user_drawings':
                await self.handle_clear_user_drawings(data)
            elif message_type == 'drawing_cleanup':
                await self.handle_drawing_cleanup(data)
            elif message_type == 'region_deleted':
                await self.handle_region_deleted(data)
            elif message_type == 'region_edit_start':
                await self.handle_region_edit_start(data)
            elif message_type == 'region_edit_end':
                await self.handle_region_edit_end(data)
            elif message_type == 'style_change':
                await self.handle_style_change(data)
            elif message_type == 'arrow_direction_selected':
                await self.handle_arrow_direction_selected(data)
            else:
                await self.send_error('Unknown message type')
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            await self.send_error(f'Error processing message: {str(e)}')
    
    async def handle_join(self, data):
        """Handle user joining the room"""
        self.username = data.get('username')
        self.user_id = data.get('userId')  # Get user ID for verification
        
        if not self.username:
            await self.send_error('Username is required')
            return
            
        if not self.user_id:
            await self.send_error('User ID is required for verification')
            return
        
        print(f"User {self.username} (ID: {self.user_id}) joining room {self.room_id}")
        
        # Add user to room connections using user ID for duplicate detection
        users = await room_manager.add_user_to_room(self.room_id, self.user_id, self.username, self.channel_name)
        
        print(f"Users in room after join: {users}")
        print(f"[handle_join] Broadcasting to room group: {self.room_group_name}")
        
        # Broadcast the updated users list to ALL users in the room (including the joiner)
        # This ensures everyone gets the same update at the same time
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'username': self.username,
                'users': users,
                'sender_channel': self.channel_name
            }
        )
        print(f"[handle_join] Broadcast sent for {self.username} joining")
    
    async def handle_leave(self, data):
        """Handle user leaving the room"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        
        if user_id:
            users = await room_manager.remove_user_from_room(self.room_id, user_id, username, self.channel_name)
            
            # Notify other users
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'username': username,
                    'users': users
                }
            )
    
    async def handle_ping(self, data):
        """Handle ping messages"""
        # Don't add temporary ping users to the room
        temp_username = data.get('username', '')
        temp_user_id = data.get('userId', '')
        
        # Check if this is a temporary ping (for fetching existing connections)
        is_temp_ping = 'temp' in str(temp_username).lower() or 'temp' in str(temp_user_id).lower()
        
        # Get current users in room (will return list of display usernames)
        users = await room_manager.get_users_in_room(self.room_id)
        
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'users': users,
            'count': len(users),
            'timestamp': datetime.now().isoformat()
        }))
        
        # Also send users_update to ensure consistency
        await self.send(text_data=json.dumps({
            'type': 'users_update',
            'action': 'ping_response',
            'username': self.username,
            'users': users,
            'count': len(users),
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_cursor_move(self, data):
        """Handle cursor movement broadcast with rate limiting"""
        # Apply rate limiting to prevent overwhelming with cursor updates
        if self.is_rate_limited('cursor_move'):
            return  # Skip this update to maintain performance
            
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        x = data.get('x')
        y = data.get('y')
        
        if not username or x is None or y is None:
            return  # Silently ignore invalid cursor data
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        print(f"Cursor display username: {display_username}")
        
        # Broadcast cursor position to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'cursor_position',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'x': x,
                'y': y,
                'sender_channel': self.channel_name
            }
        )
        print(f"Cursor position broadcast to room {self.room_group_name}")
    
    # NEW: Drawing-related handlers
    async def handle_add_icon_click(self, data):
        """Handle add icon click to activate draw mode"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        geometry_type = data.get('geometry_type', 'Polygon')
        selected_node = data.get('selected_node')
        
        print(f"[DRAWING] Add icon clicked - User: {username} (ID: {user_id}), Geometry: {geometry_type}, Room: {self.room_id}")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        print(f"[DRAWING] Add icon display username: {display_username}")
        
        # Broadcast add icon click to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'add_icon_clicked',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'geometry_type': geometry_type,
                'selected_node': selected_node,
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_geometry_select(self, data):
        """Handle geometry type selection"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        geometry_type = data.get('geometry_type')
        
        print(f"[DRAWING] Geometry selected - User: {username} (ID: {user_id}), Type: {geometry_type}, Room: {self.room_id}")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast geometry selection to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'geometry_selected',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'geometry_type': geometry_type,
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_arrow_direction_selected(self, data):
        """Handle arrow direction selection"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        arrow_direction = data.get('arrow_direction')
        
        print(f"[DRAWING] Arrow direction selected - User: {username} (ID: {user_id}), Direction: {arrow_direction}, Room: {self.room_id}")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast arrow direction selection to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'arrow_direction_selected_broadcast',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'arrow_direction': arrow_direction,
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_drawing_start(self, data):
        """Handle drawing start event"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        geometry_type = data.get('geometry_type')
        start_coordinates = data.get('start_coordinates')
        drawing_id = data.get('drawing_id')
        selected_node = data.get('selected_node')
        arrow_direction = data.get('arrow_direction')
        
        # Validate required fields
        if not all([username, user_id, geometry_type, drawing_id]):
            print(f"[DRAWING ERROR] Missing required fields - User: {username}, ID: {user_id}, Type: {geometry_type}, DrawingID: {drawing_id}")
            await self.send_error('Missing required fields for drawing start')
            return
        
        print(f"[DRAWING] Drawing started - User: {username} (ID: {user_id}), Type: {geometry_type}, DrawingID: {drawing_id}, Room: {self.room_id}")
        
        # Track this drawing for the user
        self.active_drawings[drawing_id] = {
            'geometry_type': geometry_type,
            'started_at': datetime.now(),
            'username': username,
            'user_id': user_id
        }
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast drawing start to all OTHER users in the room
        try:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'drawing_started',
                    'username': display_username,  # Use display username with ID if needed
                    'user_id': user_id,  # Include user ID for identification
                    'geometry_type': geometry_type,
                    'start_coordinates': start_coordinates,
                    'drawing_id': drawing_id,
                    'selected_node': selected_node,
                    'arrow_direction': arrow_direction,  # Include arrow direction
                    'sender_channel': self.channel_name
                }
            )
            print(f"[DRAWING] Successfully broadcast drawing start for {username} (DrawingID: {drawing_id})")
        except Exception as e:
            print(f"[DRAWING ERROR] Failed to broadcast drawing start: {str(e)}")
            await self.send_error(f'Failed to broadcast drawing start: {str(e)}')
    
    async def handle_drawing_update(self, data):
        """Handle drawing update event with rate limiting"""
        # Apply rate limiting to prevent overwhelming with drawing updates
        if self.is_rate_limited('drawing_update'):
            return  # Skip this update to maintain performance
            
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        coordinates = data.get('coordinates')
        drawing_id = data.get('drawing_id')
        geometry_type = data.get('geometry_type')
        
        # Validate critical fields
        if not all([username, user_id, drawing_id, coordinates]):
            return  # Silently ignore invalid updates to avoid spam
        
        # Validate coordinates format
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) == 0:
            return  # Silently ignore invalid coordinates
        
        # Log occasionally for debugging (every 10th update)
        import random
        if random.randint(1, 10) == 1:
            print(f"[DRAWING UPDATE] User: {username} (ID: {user_id}), DrawingID: {drawing_id}, Room: {self.room_id}")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast drawing update to all OTHER users in the room
        try:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'drawing_updated',
                    'username': display_username,  # Use display username with ID if needed
                    'user_id': user_id,  # Include user ID for identification
                    'coordinates': coordinates,
                    'drawing_id': drawing_id,
                    'geometry_type': geometry_type,
                    'sender_channel': self.channel_name
                }
            )
        except Exception as e:
            print(f"[DRAWING UPDATE ERROR] Failed to broadcast update for {username}: {str(e)}")
            # Don't send error response to avoid flooding - updates should be resilient
    
    async def handle_drawing_end(self, data):
        """Handle drawing end event"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        final_coordinates = data.get('final_coordinates')
        drawing_id = data.get('drawing_id')
        geometry_type = data.get('geometry_type')
        selected_node = data.get('selected_node')
        arrow_direction = data.get('arrow_direction')
        
        # Validate required fields
        if not all([username, user_id, geometry_type, drawing_id]):
            print(f"[DRAWING END ERROR] Missing required fields - User: {username}, ID: {user_id}, Type: {geometry_type}, DrawingID: {drawing_id}")
            await self.send_error('Missing required fields for drawing end')
            return
        
        # Validate final coordinates
        if not final_coordinates:
            print(f"[DRAWING END ERROR] Missing final coordinates for {username} (DrawingID: {drawing_id})")
            await self.send_error('Missing final coordinates for drawing end')
            return
        
        print(f"[DRAWING] Drawing ended - User: {username} (ID: {user_id}), Type: {geometry_type}, DrawingID: {drawing_id}, Room: {self.room_id}")
        
        # Remove from active drawings tracking
        if drawing_id in self.active_drawings:
            drawing_info = self.active_drawings[drawing_id]
            duration = datetime.now() - drawing_info['started_at']
            print(f"[DRAWING] Drawing {drawing_id} completed in {duration.total_seconds():.2f} seconds")
            del self.active_drawings[drawing_id]
        else:
            print(f"[DRAWING WARNING] Drawing {drawing_id} not found in active drawings tracking")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast drawing end to all OTHER users in the room
        try:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'drawing_ended',
                    'username': display_username,  # Use display username with ID if needed
                    'user_id': user_id,  # Include user ID for identification
                    'final_coordinates': final_coordinates,
                    'drawing_id': drawing_id,
                    'geometry_type': geometry_type,
                    'selected_node': selected_node,
                    'arrow_direction': arrow_direction,  # Include arrow direction
                    'sender_channel': self.channel_name
                }
            )
            print(f"[DRAWING] Successfully broadcast drawing end for {username} (DrawingID: {drawing_id})")
        except Exception as e:
            print(f"[DRAWING END ERROR] Failed to broadcast drawing end: {str(e)}")
            await self.send_error(f'Failed to broadcast drawing end: {str(e)}')
    
    async def handle_drawing_cleanup(self, data):
        """Handle drawing cleanup event when user switches tools/modes"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        drawing_id = data.get('drawing_id')
        
        # Validate required fields
        if not all([username, user_id, drawing_id]):
            print(f"[DRAWING CLEANUP ERROR] Missing required fields - User: {username}, ID: {user_id}, DrawingID: {drawing_id}")
            await self.send_error('Missing required fields for drawing cleanup')
            return
        
        print(f"[DRAWING] Drawing cleanup - User: {username} (ID: {user_id}), DrawingID: {drawing_id}, Room: {self.room_id}")
        
        # Remove from active drawings tracking if exists
        if drawing_id in self.active_drawings:
            drawing_info = self.active_drawings[drawing_id]
            duration = datetime.now() - drawing_info['started_at']
            print(f"[DRAWING] Cleaning up incomplete drawing {drawing_id} after {duration.total_seconds():.2f} seconds")
            del self.active_drawings[drawing_id]
        
        # Get the display username for this user
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast drawing cleanup to all OTHER users in the room
        try:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'drawing_cleanup',
                    'username': display_username,
                    'user_id': user_id,
                    'drawing_id': drawing_id,
                    'sender_channel': self.channel_name
                }
            )
            print(f"[DRAWING] Successfully broadcast drawing cleanup for {username} (DrawingID: {drawing_id})")
        except Exception as e:
            print(f"[DRAWING CLEANUP ERROR] Failed to broadcast drawing cleanup: {str(e)}")
            await self.send_error(f'Failed to broadcast drawing cleanup: {str(e)}')
    
    async def user_joined(self, event):
        """Send user joined notification to WebSocket"""
        # Send update to ALL users in the room to ensure everyone has the current count
        print(f"[user_joined] Sending update to {self.username} about {event['username']} joining")
        print(f"[user_joined] Users in room: {event['users']}, count: {len(event['users'])}")
        
        await self.send(text_data=json.dumps({
            'type': 'users_update',
            'action': 'joined',
            'username': event['username'],
            'users': event['users'],
            'count': len(event['users']),
            'timestamp': datetime.now().isoformat()
        }))
    
    async def user_left(self, event):
        """Send user left notification to WebSocket"""
        # Send update to all remaining users to ensure everyone has the current count
        print(f"[user_left] Sending update to {self.username} about {event['username']} leaving")
        print(f"[user_left] Users remaining: {event['users']}, count: {len(event['users'])}")
        
        await self.send(text_data=json.dumps({
            'type': 'users_update',
            'action': 'left',
            'username': event['username'],
            'users': event['users'],
            'count': len(event['users']),
            'timestamp': datetime.now().isoformat()
        }))
    
    async def cursor_position(self, event):
        """Send cursor position to WebSocket"""
        # Don't send cursor position back to the sender
        if event.get('sender_channel') != self.channel_name:
            print(f"Sending cursor update to client - User: {event['username']} (ID: {event.get('user_id')}), X: {event['x']}, Y: {event['y']}")
            await self.send(text_data=json.dumps({
                'type': 'cursor_update',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'x': event['x'],
                'y': event['y'],
                'timestamp': datetime.now().isoformat()
            }))
        else:
            print(f"Skipping cursor update for sender: {event['username']} (ID: {event.get('user_id')})")
    
    # NEW: Drawing event broadcasts
    async def add_icon_clicked(self, event):
        """Send add icon click to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'add_icon_clicked',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'geometry_type': event['geometry_type'],
                'selected_node': event['selected_node'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def geometry_selected(self, event):
        """Send geometry selection to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'geometry_selected',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'geometry_type': event['geometry_type'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def arrow_direction_selected_broadcast(self, event):
        """Send arrow direction selection to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'arrow_direction_selected',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'arrow_direction': event['arrow_direction'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def drawing_started(self, event):
        """Send drawing start to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            message_data = {
                'type': 'drawing_started',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'geometry_type': event['geometry_type'],
                'start_coordinates': event['start_coordinates'],
                'drawing_id': event['drawing_id'],
                'selected_node': event['selected_node'],
                'timestamp': datetime.now().isoformat()
            }
            
            # Include arrow direction if present
            if 'arrow_direction' in event:
                message_data['arrow_direction'] = event['arrow_direction']
            
            await self.send(text_data=json.dumps(message_data))
    
    async def drawing_updated(self, event):
        """Send drawing update to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'drawing_updated',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'coordinates': event['coordinates'],
                'drawing_id': event['drawing_id'],
                'geometry_type': event['geometry_type'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def drawing_ended(self, event):
        """Send drawing end to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            message_data = {
                'type': 'drawing_ended',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'final_coordinates': event['final_coordinates'],
                'drawing_id': event['drawing_id'],
                'geometry_type': event['geometry_type'],
                'selected_node': event['selected_node'],
                'timestamp': datetime.now().isoformat()
            }
            
            # Include arrow direction if present
            if 'arrow_direction' in event:
                message_data['arrow_direction'] = event['arrow_direction']
                
            await self.send(text_data=json.dumps(message_data))
    
    async def drawing_cleanup(self, event):
        """Send drawing cleanup to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            message_data = {
                'type': 'drawing_cleanup',
                'username': event['username'],
                'user_id': event.get('user_id'),
                'drawing_id': event['drawing_id'],
                'timestamp': datetime.now().isoformat()
            }
            
            await self.send(text_data=json.dumps(message_data))
    
    async def handle_chat_message(self, data):
        """Handle chat messages with rate limiting"""
        # Apply rate limiting to prevent chat spam
        if self.is_rate_limited('chat'):
            await self.send_error('Message rate limit exceeded. Please slow down.')
            return
            
        username = data.get('username', self.username)
        message = data.get('message')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        print(f"[SERVER] Chat message from {username} in room {self.room_id}: '{message}'")
        print(f"[SERVER] Room group name: {self.room_group_name}")
        print(f"[SERVER] Sender channel: {self.channel_name}")
        
        # Get current users in room for debugging
        users = await room_manager.get_users_in_room(self.room_id)
        print(f"[SERVER] Current users in room: {users}")
        
        if not username or not message:
            print(f"[SERVER] ERROR: Missing username ({username}) or message ({message})")
            await self.send_error('Username and message are required')
            return
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, self.user_id, self.username)
        print(f"[SERVER] Display username for chat: {display_username}")
        
        print(f"[SERVER] Broadcasting message to group: {self.room_group_name}")
        # Broadcast chat message to all users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_broadcast',
                'username': display_username,  # Use display username with ID suffix if needed
                'message': message,
                'timestamp': timestamp,
                'sender_channel': self.channel_name
            }
        )
        print(f"[SERVER] Message broadcast sent")
    
    async def chat_broadcast(self, event):
        """Send chat message to WebSocket"""
        print(f"[SERVER] chat_broadcast called for user {self.username}")
        print(f"[SERVER] Broadcasting message from {event['username']}: '{event['message']}'")
        print(f"[SERVER] Channel: {self.channel_name}")
        
        # Send to all users including the sender
        message_data = {
            'type': 'chat_message',
            'username': event['username'],
            'message': event['message'],
            'timestamp': event['timestamp']
        }
        
        print(f"[SERVER] Sending message data: {message_data}")
        await self.send(text_data=json.dumps(message_data))
        print(f"[SERVER] Message sent to {self.username}")
    
    async def handle_clear_user_drawings(self, data):
        """Handle request to clear a user's drawings"""
        username = data.get('username')
        user_id = data.get('userId', self.user_id)
        
        if not username:
            await self.send_error('Username is required for clearing drawings')
            return
        
        print(f"[DRAWING] Clearing drawings for user: {username} (ID: {user_id})")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast clear drawings message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'clear_drawings',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'sender_channel': self.channel_name
            }
        )
    
    async def clear_drawings(self, event):
        """Send clear drawings message to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'clear_user_drawings',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'timestamp': datetime.now().isoformat()
            }))
    
    async def handle_region_deleted(self, data):
        """Handle region deletion event"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        region_name = data.get('region_name')
        region_data = data.get('region_data')
        feature_id = data.get('feature_id')  # Extract feature ID if provided
        
        print(f"[REGION DELETE] Region '{region_name}' deleted by user: {username} (ID: {user_id}) in room {self.room_id}")
        print(f"[REGION DELETE] Feature ID: {feature_id if feature_id else 'NOT PROVIDED'}")
        print(f"[REGION DELETE] Region data: {region_data}")
        
        # Extract feature ID from region_data if not provided directly
        if not feature_id and region_data:
            if isinstance(region_data, dict):
                feature_id = region_data.get('featureId')
                if feature_id:
                    print(f"[REGION DELETE] Extracted feature ID from region_data: {feature_id}")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        print(f"[REGION DELETE] Display username for deletion: {display_username}")
        
        # Broadcast region deletion to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'region_deleted_broadcast',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'region_name': region_name,
                'region_data': region_data,
                'feature_id': feature_id,  # Include feature_id in broadcast
                'sender_channel': self.channel_name
            }
        )
        print(f"[REGION DELETE] Broadcast sent to room group: {self.room_group_name}")

    async def region_deleted_broadcast(self, event):
        """Send region deletion to WebSocket"""
        # Don't send back to the sender - only to other users
        if event.get('sender_channel') != self.channel_name:
            print(f"[REGION DELETE] Sending deletion message to user {self.username}")
            await self.send(text_data=json.dumps({
                'type': 'region_deleted',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'region_name': event['region_name'],
                'region_data': event['region_data'],
                'feature_id': event.get('feature_id'),  # Include feature_id
                'timestamp': datetime.now().isoformat()
            }))
        else:
            print(f"[REGION DELETE] Skipping sender {self.username}")

    async def handle_region_edit_start(self, data):
        """Handle region edit start event"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        region_id = data.get('region_id')
        region_name = data.get('region_name')
        region_data = data.get('region_data')
        feature_id = data.get('feature_id')  # Feature ID from frontend
        coordinates = data.get('coordinates')
        geometry_type = data.get('geometry_type')
        original_coordinates = data.get('original_coordinates')  # Original coordinates before edit
        
        print(f"[REGION EDIT START] Region '{region_name}' being edited by user: {username} (ID: {user_id}) in room {self.room_id}")
        print(f"[REGION EDIT START] Feature ID: {feature_id} - THIS IS THE PRIMARY IDENTIFIER")
        print(f"[REGION EDIT START] Region ID (data.id): {region_id}")
        print(f"[REGION EDIT START] Region data: {region_data}")
        print(f"[REGION EDIT START] Geometry type: {geometry_type}")
        print(f"[REGION EDIT START] Has original coordinates: {'Yes' if original_coordinates else 'No'}")
        if original_coordinates:
            print(f"[REGION EDIT START] Original coordinates sample: {str(original_coordinates)[:100]}...")
        
        # Validate feature ID
        if not feature_id:
            print(f"[REGION EDIT START] WARNING: No feature_id provided! This may cause issues with duplicate named regions")
        else:
            print(f"[REGION EDIT START] ✓ Feature ID present: {feature_id}")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast region edit start to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'region_edit_start_broadcast',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'region_id': region_id,
                'region_name': region_name,
                'region_data': region_data,
                'feature_id': feature_id,  # Include feature_id in broadcast
                'coordinates': coordinates,
                'geometry_type': geometry_type,
                'original_coordinates': original_coordinates,  # Pass through original coordinates
                'sender_channel': self.channel_name
            }
        )
        print(f"[REGION EDIT START] Broadcast sent to room group: {self.room_group_name}")

    async def region_edit_start_broadcast(self, event):
        """Send region edit start to WebSocket"""
        # Don't send back to the sender - only to other users
        if event.get('sender_channel') != self.channel_name:
            print(f"[REGION EDIT START] Sending edit start message to user {self.username}")
            await self.send(text_data=json.dumps({
                'type': 'region_edit_start',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'region_id': event['region_id'],
                'region_name': event['region_name'],
                'region_data': event['region_data'],
                'feature_id': event.get('feature_id'),  # Include feature_id
                'coordinates': event['coordinates'],
                'geometry_type': event['geometry_type'],
                'original_coordinates': event.get('original_coordinates'),  # Pass through original coordinates
                'timestamp': datetime.now().isoformat()
            }))
        else:
            print(f"[REGION EDIT START] Skipping sender {self.username}")

    async def handle_region_edit_end(self, data):
        """Handle region edit end event"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        region_id = data.get('region_id')
        region_name = data.get('region_name')
        region_data = data.get('region_data')
        feature_id = data.get('feature_id')  # Feature ID from frontend
        final_coordinates = data.get('final_coordinates')
        geometry_type = data.get('geometry_type')
        original_coordinates = data.get('original_coordinates')  # Original coordinates for proper matching
        
        print(f"[REGION EDIT END] Region '{region_name}' edit completed by user: {username} (ID: {user_id}) in room {self.room_id}")
        print(f"[REGION EDIT END] Feature ID: {feature_id} - THIS IS THE PRIMARY IDENTIFIER")
        print(f"[REGION EDIT END] Region ID (data.id): {region_id}")
        print(f"[REGION EDIT END] Region data: {region_data}")
        print(f"[REGION EDIT END] Geometry type: {geometry_type}")
        print(f"[REGION EDIT END] Final coordinates length: {len(final_coordinates) if final_coordinates else 0}")
        print(f"[REGION EDIT END] Has original coordinates: {'Yes' if original_coordinates else 'No'}")
        if original_coordinates:
            print(f"[REGION EDIT END] Original coordinates length: {len(original_coordinates)}")
        
        # Validate feature ID
        if not feature_id:
            print(f"[REGION EDIT END] WARNING: No feature_id provided! This will cause issues with duplicate named regions")
            print(f"[REGION EDIT END] Will fall back to name-based matching which is unreliable with duplicates")
        else:
            print(f"[REGION EDIT END] ✓ Feature ID present: {feature_id}")
        
        # Validate that we have essential data
        if not region_name and not feature_id:
            print(f"[REGION EDIT END] ERROR: Missing both region_name and feature_id - cannot identify region!")
        
        if not final_coordinates:
            print(f"[REGION EDIT END] ERROR: No final coordinates provided!")
            await self.send_error('Region edit end missing final coordinates')
            return
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast region edit end to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'region_edit_end_broadcast',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'region_id': region_id,
                'region_name': region_name,
                'region_data': region_data,
                'feature_id': feature_id,  # Include feature_id in broadcast
                'final_coordinates': final_coordinates,
                'geometry_type': geometry_type,
                'original_coordinates': original_coordinates,  # Pass through for proper matching
                'sender_channel': self.channel_name
            }
        )
        print(f"[REGION EDIT END] Broadcast sent to room group: {self.room_group_name}")

    async def handle_style_change(self, data):
        """Handle style change event"""
        username = data.get('username', self.username)
        user_id = data.get('userId', self.user_id)
        feature_id = data.get('feature_id')
        style_changes = data.get('style_changes')
        
        print(f"[STYLE CHANGE] Feature '{feature_id}' style changed by user: {username} (ID: {user_id}) in room {self.room_id}")
        print(f"[STYLE CHANGE] Style changes: {style_changes}")
        
        # Get the display username for this user (handles duplicates with ID suffixes)
        display_username = await room_manager.get_display_username_for_user(self.room_id, user_id, username)
        
        # Broadcast style change to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'style_change_broadcast',
                'username': display_username,  # Use display username with ID if needed
                'user_id': user_id,  # Include user ID for identification
                'feature_id': feature_id,
                'style_changes': style_changes,
                'sender_channel': self.channel_name
            }
        )
        print(f"[STYLE CHANGE] Broadcast sent to room group: {self.room_group_name}")

    async def style_change_broadcast(self, event):
        """Send style change to WebSocket"""
        # Don't send back to the sender - only to other users
        if event.get('sender_channel') != self.channel_name:
            print(f"[STYLE CHANGE] Sending style change message to user {self.username}")
            await self.send(text_data=json.dumps({
                'type': 'style_change',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'feature_id': event['feature_id'],
                'style_changes': event['style_changes'],
                'timestamp': datetime.now().isoformat()
            }))
        else:
            print(f"[STYLE CHANGE] Skipping sender {self.username}")

    async def region_edit_end_broadcast(self, event):
        """Send region edit end to WebSocket"""
        # Don't send back to the sender - only to other users
        if event.get('sender_channel') != self.channel_name:
            print(f"[REGION EDIT END BROADCAST] Sending edit end message to user {self.username}")
            print(f"[REGION EDIT END BROADCAST] Event region: {event.get('region_name')} (ID: {event.get('feature_id')})")
            print(f"[REGION EDIT END BROADCAST] Sender: {event.get('username')}")
            
            # Create message with all necessary data
            message_data = {
                'type': 'region_edit_end',
                'username': event['username'],  # This now includes ID suffix if needed
                'user_id': event.get('user_id'),  # Include user ID for frontend tracking
                'region_id': event.get('region_id'),
                'region_name': event.get('region_name'),
                'region_data': event.get('region_data'),
                'feature_id': event.get('feature_id'),  # Include feature_id
                'final_coordinates': event.get('final_coordinates'),
                'geometry_type': event.get('geometry_type'),
                'original_coordinates': event.get('original_coordinates'),  # Include original coordinates for matching
                'timestamp': datetime.now().isoformat()
            }
            
            # Validate message before sending
            if not message_data.get('final_coordinates'):
                print(f"[REGION EDIT END BROADCAST] WARNING: No coordinates in broadcast message!")
            
            await self.send(text_data=json.dumps(message_data))
            print(f"[REGION EDIT END BROADCAST] Message sent to {self.username}")
        else:
            print(f"[REGION EDIT END BROADCAST] Correctly skipping sender {self.username}")
    
    async def send_error(self, error_message):
        """Send error message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }))