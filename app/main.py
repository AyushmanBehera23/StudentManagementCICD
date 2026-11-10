import datetime as dt
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from . import audit, models, schemas
from .auth import create_token, current_user, verify_password
from .config import settings
from .db import SessionLocal, engine, get_db
from .logging_conf import configure_logging
from .seed import seed

configure_logging(settings.log_level)
log = logging.getLogger("app")

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["route"])


def init_db() -> None:
    models.Base.metadata.create_all(engine)
    if settings.seed_on_start:
        with SessionLocal() as db:
            if seed(db, settings.seed_password):
                log.info("seeded synthetic data")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    log.info("startup complete", extra={"version": settings.app_version})
    yield


app = FastAPI(title="School Attendance API", version=settings.app_version, lifespan=lifespan)


@app.middleware("http")
async def observe(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    finally:
        duration = time.perf_counter() - start
        route_obj = request.scope.get("route")
        route = getattr(route_obj, "path", "unmatched")
        REQUESTS.labels(request.method, route, str(status)).inc()
        LATENCY.labels(route).observe(duration)
        if route not in ("/healthz", "/readyz", "/metrics"):
            log.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round(duration * 1000, 1),
                },
            )


# ---------- health / ops ----------
@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    """Liveness: process is up. Does not touch dependencies."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/readyz", tags=["ops"])
def readyz(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness: can we serve traffic (database reachable)?"""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        log.error("readiness check failed: database unreachable")
        response.status_code = 503
        return {"status": "unavailable", "database": "down"}
    return {"status": "ready", "database": "up"}


@app.get("/metrics", tags=["ops"], include_in_schema=False)
def metrics() -> Response:
    # Not exposed through the reverse proxy (see deploy/nginx/default.conf).
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------- auth ----------
@app.post("/auth/login", response_model=schemas.TokenResponse, tags=["auth"])
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)) -> schemas.TokenResponse:
    user = db.scalar(select(models.User).where(models.User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        audit.record(
            db, actor=body.username[:50], action="login", resource="auth", outcome="denied"
        )
        raise HTTPException(status_code=401, detail="invalid credentials")
    audit.record(db, actor=user.username, action="login", resource="auth", outcome="success")
    return schemas.TokenResponse(access_token=create_token(user))


# ---------- helpers ----------
def _get_class_or_404(db: Session, class_id: int) -> models.SchoolClass:
    klass = db.get(models.SchoolClass, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="class not found")
    return klass


def _require_class_read(db: Session, user: models.User, class_id: int) -> models.SchoolClass:
    if user.role not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="forbidden")
    klass = _get_class_or_404(db, class_id)
    if user.role == "teacher" and klass.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="not assigned to this class")
    return klass


# ---------- read endpoints ----------
@app.get("/classes", response_model=list[schemas.ClassOut], tags=["classes"])
def list_classes(
    user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> list[schemas.ClassOut]:
    if user.role not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="forbidden")
    q = (
        select(
            models.SchoolClass.id,
            models.SchoolClass.name,
            models.User.username,
            func.count(models.Enrollment.student_id),
        )
        .join(models.User, models.User.id == models.SchoolClass.teacher_id)
        .outerjoin(models.Enrollment, models.Enrollment.class_id == models.SchoolClass.id)
        .group_by(models.SchoolClass.id, models.SchoolClass.name, models.User.username)
        .order_by(models.SchoolClass.id)
    )
    if user.role == "teacher":
        q = q.where(models.SchoolClass.teacher_id == user.id)
    return [
        schemas.ClassOut(id=i, name=n, teacher=t, student_count=c) for i, n, t, c in db.execute(q)
    ]


@app.get("/classes/{class_id}/students", response_model=list[schemas.StudentOut], tags=["classes"])
def list_students(
    class_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> list[models.Student]:
    _require_class_read(db, user, class_id)
    q = (
        select(models.Student)
        .join(models.Enrollment, models.Enrollment.student_id == models.Student.id)
        .where(models.Enrollment.class_id == class_id)
        .order_by(models.Student.roll_no)
    )
    return list(db.scalars(q))


@app.get(
    "/classes/{class_id}/attendance",
    response_model=list[schemas.AttendanceOut],
    tags=["attendance"],
)
def list_attendance(
    class_id: int,
    date: dt.date | None = None,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[models.Attendance]:
    _require_class_read(db, user, class_id)
    q = select(models.Attendance).where(models.Attendance.class_id == class_id)
    if date:
        q = q.where(models.Attendance.att_date == date)
    return list(db.scalars(q.order_by(models.Attendance.att_date, models.Attendance.student_id)))


# ---------- write endpoint ----------
@app.post(
    "/classes/{class_id}/attendance",
    response_model=schemas.AttendanceResult,
    status_code=201,
    tags=["attendance"],
)
def record_attendance(
    class_id: int,
    body: schemas.AttendanceBatch,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
) -> schemas.AttendanceResult:
    resource = f"class:{class_id}"
    action = "record_attendance"

    # 1. Role restriction: only teachers write attendance.
    if user.role != "teacher":
        audit.record(
            db,
            actor=user.username,
            action=action,
            resource=resource,
            outcome="denied",
            detail=f"role={user.role}",
        )
        raise HTTPException(status_code=403, detail="only teachers can record attendance")

    klass = _get_class_or_404(db, class_id)

    # 2. Teacher must be assigned to this class.
    if klass.teacher_id != user.id:
        audit.record(
            db,
            actor=user.username,
            action=action,
            resource=resource,
            outcome="denied",
            detail="teacher not assigned to class",
        )
        raise HTTPException(status_code=403, detail="not assigned to this class")

    # 3. Every student must be a member of this class.
    wanted = {r.student_id for r in body.records}
    members = set(
        db.scalars(
            select(models.Enrollment.student_id).where(models.Enrollment.class_id == class_id)
        )
    )
    not_members = sorted(wanted - members)
    if not_members:
        audit.record(
            db,
            actor=user.username,
            action=action,
            resource=resource,
            outcome="rejected",
            detail=f"non-member students: {not_members}",
        )
        raise HTTPException(
            status_code=422, detail={"error": "students not in class", "student_ids": not_members}
        )

    # 4. No duplicate entry for same date/session.
    dupes = sorted(
        db.scalars(
            select(models.Attendance.student_id).where(
                models.Attendance.class_id == class_id,
                models.Attendance.att_date == body.date,
                models.Attendance.session == body.session,
                models.Attendance.student_id.in_(wanted),
            )
        )
    )
    if dupes:
        audit.record(
            db,
            actor=user.username,
            action=action,
            resource=resource,
            outcome="conflict",
            detail=f"duplicate for {body.date} {body.session}: {dupes}",
        )
        raise HTTPException(
            status_code=409, detail={"error": "attendance already recorded", "student_ids": dupes}
        )

    db.add_all(
        models.Attendance(
            class_id=class_id,
            student_id=r.student_id,
            att_date=body.date,
            session=body.session,
            status=r.status,
            recorded_by=user.id,
        )
        for r in body.records
    )
    try:
        db.commit()  # all-or-nothing; unique constraint also guards concurrent requests
    except IntegrityError:
        db.rollback()
        audit.record(
            db,
            actor=user.username,
            action=action,
            resource=resource,
            outcome="conflict",
            detail="integrity error (concurrent duplicate)",
        )
        raise HTTPException(status_code=409, detail="attendance already recorded") from None

    audit.record(
        db,
        actor=user.username,
        action=action,
        resource=resource,
        outcome="success",
        detail=f"{len(body.records)} records {body.date} {body.session}",
    )
    return schemas.AttendanceResult(
        class_id=class_id, date=body.date, session=body.session, recorded=len(body.records)
    )


# ---------- audit ----------
@app.get("/audit", response_model=list[schemas.AuditOut], tags=["audit"])
def read_audit(
    limit: int = 100, user: models.User = Depends(current_user), db: Session = Depends(get_db)
) -> list[models.AuditLog]:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    limit = max(1, min(limit, 500))
    return list(
        db.scalars(select(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(limit))
    )
