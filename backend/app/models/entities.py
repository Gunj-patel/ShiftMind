from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class UploadedDocument(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20))  # csv | xlsx | pdf | text
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    rows_parsed: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    parse_notes: Mapped[str] = mapped_column(Text, default="")

    records: Mapped[list["ShiftRecord"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class ShiftRecord(Base):
    """One machine's report for one shift on one day."""

    __tablename__ = "shift_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    source_ref: Mapped[str] = mapped_column(String(255), default="")  # e.g. "daily.xlsx row 7"
    shift_date: Mapped[date] = mapped_column(Date, index=True)
    shift: Mapped[str] = mapped_column(String(10), index=True)  # morning | evening | night
    machine: Mapped[str] = mapped_column(String(50), index=True)
    product: Mapped[str] = mapped_column(String(100), default="")
    target_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    downtime_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejected_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_material_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    downtime_reason: Mapped[str] = mapped_column(Text, default="")
    quality_issue: Mapped[str] = mapped_column(Text, default="")
    maintenance_status: Mapped[str] = mapped_column(String(30), default="")  # pending|done|none|""
    notes: Mapped[str] = mapped_column(Text, default="")
    operator: Mapped[str] = mapped_column(String(100), default="")

    document: Mapped["UploadedDocument | None"] = relationship(back_populates="records")
    anomalies: Mapped[list["Anomaly"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("shift_records.id"), index=True)
    rule: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(10))  # info | warning | critical
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text, default="")  # human-readable numbers behind the flag

    record: Mapped["ShiftRecord"] = relationship(back_populates="anomalies")


class HandoverAction(Base):
    __tablename__ = "handover_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_date: Mapped[date] = mapped_column(Date, index=True)
    from_shift: Mapped[str] = mapped_column(String(10))
    machine: Mapped[str] = mapped_column(String(50), default="")
    priority: Mapped[str] = mapped_column(String(10))  # high | medium | low
    action: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")
    source_record_id: Mapped[int | None] = mapped_column(ForeignKey("shift_records.id"), nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
