from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import SQLModel, Field

def uid():
    return str(uuid4())

def now():
    return datetime.now(timezone.utc)

class Project(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    name: str
    task: str
    classes: list[str] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=now)

class Asset(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    name: str
    kind: str
    storage_name: str
    width: int | None = None
    height: int | None = None
    size_bytes: int

class LabelSet(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    source: str  # ground_truth | ai | manual | assisted
    name: str
    annotator: str | None = None
    parent_id: str | None = Field(default=None, foreign_key="labelset.id")
    payload: dict = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=now)
