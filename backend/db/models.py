from datetime import datetime, timezone
import uuid
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    memberships = relationship("TenantMembership", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    projects = relationship("Project", back_populates="tenant", cascade="all, delete-orphan")
    memberships = relationship("TenantMembership", back_populates="tenant", cascade="all, delete-orphan")


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False, default="member")  # owner, admin, member
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("User", back_populates="memberships")
    tenant = relationship("Tenant", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant_membership"),
        Index("ix_tenant_memberships_user_tenant", "user_id", "tenant_id"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    session_token_hash = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    active_tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    active_project_id = Column(String(64), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)

    user = relationship("User", back_populates="sessions")
    active_tenant = relationship("Tenant")
    active_project = relationship("Project")


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
    role = Column(String(32), nullable=False, default="inference")
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


class SemanticVectorEntry(Base):
    __tablename__ = "semantic_cache_entries"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    scope_hash = Column(String(64), nullable=False, index=True)
    exact_request_hash = Column(String(64), nullable=False, unique=True, index=True)
    tenant_id = Column(String(64), nullable=True, index=True)
    project_id = Column(String(64), nullable=True, index=True)

    provider = Column(String(64), nullable=False, default="unknown")
    model = Column(String(128), nullable=False, default="unknown")
    system_prompt = Column(Text, nullable=True)
    input_text = Column(Text, nullable=True)

    namespace = Column(String(128), nullable=True, index=True)
    tags = Column(JSON, nullable=True)

    response_payload = Column(JSON, nullable=False)
    embedding = Column(Vector(384), nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    ttl_seconds = Column(Integer, nullable=True, default=86400)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    __table_args__ = (
        Index("ix_semantic_scope_created", "scope_hash", "created_at"),
        Index("ix_semantic_tenant_scope", "tenant_id", "scope_hash"),
    )
