import enum
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text, Integer, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class RoleName(str, enum.Enum):
    validation_tester = "Validation Tester"
    validation_lead = "Validation Lead"
    qa = "QA"
    admin = "Administrator"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[RoleName] = mapped_column(Enum(RoleName), unique=True)

    users: Mapped[list["UserRole"]] = relationship(back_populates="role", cascade="all, delete-orphan")

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship(back_populates="users")

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str] = mapped_column(String(500))
    environment: Mapped[str] = mapped_column(String(100), default="non-prod")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Page(Base):
    __tablename__ = "pages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    url: Mapped[str] = mapped_column(String(800), index=True)
    title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    dom_hash: Mapped[str] = mapped_column(String(64), index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Element(Base):
    __tablename__ = "elements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), index=True)
    selector: Mapped[str] = mapped_column(String(800))
    role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    req_id: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="Active")

    __table_args__ = (UniqueConstraint("project_id", "req_id", "version", name="uq_req_version"),)


class LLMSettings(Base):
    __tablename__ = "llm_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="stub")  # stub|openai
    model: Mapped[str] = mapped_column(String(120), default="gpt-5")
    temperature: Mapped[float] = mapped_column(sa.Float, default=0.2)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=2500)
    strict_json: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TestBundleStatus(str, enum.Enum):
    draft = "Draft"
    approved = "Approved"
    rejected = "Rejected"

class TestBundle(Base):
    __tablename__ = "test_bundles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    version_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[TestBundleStatus] = mapped_column(Enum(TestBundleStatus), default=TestBundleStatus.draft)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    llm_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TestCase(Base):
    __tablename__ = "tests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("test_bundles.id"), index=True)
    test_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(300))
    objective: Mapped[str] = mapped_column(Text)
    preconditions: Mapped[str] = mapped_column(Text, default="[]") # JSON list as text for MVP
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    risk: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requirement_ids_json: Mapped[str] = mapped_column(Text, default="[]")

class TestStep(Base):
    __tablename__ = "test_steps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(40))
    selector_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    critical: Mapped[bool] = mapped_column(Boolean, default=False)

class RunStatus(str, enum.Enum):
    running = "Running"
    passed = "Passed"
    failed = "Failed"
    error = "Error"

class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("test_bundles.id"), index=True)
    started_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.running)
    environment_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")

class ResultStatus(str, enum.Enum):
    pass_ = "PASS"
    fail = "FAIL"

class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("test_steps.id"), index=True)
    status: Mapped[ResultStatus] = mapped_column(Enum(ResultStatus))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("results.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="screenshot")
    path: Mapped[str] = mapped_column(String(800))
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ApprovalStatus(str, enum.Enum):
    approved = "Approved"
    rejected = "Rejected"

class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(50))
    object_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(50))
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus))
    signed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_hash: Mapped[str] = mapped_column(String(64))

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    payload_json: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
