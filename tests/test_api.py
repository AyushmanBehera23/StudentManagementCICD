from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db
from app.main import app

from .conftest import PASSWORD

BODY = {
    "date": "2025-01-15",
    "session": "morning",
    "records": [{"student_id": 1, "status": "present"}, {"student_id": 2, "status": "absent"}],
}


def class_id(client, headers, name):
    return next(
        c["id"] for c in client.get("/classes", headers=headers).json() if c["name"] == name
    )


# ---------- health ----------
def test_health_and_readiness(client):
    assert client.get("/healthz").json()["status"] == "ok"
    r = client.get("/readyz")
    assert r.status_code == 200 and r.json()["database"] == "up"


def test_readiness_fails_when_database_down(client):
    class BrokenSession:
        def execute(self, *_a, **_k):
            raise SQLAlchemyError("db down")

    def broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    assert client.get("/healthz").status_code == 200  # liveness unaffected
    assert client.get("/readyz").status_code == 503
    app.dependency_overrides.clear()


# ---------- auth ----------
def test_login_bad_password(client):
    r = client.post("/auth/login", json={"username": "teacher_a", "password": "wrong"})
    assert r.status_code == 401


def test_requires_authentication(client):
    assert client.get("/classes").status_code == 401
    assert client.post("/classes/1/attendance", json=BODY).status_code == 401


# ---------- read endpoints ----------
def test_teacher_sees_only_assigned_classes(client, teacher_a, teacher_b, admin):
    assert {c["name"] for c in client.get("/classes", headers=teacher_a).json()} == {"7A", "7B"}
    assert {c["name"] for c in client.get("/classes", headers=teacher_b).json()} == {"8A"}
    assert len(client.get("/classes", headers=admin).json()) == 3


def test_list_students_of_class(client, teacher_a):
    cid = class_id(client, teacher_a, "7A")
    students = client.get(f"/classes/{cid}/students", headers=teacher_a).json()
    assert len(students) == 5 and students[0]["roll_no"] == "S001"


def test_unassigned_teacher_cannot_read_class(client, teacher_a, teacher_b):
    cid = class_id(client, teacher_a, "7A")
    assert client.get(f"/classes/{cid}/students", headers=teacher_b).status_code == 403


# ---------- ACCEPTANCE TEST 1: role / assignment restrictions ----------
def test_non_teacher_cannot_write_attendance(client, student, admin, teacher_a):
    cid = class_id(client, teacher_a, "7A")
    assert client.post(f"/classes/{cid}/attendance", json=BODY, headers=student).status_code == 403
    assert client.post(f"/classes/{cid}/attendance", json=BODY, headers=admin).status_code == 403


def test_unassigned_teacher_cannot_write_attendance(client, teacher_a, teacher_b):
    cid = class_id(client, teacher_a, "7A")
    r = client.post(f"/classes/{cid}/attendance", json=BODY, headers=teacher_b)
    assert r.status_code == 403
    assert client.get(f"/classes/{cid}/attendance", headers=teacher_a).json() == []


# ---------- domain rules ----------
def test_assigned_teacher_records_attendance(client, teacher_a):
    cid = class_id(client, teacher_a, "7A")
    r = client.post(f"/classes/{cid}/attendance", json=BODY, headers=teacher_a)
    assert r.status_code == 201 and r.json()["recorded"] == 2
    rows = client.get(f"/classes/{cid}/attendance?date=2025-01-15", headers=teacher_a).json()
    assert {(x["student_id"], x["status"]) for x in rows} == {(1, "present"), (2, "absent")}


def test_duplicate_same_date_session_rejected(client, teacher_a):
    cid = class_id(client, teacher_a, "7A")
    assert (
        client.post(f"/classes/{cid}/attendance", json=BODY, headers=teacher_a).status_code == 201
    )
    assert (
        client.post(f"/classes/{cid}/attendance", json=BODY, headers=teacher_a).status_code == 409
    )


def test_other_session_or_date_allowed(client, teacher_a):
    cid = class_id(client, teacher_a, "7A")
    client.post(f"/classes/{cid}/attendance", json=BODY, headers=teacher_a)
    afternoon = {**BODY, "session": "afternoon"}
    next_day = {**BODY, "date": "2025-01-16"}
    assert (
        client.post(f"/classes/{cid}/attendance", json=afternoon, headers=teacher_a).status_code
        == 201
    )
    assert (
        client.post(f"/classes/{cid}/attendance", json=next_day, headers=teacher_a).status_code
        == 201
    )


def test_student_not_in_class_rejected_and_nothing_saved(client, teacher_a):
    cid = class_id(client, teacher_a, "7A")
    bad = {
        **BODY,
        "records": [{"student_id": 1, "status": "present"}, {"student_id": 12, "status": "late"}],
    }
    r = client.post(f"/classes/{cid}/attendance", json=bad, headers=teacher_a)
    assert r.status_code == 422 and r.json()["detail"]["student_ids"] == [12]
    assert client.get(f"/classes/{cid}/attendance", headers=teacher_a).json() == []


def test_duplicate_student_in_payload_rejected(client, teacher_a):
    cid = class_id(client, teacher_a, "7A")
    bad = {**BODY, "records": [{"student_id": 1, "status": "present"}] * 2}
    assert client.post(f"/classes/{cid}/attendance", json=bad, headers=teacher_a).status_code == 422


def test_invalid_status_rejected(client, teacher_a):
    cid = class_id(client, teacher_a, "7A")
    bad = {**BODY, "records": [{"student_id": 1, "status": "sleeping"}]}
    assert client.post(f"/classes/{cid}/attendance", json=bad, headers=teacher_a).status_code == 422


def test_unknown_class_404(client, teacher_a):
    assert client.post("/classes/999/attendance", json=BODY, headers=teacher_a).status_code == 404


# ---------- audit log ----------
def test_audit_log_records_denial_and_success(client, teacher_a, teacher_b, admin):
    cid = class_id(client, teacher_a, "7A")
    client.post(f"/classes/{cid}/attendance", json=BODY, headers=teacher_b)  # denied
    client.post(f"/classes/{cid}/attendance", json=BODY, headers=teacher_a)  # success
    entries = client.get("/audit", headers=admin).json()
    attendance = [e for e in entries if e["action"] == "record_attendance"]
    assert {(e["actor"], e["outcome"]) for e in attendance} == {
        ("teacher_b", "denied"),
        ("teacher_a", "success"),
    }


def test_audit_log_admin_only(client, teacher_a):
    assert client.get("/audit", headers=teacher_a).status_code == 403


def test_failed_login_is_audited(client, admin):
    client.post("/auth/login", json={"username": "teacher_a", "password": PASSWORD + "x"})
    entries = client.get("/audit", headers=admin).json()
    assert any(e["action"] == "login" and e["outcome"] == "denied" for e in entries)


def test_metrics_endpoint(client):
    client.get("/healthz")
    assert "http_requests_total" in client.get("/metrics").text
