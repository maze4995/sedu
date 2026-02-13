"""Repository helpers for sets."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.set import Set
from app.utils.ids import new_public_id


def create_set(
    db: Session,
    *,
    source_filename: str | None,
    source_mime: str | None,
    source_size: int | None,
    title: str | None = None,
) -> Set:
    set_obj = Set(
        public_id=new_public_id("set_"),
        status="created",
        title=title,
        file_name=source_filename,
        source_filename=source_filename,
        source_mime=source_mime,
        source_size=source_size,
    )
    db.add(set_obj)
    db.commit()
    db.refresh(set_obj)
    return set_obj


def get_set_by_public_id(db: Session, public_id: str) -> Set | None:
    stmt = select(Set).where(Set.public_id == public_id)
    return db.execute(stmt).scalar_one_or_none()


def list_sets(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
) -> list[Set]:
    stmt = select(Set)
    if status:
        stmt = stmt.where(Set.status == status)
    stmt = stmt.order_by(Set.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def update_set_status(db: Session, set_obj: Set, status: str) -> Set:
    set_obj.status = status
    db.add(set_obj)
    db.commit()
    db.refresh(set_obj)
    return set_obj
