# 🚀 FastAPI Backend

## Overview

The FastAPI backend is the central hub of the platform. It receives pipeline triggers, orchestrates agent execution in background threads, persists all results to PostgreSQL, and exposes both REST and WebSocket interfaces.

---

## Architecture

```
External Trigger                FastAPI                    Internal
(GitHub Actions /               (port 8000)                Services
 Dashboard / curl)                   │
        │                            │
        │  POST /pipeline/trigger    │
        └───────────────────────────►│
                                     │  BackgroundTask
                                     ├─────────────────► run_full_pipeline()
                                     │                        │
                                     │  ← run_id immediately  │  (async)
                                     │                        ▼
                                     │                   Agents execute
                                     │                        │
                                     │                        ▼
                                     │                   PostgreSQL write
                                     │
        │  GET /pipeline/runs/{id}   │
        └───────────────────────────►│
                                     │──────────────────► PostgreSQL read
                                     │◄──────────────────
                                     │
                                     │  ← full run detail
                                     │
        │  ws://localhost:8000/      │
        │     ws/pipeline/{id}       │
        └───────────────────────────►│
                                     │──────────────────► pipeline_logger
                                     │◄── stream logs ───
```

---

## Files

```
api/
├── main.py          # FastAPI app, lifespan, WebSocket endpoint
├── database.py      # SQLAlchemy async engine + session
├── models.py        # ORM models (4 tables)
├── pipeline_logger.py  # In-memory WebSocket message bus
├── ws_logger.py     # Sync-safe bridge for agent threads
└── routes/
    ├── health.py    # GET /health
    └── pipelines.py # POST /pipeline/trigger, GET /pipeline/runs
```

---

## Endpoints

### Health Check
```
GET /health
```
Returns status of API, Redis, and PostgreSQL.

**Response:**
```json
{
  "status": "ok",
  "redis": "ok",
  "database": "ok"
}
```

---

### Trigger Pipeline
```
POST /pipeline/trigger
```
Starts a firmware validation pipeline in the background. Returns immediately with a `run_id`.

**Request body:**
```json
{
  "firmware_path":  "firmware/v1.2.0.bin",
  "device_profile": "rpi4",
  "firmware_image": "ubuntu:22.04",
  "simulator_url":  "http://localhost:8080"
}
```

**Response:**
```json
{
  "run_id":        "9f3165b1-5980-4ade-b8ef-fd9b0778899b",
  "firmware_hash": "27c926a8394cbd18",
  "status":        "triggered",
  "message":       "Pipeline running in background. Poll /pipeline/runs/{run_id} for result."
}
```

**Fields:**
| Field | Description |
|-------|-------------|
| `firmware_path` | Path or identifier for firmware being validated |
| `device_profile` | Device type — currently `rpi4` |
| `firmware_image` | Docker image scanned by Trivy/Grype for CVEs |
| `simulator_url` | RPi4 simulator endpoint |

**Demo scenarios:**
```bash
# S1 — Golden path (DEPLOY)
{"firmware_image": "ubuntu:22.04"}

# S2 — CVE block (BLOCK)
{"firmware_image": "nginx:1.14.0"}
```

---

### List Pipeline Runs
```
GET /pipeline/runs
```
Returns all pipeline runs ordered by most recent.

**Response:**
```json
[
  {
    "id":         "9f3165b1-5980-4ade-b8ef-fd9b0778899b",
    "status":     "completed",
    "decision":   "DEPLOY",
    "confidence": 1.0,
    "profile":    "rpi4",
    "triggered":  "2026-04-01T10:23:45.123456+00:00",
    "completed":  "2026-04-01T10:25:12.456789+00:00"
  }
]
```

**Status values:**
| Status | Meaning |
|--------|---------|
| `running` | Pipeline executing |
| `completed` | Pipeline finished, decision available |
| `error` | Pipeline failed |

---

### Get Run Detail
```
GET /pipeline/runs/{run_id}
```
Returns full detail for a specific run including all agent decisions.

**Response:**
```json
{
  "id":            "9f3165b1-5980-4ade-b8ef-fd9b0778899b",
  "status":        "completed",
  "decision":      "DEPLOY",
  "confidence":    1.0,
  "profile":       "rpi4",
  "firmware_hash": "27c926a8394cbd18",
  "langsmith_url": "https://smith.langchain.com/projects/ai-embedded-devops",
  "triggered":     "2026-04-01T10:23:45.123456+00:00",
  "completed":     "2026-04-01T10:25:12.456789+00:00",
  "agents": [
    {
      "agent":      "testing_agent",
      "output": {
        "tests_run":    5,
        "tests_passed": 5,
        "boot_success": true,
        "confidence":   0.95,
        "summary":      "5/5 tests passed..."
      },
      "reflection": false,
      "latency_ms": null
    },
    {
      "agent":      "security_agent",
      "output": {
        "critical_cves": 0,
        "high_cves":     0,
        "risk_score":    0.04,
        "blocking":      false,
        "sbom_packages": 92,
        "summary":       "PASSED: No critical CVEs..."
      },
      "reflection": false,
      "latency_ms": null
    },
    {
      "agent":      "orchestrator",
      "output": {
        "decision":          "DEPLOY",
        "confidence":        1.0,
        "justification":     "Firmware passed all 5 tests...",
        "reflection_used":   false,
        "reflection_rounds": 0,
        "risk_level":        "LOW",
        "primary_factor":    "all tests passed with high confidence",
        "recommendation":    "proceed with deployment"
      },
      "reflection": false,
      "latency_ms": null
    }
  ]
}
```

---

### WebSocket — Live Logs
```
WS /ws/pipeline/{run_id}
```
Stream real-time logs from a running pipeline.

See `README_WEBSOCKETS.md` for full protocol documentation.

---

### API Documentation
```
GET /docs
```
Auto-generated interactive OpenAPI documentation. Available at `http://localhost:8000/docs`.

---

## Background Task Pattern

The pipeline runs in a FastAPI `BackgroundTask` — the API returns immediately and the pipeline executes asynchronously:

```python
@router.post("/trigger")
async def trigger_pipeline(req, background_tasks, db):
    # 1. create DB row immediately
    run = PipelineRun(status="running")
    db.add(run)
    await db.commit()

    # 2. return run_id to caller immediately
    background_tasks.add_task(run_pipeline_task, str(run.id), req)
    return {"run_id": str(run.id), "status": "triggered"}

# runs in background thread
async def run_pipeline_task(run_id, req):
    decision = run_full_pipeline(...)  # takes 2-5 minutes
    # update DB with results
    run.status = "completed"
    run.final_decision = decision.decision.value
    await db.commit()
```

**Why background tasks?**
- HTTP timeout would kill a 5-minute synchronous request
- Caller gets `run_id` immediately to start polling or WebSocket streaming
- Multiple pipelines can run concurrently

---

## Database Layer

### Connection
```python
# database.py
DATABASE_URL = os.getenv("DATABASE_URL").replace(
    "postgresql://", "postgresql+asyncpg://"
)
engine = create_async_engine(DATABASE_URL, echo=True)
```

Uses `asyncpg` driver for async PostgreSQL — compatible with FastAPI's async event loop.

### Tables

**`pipeline_runs`** — one row per pipeline execution
```
id (UUID PK)       firmware_hash    device_profile
status             final_decision   confidence
langsmith_trace_url  triggered_at   completed_at
```

**`test_results`** — one row per individual test
```
id (UUID PK)    pipeline_run_id (FK)    test_name
passed          duration_ms             metrics (JSONB)
```

**`sbom_entries`** — one row per CVE found in SBOM
```
id (UUID PK)    pipeline_run_id (FK)    package_name
version         license                  cve_count
highest_cvss
```

**`agent_decisions`** — full audit trail per agent per run
```
id (UUID PK)    pipeline_run_id (FK)    agent_name
input_state (JSONB)  output (JSONB)     llm_model
latency_ms      reflection_triggered    created_at
```

### Table Initialization
Tables are created automatically on startup via SQLAlchemy `create_all`:
```python
@asynccontextmanager
async def lifespan(app):
    await init_db()  # creates all tables if they don't exist
    yield
```

---

## Environment Variables

```bash
# PostgreSQL
DATABASE_URL=postgresql://devops:devops123@localhost:5432/embedded_devops

# Redis
REDIS_URL=redis://localhost:6379/0

# LangSmith
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ai-embedded-devops

# API
API_HOST=0.0.0.0
API_PORT=8000
```

---

## Running the API

```bash
# development (auto-reload on file changes)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# production
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**Note:** Use `--workers 1` only — the WebSocket message bus uses in-memory state that is not shared across worker processes.

---

## Error Handling

### Pipeline Errors
If the pipeline crashes, the error is caught and persisted:
```python
except Exception as e:
    log(run_id, f"Pipeline failed: {e}", "system", "error")
    log_final(run_id, "ERROR", 0.0)
    run.status = "error"
    await db.commit()
```

The run appears in history with `status: "error"` and `decision: null`.

### LLM Unavailable
The orchestrator has a safe fallback — if Phi3/DeepSeek is unreachable after retries, it uses pre-computed defaults and continues:
```python
except RuntimeError as e:
    justification = f"Automated decision: confidence {confidence}..."
    risk_level    = "CRITICAL" if critical_cves > 0 else "LOW"
    # pipeline continues — never crashes due to LLM failure
```

### Database Unavailable
If PostgreSQL is down on startup, the API fails to start with a clear error:
```
ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)
```
Fix: `docker-compose up -d` to start PostgreSQL.

---

## Quick Reference

```bash
# health check
curl http://localhost:8000/health

# trigger S1 (golden path)
curl -X POST http://localhost:8000/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"ubuntu:22.04","simulator_url":"http://localhost:8080"}'

# trigger S2 (CVE block)
curl -X POST http://localhost:8000/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{"firmware_path":"firmware/v1.3.0-vulnerable.bin","firmware_image":"nginx:1.14.0","simulator_url":"http://localhost:8080"}'

# list all runs
curl http://localhost:8000/pipeline/runs

# get specific run
curl http://localhost:8000/pipeline/runs/{run_id}

# interactive docs
open http://localhost:8000/docs
```
