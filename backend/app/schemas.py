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
    points: list[tuple[float, float]] = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def simple_polygon(self):
        points = self.points
        if len(set(points)) != len(points):
            raise ValueError('Polygon không được có đỉnh trùng; không lặp đỉnh đầu ở cuối')
        signed = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(points, points[1:]+points[:1]))
        if abs(signed) < 1e-9:
            raise ValueError('Polygon phải có diện tích dương')
        def cross(a, b, c):
            return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        def on(a, b, p):
            return min(a[0],b[0]) <= p[0] <= max(a[0],b[0]) and min(a[1],b[1]) <= p[1] <= max(a[1],b[1])
        for i, b in enumerate(points):
            a, c = points[i-1], points[(i+1) % len(points)]
            if cross(a,b,c) == 0 and (b[0]-a[0])*(c[0]-b[0])+(b[1]-a[1])*(c[1]-b[1]) < 0:
                raise ValueError('Các cạnh kề của polygon không được chồng lên nhau')
        edges = list(zip(points, points[1:]+points[:1]))
        for i, (a, b) in enumerate(edges):
            for j in range(i+1, len(edges)):
                if j == i+1 or (i == 0 and j == len(edges)-1):
                    continue
                c, d = edges[j]
                ab_c, ab_d, cd_a, cd_b = cross(a,b,c), cross(a,b,d), cross(c,d,a), cross(c,d,b)
                if (ab_c*ab_d < 0 and cd_a*cd_b < 0) or any((value == 0 and on(u,v,p)) for value,u,v,p in
                        [(ab_c,a,b,c), (ab_d,a,b,d), (cd_a,c,d,a), (cd_b,c,d,b)]):
                    raise ValueError('Polygon không được tự giao hoặc tự chạm')
        return self

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
