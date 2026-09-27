from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    projects = relationship("Project", back_populates="tenant", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    tenant = relationship("Tenant", back_populates="projects")
    api_keys = relationship("APIKey", back_populates="project", cascade="all, delete-orphan")


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    key_prefix = Column(String(32), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False, default="Default Key")
    role = Column(String(32), nullable=False, default="admin")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="api_keys")


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    request_id = Column(String(64), nullable=False, unique=True, index=True)
    tenant_id = Column(String(64), nullable=False)
    project_id = Column(String(64), nullable=False)

    provider = Column(String(64), nullable=False)
    requested_model = Column(String(128), nullable=False)
    actual_model = Column(String(128), nullable=False)

    cache_status = Column(String(32), nullable=False)  # EXACT_HIT, L2_HIT, MISS, BYPASS, ERROR
    exact_request_hash = Column(String(64), nullable=False)

    # Phase 2 Semantic Metrics
    similarity_score = Column(Float, nullable=True)
    guardrail_status = Column(Boolean, nullable=True)
    guardrail_failed_check = Column(String(255), nullable=True)

    gateway_latency_ms = Column(Float, nullable=False)
    upstream_latency_ms = Column(Float, nullable=True)
    exact_cache_lookup_ms = Column(Float, nullable=False, default=0.0)

    upstream_called = Column(Boolean, nullable=False, default=False)

    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_request_logs_project_created", "project_id", "created_at"),
        Index("ix_request_logs_tenant_created", "tenant_id", "created_at"),
    )
