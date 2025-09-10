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
                await self.handle_ping()
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
            elif message_type == 'region_deleted':
                await self.handle_region_deleted(data)
            elif message_type == 'region_edit_start':
                await self.handle_region_edit_start(data)
            elif message_type == 'region_edit_end':
                await self.handle_region_edit_end(data)
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
    
    # NEW: Drawing-related handlers
    async def handle_add_icon_click(self, data):
        """Handle add icon click to activate draw mode"""
        username = data.get('username', self.username)
        geometry_type = data.get('geometry_type', 'Polygon')
        selected_node = data.get('selected_node')
        
        print(f"[DRAWING] Add icon clicked - User: {username}, Geometry: {geometry_type}, Room: {self.room_id}")
        
        # Broadcast add icon click to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'add_icon_clicked',
                'username': username,
                'geometry_type': geometry_type,
                'selected_node': selected_node,
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_geometry_select(self, data):
        """Handle geometry type selection"""
        username = data.get('username', self.username)
        geometry_type = data.get('geometry_type')
        
        print(f"[DRAWING] Geometry selected - User: {username}, Type: {geometry_type}, Room: {self.room_id}")
        
        # Broadcast geometry selection to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'geometry_selected',
                'username': username,
                'geometry_type': geometry_type,
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_drawing_start(self, data):
        """Handle drawing start event"""
        username = data.get('username', self.username)
        geometry_type = data.get('geometry_type')
        start_coordinates = data.get('start_coordinates')
        drawing_id = data.get('drawing_id')
        selected_node = data.get('selected_node')
        
        print(f"[DRAWING] Drawing started - User: {username}, Type: {geometry_type}, Room: {self.room_id}")
        
        # Broadcast drawing start to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'drawing_started',
                'username': username,
                'geometry_type': geometry_type,
                'start_coordinates': start_coordinates,
                'drawing_id': drawing_id,
                'selected_node': selected_node,
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_drawing_update(self, data):
        """Handle drawing update event"""
        username = data.get('username', self.username)
        coordinates = data.get('coordinates')
        drawing_id = data.get('drawing_id')
        geometry_type = data.get('geometry_type')
        
        # Don't log every update to avoid spam
        # print(f"[DRAWING] Drawing update - User: {username}, Room: {self.room_id}")
        
        # Broadcast drawing update to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'drawing_updated',
                'username': username,
                'coordinates': coordinates,
                'drawing_id': drawing_id,
                'geometry_type': geometry_type,
                'sender_channel': self.channel_name
            }
        )
    
    async def handle_drawing_end(self, data):
        """Handle drawing end event"""
        username = data.get('username', self.username)
        final_coordinates = data.get('final_coordinates')
        drawing_id = data.get('drawing_id')
        geometry_type = data.get('geometry_type')
        selected_node = data.get('selected_node')
        
        print(f"[DRAWING] Drawing ended - User: {username}, Type: {geometry_type}, Room: {self.room_id}")
        
        # Broadcast drawing end to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'drawing_ended',
                'username': username,
                'final_coordinates': final_coordinates,
                'drawing_id': drawing_id,
                'geometry_type': geometry_type,
                'selected_node': selected_node,
                'sender_channel': self.channel_name
            }
        )
    
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
    
    # NEW: Drawing event broadcasts
    async def add_icon_clicked(self, event):
        """Send add icon click to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'add_icon_clicked',
                'username': event['username'],
                'geometry_type': event['geometry_type'],
                'selected_node': event['selected_node'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def geometry_selected(self, event):
        """Send geometry selection to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'geometry_selected',
                'username': event['username'],
                'geometry_type': event['geometry_type'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def drawing_started(self, event):
        """Send drawing start to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'drawing_started',
                'username': event['username'],
                'geometry_type': event['geometry_type'],
                'start_coordinates': event['start_coordinates'],
                'drawing_id': event['drawing_id'],
                'selected_node': event['selected_node'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def drawing_updated(self, event):
        """Send drawing update to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'drawing_updated',
                'username': event['username'],
                'coordinates': event['coordinates'],
                'drawing_id': event['drawing_id'],
                'geometry_type': event['geometry_type'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def drawing_ended(self, event):
        """Send drawing end to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'drawing_ended',
                'username': event['username'],
                'final_coordinates': event['final_coordinates'],
                'drawing_id': event['drawing_id'],
                'geometry_type': event['geometry_type'],
                'selected_node': event['selected_node'],
                'timestamp': datetime.now().isoformat()
            }))
    
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
    
    async def handle_clear_user_drawings(self, data):
        """Handle request to clear a user's drawings"""
        username = data.get('username')
        
        if not username:
            await self.send_error('Username is required for clearing drawings')
            return
        
        print(f"[DRAWING] Clearing drawings for user: {username}")
        
        # Broadcast clear drawings message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'clear_drawings',
                'username': username,
                'sender_channel': self.channel_name
            }
        )
    
    async def clear_drawings(self, event):
        """Send clear drawings message to WebSocket"""
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'clear_user_drawings',
                'username': event['username'],
                'timestamp': datetime.now().isoformat()
            }))
    
    async def handle_region_deleted(self, data):
        """Handle region deletion event"""
        username = data.get('username', self.username)
        region_name = data.get('region_name')
        region_data = data.get('region_data')
        
        print(f"[REGION DELETE] Region '{region_name}' deleted by user: {username} in room {self.room_id}")
        print(f"[REGION DELETE] Region data: {region_data}")
        
        # Broadcast region deletion to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'region_deleted_broadcast',
                'username': username,
                'region_name': region_name,
                'region_data': region_data,
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
                'username': event['username'],
                'region_name': event['region_name'],
                'region_data': event['region_data'],
                'timestamp': datetime.now().isoformat()
            }))
        else:
            print(f"[REGION DELETE] Skipping sender {self.username}")

    async def handle_region_edit_start(self, data):
        """Handle region edit start event"""
        username = data.get('username', self.username)
        region_id = data.get('region_id')
        region_name = data.get('region_name')
        region_data = data.get('region_data')
        coordinates = data.get('coordinates')
        geometry_type = data.get('geometry_type')
        
        print(f"[REGION EDIT START] Region '{region_name}' (ID: {region_id}) being edited by user: {username} in room {self.room_id}")
        print(f"[REGION EDIT START] Geometry type: {geometry_type}")
        
        # Broadcast region edit start to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'region_edit_start_broadcast',
                'username': username,
                'region_id': region_id,
                'region_name': region_name,
                'region_data': region_data,
                'coordinates': coordinates,
                'geometry_type': geometry_type,
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
                'username': event['username'],
                'region_id': event['region_id'],
                'region_name': event['region_name'],
                'region_data': event['region_data'],
                'coordinates': event['coordinates'],
                'geometry_type': event['geometry_type'],
                'timestamp': datetime.now().isoformat()
            }))
        else:
            print(f"[REGION EDIT START] Skipping sender {self.username}")

    async def handle_region_edit_end(self, data):
        """Handle region edit end event"""
        username = data.get('username', self.username)
        region_id = data.get('region_id')
        region_name = data.get('region_name')
        region_data = data.get('region_data')
        final_coordinates = data.get('final_coordinates')
        geometry_type = data.get('geometry_type')
        
        print(f"[REGION EDIT END] Region '{region_name}' (ID: {region_id}) edit completed by user: {username} in room {self.room_id}")
        print(f"[REGION EDIT END] Final coordinates: {final_coordinates}")
        
        # Broadcast region edit end to all OTHER users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'region_edit_end_broadcast',
                'username': username,
                'region_id': region_id,
                'region_name': region_name,
                'region_data': region_data,
                'final_coordinates': final_coordinates,
                'geometry_type': geometry_type,
                'sender_channel': self.channel_name
            }
        )
        print(f"[REGION EDIT END] Broadcast sent to room group: {self.room_group_name}")

    async def region_edit_end_broadcast(self, event):
        """Send region edit end to WebSocket"""
        # Don't send back to the sender - only to other users
        if event.get('sender_channel') != self.channel_name:
            print(f"[REGION EDIT END] Sending edit end message to user {self.username}")
            await self.send(text_data=json.dumps({
                'type': 'region_edit_end',
                'username': event['username'],
                'region_id': event['region_id'],
                'region_name': event['region_name'],
                'region_data': event['region_data'],
                'final_coordinates': event['final_coordinates'],
                'geometry_type': event['geometry_type'],
                'timestamp': datetime.now().isoformat()
            }))
        else:
            print(f"[REGION EDIT END] Skipping sender {self.username}")
    
    async def send_error(self, error_message):
        """Send error message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }))