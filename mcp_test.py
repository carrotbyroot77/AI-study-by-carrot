# mcp_test.py  -- SSE 응답 파싱 + tools/call 방식
import requests, json

MCP_URL = "http://127.0.0.1:8000/mcp/"  
HD = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

def call_tool(name: str, arguments: dict):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    r = requests.post(MCP_URL, headers=HD, json=body, timeout=20)

    # SSE 본문에서 data: 라인만 추출해서 JSON 파싱
    text = r.text
    data_line = next((line for line in text.splitlines() if line.startswith("data: ")), None)
    if not data_line:
        raise RuntimeError(f"SSE data line not found.\n--- RAW ---\n{text[:500]}")
    payload = json.loads(data_line[6:])  # strip "data: "
    if "error" in payload:
        raise RuntimeError(f"MCP error: {payload['error']}")
    return payload.get("result")

if __name__ == "__main__":
    result = call_tool("weather_now", {"city": "Seoul"})
    print(json.dumps(result, ensure_ascii=False, indent=2))

