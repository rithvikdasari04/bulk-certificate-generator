"""Database models for certificate jobs and their recipients."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CertificateJob(Base):
    """A request to generate certificates for a group of recipients."""

    __tablename__ = "certificate_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    recipients: Mapped[list["Recipient"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Recipient(Base):
    """One person included in a certificate generation job."""

    __tablename__ = "recipients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    generation_status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("certificate_jobs.id", ondelete="CASCADE"), nullable=False
    )
    job: Mapped[CertificateJob] = relationship(back_populates="recipients")
