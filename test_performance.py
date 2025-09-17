#!/usr/bin/env python3
"""
Performance test script for WebSocket server
Tests concurrent connections and message handling
Designed to verify 10-15 user capacity
"""

import asyncio
import websockets
import json
import time
import random
import sys
from datetime import datetime

class WebSocketTester:
    def __init__(self, server_url, room_id="test_room"):
        self.server_url = server_url
        self.room_id = room_id
        self.connected_clients = []
        self.total_messages_sent = 0
        self.total_messages_received = 0
        self.errors = []
        
    async def create_client(self, user_id, username):
        """Create a single WebSocket client"""
        try:
            uri = f"{self.server_url}/ws/annotation/{self.room_id}/"
            websocket = await websockets.connect(uri)
            
            # Join the room
            join_msg = {
                "type": "join",
                "username": username,
                "userId": user_id
            }
            await websocket.send(json.dumps(join_msg))
            
            client_info = {
                "websocket": websocket,
                "user_id": user_id,
                "username": username,
                "messages_sent": 0,
                "messages_received": 0
            }
            
            print(f"✓ Client {username} connected")
            return client_info
            
        except Exception as e:
            print(f"✗ Failed to connect client {username}: {e}")
            self.errors.append(f"Connection error for {username}: {e}")
            return None
    
    async def message_listener(self, client_info):
        """Listen for incoming messages for a client"""
        try:
            websocket = client_info["websocket"]
            username = client_info["username"]
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    client_info["messages_received"] += 1
                    self.total_messages_received += 1
                    
                    # Log important message types
                    msg_type = data.get("type", "unknown")
                    if msg_type in ["users_update", "error"]:
                        print(f"📨 {username} received {msg_type}: {data}")
                        
                except json.JSONDecodeError:
                    print(f"⚠️  {username} received invalid JSON")
                    
        except websockets.exceptions.ConnectionClosed:
            print(f"🔌 Connection closed for {username}")
        except Exception as e:
            print(f"⚠️  Message listener error for {username}: {e}")
            self.errors.append(f"Listener error for {username}: {e}")
    
    async def send_test_messages(self, client_info, duration=10):
        """Send test messages from a client"""
        try:
            websocket = client_info["websocket"]
            username = client_info["username"]
            user_id = client_info["user_id"]
            
            start_time = time.time()
            message_count = 0
            
            while time.time() - start_time < duration:
                # Send different types of messages
                message_types = ["ping", "cursor_move", "chat"]
                msg_type = random.choice(message_types)
                
                if msg_type == "ping":
                    msg = {
                        "type": "ping",
                        "username": username,
                        "userId": user_id
                    }
                elif msg_type == "cursor_move":
                    msg = {
                        "type": "cursor_move",
                        "username": username,
                        "userId": user_id,
                        "x": random.randint(100, 800),
                        "y": random.randint(100, 600)
                    }
                elif msg_type == "chat":
                    msg = {
                        "type": "chat",
                        "username": username,
                        "userId": user_id,
                        "message": f"Test message {message_count} from {username}",
                        "timestamp": datetime.now().isoformat()
                    }
                
                await websocket.send(json.dumps(msg))
                client_info["messages_sent"] += 1
                self.total_messages_sent += 1
                message_count += 1
                
                # Random delay to simulate real usage
                await asyncio.sleep(random.uniform(0.1, 2.0))
                
        except Exception as e:
            print(f"⚠️  Send messages error for {username}: {e}")
            self.errors.append(f"Send error for {username}: {e}")
    
    async def run_performance_test(self, num_clients=10, test_duration=30):
        """Run the main performance test"""
        print(f"🚀 Starting performance test with {num_clients} clients")
        print(f"📊 Test duration: {test_duration} seconds")
        print(f"🎯 Target: Verify server handles 10-15 concurrent users")
        print("-" * 50)
        
        # Create clients
        tasks = []
        for i in range(num_clients):
            user_id = f"test_user_{i+1}"
            username = f"TestUser{i+1}"
            client_info = await self.create_client(user_id, username)
            
            if client_info:
                self.connected_clients.append(client_info)
                
                # Start message listener
                tasks.append(asyncio.create_task(
                    self.message_listener(client_info)
                ))
                
                # Small delay between connections
                await asyncio.sleep(0.5)
        
        print(f"✅ Successfully connected {len(self.connected_clients)} clients")
        
        if len(self.connected_clients) == 0:
            print("❌ No clients connected. Test failed.")
            return
        
        # Wait for connections to stabilize
        await asyncio.sleep(2)
        
        # Start sending messages from all clients
        print("📤 Starting message sending phase...")
        for client_info in self.connected_clients:
            tasks.append(asyncio.create_task(
                self.send_test_messages(client_info, test_duration)
            ))
        
        # Wait for test duration
        start_time = time.time()
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), 
                timeout=test_duration + 10
            )
        except asyncio.TimeoutError:
            print("⚠️  Test timeout reached")
        
        # Clean up connections
        print("🧹 Cleaning up connections...")
        for client_info in self.connected_clients:
            try:
                await client_info["websocket"].close()
            except:
                pass
        
        # Print results
        self.print_results(test_duration)
    
    def print_results(self, duration):
        """Print test results"""
        print("\n" + "="*50)
        print("📊 PERFORMANCE TEST RESULTS")
        print("="*50)
        
        print(f"👥 Total clients attempted: {len(self.connected_clients)}")
        print(f"⏱️  Test duration: {duration} seconds")
        print(f"📤 Total messages sent: {self.total_messages_sent}")
        print(f"📥 Total messages received: {self.total_messages_received}")
        
        if self.connected_clients:
            avg_sent = self.total_messages_sent / len(self.connected_clients)
            avg_received = self.total_messages_received / len(self.connected_clients)
            print(f"📊 Average messages per client:")
            print(f"   Sent: {avg_sent:.1f}")
            print(f"   Received: {avg_received:.1f}")
        
        print(f"⚠️  Total errors: {len(self.errors)}")
        
        if self.errors:
            print("\n🚨 ERRORS ENCOUNTERED:")
            for error in self.errors[:5]:  # Show first 5 errors
                print(f"   - {error}")
            if len(self.errors) > 5:
                print(f"   ... and {len(self.errors) - 5} more errors")
        
        # Performance assessment
        print("\n🎯 PERFORMANCE ASSESSMENT:")
        if len(self.connected_clients) >= 10:
            print("✅ Successfully connected 10+ clients")
        else:
            print("❌ Failed to connect 10+ clients")
            
        if len(self.errors) == 0:
            print("✅ No errors encountered")
        elif len(self.errors) < 5:
            print("⚠️  Minor errors occurred")
        else:
            print("❌ Significant errors encountered")
            
        if self.total_messages_sent > 0 and self.total_messages_received > 0:
            print("✅ Messages sent and received successfully")
        else:
            print("❌ Message flow issues detected")
        
        print("\n💡 RECOMMENDATION:")
        if len(self.connected_clients) >= 10 and len(self.errors) < 5:
            print("✅ Server appears ready for 10-15 concurrent users")
        else:
            print("⚠️  Server may need optimization for high concurrency")

async def main():
    if len(sys.argv) < 2:
        server_url = "ws://localhost:7000"
        print(f"Using default server URL: {server_url}")
        print("Usage: python test_performance.py <server_url> [num_clients] [duration]")
        print("Example: python test_performance.py ws://dev2adi.humanbrain.in:7000 12 30")
    else:
        server_url = sys.argv[1]
    
    num_clients = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    
    # Clamp values for safety
    num_clients = min(max(num_clients, 1), 20)
    duration = min(max(duration, 10), 120)
    
    print(f"🌐 Server URL: {server_url}")
    print(f"👥 Number of clients: {num_clients}")
    print(f"⏱️  Duration: {duration} seconds")
    
    tester = WebSocketTester(server_url)
    await tester.run_performance_test(num_clients, duration)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")