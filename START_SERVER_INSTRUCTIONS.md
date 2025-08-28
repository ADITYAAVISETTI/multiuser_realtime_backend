# WebSocket Server Start Instructions

## Quick Start Commands

Run these commands in your terminal:

```bash
cd /apps/websocket_server
pip install -r requirements_compatible.txt
python3 -m daphne -b 0.0.0.0 -p 7000 websocket_project.asgi:application
```

## Alternative: Use the Start Script

```bash
cd /apps/websocket_server
./start_websocket_django3.sh
```

## What You Should See

When the server starts successfully:
```
2024-XX-XX XX:XX:XX,XXX - INFO - server - Listening on TCP address 0.0.0.0:7000
```

## Testing the Connection

1. **Keep the WebSocket server running** in the terminal
2. **Open your browser** and go to the annotation viewer
3. **Click the draw icon** → "Join Session"
4. **Check the footer** for "Active Connections: 1"

## Troubleshooting

If you get "No module named 'daphne'":
```bash
pip install daphne==3.0.2
```

If you get "No module named 'channels'":
```bash
pip install channels==3.0.4
```

If you get "No module named 'django'":
```bash
pip install Django==3.2.25
```

## Running in Background

To keep the server running even after closing the terminal:
```bash
cd /apps/websocket_server
nohup python3 -m daphne -b 0.0.0.0 -p 7000 websocket_project.asgi:application > websocket.log 2>&1 &
```

To check if it's running:
```bash
ps aux | grep daphne
```

To see the logs:
```bash
tail -f websocket.log
```

## Important Notes

- The server MUST be running for Active Connections to work
- All users working on the same brain section will see each other
- The connection count updates in real-time