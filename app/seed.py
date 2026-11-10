"""Synthetic seed data only. No real personal data."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .auth import hash_password

STUDENTS = [
    ("S001", "Aarav Synthetic"),
    ("S002", "Diya Example"),
    ("S003", "Kabir Sample"),
    ("S004", "Meera Test"),
    ("S005", "Rohan Demo"),
    ("S006", "Sana Fake"),
    ("S007", "Tara Mock"),
    ("S008", "Veer Dummy"),
    ("S009", "Isha Placeholder"),
    ("S010", "Neel Testcase"),
    ("S011", "Anaya Sandbox"),
    ("S012", "Yash Fixture"),
]


def seed(db: Session, password: str) -> bool:
    """Seed if the database is empty. Returns True if data was inserted."""
    if db.scalar(select(func.count()).select_from(models.User)):
        return False
    pw = hash_password(password)
    admin = models.User(username="admin1", password_hash=pw, role="admin")
    t_a = models.User(username="teacher_a", password_hash=pw, role="teacher")
    t_b = models.User(username="teacher_b", password_hash=pw, role="teacher")
    stu = models.User(username="student1", password_hash=pw, role="student")
    db.add_all([admin, t_a, t_b, stu])
    db.flush()

    students = [models.Student(roll_no=r, full_name=n) for r, n in STUDENTS]
    classes = [
        models.SchoolClass(name="7A", teacher_id=t_a.id),
        models.SchoolClass(name="7B", teacher_id=t_a.id),
        models.SchoolClass(name="8A", teacher_id=t_b.id),
    ]
    db.add_all(students + classes)
    db.flush()

    layout = {0: students[0:5], 1: students[5:8], 2: students[8:12]}
    for idx, members in layout.items():
        for s in members:
            db.add(models.Enrollment(class_id=classes[idx].id, student_id=s.id))
    db.commit()
    return True
