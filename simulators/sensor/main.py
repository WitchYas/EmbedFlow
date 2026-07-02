from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import generate_latest, Counter, Gauge, Histogram, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time, random, asyncio, math

app = FastAPI(title="Generic Sensor Simulator — ARM32")

# ── State ──────────────────────────────────────────────────────────────
state = {
    "status":        "idle",
    "booted_at":     None,
    "boot_time":     None,
    "fault":         None,       # None | coap_timeout | memory_full | low_battery | sensor_drift
    "battery_pct":   100.0,
    "sleep_cycles":  0,
}

# ── Prometheus Metrics ─────────────────────────────────────────────────
cpu_gauge     = Gauge("sensor_cpu_percent",      "CPU usage percent")
ram_gauge     = Gauge("sensor_ram_used_kb",      "RAM used in KB")   # KB not MB — constrained device
uptime_gauge  = Gauge("sensor_uptime_seconds",   "Uptime in seconds")
battery_gauge = Gauge("sensor_battery_percent",  "Battery level percent")
boot_hist     = Histogram("sensor_boot_seconds", "Boot duration seconds")
test_counter  = Counter("sensor_tests_total",    "Tests run", ["test_name","result"])

# ── Key difference from RPi4 ───────────────────────────────────────────
# This device runs FreeRTOS-style low-power cycles
# RAM is in KB not MB — 256MB total = 262144 KB
# CoAP over UDP — not MQTT over TCP
# Battery powered — battery drain is a test dimension
# Sensor readings drift over time — needs calibration check

class TestRequest(BaseModel):
    test: str  # coap_publish | low_power_mode | sensor_reading | memory_check | watchdog_check

class FaultRequest(BaseModel):
    fault: str  # coap_timeout | memory_full | low_battery | sensor_drift | none

# ── Endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    uptime = round(time.time() - state["booted_at"], 1) if state["booted_at"] else 0
    uptime_gauge.set(uptime)
    battery_gauge.set(state["battery_pct"])

    # battery drains slowly while running
    if state["status"] == "running":
        state["battery_pct"] = max(0.0, state["battery_pct"] - 0.001)

    return {
        "status":        state["status"],
        "device":        "generic-sensor-arm32",
        "architecture":  "ARM32",
        "cpu":           "Cortex-M4 @ 120MHz",
        "ram_kb":        262144,             # 256MB in KB
        "flash_kb":      524288,             # 512MB flash
        "uptime_s":      uptime,
        "battery_pct":   round(state["battery_pct"], 1),
        "sleep_cycles":  state["sleep_cycles"],
        "fault":         state["fault"],
        "protocol":      "CoAP/UDP",
    }

@app.post("/boot")
async def boot():
    # ARM32 Cortex-M4 boots faster than ARM64 RPi4
    # but has a longer firmware validation step (checksum)
    if state["fault"] == "low_battery" and state["battery_pct"] < 10:
        state["status"] = "error"
        raise HTTPException(
            status_code=500,
            detail=f"Boot failed — battery critically low ({state['battery_pct']:.1f}%)"
        )

    state["status"] = "booting"

    # Phase 1 — bootloader + firmware checksum (fast, ~0.3s)
    await asyncio.sleep(round(random.uniform(0.2, 0.4), 2))

    # Phase 2 — RTOS init + peripheral setup (slower)
    await asyncio.sleep(round(random.uniform(0.8, 1.5), 2))

    # Phase 3 — sensor calibration on startup
    await asyncio.sleep(round(random.uniform(0.3, 0.6), 2))

    boot_duration = round(random.uniform(1.3, 2.5), 2)   # much faster than RPi4
    boot_hist.observe(boot_duration)

    state["status"]    = "running"
    state["booted_at"] = time.time()
    state["boot_time"] = boot_duration

    return {
        "status":       "booted",
        "boot_time_s":  boot_duration,
        "rtos":         "FreeRTOS 10.4.3 (simulated)",
        "firmware":     "sensor-fw-arm32-v2.1.0",
        "ip":           "192.168.1.102",
        "mac":          "AA:BB:CC:DD:EE:02",
    }

@app.post("/run-test")
async def run_test(req: TestRequest):
    if state["status"] != "running":
        raise HTTPException(status_code=400, detail="Device not booted. Call /boot first.")

    test = req.test
    await asyncio.sleep(random.uniform(0.05, 0.2))   # faster than RPi4 — simpler tests

    # ── CoAP network simulation ────────────────────────────────────────
    # CoAP uses UDP — very different from TCP/MQTT
    # Key difference: no connection state, higher natural loss rate
    def simulate_coap():
        """CoAP/UDP has higher baseline loss than TCP/MQTT"""
        base_latency = max(1, round(random.gauss(mu=12, sigma=5), 1))  # CoAP is faster than MQTT
        # UDP has higher natural packet loss than TCP
        packet_loss  = random.random() < 0.05   # 5% baseline (vs 2% for MQTT/TCP)
        degraded     = state["fault"] == "coap_timeout"
        if degraded:
            base_latency = max(1, round(random.gauss(mu=2000, sigma=300), 1))
            packet_loss  = random.random() < 0.60
        return base_latency, packet_loss

    # ── Sensor reading simulation ──────────────────────────────────────
    # Simulates a temperature + humidity sensor with drift
    def simulate_sensor_reading():
        base_temp = 23.5
        base_hum  = 58.0
        if state["fault"] == "sensor_drift":
            # drift = reading shifts gradually from true value
            drift = random.gauss(mu=8.0, sigma=2.0)
            return base_temp + drift, base_hum + drift * 0.5
        # normal noise — all real sensors have this
        return (
            round(base_temp + random.gauss(0, 0.1), 2),
            round(base_hum  + random.gauss(0, 0.3), 2),
        )

    coap_latency, coap_loss = simulate_coap()
    temp, humidity          = simulate_sensor_reading()

    # ── RAM in KB — constrained device ────────────────────────────────
    total_ram_kb  = 262144
    used_ram_kb   = (
        250000 if state["fault"] == "memory_full"
        else random.randint(40000, 80000)   # typical RTOS footprint: 40-80MB
    )
    ram_pct = round(used_ram_kb / total_ram_kb * 100, 1)

    results = {
        "coap_publish": {
            "passed":      not coap_loss and state["fault"] != "coap_timeout",
            "detail":      (
                f"CoAP publish OK — {coap_latency}ms (UDP)"
                if not coap_loss and state["fault"] != "coap_timeout"
                else f"CoAP timeout — {coap_latency}ms, packet_loss={coap_loss}"
            ),
            "latency_ms":  coap_latency,
            "packet_loss": coap_loss,
            "protocol":    "CoAP/UDP",
            "server":      "coap://192.168.1.1:5683",
            "method":      "PUT",
            "path":        "/sensors/temperature",
        },
        "low_power_mode": {
            # Tests that device can enter/exit sleep cycle correctly
            # Critical for battery-powered devices
            "passed":        state["battery_pct"] > 5.0,
            "detail":        (
                f"Sleep cycle OK — woke in {random.randint(95, 105)}ms"
                if state["battery_pct"] > 5.0
                else "Cannot enter sleep — battery critically low"
            ),
            "sleep_ms":      random.randint(95, 105),
            "wake_current_ma": round(random.uniform(0.8, 1.2), 2),
            "sleep_current_ua": round(random.uniform(8, 15), 1),   # microamps during sleep
            "battery_pct":   round(state["battery_pct"], 1),
        },
        "sensor_reading": {
            # Validates sensor readings are within calibration bounds
            "passed":        state["fault"] != "sensor_drift",
            "detail":        (
                f"Sensor nominal — temp {temp}°C, humidity {humidity}%"
                if state["fault"] != "sensor_drift"
                else f"Sensor drift detected — temp {temp}°C (expected ~23.5°C)"
            ),
            "temperature_c": temp,
            "humidity_pct":  humidity,
            "temp_in_bounds": abs(temp - 23.5) < 1.0,
            "hum_in_bounds":  abs(humidity - 58.0) < 5.0,
            "calibration_ok": state["fault"] != "sensor_drift",
        },
        "memory_check": {
            "passed":      state["fault"] != "memory_full",
            "detail":      (
                f"Memory OK — {used_ram_kb}KB / {total_ram_kb}KB ({ram_pct}%)"
                if state["fault"] != "memory_full"
                else f"Memory critical — {used_ram_kb}KB / {total_ram_kb}KB ({ram_pct}%)"
            ),
            "used_kb":     used_ram_kb,
            "total_kb":    total_ram_kb,
            "usage_pct":   ram_pct,
            "heap_free_kb": total_ram_kb - used_ram_kb,
        },
        "watchdog_check": {
            # Watchdog timer — critical for embedded devices
            # If main loop hangs, watchdog resets the device
            "passed":           True,
            "detail":           "Watchdog responsive — last kick 450ms ago",
            "last_kick_ms":     random.randint(400, 500),
            "timeout_ms":       5000,
            "resets_since_boot": random.randint(0, 2),
        },
    }

    if test not in results:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown test '{test}'. Available: {list(results.keys())}"
        )

    result = results[test]
    label  = "pass" if result["passed"] else "fail"
    test_counter.labels(test_name=test, result=label).inc()

    if "cpu_pct" in result:
        cpu_gauge.set(result["cpu_pct"])

    ram_gauge.set(used_ram_kb)

    return {"test": test, **result}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/inject-fault")
def inject_fault(req: FaultRequest):
    state["fault"] = req.fault if req.fault != "none" else None

    # low_battery fault also drops battery level immediately
    if req.fault == "low_battery":
        state["battery_pct"] = round(random.uniform(3.0, 8.0), 1)

    return {
        "fault_injected": state["fault"],
        "battery_pct":    state["battery_pct"],
    }

@app.post("/reset")
def reset():
    state["status"]       = "idle"
    state["booted_at"]    = None
    state["boot_time"]    = None
    state["fault"]        = None
    state["battery_pct"]  = 100.0
    state["sleep_cycles"] = 0
    return {"status": "reset", "message": "Sensor simulator ready"}
