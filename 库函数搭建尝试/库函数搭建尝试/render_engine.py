"""Tkinter动画画布：绘制坐标系、轨迹、基础图形和特殊场景。"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from models import ProblemSpec, SceneObject
from physics_engine import BodyState, PhysicsEngine


class PhysicsCanvas(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, background="#f8fafc", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self.spec: ProblemSpec | None = None
        self.engine: PhysicsEngine | None = None
        self.current_time = 0.0
        self.scale = 55.0
        self.center = (400.0, 300.0)

    def set_scene(self, spec: ProblemSpec) -> None:
        self.spec = spec
        self.engine = PhysicsEngine(spec)
        self.current_time = 0
        self._fit_view()
        self.redraw()

    def set_time(self, time_value: float) -> None:
        self.current_time = max(0, float(time_value))
        self.redraw()

    def _fit_view(self) -> None:
        if not self.engine or not self.spec:
            return
        points: list[tuple[float, float]] = []
        for obj in self.spec.objects:
            points.extend(self.engine.trajectory(obj.id, 100))
        finite = [(x, y) for x, y in points if math.isfinite(x) and math.isfinite(y)]
        if not finite:
            return
        xs, ys = [x for x, _ in finite], [y for _, y in finite]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max(4.0, max_x - min_x + 3.0)
        height = max(4.0, max_y - min_y + 3.0)
        canvas_w = max(500, self.canvas.winfo_width())
        canvas_h = max(420, self.canvas.winfo_height())
        self.scale = max(22, min(85, (canvas_w - 70) / width, (canvas_h - 90) / height))
        world_cx = (min_x + max_x) / 2
        world_cy = (min_y + max_y) / 2
        self.center = (canvas_w / 2 - world_cx * self.scale, canvas_h / 2 + world_cy * self.scale)

    def world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        return self.center[0] + x * self.scale, self.center[1] - y * self.scale

    def redraw(self) -> None:
        self.canvas.delete("all")
        if not self.spec or not self.engine:
            self._draw_empty()
            return
        self._draw_grid()
        self._draw_special_background()
        self._draw_trajectories()
        states = self.engine.state_at(self.current_time)
        for obj in self.spec.objects:
            self._draw_object(obj, states[obj.id])
        self._draw_overlay(states)

    def _draw_empty(self) -> None:
        w, h = max(500, self.canvas.winfo_width()), max(420, self.canvas.winfo_height())
        self.canvas.create_text(
            w / 2, h / 2 - 15, text="物理动画预览区", fill="#334155",
            font=("Microsoft YaHei UI", 20, "bold"),
        )
        self.canvas.create_text(
            w / 2, h / 2 + 25, text="输入题目并点击“规则解析”或“调用本地AI”",
            fill="#64748b", font=("Microsoft YaHei UI", 11),
        )

    def _draw_grid(self) -> None:
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        step = self.scale
        origin_x, origin_y = self.center
        x = origin_x % step
        while x < w:
            self.canvas.create_line(x, 0, x, h, fill="#e2e8f0")
            x += step
        y = origin_y % step
        while y < h:
            self.canvas.create_line(0, y, w, y, fill="#e2e8f0")
            y += step
        self.canvas.create_line(0, origin_y, w, origin_y, fill="#64748b", width=2, arrow="last")
        self.canvas.create_line(origin_x, h, origin_x, 0, fill="#64748b", width=2, arrow="last")
        self.canvas.create_text(w - 16, origin_y - 12, text="x", fill="#334155")
        self.canvas.create_text(origin_x + 12, 12, text="y", fill="#334155")

    def _draw_special_background(self) -> None:
        kind = self.spec.problem_type
        if kind == "circular":
            obj = self.spec.objects[0]
            p = obj.motion.parameters
            cx, cy, radius = p.get("cx", 0), p.get("cy", 0), p.get("r", 3)
            x0, y0 = self.world_to_canvas(cx - radius, cy + radius)
            x1, y1 = self.world_to_canvas(cx + radius, cy - radius)
            self.canvas.create_oval(x0, y0, x1, y1, outline="#94a3b8", width=3, dash=(8, 5))
            ccx, ccy = self.world_to_canvas(cx, cy)
            self.canvas.create_oval(ccx - 4, ccy - 4, ccx + 4, ccy + 4, fill="#0f172a")
        elif kind == "semicircle_launch":
            obj = self.spec.objects[0]
            p = obj.motion.parameters
            cx, cy, radius = p.get("cx", 0), p.get("cy", 0), p.get("r", 3)
            points = []
            start = p.get("start_angle", math.pi)
            omega = p.get("omega", -1.25)
            duration = p.get("arc_duration", abs(math.pi / omega) if omega else 0)
            for i in range(81):
                theta = start + omega * duration * i / 80
                points.extend(self.world_to_canvas(cx + radius * math.cos(theta), cy + radius * math.sin(theta)))
            self.canvas.create_line(*points, fill="#475569", width=5, smooth=True)
        elif kind == "block_plank":
            plank = next((o for o in self.spec.objects if o.role == "plank"), None)
            if plank:
                x, y = plank.initial_position
                left, top = self.world_to_canvas(x - plank.size[0] / 2, y + plank.size[1] / 2)
                right, bottom = self.world_to_canvas(x + plank.size[0] / 2, y - plank.size[1] / 2)
                self.canvas.create_rectangle(left, top, right, bottom, fill="#ca8a04", outline="#713f12", width=2)

    def _draw_trajectories(self) -> None:
        for obj in self.spec.objects:
            if obj.role == "plank":
                continue
            points = []
            for x, y in self.engine.trajectory(obj.id, 120):
                if math.isfinite(x) and math.isfinite(y):
                    points.extend(self.world_to_canvas(x, y))
            if len(points) >= 4:
                self.canvas.create_line(*points, fill=obj.color, width=2, dash=(4, 5), smooth=True)

    def _draw_object(self, obj: SceneObject, state: BodyState) -> None:
        if obj.role == "plank":
            return
        cx, cy = self.world_to_canvas(state.x, state.y)
        if obj.shape == "point":
            radius = max(5, obj.radius * self.scale)
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                    fill=obj.color, outline="#ffffff", width=2)
        elif obj.shape == "circle":
            radius = max(7, obj.radius * self.scale)
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                    fill=obj.color, outline="#0f172a", width=2)
        else:
            width = obj.size[0] * self.scale
            height = (obj.size[0] if obj.shape == "square" else obj.size[1]) * self.scale
            self.canvas.create_rectangle(cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2,
                                         fill=obj.color, outline="#0f172a", width=2)
        self.canvas.create_text(cx, cy - max(18, obj.size[1] * self.scale / 2 + 14),
                                text=obj.name, fill="#0f172a", font=("Microsoft YaHei UI", 9, "bold"))
        speed = math.hypot(state.vx, state.vy)
        if speed > 0.02:
            factor = min(55, speed * 10) / speed
            self.canvas.create_line(cx, cy, cx + state.vx * factor, cy - state.vy * factor,
                                    fill="#ef4444", width=2, arrow="last")

    def _draw_overlay(self, states: dict[str, BodyState]) -> None:
        lines = [f"t = {self.current_time:.2f} s"]
        for obj in self.spec.objects:
            if obj.role == "plank":
                continue
            state = states[obj.id]
            lines.append(
                f"{obj.name}: ({state.x:.2f}, {state.y:.2f}) m  "
                f"v=({state.vx:.2f}, {state.vy:.2f}) m/s  {state.phase}"
            )
        text = "\n".join(lines)
        box = self.canvas.create_text(14, 14, anchor="nw", text=text, fill="#0f172a",
                                      font=("Consolas", 10), justify="left")
        bounds = self.canvas.bbox(box)
        if bounds:
            background = self.canvas.create_rectangle(
                bounds[0] - 7, bounds[1] - 5, bounds[2] + 7, bounds[3] + 5,
                fill="#ffffff", outline="#cbd5e1",
            )
            self.canvas.tag_lower(background, box)

    def export_postscript(self, filename: str) -> None:
        self.canvas.postscript(file=filename, colormode="color")


class AnimationRenderer:
    """兼容原类名的独立预览窗口。"""

    def run_animation(self, simulator: PhysicsEngine) -> None:
        root = tk.Tk()
        root.title("Video Tutor 物理动画")
        view = PhysicsCanvas(root)
        view.pack(fill="both", expand=True)
        view.set_scene(simulator.spec)
        state = {"t": 0.0}

        def tick():
            state["t"] += 1 / 60
            if state["t"] > simulator.spec.duration:
                state["t"] = 0
            view.set_time(state["t"])
            root.after(16, tick)

        root.geometry("1000x700")
        root.after(16, tick)
        root.mainloop()
