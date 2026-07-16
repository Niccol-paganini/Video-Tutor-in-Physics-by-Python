"""与界面解耦的二维运动/碰撞计算核心。"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Callable

from models import MotionDefinition, ProblemSpec, SceneObject


@dataclass(frozen=True, slots=True)
class BodyState:
    x: float
    y: float
    vx: float
    vy: float
    angle: float = 0.0
    phase: str = "运动中"


_FUNCTIONS: dict[str, Callable[..., float]] = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "sqrt": math.sqrt, "exp": math.exp, "log": math.log,
    "abs": abs, "min": min, "max": max,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_ALLOWED_AST = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Load, ast.Name, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd,
)


class ExpressionError(ValueError):
    pass


def evaluate_expression(expression: str, variables: dict[str, float]) -> float:
    """安全计算运动函数，拒绝属性访问、索引、导入等任意代码。"""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"运动函数语法错误：{expression}") from exc
    allowed_names = set(variables) | set(_FUNCTIONS) | set(_CONSTANTS)
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST):
            raise ExpressionError(f"运动函数包含不允许的语法：{type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ExpressionError(f"运动函数包含未知变量：{node.id}")
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS
        ):
            raise ExpressionError("运动函数只允许调用白名单数学函数。")
    env = {**_FUNCTIONS, **_CONSTANTS, **variables}
    try:
        result = eval(compile(tree, "<motion>", "eval"), {"__builtins__": {}}, env)
        return float(result)
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ExpressionError(f"运动函数计算失败：{expression}") from exc


class PhysicsEngine:
    def __init__(self, spec: ProblemSpec):
        self.spec = spec

    def state_at(self, t: float) -> dict[str, BodyState]:
        time = max(0.0, min(float(t), self.spec.duration))
        if self.spec.problem_type == "collision_1d":
            return self._collision_states(time)
        return {obj.id: self._object_state(obj, time) for obj in self.spec.objects}

    def _object_state(self, obj: SceneObject, t: float) -> BodyState:
        x0, y0 = obj.initial_position
        vx, vy = obj.initial_velocity
        ax, ay = obj.acceleration
        kind = obj.motion.kind
        params = obj.motion.parameters
        if kind == "static":
            return BodyState(x0, y0, 0, 0, phase="静止")
        if kind in {"linear", "projectile"}:
            x = x0 + vx * t + 0.5 * ax * t * t
            y = y0 + vy * t + 0.5 * ay * t * t
            sx, sy = vx + ax * t, vy + ay * t
            return BodyState(x, y, sx, sy, math.atan2(sy, sx) if sx or sy else 0)
        if kind == "circular":
            cx, cy = params.get("cx", 0), params.get("cy", 0)
            radius = params.get("r", 3)
            omega, phase = params.get("omega", 1), params.get("phase", 0)
            theta = omega * t + phase
            x, y = cx + radius * math.cos(theta), cy + radius * math.sin(theta)
            sx, sy = -radius * omega * math.sin(theta), radius * omega * math.cos(theta)
            return BodyState(x, y, sx, sy, theta, "圆周运动")
        if kind == "custom":
            variables = {
                "t": t, "x0": x0, "y0": y0, "vx": vx, "vy": vy, "ax": ax, "ay": ay,
                **params,
            }
            x = evaluate_expression(obj.motion.x, variables)
            y = evaluate_expression(obj.motion.y, variables)
            delta = 1e-4
            variables["t"] = t + delta
            sx = (evaluate_expression(obj.motion.x, variables) - x) / delta
            sy = (evaluate_expression(obj.motion.y, variables) - y) / delta
            return BodyState(x, y, sx, sy, math.atan2(sy, sx) if sx or sy else 0, "自定义函数")
        if kind == "semicircle_launch":
            return self._semicircle_state(params, t)
        if kind == "block_plank":
            return self._block_plank_state(obj, t)
        if kind == "collision_1d":
            return BodyState(x0 + vx * t, y0 + vy * t, vx, vy)
        return BodyState(x0, y0, 0, 0, phase="未知运动")

    @staticmethod
    def _semicircle_state(params: dict[str, float], t: float) -> BodyState:
        cx, cy, radius = params.get("cx", 0), params.get("cy", 0), params.get("r", 3)
        start = params.get("start_angle", math.pi)
        omega = params.get("omega", -1.25)
        arc_duration = max(0, params.get("arc_duration", abs(math.pi / omega) if omega else 0))
        gravity = abs(params.get("gravity", 9.8))

        on_arc_time = min(t, arc_duration)
        theta = start + omega * on_arc_time
        x_launch = cx + radius * math.cos(theta)
        y_launch = cy + radius * math.sin(theta)
        vx_launch = -radius * omega * math.sin(theta)
        vy_launch = radius * omega * math.cos(theta)
        if t <= arc_duration:
            return BodyState(
                x_launch, y_launch, vx_launch, vy_launch, theta,
                "沿半圆轨道运动",
            )
        dt = t - arc_duration
        x = x_launch + vx_launch * dt
        y = y_launch + vy_launch * dt - 0.5 * gravity * dt * dt
        vy = vy_launch - gravity * dt
        return BodyState(x, y, vx_launch, vy, math.atan2(vy, vx_launch), "离轨抛体运动")

    @staticmethod
    def _block_plank_state(obj: SceneObject, t: float) -> BodyState:
        params = obj.motion.parameters
        start = params.get("start_relative_x", obj.initial_position[0])
        relative_v = params.get("relative_velocity", obj.initial_velocity[0])
        relative_a = params.get("relative_acceleration", 0)
        stop_time = math.inf
        if relative_a and relative_v * relative_a < 0:
            stop_time = -relative_v / relative_a
        active_t = min(t, stop_time)
        relative_x = start + relative_v * active_t + 0.5 * relative_a * active_t * active_t
        current_relative_v = relative_v + relative_a * active_t if t < stop_time else 0
        length = params.get("plank_length", 6)
        object_width = obj.size[0]
        limit = max(0, length / 2 - object_width / 2)
        phase = "相对滑动"
        if relative_x >= limit:
            relative_x = limit
            phase = "恰好到达木板右端" if params.get("just_not_fall", 0) else "到达木板边缘"
        elif t >= stop_time:
            phase = "相对静止"
        plank_velocity = params.get("plank_velocity", 0)
        x = params.get("plank_initial_x", 0) + plank_velocity * t + relative_x
        y = obj.initial_position[1]
        return BodyState(x, y, plank_velocity + current_relative_v, 0, phase=phase)

    def _collision_states(self, t: float) -> dict[str, BodyState]:
        if len(self.spec.objects) < 2:
            return {obj.id: self._object_state(obj, t) for obj in self.spec.objects}
        first, second = self.spec.objects[:2]
        x1, y1 = first.initial_position
        x2, y2 = second.initial_position
        u1, u2 = first.initial_velocity[0], second.initial_velocity[0]
        r1 = first.radius if first.shape in {"circle", "point"} else first.size[0] / 2
        r2 = second.radius if second.shape in {"circle", "point"} else second.size[0] / 2
        relative_speed = u1 - u2
        gap = x2 - x1 - r1 - r2
        collision_time = gap / relative_speed if relative_speed > 0 and gap >= 0 else math.inf
        elasticity = float(self.spec.special_case.get("elasticity", 1.0))
        m1, m2 = first.mass, second.mass
        v1 = (m1 * u1 + m2 * u2 - m2 * elasticity * (u1 - u2)) / (m1 + m2)
        v2 = (m1 * u1 + m2 * u2 + m1 * elasticity * (u1 - u2)) / (m1 + m2)

        states: dict[str, BodyState] = {}
        if t <= collision_time:
            states[first.id] = BodyState(x1 + u1 * t, y1, u1, 0, phase="碰撞前")
            states[second.id] = BodyState(x2 + u2 * t, y2, u2, 0, phase="碰撞前")
        else:
            dt = t - collision_time
            contact1, contact2 = x1 + u1 * collision_time, x2 + u2 * collision_time
            states[first.id] = BodyState(contact1 + v1 * dt, y1, v1, 0, phase="碰撞后")
            states[second.id] = BodyState(contact2 + v2 * dt, y2, v2, 0, phase="碰撞后")
        for obj in self.spec.objects[2:]:
            states[obj.id] = self._object_state(obj, t)
        return states

    def trajectory(self, object_id: str, samples: int = 160) -> list[tuple[float, float]]:
        if samples < 2:
            samples = 2
        result: list[tuple[float, float]] = []
        for i in range(samples):
            states = self.state_at(self.spec.duration * i / (samples - 1))
            state = states[object_id]
            result.append((state.x, state.y))
        return result

    def motion_summary(self, obj: SceneObject) -> str:
        kind = obj.motion.kind
        if kind == "linear":
            return "x=x₀+vₓt+½aₓt²；y=y₀+vᵧt+½aᵧt²"
        if kind == "projectile":
            return "x=x₀+v₀ₓt；y=y₀+v₀ᵧt-½gt²"
        if kind == "circular":
            return "x=cₓ+r·cos(ωt+φ)；y=cᵧ+r·sin(ωt+φ)"
        if kind == "semicircle_launch":
            return "轨道阶段使用圆参数方程；离轨后使用切向初速度的抛体方程"
        if kind == "block_plank":
            return "x相=x₀相+v₀相t+½a相t²；以最大相对位移判断是否冲出"
        if kind == "collision_1d":
            return "碰撞前匀速；碰撞后由动量守恒和恢复系数计算速度"
        if kind == "custom":
            return f"x(t)={obj.motion.x}；y(t)={obj.motion.y}"
        return "位置不随时间变化"

    def special_metrics(self) -> dict[str, float | str]:
        if self.spec.problem_type == "collision_1d" and len(self.spec.objects) >= 2:
            a, b = self.spec.objects[:2]
            gap = b.initial_position[0] - a.initial_position[0] - a.size[0] / 2 - b.size[0] / 2
            relative = a.initial_velocity[0] - b.initial_velocity[0]
            return {"碰撞时刻": max(0, gap / relative) if relative > 0 else "不会碰撞"}
        if self.spec.problem_type == "block_plank":
            slider = next((x for x in self.spec.objects if x.motion.kind == "block_plank"), None)
            if slider:
                p = slider.motion.parameters
                v, a = p.get("relative_velocity", 0), p.get("relative_acceleration", 0)
                displacement = v * v / (2 * abs(a)) if a and v * a < 0 else 0
                usable = p.get("plank_length", 6) - slider.size[0]
                return {"最大相对位移": displacement, "可用行程": usable,
                        "判断": "恰好不冲出" if abs(displacement - usable) < 0.03 else "需核对参数"}
        return {}


class CollisionSimulator(PhysicsEngine):
    """保留原类名，兼容仍从physics_engine导入CollisionSimulator的代码。"""

    def __init__(self, spec: ProblemSpec | None = None, gravity: tuple[float, float] = (0, 0)):
        self.gravity = gravity
        self.current_time = 0.0
        super().__init__(spec or ProblemSpec(objects=[]))

    def add_block(self, id: str, mass: float, size, position, velocity) -> None:
        self.spec.objects.append(SceneObject(
            id=id, name=id, shape="rectangle", mass=float(mass),
            size=(float(size[0]), float(size[1])),
            initial_position=(float(position[0]), float(position[1])),
            initial_velocity=(float(velocity[0]), float(velocity[1])),
            acceleration=(float(self.gravity[0]), float(self.gravity[1])),
            motion=MotionDefinition(kind="linear"),
        ))

    def step(self, dt: float) -> dict[str, BodyState]:
        self.current_time += float(dt)
        return self.state_at(self.current_time)
