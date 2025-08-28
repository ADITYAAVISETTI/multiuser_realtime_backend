import json
from channels.generic.websocket import AsyncWebsocketConsumer
from datetime import datetime
from .room_manager import room_manager


class AnnotationRoomConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling real-time annotation room connections
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'annotation_room_{self.room_id}'
        self.username = None
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        print(f"WebSocket connected to room {self.room_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        print(f"WebSocket disconnecting from room {self.room_id}, user: {self.username}")
        
        # Remove user from room connections
        if self.username:
            users = await room_manager.remove_user_from_room(self.room_id, self.username, self.channel_name)
            
            # Notify other users about the disconnection
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'username': self.username,
                    'users': users
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
                await self.handle_ping()
            elif message_type == 'cursor_move':
                await self.handle_cursor_move(data)
            elif message_type == 'chat':
                await self.handle_chat_message(data)
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
        
        if not self.username:
            await self.send_error('Username is required')
            return
        
        print(f"User {self.username} joining room {self.room_id}")
        
        # Add user to room connections using room manager
        users = await room_manager.add_user_to_room(self.room_id, self.username, self.channel_name)
        
        print(f"Users in room after join: {users}")
        
        # First send the current users list to the joining user
        await self.send(text_data=json.dumps({
            'type': 'users_update',
            'action': 'joined',
            'username': self.username,
            'users': users,
            'count': len(users),
            'timestamp': datetime.now().isoformat()
        }))
        
        # Then notify all OTHER users in the room about the new connection
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'username': self.username,
                'users': users
            }
        )
    
    async def handle_leave(self, data):
        """Handle user leaving the room"""
        username = data.get('username', self.username)
        
        if username:
            users = await room_manager.remove_user_from_room(self.room_id, username, self.channel_name)
            
            # Notify other users
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'username': username,
                    'users': users
                }
            )
    
    async def handle_ping(self):
        """Handle ping messages"""
        # Get current users in room
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
        """Handle cursor movement broadcast"""
        username = data.get('username', self.username)
        x = data.get('x')
        y = data.get('y')
        
        print(f"Cursor move received - User: {username}, X: {x}, Y: {y}, Room: {self.room_id}")
        
        if not username or x is None or y is None:
            print(f"Invalid cursor data - username: {username}, x: {x}, y: {y}")
            return  # Silently ignore invalid cursor data
        
        # Broadcast cursor position to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'cursor_position',
                'username': username,
                'x': x,
                'y': y,
                'sender_channel': self.channel_name
            }
        )
        print(f"Cursor position broadcast to room {self.room_group_name}")
    
    async def user_joined(self, event):
        """Send user joined notification to WebSocket"""
        # Don't send the join notification to the user who just joined
        # They already received it in handle_join
        if event['username'] != self.username:
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
        # Don't send the leave notification to the user who is leaving
        if event['username'] != self.username:
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
            print(f"Sending cursor update to client - User: {event['username']}, X: {event['x']}, Y: {event['y']}")
            await self.send(text_data=json.dumps({
                'type': 'cursor_update',
                'username': event['username'],
                'x': event['x'],
                'y': event['y'],
                'timestamp': datetime.now().isoformat()
            }))
        else:
            print(f"Skipping cursor update for sender: {event['username']}")
    
    async def handle_chat_message(self, data):
        """Handle chat messages"""
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
        
        print(f"[SERVER] Broadcasting message to group: {self.room_group_name}")
        # Broadcast chat message to all users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_broadcast',
                'username': username,
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
    
    async def send_error(self, error_message):
        """Send error message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }))