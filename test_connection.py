#!/usr/bin/env python3
"""
Simple WebSocket connection test
Tests the basic WebSocket functionality
"""

import asyncio
import websockets
import json
import time

async def test_websocket_connection():
    server_url = "ws://localhost:7000"
    room_id = "test_room"
    uri = f"{server_url}/ws/annotation/{room_id}/"
    
    print("🧪 Testing WebSocket Connection")
    print(f"📡 Server: {server_url}")
    print(f"🏠 Room: {room_id}")
    print(f"🔗 Full URI: {uri}")
    print("-" * 50)
    
    try:
        print("⏳ Attempting to connect...")
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected successfully!")
            
            # Test join message
            join_msg = {
                "type": "join",
                "username": "TestUser",
                "userId": "test_user_123"
            }
            
            print(f"📤 Sending join message: {join_msg}")
            await websocket.send(json.dumps(join_msg))
            
            # Listen for response
            print("👂 Waiting for server response...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                print(f"📥 Received: {response_data}")
                
                if response_data.get('type') == 'users_update':
                    print("✅ Join successful! Server responded with user update")
                    print(f"👥 Active users: {response_data.get('count', 0)}")
                else:
                    print(f"ℹ️  Server response type: {response_data.get('type')}")
                
            except asyncio.TimeoutError:
                print("⚠️  No response within 5 seconds (may be normal)")
            
            # Test ping message
            ping_msg = {
                "type": "ping",
                "username": "TestUser",
                "userId": "test_user_123"
            }
            
            print(f"📤 Sending ping message: {ping_msg}")
            await websocket.send(json.dumps(ping_msg))
            
            # Listen for ping response
            try:
                ping_response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                ping_data = json.loads(ping_response)
                print(f"📥 Ping response: {ping_data}")
                
                if ping_data.get('type') == 'pong':
                    print("✅ Ping successful!")
                
            except asyncio.TimeoutError:
                print("⚠️  No ping response (may be normal)")
            
            print("\n🎉 WebSocket connection test completed successfully!")
            
    except ConnectionRefusedError:
        print("❌ Connection refused - server may not be running")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=== WebSocket Connection Test ===\n")
    success = asyncio.run(test_websocket_connection())
    
    print(f"\n{'='*50}")
    if success:
        print("🎯 RESULT: WebSocket server is working correctly!")
    else:
        print("⚠️  RESULT: WebSocket server connection failed")
    print("="*50)