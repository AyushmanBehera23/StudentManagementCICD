import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    teacher: str
    student_count: int


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    roll_no: str
    full_name: str


class AttendanceRecord(BaseModel):
    student_id: int
    status: Literal["present", "absent", "late"]


class AttendanceBatch(BaseModel):
    date: dt.date
    session: Literal["morning", "afternoon"]
    records: list[AttendanceRecord] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def no_duplicate_students(self) -> "AttendanceBatch":
        ids = [r.student_id for r in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate student_id in request")
        return self


class AttendanceResult(BaseModel):
    class_id: int
    date: dt.date
    session: str
    recorded: int


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    student_id: int
    att_date: dt.date
    session: str
    status: str


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: dt.datetime
    actor: str
    action: str
    resource: str
    outcome: str
    detail: str
