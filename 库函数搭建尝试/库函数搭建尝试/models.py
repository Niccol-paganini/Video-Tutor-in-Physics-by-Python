"""统一的题目、物体和运动描述数据模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SUPPORTED_SHAPES = {"point", "circle", "rectangle", "square"}
SUPPORTED_MOTIONS = {
    "static",
    "linear",
    "projectile",
    "circular",
    "custom",
    "semicircle_launch",
    "block_plank",
    "collision_1d",
}


@dataclass(slots=True)
class MotionDefinition:
    kind: str = "linear"
    x: str = "x0 + vx*t"
    y: str = "y0 + vy*t"
    parameters: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MotionDefinition":
        data = data or {}
        kind = str(data.get("kind", "linear")).strip().lower()
        if kind not in SUPPORTED_MOTIONS:
            kind = "custom" if data.get("x") or data.get("y") else "linear"
        return cls(
            kind=kind,
            x=str(data.get("x", "x0 + vx*t")),
            y=str(data.get("y", "y0 + vy*t")),
            parameters={str(k): float(v) for k, v in (data.get("parameters") or {}).items()},
        )


@dataclass(slots=True)
class SceneObject:
    id: str
    name: str = "运动物体"
    shape: str = "circle"
    mass: float = 1.0
    size: tuple[float, float] = (0.8, 0.8)
    radius: float = 0.4
    initial_position: tuple[float, float] = (0.0, 0.0)
    initial_velocity: tuple[float, float] = (0.0, 0.0)
    acceleration: tuple[float, float] = (0.0, 0.0)
    color: str = "#2563eb"
    role: str = "moving"
    motion: MotionDefinition = field(default_factory=MotionDefinition)

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int = 0) -> "SceneObject":
        shape = str(data.get("shape", "circle")).strip().lower()
        if shape not in SUPPORTED_SHAPES:
            shape = "circle"
        size = data.get("size", [0.8, 0.8])
        position = data.get("initial_position", data.get("position", [0.0, 0.0]))
        velocity = data.get("initial_velocity", data.get("velocity", [0.0, 0.0]))
        acceleration = data.get("acceleration", [0.0, 0.0])
        return cls(
            id=str(data.get("id", f"object_{index + 1}")),
            name=str(data.get("name", f"物体{index + 1}")),
            shape=shape,
            mass=max(1e-9, float(data.get("mass", 1.0))),
            size=(float(size[0]), float(size[1] if len(size) > 1 else size[0])),
            radius=max(0.02, float(data.get("radius", min(float(size[0]), float(size[-1])) / 2))),
            initial_position=(float(position[0]), float(position[1])),
            initial_velocity=(float(velocity[0]), float(velocity[1])),
            acceleration=(float(acceleration[0]), float(acceleration[1])),
            color=str(data.get("color", "#2563eb")),
            role=str(data.get("role", "moving")),
            motion=MotionDefinition.from_dict(data.get("motion")),
        )


@dataclass(slots=True)
class ProblemSpec:
    title: str = "基础运动演示"
    source_question: str = ""
    problem_type: str = "linear"
    coordinate_system: dict[str, str] = field(
        default_factory=lambda: {
            "origin": "运动物体初始位置",
            "x_axis": "水平向右",
            "y_axis": "竖直向上",
        }
    )
    objects: list[SceneObject] = field(default_factory=list)
    special_case: dict[str, Any] = field(default_factory=lambda: {"kind": "none"})
    duration: float = 8.0
    explanation: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parser_mode: str = "offline"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProblemSpec":
        raw_objects = data.get("objects") or []
        objects = [SceneObject.from_dict(item, i) for i, item in enumerate(raw_objects)]
        if not objects:
            objects = [SceneObject(id="object_1")]
        duration = max(0.5, min(float(data.get("duration", 8.0)), 60.0))
        return cls(
            title=str(data.get("title", "基础运动演示")),
            source_question=str(data.get("source_question", data.get("question", ""))),
            problem_type=str(data.get("problem_type", "linear")).strip().lower(),
            coordinate_system=dict(data.get("coordinate_system") or {
                "origin": "运动物体初始位置",
                "x_axis": "水平向右",
                "y_axis": "竖直向上",
            }),
            objects=objects,
            special_case=dict(data.get("special_case") or {"kind": "none"}),
            duration=duration,
            explanation=[str(x) for x in (data.get("explanation") or [])],
            warnings=[str(x) for x in (data.get("warnings") or [])],
            parser_mode=str(data.get("parser_mode", "ai")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

