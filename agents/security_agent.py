import subprocess
import json
try:
    from api.ws_logger import ws_log
except ImportError:
    def ws_log(msg, agent="system", level="info"): pass
from langgraph.graph import StateGraph, END
from agents.state import AgentState, SecurityReport


def run_cmd(cmd: list) -> dict:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        if not result.stdout.strip():
            return {"error": f"Empty output. stderr: {result.stderr[:200]}"}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after 300s: {' '.join(cmd)}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def scan_image(state: AgentState) -> dict:
    image = state.firmware_image
    if not image:
        print("[Security Agent] No image provided — skipping")
        return {}

    print(f"\n[Security Agent] ▶ Trivy scanning {image}...")
    ws_log(f"Trivy scanning {image}...", "security_agent")
    data = run_cmd([
        "trivy", "image",
        "--format", "json",
        "--quiet",
        "--timeout", "120s",
        image
    ])

    if "error" in data:
        print(f"[Security Agent] Trivy failed — will use Grype as fallback: {data['error']}")
        extras = {**state.extras, "trivy_failed": True}
        return {"extras": extras}

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    cve_details = []

    for result in data.get("Results", []):
        for vuln in result.get("Vulnerabilities", []):
            sev = vuln.get("Severity", "UNKNOWN")
            if sev in counts:
                counts[sev] += 1
            cve_details.append({
                "id":          vuln.get("VulnerabilityID"),
                "severity":    sev,
                "pkg_name":    vuln.get("PkgName"),
                "installed_version": vuln.get("InstalledVersion"),
                "fixed_in":    vuln.get("FixedVersion"),
                "cvss_score":  vuln.get("CVSS", {}).get("nvd", {}).get("V3Score", 0.0),
                "description": vuln.get("Title", "")[:100],
            })

    print(f"[Security Agent] Trivy: CRITICAL={counts['CRITICAL']} HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}")
    ws_log(f"Trivy: CRITICAL={counts['CRITICAL']} HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}", "security_agent", "error" if counts['CRITICAL'] > 0 else "info")

    extras = {**state.extras, "trivy": counts, "cves": cve_details, "trivy_failed": False}
    return {"extras": extras}


def generate_sbom(state: AgentState) -> dict:
    image = state.firmware_image
    if not image:
        return {}

    print(f"\n[Security Agent] ▶ Syft generating SBOM for {image}...")
    data = run_cmd(["syft", image, "-o", "json", "--quiet"])

    if "error" in data:
        print(f"[Security Agent] Syft error: {data['error']}")
        return {}

    count = len(data.get("artifacts", []))
    print(f"[Security Agent] SBOM: {count} packages")
    ws_log(f"SBOM generated: {count} packages", "security_agent")

    extras = {**state.extras, "sbom_count": count}
    return {"extras": extras}


def correlate_cves(state: AgentState) -> dict:
    image = state.firmware_image
    if not image:
        return {}

    print(f"\n[Security Agent] ▶ Grype correlating CVEs for {image}...")
    data = run_cmd(["grype", image, "-o", "json", "--quiet"])

    if "error" in data:
        print(f"[Security Agent] Grype error: {data['error']}")
        return {}

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for match in data.get("matches", []):
        sev = match.get("vulnerability", {}).get("severity", "UNKNOWN").upper()
        if sev in counts:
            counts[sev] += 1

    print(f"[Security Agent] Grype: CRITICAL={counts['CRITICAL']} HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}")
    ws_log(f"Grype: CRITICAL={counts['CRITICAL']} HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}", "security_agent", "error" if counts['CRITICAL'] > 0 else "info")

    extras = {**state.extras, "grype": counts}
    return {"extras": extras}


def build_report(state: AgentState) -> dict:
    print(f"\n[Security Agent] ▶ Building report...")

    trivy  = state.extras.get("trivy",      {"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0})
    grype  = state.extras.get("grype",      {"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0})
    sbom   = state.extras.get("sbom_count", 0)
    cves   = state.extras.get("cves",       [])
    trivy_failed = state.extras.get("trivy_failed", False)

    # ── use Grype as fallback if Trivy failed ────────────────────────
    if trivy_failed:
        print(f"  [Security] Trivy failed — using Grype as primary source")
        critical = grype.get("CRITICAL", 0)
        high     = grype.get("HIGH",     0)
        medium   = grype.get("MEDIUM",   0)
        low      = grype.get("LOW",      0)
    else:
        critical = trivy.get("CRITICAL", 0)
        high     = trivy.get("HIGH",     0)
        medium   = trivy.get("MEDIUM",   0)
        low      = trivy.get("LOW",      0)

    # ── disagreement detection ───────────────────────────────────────
    if not trivy_failed:
        grype_critical = grype.get("CRITICAL", 0)
        if grype_critical > critical * 2:
            print(f"  [Security] Grype/Trivy disagreement — Grype={grype_critical} vs Trivy={critical} — using higher value")
            critical = max(critical, grype_critical)
            high     = max(high, grype.get("HIGH", 0))

    risk_score = round(min(1.0,
        critical * 0.40 +
        high     * 0.10 +
        medium   * 0.02 +
        low      * 0.005
    ), 2)

    blocking = critical > 0

    if not state.firmware_image:
        summary = "No image provided for scanning."
    elif blocking:
        summary = f"BLOCKING: {critical} critical CVE(s). Risk score: {risk_score}. Immediate remediation required."
    else:
        summary = f"PASSED: No critical CVEs. Risk score: {risk_score}. {high} high, {medium} medium, {low} low."

    report = SecurityReport(
        image_scanned = state.firmware_image or "none",
        critical_cves = critical,
        high_cves     = high,
        medium_cves   = medium,
        low_cves      = low,
        sbom_packages = sbom,
        risk_score    = risk_score,
        blocking      = blocking,
        summary       = summary,
        cve_details   = cves[:10],
    )

    status = "BLOCKING" if blocking else "PASSED"
    print(f"\n[Security Agent] ══ REPORT ══════════════════════")
    print(f"  Status     : {status}")
    print(f"  CVEs       : CRITICAL={critical} HIGH={high} MEDIUM={medium} LOW={low}")
    print(f"  Source     : {'Grype (Trivy failed)' if trivy_failed else 'Trivy + Grype'}")
    print(f"  SBOM       : {sbom} packages")
    print(f"  Risk Score : {risk_score}")
    print(f"  Summary    : {summary}")
    print(f"[Security Agent] ════════════════════════════════\n")

    return {"security_report": report}


def build_security_agent():
    graph = StateGraph(AgentState)

    graph.add_node("scan_image",     scan_image)
    graph.add_node("generate_sbom",  generate_sbom)
    graph.add_node("correlate_cves", correlate_cves)
    graph.add_node("build_report",   build_report)

    graph.set_entry_point("scan_image")
    graph.add_edge("scan_image",     "generate_sbom")
    graph.add_edge("generate_sbom",  "correlate_cves")
    graph.add_edge("correlate_cves", "build_report")
    graph.add_edge("build_report",   END)

    return graph.compile()

def run_security_agent(
    firmware_image:   str,
    firmware_version: str = "v1.0.0",
    device_profile:   str = "rpi4",
) -> SecurityReport:

    agent = build_security_agent()

    result = agent.invoke(
        AgentState(
            firmware_image   = firmware_image,
            firmware_version = firmware_version,
            device_profile   = device_profile,
        ),
        config={
            "run_name": f"security-agent-{firmware_version}",
            "tags":     ["security", device_profile, firmware_version],
            "metadata": {
                "firmware_version": firmware_version,
                "device_profile":   device_profile,
                "firmware_image":   firmware_image,
            }
        }
    )
    return result["security_report"]
