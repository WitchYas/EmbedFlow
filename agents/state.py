from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class TestResult(BaseModel):
    test_name:   str
    passed:      bool
    detail:      str
    duration_ms: Optional[int]  = None
    metrics:     Optional[dict] = Field(default_factory=dict)

class TestReport(BaseModel):
    device_profile:   str
    firmware_version: str
    boot_success:     bool
    boot_time_s:      Optional[float]  = None
    tests_run:        int               = 0
    tests_passed:     int               = 0
    tests_failed:     int               = 0
    results:          List[TestResult]  = Field(default_factory=list)
    confidence:       float             = 0.0
    summary:          str               = ""

class SecurityReport(BaseModel):
    image_scanned:  str
    critical_cves:  int                = 0
    high_cves:      int                = 0
    medium_cves:    int                = 0
    low_cves:       int                = 0
    sbom_packages:  int                = 0
    risk_score:     float              = 0.0
    blocking:       bool               = False
    summary:        str                = ""
    cve_details:    List[dict]         = Field(default_factory=list)

class Decision(str, Enum):
    DEPLOY = "DEPLOY"
    BLOCK  = "BLOCK"
    REVIEW = "REVIEW"

class OrchestratorDecision(BaseModel):
    decision:          Decision
    confidence:        float
    justification:     str
    reflection_used:   bool                     = False
    reflection_rounds: int                      = 0
    test_report:       Optional[TestReport]     = None
    security_report:   Optional[SecurityReport] = None

class AgentState(BaseModel):
    firmware_version: str           = "v1.0.0"
    device_profile:   str           = "rpi4"
    simulator_url:    str           = "http://localhost:8080"
    firmware_image:   Optional[str] = None
    test_report:      Optional[TestReport]           = None
    security_report:  Optional[SecurityReport]       = None
    final_decision:   Optional[OrchestratorDecision] = None
    error:            Optional[str]        = None
    test_results:     List[TestResult]     = Field(default_factory=list)
    extras:           dict                 = Field(default_factory=dict)