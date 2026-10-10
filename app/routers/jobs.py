"""Endpoints for submitting jobs and viewing generated certificates."""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import certificate_generator
from app.database import get_db
from app.models import CertificateJob, Recipient
from app.schemas import JobCreate, JobCreated, JobProgress, RecipientResult

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _get_job_or_404(job_id: int, db: Session) -> CertificateJob:
    job = db.get(CertificateJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("", response_model=JobCreated, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobCreated:
    """Save a job, then generate one certificate for each recipient."""
    job = CertificateJob(
        status="processing",
        recipients=[
            Recipient(full_name=recipient.full_name, email=str(recipient.email))
            for recipient in payload.recipients
        ],
    )
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Could not save the certificate job."
        ) from exc

    # Catch errors per recipient so one failed PDF does not stop the rest.
    for recipient in job.recipients:
        try:
            recipient.pdf_path = certificate_generator.generate_certificate(
                recipient.full_name
            )
            recipient.generation_status = "succeeded"
            recipient.failure_message = None
        except Exception as exc:  # record a rendering or file-system failure
            recipient.generation_status = "failed"
            recipient.pdf_path = None
            recipient.failure_message = str(exc)[:500] or "Certificate generation failed."

        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=500, detail="Could not save certificate results."
            ) from exc

    failed_count = sum(
        recipient.generation_status == "failed" for recipient in job.recipients
    )
    if failed_count == 0:
        job.status = "completed"
    elif failed_count == len(job.recipients):
        job.status = "failed"
    else:
        job.status = "partial"
    try:
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Could not update the certificate job status."
        ) from exc

    return JobCreated(id=job.id, status=job.status)


@router.get("/{job_id}", response_model=JobProgress)
def get_job_progress(job_id: int, db: Session = Depends(get_db)) -> JobProgress:
    """Return a job's final/current status and recipient progress counts."""
    job = _get_job_or_404(job_id, db)
    recipients = db.scalars(
        select(Recipient).where(Recipient.job_id == job_id)
    ).all()
    succeeded = sum(item.generation_status == "succeeded" for item in recipients)
    failed = sum(item.generation_status == "failed" for item in recipients)
    total = len(recipients)
    finished = succeeded + failed
    progress = int(finished * 100 / total) if total else 100
    return JobProgress(
        id=job.id,
        status=job.status,
        total_recipients=total,
        succeeded=succeeded,
        failed=failed,
        progress_percent=progress,
    )


@router.get("/{job_id}/recipients", response_model=list[RecipientResult])
def list_job_recipients(job_id: int, db: Session = Depends(get_db)) -> list[RecipientResult]:
    """List generation results for all recipients in a job."""
    _get_job_or_404(job_id, db)
    recipients = db.scalars(
        select(Recipient).where(Recipient.job_id == job_id).order_by(Recipient.id)
    ).all()
    return [RecipientResult.model_validate(recipient) for recipient in recipients]


@router.get("/{job_id}/recipients/{recipient_id}/pdf")
def download_recipient_pdf(
    job_id: int, recipient_id: int, db: Session = Depends(get_db)
) -> FileResponse:
    """Download a successfully generated PDF for a recipient."""
    recipient = db.scalar(
        select(Recipient).where(
            Recipient.id == recipient_id, Recipient.job_id == job_id
        )
    )
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient not found.")
    if recipient.generation_status != "succeeded" or not recipient.pdf_path:
        raise HTTPException(status_code=404, detail="Certificate PDF not found.")

    # Generated filenames contain only 32 lowercase hex digits and .pdf. This
    # prevents a modified database value from escaping the output directory.
    if re.fullmatch(r"[0-9a-f]{32}\.pdf", recipient.pdf_path) is None:
        raise HTTPException(status_code=404, detail="Certificate PDF not found.")
    pdf_path = certificate_generator.OUTPUT_DIR / recipient.pdf_path
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Certificate PDF not found.")
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)
