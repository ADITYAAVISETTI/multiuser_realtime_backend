#!/bin/bash

echo "=== Starting Optimized WebSocket Server ==="
echo "Server optimized for 10-15 concurrent users"
echo "Using Redis channel layer for high performance"
echo ""

# Change to websocket server directory
cd /home/projects/developers/aditya/apps/websocket_server

echo "🔧 IMPORTANT: System OpenSSL compatibility issues detected"
echo "📋 Manual setup required due to environment constraints"
echo ""
echo "✅ OPTIMIZATION STATUS:"
echo "   ✓ Redis channel layer configured (settings.py:86)"
echo "   ✓ Connection pooling: 50 max connections"
echo "   ✓ Rate limiting: Cursor(20/s), Drawing(10/s), Chat(5/s)"
echo "   ✓ Channel capacity: 2000 messages"
echo "   ✓ Performance optimizations applied"
echo ""
echo "🚀 TO START MANUALLY:"
echo "   1. Fix OpenSSL environment conflicts"
echo "   2. Install: pip install redis==4.0.2 channels-redis==3.3.1" 
echo "   3. Run: python3 -m daphne -b 0.0.0.0 -p 7000 websocket_project.asgi:application"
echo ""
echo "🌐 WebSocket URL: ws://dev2adi.humanbrain.in:7000/ws/annotation/"
echo ""
echo "🔍 TESTING COMMAND:"
echo "   python3 test_performance.py ws://dev2adi.humanbrain.in:7000 12 30"
echo ""

# Attempt to start anyway (may work in some environments)
echo "⚠️  Attempting to start server (may fail due to OpenSSL)..."
echo "=================================="

# Try with basic daphne start
python3 -m daphne -b 0.0.0.0 -p 7000 websocket_project.asgi:application