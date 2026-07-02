import httpx
import time
try:
    from api.ws_logger import ws_log
except ImportError:
    def ws_log(msg, agent="system", level="info"): pass
from langgraph.graph import StateGraph, END
from agents.state import AgentState, TestReport, TestResult

# tests to run on every device
TESTS = [
    "mqtt_connect",
    "cpu_load",
    "memory_check",
    "network_ping",
    "gpio_check",
]

# these tests failing hurts confidence more than others
CRITICAL_TESTS = ["mqtt_connect", "memory_check"]


# ── NODE 1 ─────────────────────────────────────────────────────────────
def boot_device(state: AgentState) -> dict:
    print(f"\n[Testing Agent] ▶ Booting {state.device_profile} simulator...")

    try:
       

        # boot the device
        response = httpx.post(f"{state.simulator_url}/boot", timeout=30)
        response.raise_for_status()

        data = response.json()
        print(f"[Testing Agent] Boot successful — {data['boot_time_s']}s")
        ws_log(f"Boot successful — {data['boot_time_s']}s", "testing_agent")
        return {"error": None}

    except Exception as e:
        print(f"[Testing Agent] Boot failed — {e}")
        ws_log(f"Boot failed: {e}", "testing_agent", "error")
        return {"error": f"Boot failed: {str(e)}"}


# ── NODE 2 ─────────────────────────────────────────────────────────────
def run_tests(state: AgentState) -> dict:
    print(f"\n[Testing Agent] ▶ Running {len(TESTS)} tests...")
    results = []

    for test_name in TESTS:
        try:
            start    = time.time()
            response = httpx.post(
                f"{state.simulator_url}/run-test",
                json={"test": test_name},
                timeout=15,
            )
            duration_ms = int((time.time() - start) * 1000)
            data        = response.json()

            # separate known fields from extra metrics
            result = TestResult(
                test_name   = test_name,
                passed      = data.get("passed", False),
                detail      = data.get("detail", ""),
                duration_ms = duration_ms,
                metrics     = {
                    k: v for k, v in data.items()
                    if k not in ["test", "passed", "detail"]
                },
            )

            icon = "PASS" if result.passed else "FAIL"
            print(f"  {icon} {test_name}: {result.detail}")
            ws_log(f"{icon} {test_name}: {result.detail}", "testing_agent", "info" if result.passed else "warning")
            results.append(result)

        except Exception as e:
            print(f"  FAIL {test_name}: ERROR — {e}")
            results.append(TestResult(
                test_name = test_name,
                passed    = False,
                detail    = f"Exception: {str(e)}",
            ))

    return {"test_results": results}


# ── NODE 3 ─────────────────────────────────────────────────────────────
def build_report(state: AgentState) -> dict:
    print(f"\n[Testing Agent] ▶ Building report...")

    # boot failed — return immediately with confidence 0
    if state.error:
        report = TestReport(
            device_profile   = state.device_profile,
            firmware_version = state.firmware_version,
            boot_success     = False,
            tests_run        = 0,
            tests_passed     = 0,
            tests_failed     = 0,
            results          = [],
            confidence       = 0.0,
            summary          = f"Boot failed: {state.error}",
        )
        return {"test_report": report}

    results      = state.test_results
    total        = len(results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = total - passed_count
    ratio        = passed_count / total if total > 0 else 0

    # ── base confidence from pass ratio ────────────────────────────────
    if ratio == 1.0:
        confidence = 0.95
    elif ratio >= 0.8:
        confidence = 0.80
    elif ratio >= 0.6:
        confidence = 0.65
    elif ratio >= 0.4:
        confidence = 0.50
    else:
        confidence = 0.30

    # ── penalty for critical test failures ─────────────────────────────
    for r in results:
        if r.test_name in CRITICAL_TESTS and not r.passed:
            confidence -= 0.10
            print(f"  Confidence penalized: {r.test_name} is critical")

    confidence = round(max(0.0, min(1.0, confidence)), 2)

    # ── human readable summary ─────────────────────────────────────────
    critical_ok = all(
        r.passed for r in results if r.test_name in CRITICAL_TESTS
    )
    summary = (
        f"{passed_count}/{total} tests passed. "
        f"Confidence: {confidence}. "
        f"{'All critical tests passed.' if critical_ok else 'Critical test failures detected.'}"
    )

    report = TestReport(
        device_profile   = state.device_profile,
        firmware_version = state.firmware_version,
        boot_success     = True,
        tests_run        = total,
        tests_passed     = passed_count,
        tests_failed     = failed_count,
        results          = results,
        confidence       = confidence,
        summary          = summary,
    )

    print(f"\n[Testing Agent] ══ REPORT ══════════════════════")
    print(f"  Tests      : {passed_count}/{total} passed")
    print(f"  Confidence : {confidence}")
    print(f"  Summary    : {summary}")
    print(f"[Testing Agent] ════════════════════════════════\n")

    return {"test_report": report}


# ── ROUTING — skip tests if boot failed ────────────────────────────────
def route_after_boot(state: AgentState) -> str:
    if state.error:
        return "build_report"
    return "run_tests"


# ── BUILD THE GRAPH ────────────────────────────────────────────────────
def build_testing_agent():
    graph = StateGraph(AgentState)

    graph.add_node("boot_device",  boot_device)
    graph.add_node("run_tests",    run_tests)
    graph.add_node("build_report", build_report)

    graph.set_entry_point("boot_device")
    graph.add_conditional_edges("boot_device", route_after_boot)
    graph.add_edge("run_tests",    "build_report")
    graph.add_edge("build_report", END)

    return graph.compile()


def run_testing_agent(
    firmware_version: str = "v1.0.0",
    device_profile:   str = "rpi4",
    simulator_url:    str = "http://localhost:8080",
) -> TestReport:
    from langsmith import traceable

    agent = build_testing_agent()

    result = agent.invoke(
        AgentState(
            firmware_version = firmware_version,
            device_profile   = device_profile,
            simulator_url    = simulator_url,
        ),
        config={
            "run_name": f"testing-agent-{firmware_version}",
            "tags":     ["testing", device_profile, firmware_version],
            "metadata": {
                "firmware_version": firmware_version,
                "device_profile":   device_profile,
                "simulator_url":    simulator_url,
            }
        }
    )
    return result["test_report"]
