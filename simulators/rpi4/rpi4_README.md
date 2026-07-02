# RPi4 Device Simulator

> Containerized behavioral simulator for Raspberry Pi 4 (ARM64, 1GB RAM).  
> Exposes a standardized REST interface consumed by the AI Testing Agent.

---

## Overview

This simulator replicates the observable behavior of a Raspberry Pi 4 running Raspberry Pi OS Lite. It does not emulate the ARM64 CPU at the instruction level — instead it models the device's **external interface**: boot sequences, test outcomes, protocol behavior, and failure modes.

The Testing Agent interacts with this simulator over HTTP using the exact same interface it would use against a QEMU-based or physical RPi4. Swapping this simulator for a real device requires only changing `SIMULATOR_URL` in the environment — no agent code changes.

**Why this matters:** The platform's intelligence layer (agents, decisions, tracing) is decoupled from the simulation layer by design. This simulator is the default backend for local development and CI/CD pipelines.

---

## Device Profile

| Property | Value |
|----------|-------|
| Profile ID | DP1 |
| Architecture | ARM64 |
| CPU (simulated) | Broadcom BCM2711, Cortex-A72 |
| RAM | 1024 MB |
| OS (simulated) | Raspberry Pi OS Lite |
| Kernel | 6.1.0-rpi4-aarch64 |
| Primary protocol | MQTT over TCP |
| Port | 8080 |
| Power | Mains |

---

## Quick Start

```bash
# Build
docker build -t rpi4-sim .

# Run
docker run -d -p 8080:8080 --name rpi4-sim rpi4-sim

# Verify
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "idle",
  "device": "raspberry-pi-4",
  "architecture": "ARM64",
  "ram_mb": 1024,
  "uptime_s": 0,
  "fault": null
}
```

---

## API Reference

### `GET /health`

Returns current device status.

```bash
curl http://localhost:8080/health
```

```json
{
  "status": "running",
  "device": "raspberry-pi-4",
  "architecture": "ARM64",
  "ram_mb": 1024,
  "uptime_s": 45.2,
  "fault": null
}
```

**Status values:** `idle` | `booting` | `running` | `error`

---

### `POST /boot`

Simulates the RPi4 boot sequence. Takes 2.5–4.0 seconds (realistic boot timing based on Raspberry Pi OS cold boot benchmarks).

```bash
curl -X POST http://localhost:8080/boot
```

```json
{
  "status": "booted",
  "boot_time_s": 3.21,
  "kernel": "6.1.0-rpi4-aarch64",
  "os": "Raspberry Pi OS Lite (simulated)",
  "ip": "192.168.1.101"
}
```

**Failure mode:** If `boot_loop` fault is active, returns HTTP 500:
```json
{ "detail": "Boot loop detected — kernel panic" }
```

---

### `POST /run-test`

Executes a named test suite. Device must be booted before calling this endpoint.

```bash
curl -X POST http://localhost:8080/run-test \
  -H "Content-Type: application/json" \
  -d '{"test": "mqtt_connect"}'
```

#### Available Tests

**`mqtt_connect`** — Tests MQTT broker connectivity over TCP.

```json
{
  "test": "mqtt_connect",
  "passed": true,
  "detail": "MQTT connected — latency 42.3ms",
  "latency_ms": 42.3,
  "packet_loss": false,
  "broker": "192.168.1.1:1883"
}
```

Network behavior uses Gaussian distribution: `latency ~ N(μ=45ms, σ=15ms)`.  
Baseline packet loss: 2%. Under `network_loss` fault: latency `N(μ=400ms, σ=80ms)`, 30% loss.

---

**`cpu_load`** — Stress-tests CPU and measures load and temperature.

```json
{
  "test": "cpu_load",
  "passed": true,
  "detail": "CPU stable under load",
  "cpu_percent": 26.4,
  "temp_celsius": 54.7
}
```

CPU: `uniform(15%, 45%)`. Temperature: `uniform(42°C, 68°C)` — within RPi4 thermal envelope.

---

**`memory_check`** — Verifies RAM usage is within operational bounds.

```json
{
  "test": "memory_check",
  "passed": true,
  "detail": "Memory within limits",
  "used_mb": 372,
  "total_mb": 1024,
  "swap_mb": 12
}
```

Under `memory_full` fault: `used_mb = 950`, `detail = "Out of memory — OOM killer triggered"`.

---

**`network_ping`** — Tests gateway reachability with jitter measurement.

```json
{
  "test": "network_ping",
  "passed": true,
  "detail": "Gateway reachable — 43ms",
  "latency_ms": 43,
  "packet_loss": false,
  "jitter_ms": 3.2,
  "gateway": "192.168.1.1"
}
```

---

**`gpio_check`** — Verifies GPIO pin bus and operating voltage.

```json
{
  "test": "gpio_check",
  "passed": true,
  "detail": "GPIO pins responding",
  "pins_ok": 40,
  "voltage_v": 3.301
}
```

Voltage range: `uniform(3.28V, 3.32V)` — matches the RPi4 3.3V GPIO specification.

---

### `GET /metrics`

Returns device telemetry in Prometheus exposition format. Scraped by Prometheus every 15 seconds.

```bash
curl http://localhost:8080/metrics
```

```
# HELP device_cpu_percent CPU usage percent
device_cpu_percent 26.4

# HELP device_ram_used_mb RAM used in MB
device_ram_used_mb 372.0

# HELP device_uptime_seconds Uptime in seconds
device_uptime_seconds 45.2

# HELP device_boot_seconds Boot duration seconds
device_boot_seconds_count 1
device_boot_seconds_sum 3.21

# HELP device_tests_total Tests run
device_tests_total{test_name="mqtt_connect",result="pass"} 3.0
device_tests_total{test_name="cpu_load",result="pass"} 3.0
```

---

### `POST /inject-fault`

Injects a fault into the simulator state. Subsequent test calls will reflect the fault until reset.

```bash
curl -X POST http://localhost:8080/inject-fault \
  -H "Content-Type: application/json" \
  -d '{"fault": "network_loss"}'
```

```json
{ "fault_injected": "network_loss" }
```

#### Available Faults

| Fault | Effect |
|-------|--------|
| `network_loss` | MQTT latency spikes to ~400ms, 30% packet loss, `mqtt_connect` and `network_ping` fail |
| `memory_full` | RAM usage set to 950MB/1024MB, `memory_check` fails with OOM message |
| `boot_loop` | `/boot` returns HTTP 500 with kernel panic message |
| `none` | Clears any active fault, returns to normal behavior |

To clear: `{"fault": "none"}`

---

### `POST /reset`

Resets all simulator state to initial idle condition. Called automatically by the Testing Agent before each pipeline run.

```bash
curl -X POST http://localhost:8080/reset
```

```json
{
  "status": "reset",
  "message": "Simulator ready for next test run"
}
```

---

## Full Test Sequence

```bash
# 1. Reset to clean state
curl -X POST http://localhost:8080/reset

# 2. Boot the device
curl -X POST http://localhost:8080/boot

# 3. Run all tests
for test in mqtt_connect cpu_load memory_check network_ping gpio_check; do
  echo "Running $test..."
  curl -s -X POST http://localhost:8080/run-test \
    -H "Content-Type: application/json" \
    -d "{\"test\": \"$test\"}" | python3 -m json.tool
done

# 4. Test fault injection
curl -X POST http://localhost:8080/inject-fault -H "Content-Type: application/json" -d '{"fault": "network_loss"}'
curl -X POST http://localhost:8080/run-test -H "Content-Type: application/json" -d '{"test": "mqtt_connect"}'

# 5. Clean up
curl -X POST http://localhost:8080/reset
```

---

## State Machine

```
idle
 │
 │  POST /boot (no boot_loop fault)
 ▼
booting  ──── 2.5 to 4.0 seconds ────▶  running
                                            │
                                            │  POST /run-test
                                            │  GET /metrics
                                            │  POST /inject-fault
                                            │
                                            │  POST /reset
                                            ▼
                                          idle

booting  ──── boot_loop fault active ──▶  error
                                            │
                                            │  POST /reset
                                            ▼
                                          idle
```

---

## Network Simulation Model

The simulator uses statistically realistic network models rather than binary pass/fail:

```
Normal conditions:
  latency    ~ N(μ=45ms, σ=15ms)     Gaussian with natural jitter
  packet_loss  P = 0.02              2% baseline (IoT edge network)

Under network_loss fault:
  latency    ~ N(μ=400ms, σ=80ms)   Degraded link simulation
  packet_loss  P = 0.30             30% loss (congested/failing link)
```

This model reflects real-world IoT network behavior as documented in IEEE 802.11 edge deployment studies.

---

## Substitution with Real Hardware

This simulator implements the same interface contract as a physical RPi4 with the test harness installed. To switch from simulator to real hardware:

```bash
# .env
SIMULATOR_URL=http://192.168.1.101:8080   # real device IP
```

No agent code changes required. The Testing Agent is hardware-agnostic by design.

For QEMU-based emulation, see the `simulators/qemu-rpi4/` directory (planned extension).

---

## Files

```
simulators/rpi4/
├── main.py            FastAPI simulator application
├── Dockerfile         Container definition
├── requirements.txt   Python dependencies
└── README.md          This file
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.110.0 | HTTP framework |
| uvicorn | 0.29.0 | ASGI server |
| pydantic | 2.6.0 | Request validation |
| prometheus-client | 0.20.0 | Metrics export |
