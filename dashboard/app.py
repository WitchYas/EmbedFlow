import streamlit as st
import httpx
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────
API_URL    = os.getenv("API_URL",    "http://localhost:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.18.192.1:11434")
CHAT_MODEL = "deepseek-r1:7b"

st.set_page_config(
    page_title = "AI Embedded DevOps",
    page_icon  = "chart",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# ── Styles ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');

:root {
    --bg:       #0d1117;
    --surface:  #161b22;
    --border:   #21262d;
    --accent:   #58a6ff;
    --green:    #3fb950;
    --red:      #f85149;
    --yellow:   #d29922;
    --text:     #e6edf3;
    --muted:    #8b949e;
    --mono:     'JetBrains Mono', monospace;
    --sans:     'Inter', sans-serif;
}

html, body, [class*="css"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
}

.stApp { background-color: var(--bg) !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}

/* Cards */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
}

.card-header {
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* Decision badges */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.05em;
}
.badge-deploy { background: rgba(63,185,80,0.15); color: var(--green); border: 1px solid rgba(63,185,80,0.3); }
.badge-block  { background: rgba(248,81,73,0.15);  color: var(--red);   border: 1px solid rgba(248,81,73,0.3); }
.badge-review { background: rgba(210,153,34,0.15); color: var(--yellow); border: 1px solid rgba(210,153,34,0.3); }
.badge-running { background: rgba(88,166,255,0.15); color: var(--accent); border: 1px solid rgba(88,166,255,0.3); }

/* Pipeline row */
.pipeline-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 8px;
    background: var(--surface);
    cursor: pointer;
    transition: border-color 0.15s;
}
.pipeline-row:hover { border-color: var(--accent); }
.pipeline-row.selected { border-color: var(--accent); background: rgba(88,166,255,0.05); }

/* Confidence bar */
.conf-bar-bg {
    background: var(--border);
    border-radius: 4px;
    height: 6px;
    width: 100%;
    margin-top: 4px;
}
.conf-bar-fill {
    height: 6px;
    border-radius: 4px;
    transition: width 0.3s;
}

/* Test result */
.test-pass { color: var(--green); font-family: var(--mono); font-size: 13px; }
.test-fail { color: var(--red);   font-family: var(--mono); font-size: 13px; }

/* Metric value */
.metric-val {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 700;
    line-height: 1;
}
.metric-label {
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
}

/* Explanation box */
.explanation-box {
    background: var(--bg);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 6px;
    padding: 16px 20px;
    font-size: 14px;
    line-height: 1.7;
    white-space: pre-wrap;
}

/* Chat */
.chat-user {
    background: rgba(88,166,255,0.1);
    border: 1px solid rgba(88,166,255,0.2);
    border-radius: 8px 8px 2px 8px;
    padding: 10px 14px;
    margin: 8px 0 8px 40px;
    font-size: 14px;
}
.chat-ai {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px 8px 8px 2px;
    padding: 10px 14px;
    margin: 8px 40px 8px 0;
    font-size: 14px;
    line-height: 1.6;
}
.chat-label {
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    margin-bottom: 4px;
}

/* CVE entry */
.cve-critical { border-left: 3px solid var(--red); padding-left: 10px; margin: 6px 0; }
.cve-high     { border-left: 3px solid var(--yellow); padding-left: 10px; margin: 6px 0; }

/* Agent node */
.agent-node {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    margin: 6px 0;
    font-family: var(--mono);
    font-size: 12px;
}

/* Scrollable chat history */
.chat-history {
    max-height: 400px;
    overflow-y: auto;
    padding-right: 4px;
}

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────
def get_runs():
    try:
        r = httpx.get(f"{API_URL}/pipeline/runs", timeout=5)
        return r.json()
    except:
        return []

def get_run(run_id):
    try:
        r = httpx.get(f"{API_URL}/pipeline/runs/{run_id}", timeout=5)
        return r.json()
    except:
        return {}

def trigger_pipeline(firmware_path, firmware_image, simulator_url):
    try:
        r = httpx.post(f"{API_URL}/pipeline/trigger",
            json={
                "firmware_path":  firmware_path,
                "device_profile": "rpi4",
                "firmware_image": firmware_image,
                "simulator_url":  simulator_url,
            }, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def decision_badge(decision):
    if not decision:
        return '<span class="badge badge-running">RUNNING</span>'
    d = decision.upper()
    cls = {"DEPLOY": "badge-deploy", "BLOCK": "badge-block", "REVIEW": "badge-review"}.get(d, "badge-running")
    return f'<span class="badge {cls}">{d}</span>'

def confidence_bar(conf, decision):
    if conf is None:
        return ""
    pct   = int(conf * 100)
    color = {"DEPLOY": "#3fb950", "BLOCK": "#f85149", "REVIEW": "#d29922"}.get(
        (decision or "").upper(), "#58a6ff"
    )
    return f"""
    <div class="conf-bar-bg">
        <div class="conf-bar-fill" style="width:{pct}%;background:{color};"></div>
    </div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#8b949e;margin-top:2px;">{pct}% confidence</div>
    """

def fmt_time(iso):
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %H:%M:%S")
    except:
        return iso

def duration(triggered, completed):
    if not triggered or not completed:
        return "—"
    try:
        t1 = datetime.fromisoformat(triggered.replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        s  = int((t2 - t1).total_seconds())
        return f"{s//60}m {s%60}s"
    except:
        return "—"


# ── Chat with pipeline context ────────────────────────────────────────
def build_system_prompt(run):
    agents  = run.get("agents", [])
    orch    = next((a for a in agents if a["agent"] == "orchestrator"),  {})
    testing = next((a for a in agents if a["agent"] == "testing_agent"), {})
    sec     = next((a for a in agents if a["agent"] == "security_agent"),{})

    t_out = testing.get("output", {})
    s_out = sec.get("output", {})
    o_out = orch.get("output", {})

    reflection_note = o_out.get("reflection_note", "Not triggered")
    justification   = o_out.get("justification", "")
    final_decision  = run.get("decision", "unknown")

    return f"""You are the AI Executioner for an Embedded DevOps platform.
You have complete access to the pipeline data below for Run #{run.get('id', 'unknown')[:8]}.

═══ PIPELINE STATUS ═══
Final Decision: {final_decision.upper()}
Confidence:     {run.get('confidence', 0):.2f}
Firmware:       {run.get('firmware_hash', 'unknown')}
LangSmith:      {run.get('langsmith_trace_url', 'Not linked')}

═══ AGENT JUSTIFICATION ═══
{justification}

═══ SECURITY PROFILE ═══
Critical CVEs:  {s_out.get('critical_cves', 0)}
High CVEs:      {s_out.get('high_cves', 0)}
Risk Score:     {s_out.get('risk_score', 0)}
Security Summary: {s_out.get('summary', 'No summary')}

═══ TEST PROFILE ═══
Passed:         {t_out.get('tests_passed', '?')}/{t_out.get('tests_run', '?')}
Boot:           {"SUCCESS" if t_out.get('boot_success') else "FAILED"}
Test Summary:   {t_out.get('summary', 'No summary')}

INSTRUCTIONS:
- You are technical, concise, and direct.
- Explain WHY the decision was made based on the data.
- If asked about logs, refer to the agent summaries.
- Keep responses under 4 sentences unless deep analysis is requested.
- Always be prepared to explain why a decision was {final_decision}."""


def chat_with_api(run_id, message, model="phi3"):
    """
    Calls the dedicated backend chat endpoint for a specific run.
    """
    try:
        r = httpx.post(
            f"{API_URL}/pipeline/chat",
            json={
                "run_id": str(run_id),
                "message": message,
                "model_hint": model
            },
            timeout=120,
        )
        data = r.json()
        return data.get("response", "No response from AI."), data.get("model", "unknown")
    except Exception as e:
        return f"Chat service unavailable: {str(e)}", "error"


def build_explanation(run):
    """Generate plain-English explanation of the decision"""
    agents  = run.get("agents", [])
    orch    = next((a for a in agents if a["agent"] == "orchestrator"),  {})
    testing = next((a for a in agents if a["agent"] == "testing_agent"), {})
    sec     = next((a for a in agents if a["agent"] == "security_agent"),{})

    t_out   = testing.get("output", {})
    s_out   = sec.get("output", {})
    o_out   = orch.get("output", {})

    decision   = run.get("decision", "UNKNOWN")
    confidence = run.get("confidence", 0)
    passed     = t_out.get("tests_passed", 0)
    total      = t_out.get("tests_run", 0)
    critical   = s_out.get("critical_cves", 0)
    high       = s_out.get("high_cves", 0)
    risk       = s_out.get("risk_score", 0)
    blocking   = s_out.get("blocking", False)
    reflection = o_out.get("reflection_used", False)
    rounds     = o_out.get("reflection_rounds", 0)
    just       = o_out.get("justification", "")

    status_prefix = {"DEPLOY": "DEPLOY", "BLOCK": "BLOCK", "REVIEW": "REVIEW"}.get(decision, "RUNNING")

    lines = [f"{status_prefix} {decision} — Here's why:\n"]

    # test summary
    if total > 0:
        if passed == total:
            lines.append(f"The firmware passed all {total} functional tests successfully, "
                        f"including critical checks for MQTT connectivity and memory integrity.")
        else:
            lines.append(f"The firmware passed {passed}/{total} functional tests. "
                        f"Some tests failed, reducing the testing confidence score.")

    # security summary
    if blocking and critical > 0:
        lines.append(f"\nHowever, the security scan detected {critical} critical "
                    f"vulnerabilit{'y' if critical==1 else 'ies'} (CVSS ≥ 9.0) and {high} high-severity issues "
                    f"in the firmware image. Risk score: {risk:.2f}/1.0. "
                    f"Critical CVEs automatically trigger a blocking condition regardless of test results.")
    elif high > 0:
        lines.append(f"\nThe security scan found no critical CVEs but detected {high} high-severity "
                    f"vulnerabilities. Risk score: {risk:.2f}/1.0.")
    else:
        lines.append(f"\nThe security scan found no critical or high-severity CVEs. "
                    f"Risk score: {risk:.2f}/1.0 — within acceptable thresholds.")

    # confidence + reflection
    lines.append(f"\nThe Orchestrator calculated a confidence score of {confidence:.0%}.")
    if reflection:
        lines.append(f"This score was ambiguous, triggering {rounds} DeepSeek-R1 reflection "
                    f"round{'s' if rounds > 1 else ''} to analyze exploitability and test criticality "
                    f"before reaching the final decision.")
    else:
        lines.append("The confidence was clear enough that no reflection was needed.")

    # justification from LLM
    if just and "unavailable" not in just.lower():
        lines.append(f"\nOrchestrator reasoning: {just}")

    # fix recommendation
    if decision == "BLOCK":
        lines.append(f"\nFix: Address the critical CVEs in your base image before resubmitting. "
                    f"Consider upgrading to a more recent base image with patched dependencies.")
    elif decision == "REVIEW":
        lines.append(f"\nNext step: Manual review required before production deployment. "
                    f"Staging deployment may proceed automatically.")

    return "\n".join(lines)


# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:16px 0 24px">
        <div style="font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:#58a6ff;">
            ⬡ DevOps AI
        </div>
        <div style="font-size:11px;color:#8b949e;margin-top:4px;">
            Embedded Systems Platform
        </div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio("Navigation", ["Pipeline Runs", "Trigger Pipeline", "Live Metrics"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("""
    <div style="font-size:11px;color:#8b949e;">
    <b style="color:#e6edf3;">Quick Links</b><br><br>
    <a href="http://localhost:8000/docs" target="_blank" style="color:#58a6ff;text-decoration:none;">API Docs</a><br>
    <a href="http://localhost:9090" target="_blank" style="color:#58a6ff;text-decoration:none;">Prometheus</a><br>
    <a href="http://localhost:3000" target="_blank" style="color:#58a6ff;text-decoration:none;">Grafana</a><br>
    <a href="https://smith.langchain.com" target="_blank" style="color:#58a6ff;text-decoration:none;">LangSmith</a>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# PAGE 1 — Pipeline Runs
# ══════════════════════════════════════════════════════════════════════
if page == "Pipeline Runs":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h1 style="font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700;margin:0;">
            Pipeline Runs
        </h1>
        <div style="color:#8b949e;font-size:13px;margin-top:4px;">
            All firmware validation runs — click a run to inspect
        </div>
    </div>
    """, unsafe_allow_html=True)

    runs = get_runs()

    if not runs:
        st.info("No pipeline runs yet. Go to **Trigger Pipeline** to start one.")
    else:
        # ── Summary metrics ───────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        total   = len(runs)
        deploys = sum(1 for r in runs if r.get("decision") == "DEPLOY")
        blocks  = sum(1 for r in runs if r.get("decision") == "BLOCK")
        reviews = sum(1 for r in runs if r.get("decision") == "REVIEW")

        with col1:
            st.markdown(f"""
            <div class="card" style="text-align:center;">
                <div class="metric-val">{total}</div>
                <div class="metric-label">Total Runs</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="card" style="text-align:center;">
                <div class="metric-val" style="color:#3fb950;">{deploys}</div>
                <div class="metric-label">Deployed</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="card" style="text-align:center;">
                <div class="metric-val" style="color:#f85149;">{blocks}</div>
                <div class="metric-label">Blocked</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="card" style="text-align:center;">
                <div class="metric-val" style="color:#d29922;">{reviews}</div>
                <div class="metric-label">Review</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # ── Run list ──────────────────────────────────────────────────
        selected_run_id = st.session_state.get("selected_run_id")

        for run in runs:
            run_id   = run.get("id", "")
            decision = run.get("decision")
            conf     = run.get("confidence")
            selected = run_id == selected_run_id

            col_a, col_b, col_c, col_d = st.columns([3, 2, 2, 1])

            with col_a:
                st.markdown(f"""
                <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#8b949e;">
                    {run_id[:8]}...
                </div>
                <div style="font-size:13px;color:#e6edf3;margin-top:2px;">
                    {run.get('profile','rpi4')} · {fmt_time(run.get('triggered'))}
                </div>
                """, unsafe_allow_html=True)

            with col_b:
                st.markdown(decision_badge(decision), unsafe_allow_html=True)
                if conf is not None:
                    st.markdown(confidence_bar(conf, decision), unsafe_allow_html=True)

            with col_c:
                st.markdown(f"""
                <div style="font-size:12px;color:#8b949e;">
                    Duration: {duration(run.get('triggered'), run.get('completed'))}
                </div>
                <div style="font-size:12px;color:#8b949e;">
                    Status: {run.get('status','—')}
                </div>
                """, unsafe_allow_html=True)

            with col_d:
                if st.button("Inspect →", key=f"btn_{run_id}"):
                    st.session_state["selected_run_id"] = run_id
                    st.rerun()

            st.markdown("<hr style='border-color:#21262d;margin:4px 0;'>", unsafe_allow_html=True)

        # ── Run detail panel ──────────────────────────────────────────
        if selected_run_id:
            run = get_run(selected_run_id)
            if run and "error" not in run:
                st.markdown("---")
                st.markdown(f"""
                <h2 style="font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;">
                    Run Detail — {selected_run_id[:8]}...
                </h2>
                """, unsafe_allow_html=True)

                tab1, tab2, tab3, tab4 = st.tabs([
                    "Overview",
                    "Tests",
                    "Security",
                    "Ask the AI"
                ])

                agents  = run.get("agents", [])
                orch    = next((a for a in agents if a["agent"] == "orchestrator"),  {})
                testing = next((a for a in agents if a["agent"] == "testing_agent"), {})
                sec     = next((a for a in agents if a["agent"] == "security_agent"),{})

                # ── Tab 1: Overview ───────────────────────────────────
                with tab1:
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.markdown('<div class="card-header">Decision</div>', unsafe_allow_html=True)
                        st.markdown(decision_badge(run.get("decision")), unsafe_allow_html=True)
                        st.markdown(f"""
                        <div style="margin-top:12px;">
                            {confidence_bar(run.get('confidence'), run.get('decision'))}
                        </div>
                        <div style="margin-top:16px;font-size:13px;color:#8b949e;">
                            <b style="color:#e6edf3;">Duration:</b> {duration(run.get('triggered'), run.get('completed'))}<br>
                            <b style="color:#e6edf3;">Triggered:</b> {fmt_time(run.get('triggered'))}<br>
                            <b style="color:#e6edf3;">Profile:</b> {run.get('profile','rpi4')}
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    with col2:
                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.markdown('<div class="card-header">Agent Timeline</div>', unsafe_allow_html=True)
                        for agent in agents:
                            name      = agent.get("agent","").replace("_", " ").title()
                            reflected = agent.get("reflection", False)
                            status_text = "REflected" if reflected else "Done"
                            st.markdown(f"""
                            <div class="agent-node">
                                {status_text} {name}
                                {"<span style='color:#d29922;font-size:10px;'> · DeepSeek reflection triggered</span>" if reflected else ""}
                            </div>
                            """, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    # Explanation
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.markdown('<div class="card-header">Why did the AI decide this?</div>', unsafe_allow_html=True)
                    explanation = build_explanation(run)
                    st.markdown(f'<div class="explanation-box">{explanation}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                    # LangSmith link
                    trace_url = run.get("langsmith_trace_url")
                    if trace_url:
                        st.markdown(f"""
                        <a href="{trace_url}" target="_blank" style="
                            display:inline-block;
                            padding:8px 16px;
                            background:rgba(88,166,255,0.1);
                            border:1px solid rgba(88,166,255,0.3);
                            border-radius:6px;
                            color:#58a6ff;
                            text-decoration:none;
                            font-size:13px;
                            font-family:'JetBrains Mono',monospace;
                        ">View LangSmith Trace -></a>
                        """, unsafe_allow_html=True)

                # ── Tab 2: Tests ──────────────────────────────────────
                with tab2:
                    t_out = testing.get("output", {})

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"""
                        <div class="card" style="text-align:center;">
                            <div class="metric-val" style="color:#3fb950;">{t_out.get('tests_passed','?')}</div>
                            <div class="metric-label">Tests Passed</div>
                        </div>""", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"""
                        <div class="card" style="text-align:center;">
                            <div class="metric-val">{t_out.get('tests_run','?')}</div>
                            <div class="metric-label">Tests Run</div>
                        </div>""", unsafe_allow_html=True)
                    with col3:
                        conf = t_out.get('confidence', 0)
                        st.markdown(f"""
                        <div class="card" style="text-align:center;">
                            <div class="metric-val" style="color:#58a6ff;">{conf:.0%}</div>
                            <div class="metric-label">Test Confidence</div>
                        </div>""", unsafe_allow_html=True)

                    st.markdown(f"""
                    <div class="card">
                        <div class="card-header">Test Summary</div>
                        <div style="font-size:13px;line-height:1.6;">
                            Boot success: {"Yes" if t_out.get('boot_success') else "No"}<br>
                            {t_out.get('summary','No summary available')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # ── Tab 3: Security ───────────────────────────────────
                with tab3:
                    s_out = sec.get("output", {})

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        crit = s_out.get('critical_cves', 0)
                        st.markdown(f"""
                        <div class="card" style="text-align:center;">
                            <div class="metric-val" style="color:{'#f85149' if crit > 0 else '#3fb950'};">{crit}</div>
                            <div class="metric-label">Critical CVEs</div>
                        </div>""", unsafe_allow_html=True)
                    with col2:
                        high = s_out.get('high_cves', 0)
                        st.markdown(f"""
                        <div class="card" style="text-align:center;">
                            <div class="metric-val" style="color:{'#d29922' if high > 0 else '#3fb950'};">{high}</div>
                            <div class="metric-label">High CVEs</div>
                        </div>""", unsafe_allow_html=True)
                    with col3:
                        st.markdown(f"""
                        <div class="card" style="text-align:center;">
                            <div class="metric-val">{s_out.get('sbom_packages','?')}</div>
                            <div class="metric-label">SBOM Packages</div>
                        </div>""", unsafe_allow_html=True)
                    with col4:
                        risk = s_out.get('risk_score', 0)
                        st.markdown(f"""
                        <div class="card" style="text-align:center;">
                            <div class="metric-val" style="color:{'#f85149' if risk > 0.5 else '#d29922' if risk > 0.2 else '#3fb950'};">{risk:.2f}</div>
                            <div class="metric-label">Risk Score</div>
                        </div>""", unsafe_allow_html=True)

                    blocking = s_out.get("blocking", False)
                    status_color = "#f85149" if blocking else "#3fb950"
                    status_text  = "BLOCKING — Critical CVEs detected" if blocking else "PASSED — No critical CVEs"
                    st.markdown(f"""
                    <div class="card">
                        <div class="card-header">Security Status</div>
                        <div style="font-size:14px;color:{status_color};font-weight:600;">{status_text}</div>
                        <div style="font-size:13px;color:#8b949e;margin-top:8px;">{s_out.get('summary','No summary')}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # ── Tab 4: Chat ───────────────────────────────────────
                with tab4:
                    st.markdown("""
                    <div style="margin-bottom:16px;">
                        <div style="font-size:14px;color:#8b949e;">
                            Ask DeepSeek-R1 anything about this pipeline run.
                            It has full access to test results, CVE details, and agent reasoning.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    chat_key = f"chat_{selected_run_id}"
                    if chat_key not in st.session_state:
                        st.session_state[chat_key] = []

                    history = st.session_state[chat_key]

                    # suggested questions
                    st.markdown("**Suggested questions:**")
                    q_cols = st.columns(3)
                    suggestions = [
                        "Which CVE is most dangerous?",
                        "How do I fix this?",
                        "Would staging be safe?",
                        "Why did reflection trigger?",
                        "What's the minimum fix to DEPLOY?",
                        "Explain the confidence score",
                    ]
                    for i, q in enumerate(suggestions):
                        with q_cols[i % 3]:
                            if st.button(q, key=f"sugg_{selected_run_id}_{i}"):
                                st.session_state[f"pending_{selected_run_id}"] = q

                    st.markdown("---")

                    # chat history display
                    if history:
                        st.markdown('<div class="chat-history">', unsafe_allow_html=True)
                        for msg in history:
                            if msg["role"] == "user":
                                st.markdown(f"""
                                <div class="chat-label">You</div>
                                <div class="chat-user">{msg['content']}</div>
                                """, unsafe_allow_html=True)
                            else:
                                model_tag = msg.get('model', 'DeepSeek-R1')
                                st.markdown(f"""
                                <div class="chat-label">{model_tag.upper()}</div>
                                <div class="chat-ai">{msg['content']}</div>
                                """, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    # input
                    user_input = st.chat_input("Ask about this pipeline run...", key=f"input_{selected_run_id}")

                    # handle suggestion clicks
                    pending = st.session_state.pop(f"pending_{selected_run_id}", None)
                    if pending:
                        user_input = pending

                    if user_input:
                        with st.spinner("Talking to Decision AI..."):
                            answer, model_used = chat_with_api(selected_run_id, user_input, model="deepseek-r1:7b")

                        st.session_state[chat_key].append({"role": "user",      "content": user_input})
                        st.session_state[chat_key].append({"role": "assistant", "content": answer, "model": model_used})
                        st.rerun()

                    if history:
                        if st.button("Clear conversation", key=f"clear_{selected_run_id}"):
                            st.session_state[chat_key] = []
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════
# PAGE 2 — Trigger Pipeline
# ══════════════════════════════════════════════════════════════════════
elif page == "Trigger Pipeline":
    st.markdown("""
    <h1 style="font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700;margin-bottom:24px;">
        Trigger Pipeline
    </h1>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Pipeline Configuration</div>', unsafe_allow_html=True)

        firmware_path = st.text_input("Firmware Path", value="firmware/v1.2.0.bin",
            help="Path or identifier for the firmware being validated")
        firmware_image = st.text_input("Docker Image to Scan", value="ubuntu:22.04",
            help="Docker image Trivy/Grype will scan for CVEs")
        simulator_url = st.text_input("Simulator URL", value="http://localhost:8080",
            help="RPi4 simulator endpoint")

        st.markdown("**Quick scenarios:**")
        s_col1, s_col2, s_col3 = st.columns(3)
        with s_col1:
            if st.button("S1 — Golden Path"):
                st.session_state["fw_image"] = "ubuntu:22.04"
                st.session_state["fw_path"]  = "firmware/v1.2.0.bin"
        with s_col2:
            if st.button("S2 — CVE Block"):
                st.session_state["fw_image"] = "nginx:1.14.0"
                st.session_state["fw_path"]  = "firmware/v1.3.0-vulnerable.bin"
        with s_col3:
            if st.button("S3 — Review"):
                st.session_state["fw_image"] = "ubuntu:22.04"
                st.session_state["fw_path"]  = "firmware/v1.4.0-review.bin"

        if st.session_state.get("fw_image"):
            firmware_image = st.session_state["fw_image"]
            firmware_path  = st.session_state["fw_path"]

        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("Trigger Pipeline", use_container_width=True):
            with st.spinner("Triggering pipeline..."):
                result = trigger_pipeline(firmware_path, firmware_image, simulator_url)

            if "error" in result:
                st.error(f"Failed: {result['error']}")
            else:
                run_id = result.get("run_id")
                st.success(f"Pipeline triggered! Run ID: `{run_id}`")
                st.session_state["selected_run_id"] = run_id
                st.info("Pipeline is running in the background. Go to **Pipeline Runs** to track progress.")

    with col2:
        st.markdown("""
        <div class="card">
            <div class="card-header">Demo Scenarios</div>
            <div style="font-size:13px;line-height:1.8;">
                <div style="margin-bottom:12px;">
                    <span style="color:#3fb950;font-weight:600;">S1 — Golden Path</span><br>
                    <span style="color:#8b949e;">ubuntu:22.04 · All tests pass · No CVEs · DEPLOY</span>
                </div>
                <div style="margin-bottom:12px;">
                    <span style="color:#f85149;font-weight:600;">S2 — CVE Block</span><br>
                    <span style="color:#8b949e;">nginx:1.14.0 · Tests pass · 76 critical CVEs · BLOCK</span><br>
                    <span style="color:#8b949e;font-size:11px;">Demonstrates: functional tests passing ≠ safe to deploy</span>
                </div>
                <div>
                    <span style="color:#d29922;font-weight:600;">S3 — Review / Reflection</span><br>
                    <span style="color:#8b949e;">Ambiguous confidence triggers DeepSeek reflection loop</span>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">Pipeline Flow</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#8b949e;line-height:2;">
                git push<br>
                &nbsp;&nbsp;↓<br>
                GitHub Actions<br>
                &nbsp;&nbsp;↓<br>
                POST /pipeline/trigger<br>
                &nbsp;&nbsp;↓<br>
                Testing Agent ──┐ (parallel)<br>
                Security Agent ─┘<br>
                &nbsp;&nbsp;↓<br>
                Orchestrator + DeepSeek<br>
                &nbsp;&nbsp;↓<br>
                DEPLOY / BLOCK / REVIEW
            </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# PAGE 3 — Live Metrics
# ══════════════════════════════════════════════════════════════════════
elif page == "Live Metrics":
    st.markdown("""
    <h1 style="font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700;margin-bottom:24px;">
        Live Metrics
    </h1>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="card">
        <div class="card-header">Embedded Services</div>
        <div style="display:flex;gap:16px;flex-wrap:wrap;">
            <a href="http://localhost:3000" target="_blank" style="
                padding:12px 20px;
                background:rgba(88,166,255,0.1);
                border:1px solid rgba(88,166,255,0.3);
                border-radius:6px;
                color:#58a6ff;
                text-decoration:none;
                font-family:'JetBrains Mono',monospace;
                font-size:13px;
            ">Open Grafana -></a>
            <a href="http://localhost:9090" target="_blank" style="
                padding:12px 20px;
                background:rgba(88,166,255,0.1);
                border:1px solid rgba(88,166,255,0.3);
                border-radius:6px;
                color:#58a6ff;
                text-decoration:none;
                font-family:'JetBrains Mono',monospace;
                font-size:13px;
            ">Open Prometheus -></a>
        </div>
        <div style="margin-top:16px;font-size:13px;color:#8b949e;">
            Grafana shows real-time device metrics: CPU usage, RAM consumption,
            boot duration histogram, and test pass/fail counters — all scraped
            from the RPi4 simulator's Prometheus endpoint every 5 seconds.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # live simulator health
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header">Simulator Health</div>', unsafe_allow_html=True)
    try:
        r = httpx.get("http://localhost:8080/health", timeout=3)
        h = r.json()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div style="text-align:center;">
                <div class="metric-val" style="color:#3fb950;font-size:20px;">{h.get('status','?').upper()}</div>
                <div class="metric-label">Status</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div style="text-align:center;">
                <div class="metric-val" style="font-size:20px;">{h.get('uptime_s',0):.0f}s</div>
                <div class="metric-label">Uptime</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div style="text-align:center;">
                <div class="metric-val" style="font-size:20px;">{h.get('ram_mb','?')} MB</div>
                <div class="metric-label">RAM</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            fault = h.get("fault") or "none"
            color = "#f85149" if fault != "none" else "#3fb950"
            st.markdown(f"""
            <div style="text-align:center;">
                <div class="metric-val" style="color:{color};font-size:20px;">{fault}</div>
                <div class="metric-label">Active Fault</div>
            </div>""", unsafe_allow_html=True)
    except:
        st.error("Simulator not reachable — is it running?")

    st.markdown('</div>', unsafe_allow_html=True)

    # fault injection
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header">Fault Injection — Demo Tool</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:12px;color:#8b949e;margin-bottom:12px;">
        Inject faults to demonstrate S4 (self-healing) scenario
    </div>
    """, unsafe_allow_html=True)

    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    faults = [("none", "Clear", "#3fb950"), ("network_loss", "Network Loss", "#d29922"),
              ("memory_full", "Memory Full", "#d29922"), ("boot_loop", "Boot Loop", "#f85149")]

    for i, (fault, label, color) in enumerate(faults):
        with [f_col1, f_col2, f_col3, f_col4][i]:
            if st.button(label, key=f"fault_{fault}"):
                try:
                    httpx.post("http://localhost:8080/inject-fault",
                        json={"fault": fault}, timeout=3)
                    st.success(f"Fault set: {fault}")
                    st.rerun()
                except:
                    st.error("Simulator not reachable")

    st.markdown('</div>', unsafe_allow_html=True)