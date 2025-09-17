#!/bin/bash
echo "🚀 Starting WebSocket Server with Redis"

# Kill existing server
docker exec 0507b5e8b54d pkill -f daphne 2>/dev/null

# Test Redis
if docker exec 0507b5e8b54d python3 -c "import redis; r = redis.Redis(host='redis', port=6379); r.ping()" 2>/dev/null; then
    echo "✅ Redis connected successfully"
else
    echo "❌ Redis connection failed"
    exit 1
fi

# Start server with Redis
docker exec -d 0507b5e8b54d bash -c "cd /apps/websocket_server && python -m daphne -b 0.0.0.0 -p 7000 websocket_project.asgi:application"

sleep 2

# Check status
if docker exec 0507b5e8b54d ps -ef | grep -q "[d]aphne.*7000"; then
    echo "✅ WebSocket server running on port 7000"
    echo "📡 URL: ws://172.20.23.15:7000/ws/annotation/room1/"
    echo "🔄 Using Redis for message distribution"
else
    echo "❌ Server failed to start"
fi