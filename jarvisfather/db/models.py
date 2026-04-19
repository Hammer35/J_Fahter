import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserTier(str, enum.Enum):
    free = "free"
    pro = "pro"


class DeploymentStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    tier: Mapped[UserTier] = mapped_column(Enum(UserTier), default=UserTier.free)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    servers: Mapped[list["UserServer"]] = relationship(back_populates="user")


class UserServer(Base):
    __tablename__ = "user_servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ip: Mapped[str] = mapped_column(String(45))
    ssh_user: Mapped[str] = mapped_column(String(64))
    ssh_pass_enc: Mapped[str] = mapped_column(Text)       # зашифровано Fernet
    bot_token_enc: Mapped[str] = mapped_column(Text)      # зашифровано Fernet
    claude_auth_enc: Mapped[str] = mapped_column(Text)    # зашифровано Fernet
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="servers")
    deployments: Mapped[list["Deployment"]] = relationship(back_populates="server")


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    server_id: Mapped[int] = mapped_column(ForeignKey("user_servers.id"))
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(DeploymentStatus), default=DeploymentStatus.pending
    )
    log: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    server: Mapped["UserServer"] = relationship(back_populates="deployments")


class Configuration(Base):
    __tablename__ = "configurations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    business_type: Mapped[str] = mapped_column(String(64))
    tasks: Mapped[str] = mapped_column(Text)         # JSON: ["marketing", "email"]
    agents: Mapped[str] = mapped_column(Text)        # JSON: ["marketing-content"]
    skills: Mapped[str] = mapped_column(Text)        # JSON: ["summarize"]
    success_score: Mapped[float] = mapped_column(Float, default=0.0)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON вектор
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
