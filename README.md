# AI-Powered DevOps Platform for Embedded Systems Simulation

> An intelligent DevOps platform that orchestrates pre-deployment validation of embedded firmware through containerized simulation, stateful AI agents, and automated security analysis.

---

Made by Yasmin.

## Screenshots

![Dashboard 1](screenshots/dashboard%20(1).png)

![Dashboard 2](screenshots/dashboard%20(2).png)

![Dashboard 3](screenshots/dashboard%20(3).png)

##  Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Components](#components)
  - [RPi4 Simulator](#rpi4-simulator)
  - [AI Agents](#ai-agents)
  - [FastAPI Backend](#fastapi-backend)
  - [Data Layer](#data-layer)
- [Demo Scenarios](#demo-scenarios)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Roadmap](#roadmap)

---

## Overview

Traditional embedded firmware validation requires physical hardware, making testing expensive, slow, and difficult to automate. This platform replaces hardware with intelligent Docker-based simulators, orchestrated by a multi-agent AI system that makes deployment decisions based on test results, security scans, historical data, and deep reasoning.

**Core capabilities:**
- Containerized RPi4 simulator exposing standardized REST endpoints with Prometheus metrics
- 3 specialized LangGraph agents with stateful workflows and LangSmith-compatible tracing configuration
- Two-model LLM routing: Phi3 for fast decisions, DeepSeek-R1 for deep reflection
- Real CVE scanning via Trivy + Syft + Grype with fallback and disagreement detection
- Historical intelligence: confidence scores adjust based on past pipeline runs
- Full audit trail: every decision persisted to PostgreSQL with JSONB agent logs
- Parallel agent execution: Testing + Security agents run concurrently
- Live WebSocket logs for each pipeline run through `/ws/pipeline/{run_id}`
- GitHub Actions trigger/poll/status feedback loop for firmware changes

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRIGGER LAYER                            │
│         Developer Push → GitHub Actions → FastAPI               │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                        AGENT LAYER                              │
│                                                                 │
│   ┌─────────────────┐     ┌─────────────────┐                  │
│   │  Testing Agent  │     │ Security Agent  │  (parallel)      │
│   │  LangGraph      │     │  LangGraph      │                  │
│   │  Phi3 + tools   │     │  Trivy+Syft+    │                  │
│   └────────┬────────┘     │  Grype+Phi3     │                  │
│            │              └────────┬────────┘                  │
│            └──────────┬───────────┘                            │
│                       ▼                                         │
│            ┌─────────────────────┐                             │
│            │   Orchestrator      │                             │
│            │   LangGraph         │                             │
│            │   Phi3 + DeepSeek   │                             │
│            │   Historical DB     │                             │
│            │   Reflection Loop   │                             │
│            └─────────┬───────────┘                             │
└──────────────────────┼──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                   SIMULATION & DATA LAYER                       │
│                                                                 │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│   │ RPi4 Docker  │  │  PostgreSQL  │  │     Redis        │    │
│   │ Simulator    │  │  Audit Trail │  │ Health/Planned  │    │
│   │ :8080        │  │  :5432       │  │   :6379          │    │
│   └──────────────┘  └──────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                   OBSERVABILITY LAYER                           │
│                                                                 │
│   LangSmith project traces    Prometheus + Grafana metrics      │
│   FastAPI /docs (OpenAPI)     React Control Plane + WebSocket   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
ai-embedded-devops/
│
├── agents/                     # AI agent layer
│   ├── orchestrator.py         # Main decision agent (Phi3 + DeepSeek-R1)
│   ├── testing_agent.py        # Simulator test runner (LangGraph)
│   ├── security_agent.py       # CVE scanner (Trivy + Syft + Grype)
│   ├── llm_router.py           # Two-model LLM routing (Phi3 / DeepSeek)
│   ├── state.py                # Shared Pydantic state (AgentState)
│   └── __init__.py
│
├── api/                        # FastAPI backend
│   ├── main.py                 # App entry point + lifespan (table init)
│   ├── database.py             # SQLAlchemy async engine + session
│   ├── models.py               # ORM models (4 tables)
│   └── routes/
│       ├── health.py           # GET /health
│       └── pipelines.py        # POST /pipeline/trigger, GET /pipeline/runs
│
├── simulators/
│   └── rpi4/
│       ├── main.py             # FastAPI simulator (boot, tests, metrics, faults)
│       ├── Dockerfile
│       └── requirements.txt
│
├── dashboard/                  # Streamlit dashboard / legacy operator view
├── desktop/                    # React Control Plane (REST polling, WebSocket logs, AI console)
├── device_profiles/            # YAML device profile definitions
├── infra/                      # Prometheus + Grafana provisioning
├── tests/                      # Unit + integration tests
├── docs/                       # Academic report, diagrams
│
├── docker-compose.yml          # PostgreSQL, Redis, Prometheus, Grafana, simulators, API
├── start.sh                    # One-command startup script
├── requirements.txt
└── .env                        # Environment configuration
```

---

## Components

### RPi4 Simulator

A FastAPI Python container that simulates a Raspberry Pi 4 (ARM64, 1GB RAM) without requiring physical hardware. Exposes a standardized REST interface consumed by the Testing Agent.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Device status: idle/booting/running/error |
| POST | `/boot` | Simulate boot sequence (2.5–4s realistic delay) |
| POST | `/run-test` | Execute named test suite, returns structured results |
| GET | `/metrics` | Prometheus metrics: CPU, RAM, uptime, boot histogram |
| POST | `/inject-fault` | Inject faults: boot_loop, memory_full, network_loss |
| POST | `/reset` | Reset state for next test run |

**Supported tests:** `mqtt_connect`, `cpu_load`, `memory_check`, `network_ping`, `gpio_check`

**Fault injection** enables S4 demo scenario (self-healing / resilience testing):
```bash
# inject a network fault
curl -X POST http://localhost:8080/inject-fault \
  -H "Content-Type: application/json" \
  -d '{"fault": "network_loss"}'
```

**Prometheus metrics exported:**
- `device_cpu_percent` — CPU usage gauge
- `device_ram_used_mb` — RAM usage gauge
- `device_uptime_seconds` — uptime gauge
- `device_boot_seconds` — boot duration histogram
- `device_tests_total` — test counter by name and result label

---

### AI Agents

All agents are built with **LangGraph** — a framework for stateful, graph-based AI workflows. LangSmith tracing is configured through the LangChain/LangGraph environment variables and can be used to inspect graph execution and LLM calls. The database currently stores a LangSmith project URL rather than an exact per-run trace URL.

#### LLM Routing (`agents/llm_router.py`)

Two models serve different roles, routed via a single module:

| Function | Model | Size | Use Case |
|----------|-------|------|----------|
| `ask_fast()` | Phi3 | 3.8B / 2.3GB | Standard decisions, justifications |
| `ask_deep()` | DeepSeek-R1:7b | 7.6B / 4.7GB | Reflection rounds, ambiguous decisions |

DeepSeek-R1 may emit `<think>` blocks. The LLM router strips those blocks from the final response while printing a shortened reasoning preview in local logs.

Both models run locally via **Ollama** — zero API cost, full data privacy.

#### Testing Agent (`agents/testing_agent.py`)

**LangGraph nodes:** `boot_device` → `run_tests` → `build_report`

Boots the RPi4 simulator, executes the 5-test suite, collects per-test metrics, and produces a structured `TestReport` with confidence score.

**Confidence scoring logic:**
- 5/5 passed → 0.95 base confidence
- 4/5 passed → 0.80
- Critical test failure (mqtt_connect, memory_check) → -0.10 penalty each
- Boot failure → confidence 0.0, pipeline short-circuits

**Routing:** If boot fails, graph skips directly to `build_report` (no test execution).

#### Security Agent (`agents/security_agent.py`)

**LangGraph nodes:** `scan_image` → `generate_sbom` → `correlate_cves` → `build_report`

Runs a full supply-chain security analysis on the firmware Docker image using three complementary tools:

| Tool | Role | Output |
|------|------|--------|
| **Trivy** | Primary CVE scanner | CVE counts by severity |
| **Syft** | SBOM/package inventory generator | Syft JSON package inventory |
| **Grype** | CVE correlator | Cross-validated CVE matches |

**Grype/Trivy fallback:** If Trivy times out or fails, Grype results are used as primary source. If both run, disagreements are detected and escalated.

**Blocking logic:** Any `CRITICAL` CVE (CVSS ≥ 9.0) immediately sets `blocking=True`, which causes the Orchestrator to subtract 0.60 from confidence — nearly always resulting in a BLOCK decision.

**Risk score formula:**
```
risk_score = min(1.0,
    critical * 0.40 +
    high     * 0.10 +
    medium   * 0.02 +
    low      * 0.005
)
```

#### Orchestrator Agent (`agents/orchestrator.py`)

**LangGraph nodes:** `aggregate` → `decide` → (optional) `reflect` → `decide`

The central decision-making agent. Combines test + security reports with historical intelligence to produce a final `deploy / block / review` decision with confidence score and LLM justification.

**Parallel execution:** Testing Agent and Security Agent run concurrently via `ThreadPoolExecutor(max_workers=2)`, cutting pipeline time roughly in half.

**Historical intelligence:**
```sql
SELECT final_decision, confidence
FROM pipeline_runs
WHERE device_profile = %s AND status = 'completed'
ORDER BY triggered_at DESC LIMIT 10
```
- Block rate ≥ 60% → confidence -0.15
- Consistent deploys (0 blocks, 3+ runs) → confidence +0.05

**Confidence → Decision mapping:**

| Confidence | Decision |
|------------|----------|
| ≥ 0.80 | DEPLOY |
| 0.50 – 0.79 | REVIEW |
| < 0.50 | BLOCK |

**Reflection loop:** When confidence is between 0.40 and 0.79, DeepSeek-R1 is invoked for up to 2 reflection rounds. It analyzes whether failed tests are critical, whether CVEs are exploitable in context, and whether historical patterns support the decision. The reflection note and suggested confidence adjustment are persisted in `agent_decisions.output`; the current scoring code records the adjustment but does not yet apply it back into the final confidence.

---

### FastAPI Backend (`api/`)

Async FastAPI application serving as the interface between GitHub Actions (or any trigger) and the agent pipeline.

**Key design:** Pipeline runs in a `BackgroundTask` — the API returns immediately with a `run_id`, and the caller polls for completion.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | API + Redis + DB status |
| POST | `/pipeline/trigger` | Trigger a pipeline run (returns run_id immediately) |
| GET | `/pipeline/runs` | List all pipeline runs |
| GET | `/pipeline/runs/{run_id}` | Get run details + agent decision logs |
| POST | `/pipeline/chat` | Ask a run-grounded AI question |
| WS | `/ws/pipeline/{run_id}` | Stream live pipeline logs |
| GET | `/docs` | Auto-generated OpenAPI documentation |

**Example trigger:**
```bash
curl -X POST http://localhost:8000/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_path": "firmware/v1.2.0.bin",
    "device_profile": "rpi4",
    "firmware_image": "ubuntu:22.04",
    "simulator_url": "http://localhost:8080"
  }'
```

**Example response:**
```json
{
  "run_id": "94b82265-8d0f-42de-9272-ecb24c38064c",
  "firmware_hash": "27c926a8394cbd18",
  "status": "triggered",
  "message": "Pipeline running in background. Poll /pipeline/runs/{run_id} for result."
}
```

---

### Data Layer

#### PostgreSQL — Persistent Audit Trail

Four tables storing every pipeline run and every agent decision:

**`pipeline_runs`** — one row per firmware push
```
id (UUID) | firmware_hash | device_profile | status
final_decision | confidence | langsmith_trace_url
triggered_at | completed_at
```

**`test_results`** — per-test detail with JSONB metrics
```
id | pipeline_run_id | test_name | passed
duration_ms | metrics (JSONB: cpu_percent, latency_ms, etc.)
```

**`sbom_entries`** — SBOM package inventory per run
```
id | pipeline_run_id | package_name | version
license | cve_count | highest_cvss
```

**`agent_decisions`** — full agent audit trail
```
id | pipeline_run_id | agent_name | input_state (JSONB)
output (JSONB) | llm_model | latency_ms
reflection_triggered | created_at
```

#### Redis — Health-Checked Infrastructure / Planned LLM Cache

Caches Ollama responses by prompt hash to avoid redundant LLM calls on repeated pipeline runs.

Current implementation note: Redis is deployed and checked by `GET /health`, but `agents/llm_router.py` calls Ollama directly. Prompt-hash response caching is planned rather than active.

---

## Demo Scenarios

## Demo Scenarios & Execution

Each scenario is designed to test a specific layer of the AI orchestrator's reasoning.

### Scenario 1: Golden Path ✅
**Goal**: Demonstrate a perfect deployment where security and testing align.
**Technical Logic**:
*   **Security**: `Trivy` returns 0 Critical/High CVEs.
*   **Testing**: All hardware simulator tests (`mqtt`, `cpu`, `network`) return `passed: true`.
*   **Orchestration**: Confidence script calculates `> 0.85`. No reflection is needed.
*   **Outcome**: `DEPLOY`

**Run Command (Windows PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://172.18.205.88:8000/pipeline/trigger" -Method Post -ContentType "application/json" -Body '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"ubuntu:latest","device_profile":"rpi4"}'
```
**Run Command (WSL / Linux Terminal):**
```bash
curl -X POST http://localhost:8000/pipeline/trigger -H "Content-Type: application/json" -d '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"ubuntu:latest","device_profile":"rpi4"}'
```

---

### Scenario 2: CVE Block 🛡️
**Goal**: Prove the AI protects the device even when all functional tests pass.
**Technical Logic**:
*   **Security**: `Trivy` detects `CRITICAL` vulnerabilities in `nginx:1.14.0`. The `security_agent` returns `blocking: true`.
*   **Testing**: All functional tests still pass (100%).
*   **Orchestration**: The orchestrator receives the block signal. The confidence logic subtracts 0.60, dropping confidence below 0.40.
*   **Outcome**: `BLOCK` (The AI overrides the successful tests).

**Run Command (Windows PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://172.18.205.88:8000/pipeline/trigger" -Method Post -ContentType "application/json" -Body '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"nginx:1.14.0","device_profile":"rpi4"}'
```
**Run Command (WSL / Linux Terminal):**
```bash
curl -X POST http://localhost:8000/pipeline/trigger -H "Content-Type: application/json" -d '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"nginx:1.14.0","device_profile":"rpi4"}'
```

---

### Scenario 3: AI Reflection Layer 
**Goal**: Show DeepSeek-R1 "thinking" and re-evaluating a borderline decision.
**Technical Logic**:
*   **Context**: Using `python:3.9-slim` results in a medium-risk profile.
*   **Orchestration**: Confidence lands in the "Uncertainty Zone" (0.4 - 0.79). 
*   **Reflection**: `LangGraph` routes the state to the `reflect` node. **DeepSeek-R1** runs a Chain-of-Thought analysis to check if the security risk justifies blocking the release.
*   **Outcome**: `REVIEW` (with detailed "Think" logs in the console).

**Run Command (Windows PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://172.18.205.88:8000/pipeline/trigger" -Method Post -ContentType "application/json" -Body '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"python:3.9-slim","device_profile":"rpi4"}'
```
**Run Command (WSL / Linux Terminal):**
```bash
curl -X POST http://localhost:8000/pipeline/trigger -H "Content-Type: application/json" -d '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"python:3.9-slim","device_profile":"rpi4"}'
```

---

### Scenario 4: Self-Healing Advice 
**Goal**: Demonstrate the agent identifying a failure and proposing a technical fix.
**Technical Logic**:
*   **Fault Injection**: Using `node:14-alpine` triggers a simulated dependency conflict.
*   **Remediation**: The Orchestrator's LLM (Phi-3) compares the failure against historical patch patterns.
*   **Outcome**: `BLOCK/REVIEW` + A specific patch recommendation (e.g., *"Update libssl to v1.4.2"*) visible in the AI Console.

**Run Command (Windows PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://172.18.205.88:8000/pipeline/trigger" -Method Post -ContentType "application/json" -Body '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"node:14-alpine","device_profile":"rpi4"}'
```
**Run Command (WSL / Linux Terminal):**
```bash
curl -X POST http://localhost:8000/pipeline/trigger -H "Content-Type: application/json" -d '{"firmware_path":"firmware/v1.2.0.bin","firmware_image":"node:14-alpine","device_profile":"rpi4"}'
```


```bash
# inject boot loop fault
curl -X POST http://localhost:8080/inject-fault -d '{"fault": "boot_loop"}'
# trigger pipeline — testing agent retries, then gracefully fails
```

---

##  Scenario Command Reference

You can trigger the pipeline directly from the **Control Plane** UI or by using the CLI commands below. 

### Prerequisites: Get your WSL IP
Run `hostname -I` in WSL. If your IP is `172.18.205.88`, use it below.

### Scenario 1: Golden Path (Auto-Deploy)
*   **Context:** Secure base image, valid versioning, all tests pass.
*   **Expected Outcome:** `DEPLOY` with 95%+ confidence.
*   **Command (PowerShell):**
    ```powershell
    Invoke-RestMethod -Method Post -Uri "http://172.18.205.88:8000/pipeline/trigger" -ContentType "application/json" -Body '{"firmware_path": "v1.0.0", "firmware_image": "ubuntu:22.04"}'
    ```

### Scenario 2: Security Block (Trivy Scan)
*   **Context:** Use an outdated `node:14-alpine` image known to have CRITICAL vulnerabilities.
*   **Expected Outcome:** `BLOCK` due to high CVE count.
*   **Command (PowerShell):**
    ```powershell
    Invoke-RestMethod -Method Post -Uri "http://172.18.205.88:8000/pipeline/trigger" -ContentType "application/json" -Body '{"firmware_path": "v1.1.0", "firmware_image": "node:14-alpine"}'
    ```

### Scenario 3: Reflection Loop (DeepSeek-R1)
*   **Context:** Moderate test failures and medium CVEs. Orchestrator confidence drops below 0.8, triggering a "Reflection" round using the DeepSeek-R1 model.
*   **Expected Outcome:** `REVIEW` or `BLOCK` with detailed AI reasoning.
*   **Command (PowerShell):**
    ```powershell
    Invoke-RestMethod -Method Post -Uri "http://172.18.205.88:8000/pipeline/trigger" -ContentType "application/json" -Body '{"firmware_path": "v1.2.0-beta", "firmware_image": "python:3.9-slim"}'
    ```

### Scenario 4: Self-Healing Build
*   **Context:** A build that originally failed but the Orchestrator provides "remediation advice" based on simulator logs.
*   **Expected Outcome:** AI fixes the env and recommends a deploy.
*   **Command (PowerShell):**
    ```powershell
    Invoke-RestMethod -Method Post -Uri "http://172.18.205.88:8000/pipeline/trigger" -ContentType "application/json" -Body '{"firmware_path": "v1.3.0", "firmware_image": "alpine:3.15"}'
    ```

---

## 💻 Technical Integration: Desktop & Backend

The **Control Plane** (desktop dashboard) is a React SPA that connects to the FastAPI backend via three primary channels:

1.  **REST API (Polling):** The dashboard polls `GET /pipeline/runs` every 5 seconds to update the "Overview" and "Pipelines Table". It also checks `GET /health` for infrastructure status.
2.  **WebSockets (Live Stream):** When a pipeline run is triggered, the dashboard opens a persistent WebSocket connection to `ws://[WSL_IP]:8000/ws/pipeline/{run_id}`. 
    *   The backend redirects all agent logs (`print` and `ws_log` calls) through this socket.
    *   The frontend uses a **Virtual Terminal** to render these logs in real-time.
3.  **Cross-Platform Networking:** Since the backend runs in WSL2 and the UI may run in a Windows browser, we use the WSL Virtual Ethernet IP (e.g. `172.18.x.x`). 
    *   **CORS** is enabled on the FastAPI backend to allow the frontend to talk to the API on port 8000.
    *   `desktop/src/api.ts` currently contains a hard-coded WSL2 API base URL. Update it when the WSL IP changes.
    *   `desktop/vite.config.ts` currently uses port 3000. If Grafana is also running on 3000, run Vite on an alternate port such as 3001.

---

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Simulation | Docker + FastAPI | Python 3.12 | RPi4 device emulation |
| Agents | LangGraph | 0.1.10+ | Stateful AI workflows |
| Observability | LangSmith | Latest | Project-level agent trace visibility |
| Fast LLM | Phi3 via Ollama | 3.8B | Decisions + justifications |
| Deep LLM | DeepSeek-R1 via Ollama | 7.6B | Reflection + reasoning |
| Security | Trivy + Syft + Grype | Latest | CVE + SBOM analysis |
| Backend | FastAPI | 0.110+ | REST API + async pipeline |
| Database | PostgreSQL | 16 | Audit trail + history |
| Cache | Redis | 7.2 | Health-checked service; LLM cache planned |
| Monitoring | Prometheus | Latest | Device metrics |
| CI/CD | GitHub Actions | Latest | Pipeline trigger, polling, commit status |
| Dashboard | React + Vite | Current | Desktop Control Plane |
| Dashboard | Streamlit | 1.32+ | Legacy/operator view |
| Runtime | WSL2 + Docker Desktop | Ubuntu 24 | Local development |

---

## Getting Started

### Prerequisites

- Windows 10/11 with WSL2 enabled
- Docker Desktop
- Ollama installed on Windows
- Python 3.12 in WSL2

### 1. Clone and configure

```bash
git clone https://github.com/Witchyass/DevopsAi_platform.git
cd DevopsAi_platform
cp .env.example .env
# edit .env with your LangSmith API key
```

### 2. Pull LLM models (PowerShell)

```powershell
$env:OLLAMA_HOST = "0.0.0.0"
ollama serve
# in a new PowerShell window:
ollama pull phi3
ollama pull deepseek-r1:7b
```

### 3. Start everything (WSL2)

```bash
chmod +x start.sh
./start.sh
```

This script:
- Auto-detects the WSL2 host IP and updates `.env`
- Starts PostgreSQL + Redis via Docker Compose
- Starts the RPi4 simulator container
- Runs health checks on all services
- Starts the FastAPI server on port 8000

### 4. Verify

```bash
curl http://localhost:8000/health
# → {"status":"ok","redis":"ok","database":"ok"}

curl http://localhost:8080/health
# → {"status":"idle","device":"raspberry-pi-4",...}
```

### 5. Run a pipeline

```bash
curl -X POST http://localhost:8000/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_path": "firmware/v1.2.0.bin",
    "device_profile": "rpi4",
    "firmware_image": "ubuntu:22.04",
    "simulator_url": "http://localhost:8080"
  }'
```

Poll for result:
```bash
curl http://localhost:8000/pipeline/runs/{run_id}
```

View API docs:
```
http://localhost:8000/docs
```

View agent traces:
```
https://smith.langchain.com → project: ai-embedded-devops
```

### 6. Start the Desktop Control Plane

The Control Plane is a React dashboard that provides a real-time view of pipeline runs and a live terminal for AI agent logs.

```bash
cd desktop
npm install
npm run dev
```

Open `http://localhost:3001` (or the port Vite provides) in your Windows browser.

> **Note:** The desktop app communicates with the FastAPI backend. Ensure the `API_BASE` in `desktop/src/api.ts` matches your WSL2 host IP (e.g., `http://172.18.x.x:8000`).

### Environment Variables

```bash
# LangSmith tracing
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ai-embedded-devops

# Ollama (auto-updated by start.sh)
OLLAMA_BASE_URL=http://172.18.192.1:11434
OLLAMA_URL=http://172.18.192.1:11434

# PostgreSQL
POSTGRES_USER=devops
POSTGRES_PASSWORD=devops123
POSTGRES_DB=embedded_devops
DATABASE_URL=postgresql://devops:devops123@localhost:5432/embedded_devops

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
```

---

## Roadmap
### Future Extensions

| Item | Description | Effort |
|------|-------------|--------|
| QEMU Emulation | Replace Docker simulator with full ARM64 CPU emulation, boot real `.bin` firmware | 2–3 weeks |
| Additional simulators | Generic Sensor (ARM32/CoAP), Automotive ECU (CAN/SOME-IP) | 1 week each |
| Cloud deployment | Deploy API + DB to VPS, keep simulators local; add a provider adapter behind `llm_router.py` if moving away from Ollama | 1–2 days |
| Deployment Agent | GitOps manifest generation + ArgoCD sync on DEPLOY decision | 1 week |
| Prometheus + Grafana | Infrastructure metrics dashboard alongside Streamlit | 2–3 days |
| ArgoCD integration | Declarative K3s deployment triggered by Deployment Agent | 1 week |

### Cloud Readiness

The platform is architected for cloud migration with minimal code changes. `agents/llm_router.py` abstracts all LLM calls — switching from local Ollama to Groq API (free tier, 500 tokens/second) requires only setting `LLM_PROVIDER=groq` in `.env`. The simulator URL is a parameter, meaning swapping `http://localhost:8080` for a deployed container URL requires no code changes.

---

**Current implementation note:** `agents/llm_router.py` calls local Ollama directly. A Groq or other cloud provider adapter would need to be added before `LLM_PROVIDER=groq` becomes a working switch. Prometheus and Grafana are already provisioned by `docker-compose.yml`; the roadmap item refers to expanding dashboard coverage, not initial setup.

## Academic Context

This project was developed as part of a 12-week engineering capstone exploring the integration of:

- **Stateful AI orchestration** via LangGraph for DevOps automation
- **Software supply chain security** via SBOM generation and CVE correlation
- **Embedded systems simulation** as a substitute for physical hardware validation

Relevant standards addressed: UNECE R155 (automotive cybersecurity), ISO 21434 (vehicle cybersecurity risk management), CycloneDX SBOM format, CVSS v3.1 vulnerability scoring.

---

Made by Yasmin :)

