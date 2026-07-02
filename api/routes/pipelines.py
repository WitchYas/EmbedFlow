import os
import uuid
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from api.database import get_db
from api.models import PipelineRun, AgentDecision, TestResult as TestResultDB, SbomEntry
from api.pipeline_logger import init_run, log, log_final, cleanup_if_idle
from api.ws_logger import set_run_id, clear_run_id
import threading

router = APIRouter()


class TriggerRequest(BaseModel):
    firmware_path:  str
    device_profile: str = "rpi4"
    firmware_image: str = "ubuntu:22.04"
    simulator_url:  str = "http://localhost:8080"


# ── background task ───────────────────────────────────────────────────
async def run_pipeline_task(run_id: str, req: TriggerRequest):
    from api.database import AsyncSessionLocal
    from agents.orchestrator import run_full_pipeline

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id))
        )
        run = result.scalar_one_or_none()
        if not run:
            return

        # set thread context (init_run moved to trigger for early buffering)
        thread_id = threading.current_thread().ident
        set_run_id(thread_id, run_id)
        log(run_id, f"Pipeline {run_id[:8]} started", "system", "info")

        try:
            # ── run full pipeline ─────────────────────────────────────
            import anyio
            decision = await anyio.to_thread.run_sync(
                run_full_pipeline,
                req.firmware_path,
                req.device_profile,
                req.simulator_url,
                req.firmware_image,
                run_id,
            )

            # ── get structured LLM output from extras ─────────────────
            extras     = getattr(decision, '_extras', {})
            structured = extras.get('llm_structured', {})
            reflection = extras.get('reflection_structured', {})

            # ── update pipeline_runs ──────────────────────────────────
            run.status          = "completed"
            run.final_decision  = decision.decision.value
            run.confidence      = decision.confidence
            run.completed_at    = datetime.now(timezone.utc)
            run.langsmith_trace_url = (
                f"https://smith.langchain.com/projects/"
                f"{os.getenv('LANGCHAIN_PROJECT', 'ai-embedded-devops')}"
            )

            # ── orchestrator agent decision ───────────────────────────
            db.add(AgentDecision(
                pipeline_run_id      = uuid.UUID(run_id),
                agent_name           = "orchestrator",
                input_state          = {
                    "firmware": req.firmware_path,
                    "device":   req.device_profile,
                    "image":    req.firmware_image,
                },
                output               = {
                    # core decision
                    "decision":          decision.decision.value,
                    "confidence":        decision.confidence,
                    "justification":     decision.justification,
                    "reflection_used":   decision.reflection_used,
                    "reflection_rounds": decision.reflection_rounds,
                    # structured LLM output — new fields
                    "risk_level":        structured.get("risk_level", "UNKNOWN"),
                    "primary_factor":    structured.get("primary_factor", ""),
                    "recommendation":    structured.get("recommendation", ""),
                    # reflection analysis if triggered
                    "reflection_note":       reflection.get("reasoning", ""),
                    "reflection_adjustment": reflection.get("confidence_adjustment", 0.0),
                    "cves_exploitable":      reflection.get("cves_exploitable", False),
                    "failed_tests_critical": reflection.get("failed_tests_critical", False),
                },
                llm_model            = "phi3",
                reflection_triggered = decision.reflection_used,
            ))

            # ── testing agent decision ────────────────────────────────
            if decision.test_report:
                tr = decision.test_report

                # individual test results
                for t in tr.results:
                    db.add(TestResultDB(
                        pipeline_run_id = uuid.UUID(run_id),
                        test_name       = t.test_name,
                        passed          = t.passed,
                        duration_ms     = t.duration_ms,
                        metrics         = t.metrics or {},
                    ))

                db.add(AgentDecision(
                    pipeline_run_id = uuid.UUID(run_id),
                    agent_name      = "testing_agent",
                    output          = {
                        "tests_run":    tr.tests_run,
                        "tests_passed": tr.tests_passed,
                        "tests_failed": tr.tests_failed,
                        "boot_success": tr.boot_success,
                        "boot_time_s":  tr.boot_time_s,
                        "confidence":   tr.confidence,
                        "summary":      tr.summary,
                    },
                    llm_model = "phi3",
                ))

            # ── security agent decision ───────────────────────────────
            if decision.security_report:
                sec = decision.security_report

                # SBOM entries
                for cve in sec.cve_details:
                    db.add(SbomEntry(
                        pipeline_run_id = uuid.UUID(run_id),
                        package_name    = cve.get("pkg_name",
                                          cve.get("package", "unknown")),
                        version         = cve.get("installed_version",
                                          cve.get("version", "")),
                        cve_count       = 1,
                        highest_cvss    = float(cve.get("cvss_score", 0.0)),
                    ))

                db.add(AgentDecision(
                    pipeline_run_id = uuid.UUID(run_id),
                    agent_name      = "security_agent",
                    output          = {
                        "critical":      sec.critical_cves,
                        "high":          sec.high_cves,
                        "medium":        sec.medium_cves,
                        "low":           sec.low_cves,
                        "critical_cves": sec.critical_cves,
                        "high_cves":     sec.high_cves,
                        "medium_cves":   sec.medium_cves,
                        "low_cves":      sec.low_cves,
                        "risk_score":    sec.risk_score,
                        "blocking":      sec.blocking,
                        "sbom_packages": sec.sbom_packages,
                        "summary":       sec.summary,
                    },
                    llm_model = "phi3",
                ))

            log_final(run_id, decision.decision.value, decision.confidence)
            cleanup_if_idle(run_id)
            await db.commit()
            print(f"\n[API] ✅ Pipeline {run_id} → "
                  f"{decision.decision.value} ({decision.confidence}) "
                  f"| risk={structured.get('risk_level','?')}")

        except Exception as e:
            log(run_id, f"Pipeline failed: {e}", "system", "error")
            log_final(run_id, "ERROR", 0.0)
            cleanup_if_idle(run_id)
            run.status       = "error"
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            print(f"\n[API] ❌ Pipeline {run_id} FAILED: {e}")
            raise
        finally:
            clear_run_id(threading.current_thread().ident)


# ── POST /pipeline/trigger ────────────────────────────────────────────
@router.post("/trigger")
async def trigger_pipeline(
    req:              TriggerRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
):
    firmware_hash = hashlib.sha256(req.firmware_path.encode()).hexdigest()[:16]

    run = PipelineRun(
        firmware_hash  = firmware_hash,
        device_profile = req.device_profile,
        status         = "running",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Initialize log buffer immediately so WebSocket can connect early
    init_run(str(run.id))

    background_tasks.add_task(run_pipeline_task, str(run.id), req)

    return {
        "run_id":        str(run.id),
        "firmware_hash": firmware_hash,
        "status":        "triggered",
        "message":       "Pipeline running in background. "
                         "Poll /pipeline/runs/{run_id} for result.",
    }


# ── GET /pipeline/runs ────────────────────────────────────────────────
@router.get("/runs")
async def get_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PipelineRun).order_by(PipelineRun.triggered_at.desc())
    )
    runs = result.scalars().all()
    
    pipeline_data = []
    for r in runs:
        # Get decisions for deep nested data
        dec_res = await db.execute(
            select(AgentDecision).where(AgentDecision.pipeline_run_id == r.id)
        )
        decisions = dec_res.scalars().all()
        
        # Get SBOM entries
        sbom_res = await db.execute(
            select(SbomEntry).where(SbomEntry.pipeline_run_id == r.id)
        )
        sbom = sbom_res.scalars().all()
        
        pipeline_data.append({
            "id":               str(r.id),
            "status":           r.status,
            "decision":         r.final_decision,
            "confidence":       r.confidence,
            "profile":          r.device_profile,
            "firmware_hash":    r.firmware_hash,
            "triggered":        r.triggered_at.isoformat() if r.triggered_at else None,
            "completed":        r.completed_at.isoformat() if r.completed_at else None,
            "decision_details": [
                {"agent_name": d.agent_name, "output": d.output} for d in decisions
            ],
            "sbom_entries": [
                {
                    "package_name": s.package_name, 
                    "version": s.version, 
                    "highest_cvss": s.highest_cvss
                } for s in sbom
            ]
        })
    return pipeline_data


# ── GET /pipeline/runs/{run_id} ───────────────────────────────────────
@router.get("/runs/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id))
    )
    run = result.scalar_one_or_none()
    if not run:
        return {"error": "not found"}

    decisions = await db.execute(
        select(AgentDecision).where(
            AgentDecision.pipeline_run_id == uuid.UUID(run_id)
        )
    )
    agent_logs = [
        {
            "agent":      d.agent_name,
            "output":     d.output,
            "reflection": d.reflection_triggered,
            "latency_ms": d.latency_ms,
        }
        for d in decisions.scalars().all()
    ]

    return {
        "id":               str(run.id),
        "status":           run.status,
        "decision":         run.final_decision,
        "confidence":       run.confidence,
        "profile":          run.device_profile,
        "firmware_hash":    run.firmware_hash,
        "langsmith_url":    run.langsmith_trace_url,
        "triggered":        run.triggered_at.isoformat() if run.triggered_at else None,
        "completed":        run.completed_at.isoformat() if run.completed_at else None,
        "agents":           agent_logs,
    }

class ChatRequest(BaseModel):
    run_id: str
    message: str
    model_hint: str = "phi3"

@router.post("/chat")
async def chat_with_decision(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Conversational endpoint to discuss a specific pipeline decision.
    """
    from agents.llm_router import ask_fast, ask_deep
    import json
    
    # 1. Get run context
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == uuid.UUID(req.run_id))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # 2. Get agent reasoning
    agent_res = await db.execute(
        select(AgentDecision).where(AgentDecision.pipeline_run_id == uuid.UUID(req.run_id))
    )
    decisions = agent_res.scalars().all()
    context = "\n".join([f"{d.agent_name}: {json.dumps(d.output)}" for d in decisions])

    # 3. Create prompt
    prompt = f"""You are the AI Orchestrator for an Embedded DevOps platform. 
The user is asking about Run #{str(run.id)[:8]}.

DECISION CONTEXT:
Final Decision: {run.final_decision}
Confidence: {run.confidence}
Agent Details:
{context}

User Question: {req.message}

Explain your reasoning clearly and concisely. Be professional and technical."""

    # 4. Invoke LLM
    try:
        model = req.model_hint
        if "deepseek" in model:
            response = ask_deep(prompt)
        else:
            response = ask_fast(prompt)
        
        return {"response": response, "model": model}
    except Exception as e:
        return {"response": f"AI unavailable: {str(e)}", "model": "fallback"}

