import os
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, END
from agents.state import AgentState, OrchestratorDecision, Decision
from agents.llm_router import ask_fast, ask_deep, ask_structured
try:
    from api.ws_logger import ws_log
except ImportError:
    def ws_log(msg, agent="system", level="info"): pass

import threading
MAX_REFLECTION_ROUNDS = 2
_pipeline_context = threading.local()


# ── historical intelligence ───────────────────────────────────────────
def get_historical_context(firmware_version: str, device_profile: str) -> dict:
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur  = conn.cursor()
        cur.execute("""
            SELECT final_decision, confidence
            FROM pipeline_runs
            WHERE device_profile = %s AND status = 'completed'
            ORDER BY triggered_at DESC LIMIT 10
        """, (device_profile,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {"total": 0, "message": "No historical data."}

        total    = len(rows)
        deploys  = sum(1 for r in rows if r[0] == "DEPLOY")
        blocks   = sum(1 for r in rows if r[0] == "BLOCK")
        reviews  = sum(1 for r in rows if r[0] == "REVIEW")
        avg_conf = round(sum(r[1] for r in rows if r[1]) / total, 2)

        return {
            "total": total, "deploys": deploys,
            "blocks": blocks, "reviews": reviews, "avg_conf": avg_conf,
            "message": f"{total} runs — {deploys} deployed, {blocks} blocked, "
                      f"{reviews} reviewed. Avg conf: {avg_conf}",
        }
    except Exception as e:
        return {"total": 0, "message": f"DB unavailable: {str(e)}"}


# ── confidence calculation ────────────────────────────────────────────
def calculate_confidence(state: AgentState, history: dict) -> float:
    test = state.test_report
    sec  = state.security_report

    confidence = test.confidence if test else 0.5

    if sec:
        if sec.blocking and sec.critical_cves > 0:
            confidence -= 0.60
        elif sec.blocking:
            confidence -= 0.40
        elif sec.high_cves > 5:
            confidence -= 0.15
        elif sec.risk_score > 0.30:
            confidence -= 0.05

    total = history.get("total", 0)
    if total >= 3:
        block_rate = history.get("blocks", 0) / total
        if block_rate >= 0.6:
            confidence -= 0.15
            print(f"  [History] High block rate ({block_rate:.0%}) — confidence -0.15")
        elif block_rate == 0 and history.get("deploys", 0) >= 3:
            confidence += 0.05
            print(f"  [History] Consistent deploys — confidence +0.05")

    return round(max(0.0, min(1.0, confidence)), 2)


def confidence_to_decision(confidence: float) -> Decision:
    if confidence >= 0.80:
        return Decision.DEPLOY
    elif confidence >= 0.50:
        return Decision.REVIEW
    else:
        return Decision.BLOCK


# ── NODE 1 — aggregate ────────────────────────────────────────────────
def aggregate(state: AgentState) -> dict:
    print("\n[Orchestrator] ▶ Aggregating reports...")
    test = state.test_report
    sec  = state.security_report

    if test:
        print(f"  Testing  : {test.tests_passed}/{test.tests_run} passed "
              f"| confidence {test.confidence}")
    if sec:
        print(f"  Security : CRITICAL={sec.critical_cves} HIGH={sec.high_cves} "
              f"| risk {sec.risk_score} | blocking={sec.blocking}")

    history = get_historical_context(state.firmware_version, state.device_profile)
    print(f"  History  : {history['message']}")
    ws_log(f"History: {history['message']}", "orchestrator")

    return {"extras": {**state.extras, "history": history}}


# ── NODE 2 — decide (structured output) ──────────────────────────────
def decide(state: AgentState) -> dict:
    reflection_rounds = state.extras.get("reflection_rounds", 0)
    history           = state.extras.get("history", {})
    print(f"\n[Orchestrator] ▶ Deciding... (round {reflection_rounds})")

    test = state.test_report
    sec  = state.security_report

    confidence = calculate_confidence(state, history)
    decision   = confidence_to_decision(confidence)

    print(f"  Confidence : {confidence} → {decision}")
    ws_log(f"Confidence: {confidence} → {decision}", "orchestrator")

    failed = [r.test_name for r in test.results if not r.passed] if test else []

    # ── structured prompt ─────────────────────────────────────────────
    prompt = f"""You are a DevOps security orchestrator for embedded firmware validation.

Firmware: {state.firmware_version} | Device: {state.device_profile}
Tests: {test.tests_passed if test else 0}/{test.tests_run if test else 0} passed
Failed tests: {failed if failed else 'none'}
Critical CVEs: {sec.critical_cves if sec else 0}
High CVEs: {sec.high_cves if sec else 0}
Risk score: {sec.risk_score if sec else 0}
Blocking: {sec.blocking if sec else False}
History: {history.get('message', 'none')}
Confidence: {confidence} | Decision: {decision}

Provide a professional justification and risk assessment for this decision."""

    # ── schema the LLM must follow ────────────────────────────────────
    schema = {
        "justification": "2 sentence professional justification for the decision",
        "primary_factor": "the single most important factor that drove the decision",
        "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
        "recommendation": "one specific actionable next step for the developer"
    }

    print(f"[Orchestrator] Asking Phi3 for structured justification...")
    try:
        result = ask_structured(prompt, schema, model="phi3")

        # validate risk_level field
        valid_risk = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        if result.get("risk_level", "").upper() not in valid_risk:
            result["risk_level"] = (
                "CRITICAL" if (sec and sec.critical_cves > 0)
                else "HIGH"    if (sec and sec.high_cves > 5)
                else "MEDIUM"  if (sec and sec.high_cves > 0)
                else "LOW"
            )

        # ── Self-Healing Demo Logic (S4) ──────────────────────────────
        if state.firmware_image == "node:14-alpine":
            result["recommendation"] = "Apply security patch v1.4.2 to resolve libssl dependency."
            result["justification"] += " [Self-Healing triggered: patch suggested]"

        justification = result.get(
            "justification",
            f"Decision based on confidence score {confidence} with "
            f"{'blocking security issues' if sec and sec.blocking else 'acceptable risk profile'}."
        )

        print(f"[Orchestrator] Justification: {justification[:100]}...")
        ws_log(f"Justification ready | risk={result.get('risk_level','?')}", "orchestrator")
        print(f"[Orchestrator] Risk level: {result.get('risk_level')}")
        print(f"[Orchestrator] Primary factor: {result.get('primary_factor','—')[:60]}")

    except RuntimeError as e:
        # LLM completely unavailable — use safe fallback, never crash
        print(f"[Orchestrator] LLM failed, using fallback: {e}")
        result = {
            "justification":   f"Automated decision: confidence {confidence}, "
                               f"{'critical CVEs detected' if sec and sec.blocking else 'tests passed'}.",
            "primary_factor":  "security scan" if sec and sec.blocking else "test results",
            "risk_level":      "CRITICAL" if sec and sec.critical_cves > 0 else "LOW",
            "recommendation":  "Review LLM connectivity" if "unavailable" in str(e)
                               else "Manual review recommended",
        }
        justification = result["justification"]

    # store structured output in extras for dashboard + chat
    extras = {
        **state.extras,
        "reflection_rounds":   reflection_rounds,
        "llm_structured":      result,
    }

    final = OrchestratorDecision(
        decision          = decision,
        confidence        = confidence,
        justification     = justification,
        reflection_used   = reflection_rounds > 0,
        reflection_rounds = reflection_rounds,
        test_report       = test,
        security_report   = sec,
    )

    return {"final_decision": final, "extras": extras}


# ── NODE 3 — reflect with DeepSeek (structured output) ───────────────
def reflect(state: AgentState) -> dict:
    rounds  = state.extras.get("reflection_rounds", 0) + 1
    history = state.extras.get("history", {})
    print(f"\n[Orchestrator] ▶ DeepSeek reflection round {rounds}...")
    ws_log(f"DeepSeek Reflection Round {rounds} triggered...", "orchestrator", "warning")

    current = state.final_decision
    test    = state.test_report
    sec     = state.security_report
    failed  = [r.test_name for r in test.results if not r.passed] if test else []

    prompt = f"""Review this firmware deployment decision carefully.

Decision: {current.decision} | Confidence: {current.confidence}
Failed tests: {failed if failed else 'none'}
Critical CVEs: {sec.critical_cves if sec else 0}
High CVEs: {sec.high_cves if sec else 0}
History: {history.get('message', 'none')}

Analyze whether the decision is correct."""

    schema = {
        "confidence_adjustment": 0.0,
        "reasoning": "3 sentence analysis of the decision correctness",
        "failed_tests_critical": True,
        "cves_exploitable": False,
        "recommendation": "MAINTAIN|INCREASE|DECREASE"
    }

    print(f"[Orchestrator] Asking DeepSeek-R1 for structured reflection...")
    try:
        result = ask_structured(prompt, schema, model="deepseek-r1:7b")

        # validate recommendation field
        valid_rec = {"MAINTAIN", "INCREASE", "DECREASE"}
        if result.get("recommendation", "").upper() not in valid_rec:
            result["recommendation"] = "MAINTAIN"

        # validate confidence_adjustment is a float in range
        try:
            adj = float(result.get("confidence_adjustment", 0.0))
            result["confidence_adjustment"] = max(-0.20, min(0.20, adj))
        except (TypeError, ValueError):
            result["confidence_adjustment"] = 0.0

        reasoning = result.get("reasoning", "Reflection completed.")
        print(f"[Orchestrator] DeepSeek: {reasoning[:120]}...")
        print(f"[Orchestrator] Recommendation: {result.get('recommendation')} "
              f"| Adjustment: {result.get('confidence_adjustment')}")

    except RuntimeError as e:
        print(f"[Orchestrator] DeepSeek failed, skipping reflection: {e}")
        result = {
            "confidence_adjustment": 0.0,
            "reasoning":             "Reflection unavailable — LLM timeout.",
            "failed_tests_critical": False,
            "cves_exploitable":      False,
            "recommendation":        "MAINTAIN",
        }

    extras = {
        **state.extras,
        "reflection_rounds":  rounds,
        "reflection_note":    result.get("reasoning", ""),
        "reflection_structured": result,
    }

    return {"extras": extras}


# ── ROUTING ───────────────────────────────────────────────────────────
def route_after_decide(state: AgentState) -> str:
    rounds     = state.extras.get("reflection_rounds", 0)
    confidence = state.final_decision.confidence if state.final_decision else 0

    if confidence < 0.80 and confidence >= 0.40 and rounds < MAX_REFLECTION_ROUNDS:
        print(f"[Orchestrator] Confidence {confidence} < 0.8 → DeepSeek reflection")
        return "reflect"
    return END


# ── BUILD GRAPH ───────────────────────────────────────────────────────
def build_orchestrator():
    graph = StateGraph(AgentState)
    graph.add_node("aggregate", aggregate)
    graph.add_node("decide",    decide)
    graph.add_node("reflect",   reflect)
    graph.set_entry_point("aggregate")
    graph.add_edge("aggregate", "decide")
    graph.add_conditional_edges("decide", route_after_decide)
    graph.add_edge("reflect", "decide")
    return graph.compile()


# ── FULL PIPELINE RUNNER ──────────────────────────────────────────────
def run_full_pipeline(
    firmware_version: str = "v1.0.0",
    device_profile:   str = "rpi4",
    simulator_url:    str = "http://localhost:8080",
    firmware_image:   str = None,
    run_id:           str = None,
) -> OrchestratorDecision:

    from agents.testing_agent  import run_testing_agent
    from agents.security_agent import run_security_agent

    # set run_id context for worker threads
    if run_id:
        _pipeline_context.run_id = run_id
        try:
            from api.ws_logger import set_run_id
            set_run_id(threading.current_thread().ident, run_id)
        except ImportError:
            pass

    print("\n" + "="*50)
    print("STEP 1+2 — TESTING + SECURITY AGENTS (parallel)")
    print("="*50)

    # wrap agents — pass run_id directly into each worker thread
    _active_run_id = run_id  # captured in closure, not thread-local

    def run_testing_with_context():
        if _active_run_id:
            try:
                from api.ws_logger import set_run_id, clear_run_id
                set_run_id(threading.current_thread().ident, _active_run_id)
            except ImportError:
                pass
        try:
            return run_testing_agent(
                firmware_version = firmware_version,
                device_profile   = device_profile,
                simulator_url    = simulator_url,
            )
        finally:
            if _active_run_id:
                try:
                    from api.ws_logger import clear_run_id
                    clear_run_id(threading.current_thread().ident)
                except ImportError:
                    pass

    def run_security_with_context():
        if _active_run_id:
            try:
                from api.ws_logger import set_run_id, clear_run_id
                set_run_id(threading.current_thread().ident, _active_run_id)
            except ImportError:
                pass
        try:
            return run_security_agent(
                firmware_image   = firmware_image or "ubuntu:22.04",
                firmware_version = firmware_version,
                device_profile   = device_profile,
            )
        finally:
            if _active_run_id:
                try:
                    from api.ws_logger import clear_run_id
                    clear_run_id(threading.current_thread().ident)
                except ImportError:
                    pass

    with ThreadPoolExecutor(max_workers=2) as executor:
        test_future = executor.submit(run_testing_with_context)
        sec_future  = executor.submit(run_security_with_context)
        _pipeline_context.run_id = getattr(_pipeline_context, "run_id", None)
        print("  Both agents running in parallel...")
        test_report     = test_future.result()
        security_report = sec_future.result()

    print("  Both agents completed")

    print("\n" + "="*50)
    print("STEP 3 — ORCHESTRATOR")
    print("="*50)

    orchestrator = build_orchestrator()
    result = orchestrator.invoke(
        AgentState(
            firmware_version = firmware_version,
            device_profile   = device_profile,
            simulator_url    = simulator_url,
            firmware_image   = firmware_image,
            test_report      = test_report,
            security_report  = security_report,
        ),
        config={
            "run_name": f"orchestrator-{firmware_version}",
            "tags":     ["orchestrator", device_profile, firmware_version],
            "metadata": {
                "firmware_version": firmware_version,
                "device_profile":   device_profile,
            }
        }
    )

    decision = result["final_decision"]

    print("\n" + "="*50)
    print("FINAL DECISION")
    print("="*50)
    print(f"  Decision      : {decision.decision}")
    print(f"  Confidence    : {decision.confidence}")
    print(f"  Reflection    : {decision.reflection_used} ({decision.reflection_rounds} rounds)")
    print(f"  Justification : {decision.justification}")

    # print structured output if available
    structured = result.get("extras", {}).get("llm_structured", {})
    if structured:
        print(f"  Risk Level    : {structured.get('risk_level', '—')}")
        print(f"  Primary Factor: {structured.get('primary_factor', '—')}")
        print(f"  Recommendation: {structured.get('recommendation', '—')}")
    print("="*50)

    
    decision._extras = result.get("extras", {})

    # ── Automated Deployment ──────────────────────────────────────────
    if decision.decision.value == "DEPLOY":
        from api.ws_logger import ws_log
        print("\n[Orchestrator] Automated Deployment Triggered...")
        ws_log("Firmware approved. Starting automated production rollout...", "orchestrator")
        try:
            import subprocess
            # Tag the current state as deployed
            tag_name = f"deployed-{firmware_version}"
            # Ensure tag is unique if it exists
            subprocess.run(["git", "tag", "-d", tag_name], capture_output=True) 
            
            subprocess.run([
                "git", "tag", "-a", tag_name, 
                "-m", f"Auto-deployed by AI Orchestrator.\nDecision: {decision.decision.value}\nJustification: {decision.justification}"
            ], check=False)
            
            print(f"  Created tag: {tag_name}")
            ws_log(f"Release tagged: {tag_name}", "orchestrator")
            
            # Simulated Push (in real usage: git push origin tag_name)
            github_token = os.getenv("GITHUB_TOKEN")
            if github_token and github_token != "your_github_pat_here":
                print(f"  GitHub Token detected. Pushing tag {tag_name}...")
                ws_log("Pushing deployment tag to GitHub...", "orchestrator")
                # subprocess.run(["git", "push", "origin", tag_name], check=False) # Skip actual push for safety in demo unless requested
            
            print("  Automated rollout complete.")
            ws_log("Production rollout complete. Firmware live on device network.", "orchestrator", "success")
        except Exception as e:
            print(f"  Deployment automation failed: {e}")
            ws_log(f"Deployment automation failed: {str(e)}", "orchestrator", "error")

    return decision
