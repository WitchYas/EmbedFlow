# WebSocket Log Streaming

## Overview

The platform streams real-time pipeline logs to connected clients via WebSockets. Instead of polling for completion, clients receive every agent log message as it happens — boot events, test results, CVE counts, confidence scores, and the final decision.

---

## Architecture

```
FastAPI Background Thread          WebSocket Client
(runs pipeline)                    (Dashboard / terminal)
        │                                  │
        │   agents emit ws_log()           │
        │         │                        │
        ▼         ▼                        │
  pipeline_logger.py                       │
  (in-memory message bus)                  │
        │                                  │
        │   queue.put_nowait(entry)        │
        ▼                                  │
  asyncio.Queue per run_id                 │
        │                                  │
        │   WebSocket endpoint reads       │
        ▼   and forwards                   │
  /ws/pipeline/{run_id} ─────────────────► │
                                           │
                            receives JSON messages:
                            {"type":"log","agent":"testing_agent",...}
                            {"type":"log","agent":"security_agent",...}
                            {"type":"final","decision":"DEPLOY",...}
```

---

## Files

| File | Purpose |
|------|---------|
| `api/pipeline_logger.py` | In-memory message bus — stores + broadcasts logs |
| `api/ws_logger.py` | Sync-safe bridge — lets agent threads emit logs |
| `api/main.py` | WebSocket endpoint `/ws/pipeline/{run_id}` |

---

## WebSocket Endpoint

**URL:** `ws://localhost:8000/ws/pipeline/{run_id}`

**Protocol:**
1. Client connects immediately after triggering a pipeline
2. Server sends all buffered logs (catch-up for late connections)
3. Server streams new logs in real time as agents execute
4. Server sends `{"type": "final", ...}` when pipeline completes
5. Connection closes automatically

**Keepalive:** Server sends `{"type": "ping"}` every 30s to prevent timeout.

---

## Message Format

### Log Message
```json
{
  "type":      "log",
  "run_id":    "9f3165b1-5980-4ade-b8ef-fd9b0778899b",
  "agent":     "testing_agent",
  "message":   "mqtt_connect: MQTT connected — latency 51.2ms",
  "level":     "info",
  "timestamp": "2026-04-01T10:23:45.123456+00:00"
}
```

### Final Decision Message
```json
{
  "type":       "final",
  "run_id":     "9f3165b1-5980-4ade-b8ef-fd9b0778899b",
  "decision":   "DEPLOY",
  "confidence": 1.0,
  "timestamp":  "2026-04-01T10:25:12.456789+00:00"
}
```

### Ping (keepalive)
```json
{"type": "ping"}
```

---

## Log Levels

| Level | Meaning | Example |
|-------|---------|---------|
| `info` | Normal operation | Boot success, test passed |
| `warning` | Attention needed | Reflection triggered, test failed |
| `error` | Blocking issue | CVEs detected, boot failed |

---

## Agent Log Sources

### Testing Agent
```
Booting rpi4 simulator...
Boot successful — 2.71s
mqtt_connect: MQTT connected — latency 51.2ms
cpu_load: CPU stable under load
memory_check: Memory within limits
network_ping: Gateway reachable — 40.4ms
gpio_check: GPIO pins responding
```

### Security Agent
```
Trivy scanning ubuntu:22.04...
Trivy: CRITICAL=0 HIGH=0 MEDIUM=2 LOW=0
SBOM generated: 92 packages
Grype: CRITICAL=0 HIGH=0 MEDIUM=9 LOW=29
```

### Orchestrator
```
History: 10 runs — 8 deployed, 1 blocked, 1 reviewed. Avg conf: 0.89
Confidence: 1.0 → DEPLOY
Justification ready | risk=LOW
```

### System
```
Pipeline 9f3165b1 started
Pipeline failed: <error message>  ← only on errors
```

---

## How ws_log() Works

Agents run in background threads (not async). `ws_log()` bridges the sync/async boundary:

```python
# In any agent — just call ws_log()
from api.ws_logger import ws_log

ws_log("Boot successful", agent="testing_agent", level="info")
ws_log("76 critical CVEs detected", agent="security_agent", level="error")
```

**Thread safety mechanism:**
```python
# pipeline task sets run_id for its thread
set_run_id(thread_id, run_id)

# ws_log() looks up run_id by current thread
run_id = _current_run[threading.current_thread().ident]

# routes to correct pipeline's message bus
pipeline_logger.log(run_id, message, agent, level)
```

This means multiple pipelines can run simultaneously — each agent thread automatically routes to the correct run's message bus.

---

## Memory Management

- Each run keeps a **deque(maxlen=500)** — last 500 messages
- Late-joining clients receive full history on connect
- `cleanup(run_id)` removes the buffer after the run completes
- Listeners are automatically removed on disconnect

---

## Testing WebSockets

### Python client (terminal)
```python
import websocket, json

def on_message(ws, message):
    data = json.loads(message)
    if data.get("type") == "ping": return
    print(f"[{data.get('agent')}] {data.get('message','')}")
    if data.get("type") == "final":
        print(f"FINAL: {data.get('decision')} ({data.get('confidence')})")
        ws.close()

ws = websocket.WebSocketApp(
    "ws://localhost:8000/ws/pipeline/{run_id}",
    on_message=on_message
)
ws.run_forever()
```

### Streamlit integration
```python
import websocket, json, threading

def stream_logs(run_id: str, log_container):
    def on_message(ws, message):
        data = json.loads(message)
        if data.get("type") == "log":
            log_container.write(f"[{data['agent']}] {data['message']}")
        elif data.get("type") == "final":
            ws.close()

    ws = websocket.WebSocketApp(
        f"ws://localhost:8000/ws/pipeline/{run_id}",
        on_message=on_message
    )
    thread = threading.Thread(target=ws.run_forever)
    thread.daemon = True
    thread.start()
```

---

## Complete Flow Example

```
t=0s   Client triggers POST /pipeline/trigger
       ← {"run_id": "abc123", "status": "triggered"}

t=0s   Client connects: ws://localhost:8000/ws/pipeline/abc123
       → Server: {"type":"log","agent":"system","message":"Pipeline abc123 started"}

t=1s   → {"type":"log","agent":"testing_agent","message":"Booting rpi4 simulator..."}
t=3s   → {"type":"log","agent":"testing_agent","message":"Boot successful — 2.71s"}
t=3s   → {"type":"log","agent":"security_agent","message":"Trivy scanning ubuntu:22.04..."}
t=4s   → {"type":"log","agent":"testing_agent","message":"mqtt_connect: latency 51.2ms"}
t=4s   → {"type":"log","agent":"testing_agent","message":"cpu_load: 18.3%"}
t=5s   → {"type":"log","agent":"testing_agent","message":"memory_check: 423MB/1024MB"}
t=5s   → {"type":"log","agent":"testing_agent","message":"network_ping: 40.4ms"}
t=5s   → {"type":"log","agent":"testing_agent","message":"gpio_check: 40 pins OK"}
t=18s  → {"type":"log","agent":"security_agent","message":"Trivy: CRITICAL=0 HIGH=0"}
t=18s  → {"type":"log","agent":"security_agent","message":"SBOM generated: 92 packages"}
t=33s  → {"type":"log","agent":"security_agent","message":"Grype: CRITICAL=0 HIGH=0"}
t=33s  → {"type":"log","agent":"orchestrator","message":"History: 10 runs — 8 deployed"}
t=33s  → {"type":"log","agent":"orchestrator","message":"Confidence: 1.0 → DEPLOY"}
t=72s  → {"type":"log","agent":"orchestrator","message":"Justification ready | risk=LOW"}
t=72s  → {"type":"final","decision":"DEPLOY","confidence":1.0}

Connection closes automatically.
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Client connects before pipeline starts | Receives empty history, waits for live logs |
| Client connects after pipeline completes | Receives full history, sees final message, disconnects |
| Pipeline errors | `{"type":"final","decision":"ERROR","confidence":0.0}` sent |
| Client disconnects mid-stream | Server cleans up queue, pipeline continues unaffected |
| LLM timeout | ws_log() silently skips — never crashes pipeline |
| Full queue (200 messages) | Oldest messages dropped, client still receives new ones |
