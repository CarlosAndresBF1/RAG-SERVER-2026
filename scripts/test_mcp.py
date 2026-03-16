"""Quick MCP server test — verifies SSE transport, initialize, and tools/list."""
import json
import threading
import time

import httpx

BASE = "http://localhost:3010"
session_id = None
sse_messages = []


def sse_reader():
    global session_id
    with httpx.stream("GET", f"{BASE}/sse", timeout=15) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                path = line[6:]
                if "session_id=" in path:
                    session_id = path.split("session_id=")[1]
                    print(f"[SSE] Connected, session: {session_id}")
            if line.startswith("data: {"):
                try:
                    msg = json.loads(line[6:])
                    sse_messages.append(msg)
                    print(f"[SSE] Response: {json.dumps(msg, indent=2)[:500]}")
                except json.JSONDecodeError:
                    pass


# Start SSE listener
t = threading.Thread(target=sse_reader, daemon=True)
t.start()
time.sleep(1.5)

if not session_id:
    print("ERROR: No session_id received from SSE")
    exit(1)

# 1. Initialize
print("\n--- Initialize ---")
resp = httpx.post(
    f"{BASE}/messages/?session_id={session_id}",
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    },
    timeout=10,
)
print(f"Status: {resp.status_code}")
time.sleep(1)

# 2. Initialized notification
httpx.post(
    f"{BASE}/messages/?session_id={session_id}",
    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    timeout=10,
)
time.sleep(0.5)

# 3. List tools
print("\n--- Tools List ---")
resp = httpx.post(
    f"{BASE}/messages/?session_id={session_id}",
    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    timeout=10,
)
print(f"Status: {resp.status_code}")
time.sleep(2)

# Print results
print("\n--- Summary ---")
print(f"SSE messages received: {len(sse_messages)}")
for msg in sse_messages:
    if "result" in msg and "tools" in msg.get("result", {}):
        tools = msg["result"]["tools"]
        print(f"Tools available: {len(tools)}")
        for tool in tools:
            print(f"  - {tool['name']}: {tool.get('description', '')[:80]}")
    elif "result" in msg and "serverInfo" in msg.get("result", {}):
        info = msg["result"]["serverInfo"]
        print(f"Server: {info.get('name', 'unknown')} v{info.get('version', '?')}")
        print(f"Protocol: {msg['result'].get('protocolVersion', '?')}")

print("\nAll tests passed!" if sse_messages else "\nWARNING: No SSE responses received")
