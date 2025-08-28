#!/bin/bash

# Start WebSocket Server with proper Python path
echo "Starting WebSocket Server for Real-time Annotation Features..."
echo "Server will run on: ws://dev2adi.humanbrain.in:7000"
echo ""

# Set the working directory
cd /apps/websocket_server

# Export Python path to avoid conflicts
export PYTHONPATH=/apps/websocket_server:$PYTHONPATH

# Start the server
echo "Starting Daphne ASGI server on port 7000..."
python3 -m daphne -b 0.0.0.0 -p 7000 websocket_project.asgi:application