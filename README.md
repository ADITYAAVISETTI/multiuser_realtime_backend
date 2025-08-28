# WebSocket Server for Real-time Annotation Features

## Overview
This is a dedicated Django project that handles WebSocket connections for real-time annotation features. It runs separately on port 7000 to avoid interfering with the main Django application on port 8000.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Server
```bash
./start_websocket_server.sh
```

Or manually:
```bash
python -m daphne -b 0.0.0.0 -p 7000 websocket_project.asgi:application
```

### 3. Test Connection
The WebSocket server will be available at:
- **WebSocket URL**: `ws://dev2adi.humanbrain.in:7000/ws/annotation/{room_id}/`
- **HTTP Health Check**: `http://dev2adi.humanbrain.in:7000/`

## Architecture

### Components
- **Django 4.2+**: Modern Django with better ASGI support
- **Channels 3.0+**: WebSocket support
- **Daphne**: ASGI server
- **CORS**: Cross-origin support for frontend

### WebSocket Endpoints
- `/ws/annotation/{room_id}/` - Join annotation room for real-time collaboration

### Message Types
**Send to server:**
```json
{
  "type": "join",
  "username": "User1"
}
```

**Receive from server:**
```json
{
  "type": "users_update",
  "action": "joined",
  "username": "User1",
  "users": ["User1", "User2"],
  "count": 2,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Integration with Frontend

The frontend WebSocket service automatically connects to this server:
- **Service**: `websocket.service.ts`
- **URL**: `ws://dev2adi.humanbrain.in:7000/ws/annotation/`
- **Components**: Atlas map panel, unlock window popup

## Running Both Servers

1. **Main Django API Server (Port 8000)**:
   ```bash
   cd /apps/backend
   python manage.py runserver 0.0.0.0:8000
   ```

2. **WebSocket Server (Port 7000)**:
   ```bash
   cd /apps/websocket_server
   ./start_websocket_server.sh
   ```

3. **Frontend (Port 80)**:
   ```bash
   cd /apps/frontend
   npm start
   ```

## Testing Real-time Features

1. Open annotation viewer: `http://dev2adi.humanbrain.in/annotation/viewer/IIT/V1/SS-100`
2. Click draw icon → "Join Session" popup
3. Enter username → Click "Join"
4. Footer shows "1 Connection"
5. Open another browser/tab, repeat with different username
6. Both users see "2 Connections" in real-time
7. Hover over connection count to see usernames

## Troubleshooting

### WebSocket Connection Issues
- Check server is running on port 7000
- Verify CORS settings allow frontend domain
- Check browser console for connection errors

### Port Conflicts
- Ensure port 7000 is available
- Change port in both `start_websocket_server.sh` and frontend `websocket.service.ts`

## Benefits of Separate Server

✅ **No API Interference**: Main Django APIs remain unaffected  
✅ **Independent Scaling**: WebSocket server can be scaled separately  
✅ **Easy Debugging**: Isolated logs and error handling  
✅ **Modern Django**: Uses Django 4.2 with better async support  
✅ **Simple Deployment**: Can be deployed on different servers if needed