from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Task = Literal["detection_2d", "instance_segmentation", "detection_3d"]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class ProjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    task: Task
    classes: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def clean(self):
        self.name = self.name.strip()
        self.classes = [c.strip() for c in self.classes]
        if not self.name or any(not c for c in self.classes) or len(set(self.classes)) != len(self.classes):
            raise ValueError("Tên dự án/lớp không được rỗng; lớp không được trùng")
        return self

class Box2D(StrictModel):
    kind: Literal["bbox2d"]
    xyxy: tuple[float, float, float, float]

    @model_validator(mode="after")
    def valid_box(self):
        x1, y1, x2, y2 = self.xyxy
        if not (0 <= x1 < x2 and 0 <= y1 < y2):
            raise ValueError("Khung phải có 0 <= x1 < x2 và 0 <= y1 < y2")
        return self

class Polygon(StrictModel):
    kind: Literal["polygon"]
    points: list[tuple[float, float]] = Field(min_length=3)

class Cuboid(StrictModel):
    kind: Literal["cuboid3d"]
    center: tuple[float, float, float]
    size_lwh: tuple[float, float, float]
    yaw: float
    frame: Literal["lidar"] = "lidar"

    @model_validator(mode="after")
    def valid_size(self):
        if any(v <= 0 for v in self.size_lwh):
            raise ValueError("Kích thước hộp 3D phải dương")
        return self

Geometry = Annotated[Box2D | Polygon | Cuboid, Field(discriminator="kind")]

class ObjectLabel(StrictModel):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    geometry: Geometry
    confidence: float | None = Field(default=None, ge=0, le=1)

class SampleLabels(StrictModel):
    asset_name: str
    objects: list[ObjectLabel]
    active_seconds: float | None = Field(default=None, ge=0)

class RunMetadata(StrictModel):
    model: str | None = None
    checkpoint: str | None = None
    gpu: str | None = None
    library_version: str | None = None
    inference_seconds: float | None = Field(default=None, ge=0)
    training_seconds: float | None = Field(default=None, ge=0)
    compute_cost_vnd: float | None = Field(default=None, ge=0)

class LabelBundle(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    task: Task
    name: str = Field(min_length=1, max_length=120)
    annotator: str | None = None
    parent_id: str | None = None
    run: RunMetadata = Field(default_factory=RunMetadata)
    samples: list[SampleLabels] = Field(min_length=1)
