from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, desc, select

from app.domain.models import JobEventRecord, JobRecord, QuestionRecord, SetRecord, VariantRecord
from app.infra.db.models import JobEventRow, JobRow, QuestionRow, ReviewActionRow, SetRow, VariantRow
from app.infra.db.session import get_session_factory


class DatabaseStore:
    """Persistence layer backed by SQLAlchemy."""

    def __init__(self):
        self._session_factory = get_session_factory()

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}{uuid.uuid4().hex[:16]}"

    @staticmethod
    def _to_set_record(row: SetRow) -> SetRecord:
        return SetRecord(
            set_id=row.public_id,
            status=row.status,
            title=row.title,
            source_filename=row.source_filename,
            source_mime=row.source_mime,
            source_size=row.source_size,
            question_count=row.question_count,
        )

    @staticmethod
    def _to_job_record(row: JobRow, set_public_id: str) -> JobRecord:
        return JobRecord(
            job_id=row.public_id,
            set_id=set_public_id,
            status=row.status,
            stage=row.stage,
            percent=row.percent,
            error_message=row.error_message,
        )

    @staticmethod
    def _to_job_event_record(job_public_id: str, row: JobEventRow) -> JobEventRecord:
        created_at = row.created_at.isoformat() if row.created_at else datetime.now(timezone.utc).isoformat()
        return JobEventRecord(
            job_id=job_public_id,
            status=row.status,  # type: ignore[arg-type]
            stage=row.stage,
            percent=row.percent,
            created_at=created_at,
        )

    @staticmethod
    def _append_job_event(*, db, job_row: JobRow) -> None:
        db.add(
            JobEventRow(
                job_id=job_row.id,
                status=job_row.status,
                stage=job_row.stage,
                percent=job_row.percent,
            )
        )

    @staticmethod
    def _to_question_record(row: QuestionRow, set_public_id: str) -> QuestionRecord:
        return QuestionRecord(
            question_id=row.public_id,
            set_id=set_public_id,
            number_label=row.number_label,
            order_index=row.order_index,
            review_status=row.review_status,
            confidence=row.confidence,
            metadata=dict(row.metadata_json or {}),
            structure=dict(row.structure_json or {}),
            ocr_text=row.ocr_text,
        )

    @staticmethod
    def _to_variant_record(row: VariantRow, question_public_id: str) -> VariantRecord:
        created_at = row.created_at.isoformat() if row.created_at else datetime.now(timezone.utc).isoformat()
        return VariantRecord(
            variant_id=row.public_id,
            question_id=question_public_id,
            variant_type=row.variant_type,
            body=row.body,
            answer=row.answer,
            explanation=row.explanation,
            model=row.model,
            created_at=created_at,
        )

    def create_document(self, *, filename: str | None, mime: str | None, size: int | None) -> dict[str, str]:
        with self._session_factory() as db:
            set_id = self._new_id("set_")
            job_id = self._new_id("job_")
            document_id = self._new_id("doc_")

            set_row = SetRow(
                public_id=set_id,
                status="extracting",
                title=filename or "Untitled set",
                source_filename=filename,
                source_mime=mime,
                source_size=size,
                question_count=0,
            )
            db.add(set_row)
            db.flush()

            job_row = JobRow(
                public_id=job_id,
                set_id=set_row.id,
                status="queued",
                stage="queued",
                percent=0.0,
            )

            db.add(job_row)
            db.flush()
            self._append_job_event(db=db, job_row=job_row)
            db.commit()

            return {
                "documentId": document_id,
                "setId": set_id,
                "jobId": job_id,
                "status": "accepted",
            }

    def mark_job_running(self, *, job_id: str, stage: str, percent: float) -> bool:
        with self._session_factory() as db:
            row = db.execute(select(JobRow).where(JobRow.public_id == job_id)).scalar_one_or_none()
            if row is None:
                return False
            row.status = "running"
            row.stage = stage
            row.percent = percent
            row.error_message = None
            self._append_job_event(db=db, job_row=row)
            db.commit()
            return True

    def complete_job(
        self,
        *,
        job_id: str,
        stage: str,
        percent: float,
        set_status: str,
        questions: list[dict[str, Any]],
    ) -> bool:
        with self._session_factory() as db:
            row = (
                db.execute(select(JobRow, SetRow).join(SetRow, JobRow.set_id == SetRow.id).where(JobRow.public_id == job_id))
                .one_or_none()
            )
            if row is None:
                return False

            job_row, set_row = row
            job_row.status = "done"
            job_row.stage = stage
            job_row.percent = percent
            job_row.error_message = None
            self._append_job_event(db=db, job_row=job_row)

            db.execute(delete(QuestionRow).where(QuestionRow.set_id == set_row.id))

            created = 0
            for item in questions:
                question_row = QuestionRow(
                    public_id=self._new_id("q_"),
                    set_id=set_row.id,
                    number_label=item.get("number_label"),
                    order_index=int(item.get("order_index", 1)),
                    review_status=str(item.get("review_status") or "auto_flagged"),
                    confidence=float(item["confidence"]) if item.get("confidence") is not None else None,
                    ocr_text=item.get("ocr_text"),
                    metadata_json=dict(item.get("metadata") or {}),
                    structure_json=dict(item.get("structure") or {}),
                )
                db.add(question_row)
                created += 1

            set_row.question_count = created
            set_row.status = set_status

            db.commit()
            return True

    def fail_job(self, *, job_id: str, error_message: str) -> bool:
        with self._session_factory() as db:
            row = (
                db.execute(select(JobRow, SetRow).join(SetRow, JobRow.set_id == SetRow.id).where(JobRow.public_id == job_id))
                .one_or_none()
            )
            if row is None:
                return False

            job_row, set_row = row
            job_row.status = "failed"
            job_row.stage = "error"
            job_row.error_message = error_message
            job_row.percent = min(job_row.percent or 0.0, 99.0)
            self._append_job_event(db=db, job_row=job_row)
            set_row.status = "error"
            db.commit()
            return True

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._session_factory() as db:
            stmt = select(JobRow, SetRow.public_id).join(SetRow, JobRow.set_id == SetRow.id).where(JobRow.public_id == job_id)
            row = db.execute(stmt).one_or_none()
            if row is None:
                return None
            job_row, set_public_id = row
            return self._to_job_record(job_row, set_public_id)

    def list_job_events(self, job_id: str) -> list[JobEventRecord]:
        with self._session_factory() as db:
            row = db.execute(select(JobRow).where(JobRow.public_id == job_id)).scalar_one_or_none()
            if row is None:
                return []

            event_rows = (
                db.execute(
                    select(JobEventRow)
                    .where(JobEventRow.job_id == row.id)
                    .order_by(JobEventRow.created_at.asc(), JobEventRow.id.asc())
                )
                .scalars()
                .all()
            )
            return [self._to_job_event_record(row.public_id, item) for item in event_rows]

    def get_set(self, set_id: str) -> SetRecord | None:
        with self._session_factory() as db:
            row = db.execute(select(SetRow).where(SetRow.public_id == set_id)).scalar_one_or_none()
            if row is None:
                return None
            return self._to_set_record(row)

    def delete_set(self, set_id: str) -> bool:
        with self._session_factory() as db:
            row = db.execute(select(SetRow).where(SetRow.public_id == set_id)).scalar_one_or_none()
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True

    def get_latest_job_id_for_set(self, set_id: str) -> str | None:
        with self._session_factory() as db:
            row = db.execute(select(SetRow.id).where(SetRow.public_id == set_id)).scalar_one_or_none()
            if row is None:
                return None

            job_public_id = (
                db.execute(
                    select(JobRow.public_id)
                    .where(JobRow.set_id == row)
                    .order_by(JobRow.created_at.desc(), JobRow.id.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return job_public_id

    def list_sets(self, *, limit: int, offset: int, status: str | None = None) -> list[SetRecord]:
        with self._session_factory() as db:
            stmt = select(SetRow)
            if status:
                stmt = stmt.where(SetRow.status == status)
            stmt = stmt.order_by(desc(SetRow.created_at), desc(SetRow.id)).limit(limit).offset(offset)
            rows = db.execute(stmt).scalars().all()
            return [self._to_set_record(row) for row in rows]

    def list_questions_for_set(self, set_id: str) -> list[QuestionRecord]:
        with self._session_factory() as db:
            set_row = db.execute(select(SetRow).where(SetRow.public_id == set_id)).scalar_one_or_none()
            if set_row is None:
                return []

            stmt = (
                select(QuestionRow)
                .where(QuestionRow.set_id == set_row.id)
                .order_by(QuestionRow.order_index.asc(), QuestionRow.id.asc())
            )
            rows = db.execute(stmt).scalars().all()
            return [self._to_question_record(row, set_row.public_id) for row in rows]

    def get_question(self, question_id: str) -> QuestionRecord | None:
        with self._session_factory() as db:
            stmt = (
                select(QuestionRow, SetRow.public_id)
                .join(SetRow, QuestionRow.set_id == SetRow.id)
                .where(QuestionRow.public_id == question_id)
            )
            row = db.execute(stmt).one_or_none()
            if row is None:
                return None
            q_row, set_public_id = row
            return self._to_question_record(q_row, set_public_id)

    def list_review_queue(self, *, review_status: str = "auto_flagged") -> list[QuestionRecord]:
        with self._session_factory() as db:
            stmt = (
                select(QuestionRow, SetRow.public_id)
                .join(SetRow, QuestionRow.set_id == SetRow.id)
                .where(QuestionRow.review_status == review_status)
                .order_by(QuestionRow.id.asc())
            )
            rows = db.execute(stmt).all()
            return [self._to_question_record(q_row, set_public_id) for q_row, set_public_id in rows]

    def review_question(
        self,
        *,
        question_id: str,
        reviewer: str,
        review_status: str,
        note: str | None,
        metadata_patch: dict | None,
    ) -> QuestionRecord | None:
        with self._session_factory() as db:
            stmt = (
                select(QuestionRow, SetRow)
                .join(SetRow, QuestionRow.set_id == SetRow.id)
                .where(QuestionRow.public_id == question_id)
            )
            row = db.execute(stmt).one_or_none()
            if row is None:
                return None

            question_row, set_row = row
            question_row.review_status = review_status
            if metadata_patch:
                merged = dict(question_row.metadata_json or {})
                merged.update(metadata_patch)
                question_row.metadata_json = merged

            review_action = ReviewActionRow(
                question_id=question_row.id,
                reviewer=reviewer,
                review_status=review_status,
                note=note,
            )
            db.add(review_action)

            set_questions = db.execute(select(QuestionRow).where(QuestionRow.set_id == set_row.id)).scalars().all()
            if set_questions:
                if all(q.review_status in ("approved", "auto_ok") for q in set_questions):
                    set_row.status = "ready"
                elif any(q.review_status in ("auto_flagged", "rejected") for q in set_questions):
                    set_row.status = "needs_review"

            db.commit()
            db.refresh(question_row)
            db.refresh(set_row)

            return self._to_question_record(question_row, set_row.public_id)

    def reprocess_question(self, question_id: str) -> QuestionRecord | None:
        with self._session_factory() as db:
            stmt = (
                select(QuestionRow, SetRow)
                .join(SetRow, QuestionRow.set_id == SetRow.id)
                .where(QuestionRow.public_id == question_id)
            )
            row = db.execute(stmt).one_or_none()
            if row is None:
                return None

            question_row, set_row = row
            metadata = dict(question_row.metadata_json or {})
            metadata["reprocessed"] = True
            metadata["ocr_source"] = "mock_reprocess"
            metadata["reprocessed_at"] = datetime.now(timezone.utc).isoformat()

            question_row.metadata_json = metadata
            question_row.review_status = "auto_flagged"
            question_row.confidence = 0.8

            db.commit()
            db.refresh(question_row)

            return self._to_question_record(question_row, set_row.public_id)

    def list_variants_for_question(self, question_id: str) -> list[VariantRecord]:
        with self._session_factory() as db:
            row = db.execute(select(QuestionRow).where(QuestionRow.public_id == question_id)).scalar_one_or_none()
            if row is None:
                return []

            items = (
                db.execute(
                    select(VariantRow)
                    .where(VariantRow.question_id == row.id)
                    .order_by(VariantRow.created_at.desc(), VariantRow.id.desc())
                )
                .scalars()
                .all()
            )
            return [self._to_variant_record(item, row.public_id) for item in items]

    def create_variant_for_question(
        self,
        *,
        question_id: str,
        variant_type: str,
        body: str,
        answer: str | None,
        explanation: str | None,
        model: str | None,
    ) -> VariantRecord | None:
        with self._session_factory() as db:
            row = db.execute(select(QuestionRow).where(QuestionRow.public_id == question_id)).scalar_one_or_none()
            if row is None:
                return None

            variant_row = VariantRow(
                public_id=self._new_id("var_"),
                question_id=row.id,
                variant_type=variant_type,
                body=body,
                answer=answer,
                explanation=explanation,
                model=model,
            )
            db.add(variant_row)
            db.commit()
            db.refresh(variant_row)
            return self._to_variant_record(variant_row, row.public_id)
