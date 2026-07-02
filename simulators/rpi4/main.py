from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import generate_latest, Counter, Gauge, Histogram, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time, random, asyncio

app = FastAPI(title="RPi4 Device Simulator")

# ── State ──────────────────────────────────────────────────────────────
state = {
    "status":     "idle",       # idle | booting | running | error
    "booted_at":  None,
    "boot_time":  None,
    "fault":      None,         # None | boot_loop | memory_full | network_loss
}

# ── Prometheus Metrics ─────────────────────────────────────────────────
cpu_gauge     = Gauge("device_cpu_percent",      "CPU usage percent")
ram_gauge     = Gauge("device_ram_used_mb",      "RAM used in MB")
uptime_gauge  = Gauge("device_uptime_seconds",   "Uptime in seconds")
boot_hist     = Histogram("device_boot_seconds", "Boot duration seconds")
test_counter  = Counter("device_tests_total",    "Tests run", ["test_name","result"])

# ── Models ─────────────────────────────────────────────────────────────
class TestRequest(BaseModel):
    test: str  # mqtt_connect | cpu_load | memory_check | network_ping | gpio_check

class FaultRequest(BaseModel):
    fault: str  # boot_loop | memory_full | network_loss | none

# ── Endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    uptime = round(time.time() - state["booted_at"], 1) if state["booted_at"] else 0
    uptime_gauge.set(uptime)
    return {
        "status":      state["status"],
        "device":      "raspberry-pi-4",
        "architecture":"ARM64",
        "ram_mb":      1024,
        "uptime_s":    uptime,
        "fault":       state["fault"],
    }

@app.post("/boot")
async def boot():
    if state["fault"] == "boot_loop":
        state["status"] = "error"
        raise HTTPException(status_code=500, detail="Boot loop detected — kernel panic")

    state["status"] = "booting"
    boot_duration = round(random.uniform(2.5, 4.0), 2)

    await asyncio.sleep(boot_duration)   # simulate real boot time

    state["status"]    = "running"
    state["booted_at"] = time.time()
    state["boot_time"] = boot_duration
    boot_hist.observe(boot_duration)

    return {
        "status":        "booted",
        "boot_time_s":   boot_duration,
        "kernel":        "6.1.0-rpi4-aarch64",
        "os":            "Raspberry Pi OS Lite (simulated)",
        "ip":            "192.168.1.101",
    }

@app.post("/run-test")
async def run_test(req: TestRequest):
    if state["status"] != "running":
        raise HTTPException(status_code=400, detail="Device not booted. Call /boot first.")

    test = req.test
    await asyncio.sleep(random.uniform(0.1, 0.5))

    # ── realistic network simulation ──────────────────────────────────
    def simulate_network():
        """Gaussian latency with jitter + packet loss"""
        latency   = max(1, round(random.gauss(mu=45, sigma=15), 1))
        packet_loss = random.random() < 0.02   # 2% packet loss
        degraded  = state["fault"] == "network_loss"
        if degraded:
            latency     = max(1, round(random.gauss(mu=400, sigma=80), 1))
            packet_loss = random.random() < 0.30
        return latency, packet_loss

    mqtt_latency, mqtt_loss   = simulate_network()
    ping_latency, ping_loss   = simulate_network()

    results = {
        "mqtt_connect": {
            "passed":     state["fault"] != "network_loss" and not mqtt_loss,
            "detail":     (
                f"MQTT connected — latency {mqtt_latency}ms"
                if state["fault"] != "network_loss" and not mqtt_loss
                else f"MQTT timeout — latency {mqtt_latency}ms, packet_loss=True"
            ),
            "latency_ms": mqtt_latency,
            "packet_loss": mqtt_loss,
            "broker":     "192.168.1.1:1883",
        },
        "cpu_load": {
            "passed":      True,
            "detail":      "CPU stable under load",
            "cpu_percent": round(random.uniform(15, 45), 1),
            "temp_celsius": round(random.uniform(42, 68), 1),
        },
        "memory_check": {
            "passed":   state["fault"] != "memory_full",
            "detail":   (
                "Memory within limits"
                if state["fault"] != "memory_full"
                else "Out of memory — OOM killer triggered"
            ),
            "used_mb":  950 if state["fault"] == "memory_full" else random.randint(300, 500),
            "total_mb": 1024,
            "swap_mb":  random.randint(0, 50),
        },
        "network_ping": {
            "passed":     not ping_loss and state["fault"] != "network_loss",
            "detail":     (
                f"Gateway reachable — {ping_latency}ms"
                if not ping_loss and state["fault"] != "network_loss"
                else f"Packet loss detected — latency {ping_latency}ms"
            ),
            "latency_ms":   ping_latency,
            "packet_loss":  ping_loss,
            "jitter_ms":    round(abs(random.gauss(0, 5)), 1),
            "gateway":      "192.168.1.1",
        },
        "gpio_check": {
            "passed":   True,
            "detail":   "GPIO pins responding",
            "pins_ok":  40,
            "voltage_v": round(random.uniform(3.28, 3.32), 3),
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

    if "cpu_percent" in result:
        cpu_gauge.set(result["cpu_percent"])
    if "used_mb" in result:
        ram_gauge.set(result["used_mb"])

    return {"test": test, **result}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/inject-fault")
def inject_fault(req: FaultRequest):
    state["fault"] = req.fault if req.fault != "none" else None
    return {"fault_injected": state["fault"]}

@app.post("/reset")
def reset():
    state["status"]    = "idle"
    state["booted_at"] = None
    state["boot_time"] = None
    state["fault"]     = None
    return {"status": "reset", "message": "Simulator ready for next test run"}
