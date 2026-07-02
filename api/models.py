from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from api.database import Base
import uuid

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firmware_hash = Column(String(64), nullable=False)
    device_profile = Column(String(50), nullable=False, default="rpi4")
    status = Column(String(20), nullable=False, default="running")
    final_decision = Column(String(20), nullable=True)   # deploy / block / review
    confidence = Column(Float, nullable=True)
    langsmith_trace_url = Column(Text, nullable=True)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))
    test_name = Column(String(100), nullable=False)
    passed = Column(Boolean, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    metrics = Column(JSONB, nullable=True)   # CPU, RAM, latency etc

class SbomEntry(Base):
    __tablename__ = "sbom_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))
    package_name = Column(String(200), nullable=False)
    version = Column(String(50), nullable=True)
    license = Column(String(100), nullable=True)
    cve_count = Column(Integer, default=0)
    highest_cvss = Column(Float, default=0.0)

class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))
    agent_name = Column(String(50), nullable=False)
    input_state = Column(JSONB, nullable=True)
    output = Column(JSONB, nullable=True)
    llm_model = Column(String(50), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    reflection_triggered = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())