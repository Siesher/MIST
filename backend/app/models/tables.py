"""SQLAlchemy ORM models for MITS."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class UserTable(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    preferred_mode: Mapped[str] = mapped_column(String(30), default="guided_learning")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sessions: Mapped[list["SessionTable"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshTokenTable"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SessionTable(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(30), default="guided_learning")
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_solved: Mapped[bool] = mapped_column(Boolean, default=False)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    task_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["UserTable | None"] = relationship(back_populates="sessions")
    messages: Mapped[list["MessageTable"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="MessageTable.timestamp"
    )


class MessageTable(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    move_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    thinking: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["SessionTable"] = relationship(back_populates="messages")


class RefreshTokenTable(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["UserTable"] = relationship(back_populates="refresh_tokens")


class ExperimentTable(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    control_mode: Mapped[str] = mapped_column(String(30), default="chat")
    treatment_mode: Mapped[str] = mapped_column(String(30), default="guided_learning")
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active, completed, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    participants: Mapped[list["ExperimentParticipantTable"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentParticipantTable(Base):
    __tablename__ = "experiment_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    experiment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiments.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    group: Mapped[str] = mapped_column(String(20), nullable=False)  # control, treatment
    pre_test_score: Mapped[float | None] = mapped_column(nullable=True)
    post_test_score: Mapped[float | None] = mapped_column(nullable=True)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    experiment: Mapped["ExperimentTable"] = relationship(back_populates="participants")
    user: Mapped["UserTable"] = relationship()


class SourceTable(Base):
    """Uploaded knowledge source — feeds Knowledge Forge via LLM extraction."""

    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="text")  # text | pdf | url | notes
    domain: Mapped[str] = mapped_column(String(32), default="math")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default="pending"
    )  # pending | extracting | extracted | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    nodes_extracted: Mapped[int] = mapped_column(Integer, default=0)
    edges_extracted: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
