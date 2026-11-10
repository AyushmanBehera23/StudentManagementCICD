import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # admin | teacher | student

    __table_args__ = (CheckConstraint("role in ('admin','teacher','student')", name="ck_role"),)


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    roll_no: Mapped[str] = mapped_column(String(20), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))


class SchoolClass(Base):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Enrollment(Base):
    __tablename__ = "enrollments"
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), primary_key=True)


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    att_date: Mapped[dt.date] = mapped_column(Date)
    session: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10))
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        # Membership is enforced by the database as well as by the API.
        ForeignKeyConstraint(
            ["class_id", "student_id"], ["enrollments.class_id", "enrollments.student_id"]
        ),
        # No duplicate entry for same student/class/date/session.
        UniqueConstraint("class_id", "student_id", "att_date", "session", name="uq_attendance"),
        CheckConstraint("status in ('present','absent','late')", name="ck_status"),
        CheckConstraint("session in ('morning','afternoon')", name="ck_session"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50))
    resource: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(20))  # success | denied | rejected | conflict
    detail: Mapped[str] = mapped_column(String(500), default="")
