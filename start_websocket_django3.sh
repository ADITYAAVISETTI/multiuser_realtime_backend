#!/bin/bash

# Start WebSocket Server on Port 7000 (Django 3.2 compatible)
echo "Starting WebSocket Server for Real-time Annotation Features..."
echo "Server will run on: ws://dev2adi.humanbrain.in:7000"
echo ""

# Check if daphne is available
if ! command -v daphne &> /dev/null; then
    echo "Daphne not found. Installing compatible dependencies..."
    pip install -r requirements_compatible.txt
fi

# Start the server
echo "Starting Daphne ASGI server on port 7000..."
python3 -m daphne -b 0.0.0.0 -p 7000 websocket_project.asgi:application