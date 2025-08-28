import json
from channels.generic.websocket import AsyncWebsocketConsumer
from datetime import datetime


class AnnotationRoomConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling real-time annotation room connections
    """
    
    # Class-level dictionary to store room connections
    room_connections = {}
    
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
        
        # Initialize room connections if not exists
        if self.room_id not in self.room_connections:
            self.room_connections[self.room_id] = []
        
        print(f"WebSocket connected to room {self.room_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        print(f"WebSocket disconnecting from room {self.room_id}, user: {self.username}")
        
        # Remove user from room connections
        if self.username and self.room_id in self.room_connections:
            if self.username in self.room_connections[self.room_id]:
                self.room_connections[self.room_id].remove(self.username)
                
                # Notify other users about the disconnection
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_left',
                        'username': self.username,
                        'users': self.room_connections[self.room_id]
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
        
        # Add user to room connections
        if self.username not in self.room_connections[self.room_id]:
            self.room_connections[self.room_id].append(self.username)
        
        # Notify all users in the room about the new connection
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'username': self.username,
                'users': self.room_connections[self.room_id]
            }
        )
    
    async def handle_leave(self, data):
        """Handle user leaving the room"""
        username = data.get('username', self.username)
        
        if username and self.room_id in self.room_connections:
            if username in self.room_connections[self.room_id]:
                self.room_connections[self.room_id].remove(username)
                
                # Notify other users
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_left',
                        'username': username,
                        'users': self.room_connections[self.room_id]
                    }
                )
    
    async def handle_ping(self):
        """Handle ping messages"""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def user_joined(self, event):
        """Send user joined notification to WebSocket"""
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
        await self.send(text_data=json.dumps({
            'type': 'users_update',
            'action': 'left',
            'username': event['username'],
            'users': event['users'],
            'count': len(event['users']),
            'timestamp': datetime.now().isoformat()
        }))
    
    async def send_error(self, error_message):
        """Send error message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }))