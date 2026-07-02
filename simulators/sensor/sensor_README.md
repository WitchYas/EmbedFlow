# Generic Sensor Simulator — ARM32

> Containerized behavioral simulator for a constrained IoT sensor device (ARM32 Cortex-M4, 256MB RAM).  
> Models FreeRTOS behavior, CoAP/UDP protocol, battery management, and sensor calibration.

---

## Overview

This simulator represents a class of low-power, battery-operated IoT sensor nodes commonly deployed in industrial monitoring, smart building, and environmental sensing applications. Unlike the RPi4 simulator (DP1), this device runs a real-time operating system (FreeRTOS), communicates over CoAP/UDP instead of MQTT/TCP, and operates under strict memory and power constraints.

The Testing Agent uses the same REST interface contract as for DP1 — only the test names and response fields differ. This demonstrates the platform's extensibility: adding a new device type requires no changes to the agent layer, only a new simulator and YAML profile.

**Key differences from DP1 (RPi4):**

| Dimension | RPi4 (DP1) | Generic Sensor (DP2) |
|-----------|------------|----------------------|
| Architecture | ARM64 | ARM32 (Cortex-M4) |
| RAM | 1024 MB | 256 MB |
| OS | Raspberry Pi OS | FreeRTOS 10.4.3 |
| Protocol | MQTT / TCP | CoAP / UDP |
| Boot time | 2.5–4.0s | 1.3–2.5s |
| Network baseline loss | 2% (TCP) | 5% (UDP) |
| Power source | Mains | Battery |
| Unique failure modes | boot_loop | low_battery, sensor_drift |
| Memory unit | MB | KB |

---

## Device Profile

| Property | Value |
|----------|-------|
| Profile ID | DP2 |
| Architecture | ARM32 |
| CPU (simulated) | ARM Cortex-M4 @ 120MHz |
| RAM | 256 MB (262,144 KB) |
| Flash | 512 MB |
| OS (simulated) | FreeRTOS 10.4.3 |
| Primary protocol | CoAP over UDP |
| CoAP port | 5683 |
| HTTP API port | 8081 |
| Power | Battery |

---

## Quick Start

```bash
# Build
docker build -t sensor-sim .

# Run (note: port 8081 — different from RPi4 on 8080)
docker run -d -p 8081:8081 --name sensor-sim sensor-sim

# Verify
curl http://localhost:8081/health
```

Expected response:
```json
{
  "status": "idle",
  "device": "generic-sensor-arm32",
  "architecture": "ARM32",
  "cpu": "Cortex-M4 @ 120MHz",
  "ram_kb": 262144,
  "flash_kb": 524288,
  "uptime_s": 0,
  "battery_pct": 100.0,
  "sleep_cycles": 0,
  "fault": null,
  "protocol": "CoAP/UDP"
}
```

---

## API Reference

### `GET /health`

Returns current device status including battery level and sleep cycle count.

```bash
curl http://localhost:8081/health
```

```json
{
  "status": "running",
  "device": "generic-sensor-arm32",
  "architecture": "ARM32",
  "cpu": "Cortex-M4 @ 120MHz",
  "ram_kb": 262144,
  "uptime_s": 12.4,
  "battery_pct": 99.8,
  "sleep_cycles": 0,
  "fault": null,
  "protocol": "CoAP/UDP"
}
```

> **Note:** Battery drains at 0.001% per health check poll while running. This models real standby current draw.

---

### `POST /boot`

Simulates the three-phase FreeRTOS boot sequence. Significantly faster than RPi4 — RTOS devices have minimal userspace initialization.

```bash
curl -X POST http://localhost:8081/boot
```

```json
{
  "status": "booted",
  "boot_time_s": 1.87,
  "rtos": "FreeRTOS 10.4.3 (simulated)",
  "firmware": "sensor-fw-arm32-v2.1.0",
  "ip": "192.168.1.102",
  "mac": "AA:BB:CC:DD:EE:02"
}
```

**Three boot phases:**
1. Bootloader + firmware checksum verification (0.2–0.4s)
2. RTOS kernel init + peripheral setup (0.8–1.5s)
3. Sensor self-calibration on startup (0.3–0.6s)

**Failure mode:** If `low_battery` fault is active and battery < 10%, returns HTTP 500:
```json
{ "detail": "Boot failed — battery critically low (5.3%)" }
```

---

### `POST /run-test`

Executes a named test. Device must be booted. All 5 tests should pass on a healthy device.

```bash
curl -X POST http://localhost:8081/run-test \
  -H "Content-Type: application/json" \
  -d '{"test": "coap_publish"}'
```

#### Available Tests

**`coap_publish`** — Tests CoAP/UDP message delivery to the server.

```json
{
  "test": "coap_publish",
  "passed": true,
  "detail": "CoAP publish OK — 11.4ms (UDP)",
  "latency_ms": 11.4,
  "packet_loss": false,
  "protocol": "CoAP/UDP",
  "server": "coap://192.168.1.1:5683",
  "method": "PUT",
  "path": "/sensors/temperature"
}
```

CoAP/UDP network model:
- Normal: `latency ~ N(μ=12ms, σ=5ms)`, 5% baseline loss
- Under `coap_timeout` fault: `latency ~ N(μ=2000ms, σ=300ms)`, 60% loss

> **Why CoAP is faster than MQTT:** CoAP operates over UDP with no handshake. Latency is lower but reliability is reduced — this is the fundamental IoT protocol tradeoff.

---

**`low_power_mode`** — Verifies sleep/wake cycle functionality. Critical for battery life.

```json
{
  "test": "low_power_mode",
  "passed": true,
  "detail": "Sleep cycle OK — woke in 98ms",
  "sleep_ms": 98,
  "wake_current_ma": 1.1,
  "sleep_current_ua": 11.3,
  "battery_pct": 99.8
}
```

Current draw values reflect real Cortex-M4 low-power specifications:
- Active: ~1.0–1.2mA
- Sleep (deep sleep): 8–15μA

Fails if battery < 5%: device cannot safely enter sleep cycle.

---

**`sensor_reading`** — Validates temperature and humidity readings are within calibration bounds.

```json
{
  "test": "sensor_reading",
  "passed": true,
  "detail": "Sensor nominal — temp 23.52°C, humidity 58.2%",
  "temperature_c": 23.52,
  "humidity_pct": 58.2,
  "temp_in_bounds": true,
  "hum_in_bounds": true,
  "calibration_ok": true
}
```

Normal noise model:
- Temperature: `N(μ=23.5°C, σ=0.1°C)` — realistic sensor noise
- Humidity: `N(μ=58.0%, σ=0.3%)`

Under `sensor_drift` fault:
```json
{
  "passed": false,
  "detail": "Sensor drift detected — temp 31.7°C (expected ~23.5°C)",
  "temperature_c": 31.7,
  "calibration_ok": false
}
```

Drift is modeled as a Gaussian offset: `drift ~ N(μ=8.0°C, σ=2.0°C)`.

---

**`memory_check`** — Verifies heap usage is within operational bounds. Reported in KB for constrained device accuracy.

```json
{
  "test": "memory_check",
  "passed": true,
  "detail": "Memory OK — 65432KB / 262144KB (24.9%)",
  "used_kb": 65432,
  "total_kb": 262144,
  "usage_pct": 24.9,
  "heap_free_kb": 196712
}
```

Typical FreeRTOS footprint: 40,000–80,000 KB (kernel + tasks + buffers).

Under `memory_full` fault: `used_kb = 250000` (95.4% usage), passes `false`.

---

**`watchdog_check`** — Verifies the hardware watchdog timer is being serviced correctly.

```json
{
  "test": "watchdog_check",
  "passed": true,
  "detail": "Watchdog responsive — last kick 450ms ago",
  "last_kick_ms": 450,
  "timeout_ms": 5000,
  "resets_since_boot": 0
}
```

> **What is a watchdog?** A hardware timer that resets the device if the main loop hangs. If the firmware stops kicking the watchdog within 5000ms, the device reboots automatically. This test verifies the RTOS task scheduler is running correctly. There is no equivalent test for the RPi4 — this is specific to embedded RTOS devices.

Always passes (hardware watchdog is always responsive in normal operation). A real implementation would fail if `last_kick_ms > timeout_ms`.

---

### `GET /metrics`

Prometheus metrics in exposition format. Note: RAM reported in KB, not MB.

```bash
curl http://localhost:8081/metrics
```

```
# HELP sensor_cpu_percent CPU usage percent
sensor_cpu_percent 0.0

# HELP sensor_ram_used_kb RAM used in KB
sensor_ram_used_kb 65432.0

# HELP sensor_uptime_seconds Uptime in seconds
sensor_uptime_seconds 12.4

# HELP sensor_battery_percent Battery level percent
sensor_battery_percent 99.8

# HELP sensor_boot_seconds Boot duration seconds
sensor_boot_seconds_count 1
sensor_boot_seconds_sum 1.87

# HELP sensor_tests_total Tests run
sensor_tests_total{test_name="coap_publish",result="pass"} 1.0
```

---

### `POST /inject-fault`

Injects a fault. The `low_battery` fault also immediately drops battery level to 3–8%.

```bash
curl -X POST http://localhost:8081/inject-fault \
  -H "Content-Type: application/json" \
  -d '{"fault": "low_battery"}'
```

```json
{
  "fault_injected": "low_battery",
  "battery_pct": 5.3
}
```

#### Available Faults

| Fault | Affected Tests | Behavior |
|-------|---------------|----------|
| `coap_timeout` | `coap_publish` | Latency ~2000ms, 60% packet loss |
| `memory_full` | `memory_check` | RAM at 250,000KB (95%), OOM message |
| `low_battery` | `low_power_mode`, `/boot` | Battery drops to 3–8%, boot fails if < 10% |
| `sensor_drift` | `sensor_reading` | Temperature drifts ~8°C from true value |
| `none` | All | Clears fault, restores normal behavior |

To clear any fault:
```bash
curl -X POST http://localhost:8081/inject-fault \
  -H "Content-Type: application/json" \
  -d '{"fault": "none"}'
```

---

### `POST /reset`

Resets all state including battery level back to 100%.

```bash
curl -X POST http://localhost:8081/reset
```

```json
{
  "status": "reset",
  "message": "Sensor simulator ready"
}
```

---

## Full Test Sequence

```bash
# 1. Reset
curl -X POST http://localhost:8081/reset

# 2. Boot
curl -X POST http://localhost:8081/boot

# 3. Run all tests
for test in coap_publish low_power_mode sensor_reading memory_check watchdog_check; do
  echo "--- $test ---"
  curl -s -X POST http://localhost:8081/run-test \
    -H "Content-Type: application/json" \
    -d "{\"test\": \"$test\"}" | python3 -m json.tool
done

# 4. Inject sensor drift and observe
curl -X POST http://localhost:8081/inject-fault \
  -H "Content-Type: application/json" \
  -d '{"fault": "sensor_drift"}'

curl -X POST http://localhost:8081/run-test \
  -H "Content-Type: application/json" \
  -d '{"test": "sensor_reading"}'

# 5. Inject low battery
curl -X POST http://localhost:8081/inject-fault \
  -H "Content-Type: application/json" \
  -d '{"fault": "low_battery"}'

curl -X POST http://localhost:8081/run-test \
  -H "Content-Type: application/json" \
  -d '{"test": "low_power_mode"}'

# 6. Reset
curl -X POST http://localhost:8081/reset
```

---

## State Machine

```
idle
 │
 │  POST /boot  (battery >= 10% OR no low_battery fault)
 ▼
booting ── Phase 1: bootloader (0.2–0.4s)
         ── Phase 2: RTOS init  (0.8–1.5s)
         ── Phase 3: calibration (0.3–0.6s)
         ──────────────────────────────────▶  running
                                                │
                                                │  POST /run-test
                                                │  GET /metrics
                                                │  POST /inject-fault
                                                │
                                                │  POST /reset
                                                ▼
                                              idle

booting ── low_battery fault + battery < 10% ──▶  error
                                                     │
                                                     │  POST /reset
                                                     ▼
                                                   idle
```

---

## Network Simulation Model

CoAP/UDP has fundamentally different network characteristics from MQTT/TCP:

```
CoAP/UDP (this device):
  Normal:   latency ~ N(μ=12ms,   σ=5ms)    P(loss) = 0.05
  Degraded: latency ~ N(μ=2000ms, σ=300ms)  P(loss) = 0.60

MQTT/TCP (RPi4 DP1):
  Normal:   latency ~ N(μ=45ms,   σ=15ms)   P(loss) = 0.02
  Degraded: latency ~ N(μ=400ms,  σ=80ms)   P(loss) = 0.30
```

Key insight: CoAP is faster under normal conditions (no TCP handshake) but degrades more severely under poor network conditions (no retransmission guarantees at transport layer).

---

## Sensor Drift Model

Real sensors experience calibration drift over time due to temperature, humidity, and aging effects. The `sensor_drift` fault models this:

```
Normal:  temp = 23.5 + N(0, 0.1)     within ±1°C of true value
Drift:   temp = 23.5 + N(8.0, 2.0)   shifted ~8°C from true value
```

A drift of 8°C represents a severely miscalibrated sensor — detectable and actionable. In production, this would trigger a recalibration workflow.

---

## Relation to DP1 (RPi4)

Both simulators implement identical HTTP endpoints (`/health`, `/boot`, `/run-test`, `/metrics`, `/inject-fault`, `/reset`). The Testing Agent uses the same LangGraph workflow for both. What differs is:

- The test names (`coap_publish` vs `mqtt_connect`)
- The metric units (KB vs MB)
- The protocol behavior (UDP vs TCP)
- The fault taxonomy (sensor_drift vs boot_loop)
- The YAML device profile

To run a pipeline against this simulator instead of RPi4:

```bash
curl -X POST http://localhost:8000/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_version": "v2.0.0",
    "device_profile": "sensor",
    "simulator_url": "http://localhost:8081",
    "firmware_image": "ubuntu:22.04"
  }'
```

---

## Files

```
simulators/sensor/
├── main.py            FastAPI simulator application
├── Dockerfile         Container definition
├── requirements.txt   Python dependencies
└── README.md          This file
```

See also: `device_profiles/sensor.yaml` for the full device profile schema.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.110.0 | HTTP framework |
| uvicorn | 0.29.0 | ASGI server |
| pydantic | 2.6.0 | Request validation |
| prometheus-client | 0.20.0 | Metrics export |
