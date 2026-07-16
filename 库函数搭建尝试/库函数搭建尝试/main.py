"""Video Tutor基础物理碰撞与运动演示系统桌面端。"""

from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ai_service import AIServiceError, OllamaClient
from data_interface import FileLoadError, ProblemFileLoader, ProblemParser
from models import ProblemSpec
from physics_engine import PhysicsEngine
from render_engine import PhysicsCanvas


SAMPLE_QUESTION = "半径为3 m的圆周上，一个质点以1.2 rad/s的角速度做匀速圆周运动，请演示其位置、速度方向和运动轨迹。"


class VideoTutorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Tutor · 基础物理碰撞与运动演示系统")
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        window_w, window_h = min(1500, screen_w - 60), min(850, screen_h - 100)
        start_x, start_y = max(0, (screen_w - window_w) // 2), max(0, (screen_h - window_h) // 2)
        self.geometry(f"{window_w}x{window_h}+{start_x}+{start_y}")
        self.minsize(1180, 720)
        self.option_add("*Font", ("Microsoft YaHei UI", 10))
        self.spec: ProblemSpec | None = None
        self.engine: PhysicsEngine | None = None
        self.playing = False
        self.animation_job: str | None = None
        self.last_tick = time.perf_counter()
        self.current_time = tk.DoubleVar(value=0)
        self.speed = tk.DoubleVar(value=1.0)
        self.status = tk.StringVar(value="就绪：可输入题目、选择文件或加载示例。")
        self.file_path = tk.StringVar()
        self.ollama_url = tk.StringVar(value="http://127.0.0.1:11434")
        self.model_name = tk.StringVar(value="qwen2.5:7b")
        self._configure_style()
        self._build_ui()
        self.question_text.insert("1.0", SAMPLE_QUESTION)
        self.after(100, self.parse_offline)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 16, "bold"), foreground="#0f172a")
        style.configure("Subtitle.TLabel", foreground="#64748b")
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"))

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Video Tutor", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  物理题 → 结构化分析 → 运动函数 → 动画演示", style="Subtitle.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status, style="Subtitle.TLabel").pack(side="right")

        toolbar = ttk.Frame(self, padding=(14, 0, 14, 8))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="题目文件").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.file_path, width=47).pack(side="left", padx=(6, 5))
        ttk.Button(toolbar, text="选择文件…", command=self.select_file).pack(side="left")
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Label(toolbar, text="Ollama").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.ollama_url, width=25).pack(side="left", padx=(5, 7))
        ttk.Label(toolbar, text="模型").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.model_name, width=18).pack(side="left", padx=(5, 7))
        ttk.Button(toolbar, text="检查模型", command=self.check_models).pack(side="left")

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        left = ttk.Labelframe(panes, text="① 前端输入", padding=8)
        middle = ttk.Labelframe(panes, text="② AI结构化输出", padding=8)
        right = ttk.Labelframe(panes, text="③ 运动与碰撞动画", padding=8)
        panes.add(left, weight=24)
        panes.add(middle, weight=30)
        panes.add(right, weight=46)

        ttk.Label(left, text="输入题目，或点击上方“选择文件”：",
                  style="Subtitle.TLabel").pack(anchor="w")
        self.question_text = tk.Text(left, wrap="word", undo=True, width=34, padx=8, pady=8,
                                     relief="solid", borderwidth=1)
        self.question_text.pack(fill="both", expand=True, pady=(6, 8))
        input_buttons = ttk.Frame(left)
        input_buttons.pack(fill="x")
        ttk.Button(input_buttons, text="规则解析（离线）", command=self.parse_offline,
                   style="Primary.TButton").pack(side="left", fill="x", expand=True)
        self.ai_button = ttk.Button(input_buttons, text="调用本地AI", command=self.analyze_with_ai)
        self.ai_button.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(left, text="清空输入", command=lambda: self.question_text.delete("1.0", "end")).pack(fill="x", pady=(7, 0))

        notebook = ttk.Notebook(middle)
        notebook.pack(fill="both", expand=True)
        json_frame = ttk.Frame(notebook)
        summary_frame = ttk.Frame(notebook)
        notebook.add(json_frame, text="可执行JSON")
        notebook.add(summary_frame, text="物理判断与函数")
        self.output_text = tk.Text(json_frame, wrap="none", undo=True, padx=8, pady=8,
                                   font=("Consolas", 9), relief="solid", borderwidth=1)
        yscroll = ttk.Scrollbar(json_frame, orient="vertical", command=self.output_text.yview)
        xscroll = ttk.Scrollbar(json_frame, orient="horizontal", command=self.output_text.xview)
        self.output_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.output_text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        json_frame.rowconfigure(0, weight=1)
        json_frame.columnconfigure(0, weight=1)
        self.summary_text = tk.Text(summary_frame, wrap="word", padx=10, pady=10, state="disabled",
                                    relief="solid", borderwidth=1)
        self.summary_text.pack(fill="both", expand=True)
        output_buttons = ttk.Frame(middle)
        output_buttons.pack(fill="x", pady=(7, 0))
        ttk.Button(output_buttons, text="应用修改后的JSON", command=self.apply_output_json).pack(side="left", fill="x", expand=True)
        ttk.Button(output_buttons, text="导出JSON", command=self.export_json).pack(side="left", padx=(6, 0))

        self.physics_view = PhysicsCanvas(right)
        self.physics_view.pack(fill="both", expand=True)
        controls = ttk.Frame(right)
        controls.pack(fill="x", pady=(8, 0))
        self.play_button = ttk.Button(controls, text="▶ 播放", command=self.toggle_play)
        self.play_button.pack(side="left")
        ttk.Button(controls, text="↺ 重置", command=self.reset_animation).pack(side="left", padx=5)
        ttk.Button(controls, text="导出帧", command=self.export_frame).pack(side="right")
        ttk.Combobox(controls, textvariable=self.speed, values=(0.25, 0.5, 1.0, 1.5, 2.0),
                     width=4, state="readonly").pack(side="right", padx=(3, 6))
        ttk.Label(controls, text="速度").pack(side="right")
        self.time_label = ttk.Label(controls, text="0.00 / 0.00 s", width=14)
        self.time_label.pack(side="right", padx=(4, 5))
        self.time_scale = ttk.Scale(controls, from_=0, to=8, variable=self.current_time, command=self.scrub)
        self.time_scale.pack(side="left", fill="x", expand=True, padx=8)

    def select_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择物理题文件",
            filetypes=[
                ("支持的题目文件", "*.txt *.md *.json *.csv *.docx *.pdf"),
                ("文本文件", "*.txt *.md *.csv"), ("JSON", "*.json"),
                ("Word文档", "*.docx"), ("PDF", "*.pdf"), ("所有文件", "*.*"),
            ],
        )
        if not filename:
            return
        try:
            content = ProblemFileLoader.load(filename)
        except FileLoadError as exc:
            messagebox.showerror("文件读取失败", str(exc))
            return
        self.file_path.set(filename)
        self.question_text.delete("1.0", "end")
        self.question_text.insert("1.0", content)
        self.status.set(f"已载入：{Path(filename).name}")

    def get_question(self) -> str:
        return self.question_text.get("1.0", "end").strip()

    def parse_offline(self) -> None:
        try:
            spec = ProblemParser.parse_question(self.get_question())
            self.set_spec(spec)
            self.status.set("规则解析完成：可直接播放，也可在中栏修改JSON。")
        except Exception as exc:
            messagebox.showerror("解析失败", str(exc))

    def analyze_with_ai(self) -> None:
        question = self.get_question()
        if not question:
            messagebox.showwarning("缺少题目", "请先输入或选择一道物理题。")
            return
        self.ai_button.configure(state="disabled")
        self.status.set("正在调用本地Ollama分析，请稍候…")

        def worker() -> None:
            try:
                result = OllamaClient(self.ollama_url.get(), self.model_name.get()).analyze(question)
                self.after(0, lambda: self._finish_ai(result.spec, None))
            except Exception as exc:
                self.after(0, lambda: self._finish_ai(None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_ai(self, spec: ProblemSpec | None, error: Exception | None) -> None:
        self.ai_button.configure(state="normal")
        if error:
            self.status.set("本地AI调用失败；仍可使用离线规则解析。")
            messagebox.showerror("本地AI调用失败", str(error))
            return
        assert spec is not None
        self.set_spec(spec)
        self.status.set(f"本地AI分析完成：{self.model_name.get()}")

    def check_models(self) -> None:
        self.status.set("正在检查Ollama模型…")

        def worker() -> None:
            try:
                models = OllamaClient(self.ollama_url.get(), self.model_name.get()).list_models()
                text = "\n".join(models) if models else "Ollama已连接，但当前没有本地模型。"
                self.after(0, lambda: (self.status.set("Ollama连接正常。"), messagebox.showinfo("本地模型", text)))
            except AIServiceError as exc:
                self.after(0, lambda: (self.status.set("Ollama连接失败。"), messagebox.showerror("连接失败", str(exc))))

        threading.Thread(target=worker, daemon=True).start()

    def set_spec(self, spec: ProblemSpec) -> None:
        self.pause()
        self.spec = spec
        self.engine = PhysicsEngine(spec)
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", json.dumps(spec.to_dict(), ensure_ascii=False, indent=2))
        self.physics_view.set_scene(spec)
        self.time_scale.configure(to=spec.duration)
        self.current_time.set(0)
        self._update_time_label()
        self._update_summary()

    def _update_summary(self) -> None:
        if not self.spec or not self.engine:
            return
        lines = [
            f"【运动物体类型判断】\n场景：{self.spec.problem_type}\n",
            "【坐标系】",
            f"原点：{self.spec.coordinate_system.get('origin', '运动物体初始位置')}",
            f"X轴：{self.spec.coordinate_system.get('x_axis', '水平向右')}",
            f"Y轴：{self.spec.coordinate_system.get('y_axis', '竖直向上')}\n",
            "【运动函数】",
        ]
        for obj in self.spec.objects:
            lines.append(f"{obj.name}（{obj.shape}）：{self.engine.motion_summary(obj)}")
        lines.append("\n【特殊情况判断】")
        special = self.spec.special_case
        lines.append(f"类型：{special.get('kind', 'none')}")
        if special.get("condition"):
            lines.append(f"条件：{special['condition']}")
        for key, value in self.engine.special_metrics().items():
            lines.append(f"{key}：{value:.3f}" if isinstance(value, float) else f"{key}：{value}")
        if self.spec.explanation:
            lines.append("\n【讲解要点】")
            lines.extend(f"• {item}" for item in self.spec.explanation)
        if self.spec.warnings:
            lines.append("\n【核对提示】")
            lines.extend(f"• {item}" for item in self.spec.warnings)
        lines.append(f"\n解析来源：{self.spec.parser_mode}")
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", "\n".join(lines))
        self.summary_text.configure(state="disabled")

    def apply_output_json(self) -> None:
        try:
            spec = ProblemParser.parse_ai_output(self.output_text.get("1.0", "end"))
            spec.parser_mode = "manual-json"
            self.set_spec(spec)
            self.status.set("已应用中栏JSON，动画与函数说明已更新。")
        except Exception as exc:
            messagebox.showerror("JSON应用失败", str(exc))

    def toggle_play(self) -> None:
        if not self.spec:
            return
        if self.playing:
            self.pause()
        else:
            self.playing = True
            self.play_button.configure(text="⏸ 暂停")
            self.last_tick = time.perf_counter()
            self._tick()

    def pause(self) -> None:
        self.playing = False
        self.play_button.configure(text="▶ 播放")
        if self.animation_job:
            self.after_cancel(self.animation_job)
            self.animation_job = None

    def reset_animation(self) -> None:
        self.pause()
        self.current_time.set(0)
        self.physics_view.set_time(0)
        self._update_time_label()

    def scrub(self, _value: str | None = None) -> None:
        self.pause()
        self.physics_view.set_time(self.current_time.get())
        self._update_time_label()

    def _tick(self) -> None:
        if not self.playing or not self.spec:
            return
        now = time.perf_counter()
        dt = min(0.08, now - self.last_tick) * self.speed.get()
        self.last_tick = now
        value = self.current_time.get() + dt
        if value >= self.spec.duration:
            value = self.spec.duration
            self.current_time.set(value)
            self.physics_view.set_time(value)
            self._update_time_label()
            self.pause()
            return
        self.current_time.set(value)
        self.physics_view.set_time(value)
        self._update_time_label()
        self.animation_job = self.after(16, self._tick)

    def _update_time_label(self) -> None:
        duration = self.spec.duration if self.spec else 0
        self.time_label.configure(text=f"{self.current_time.get():.2f} / {duration:.2f} s")

    def export_json(self) -> None:
        if not self.spec:
            return
        filename = filedialog.asksaveasfilename(
            title="导出结构化题目", defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile=f"{self.spec.problem_type}_scene.json",
        )
        if filename:
            Path(filename).write_text(json.dumps(self.spec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.set(f"已导出：{Path(filename).name}")

    def export_frame(self) -> None:
        if not self.spec:
            return
        filename = filedialog.asksaveasfilename(
            title="导出当前动画帧", defaultextension=".ps", filetypes=[("PostScript", "*.ps")],
            initialfile=f"{self.spec.problem_type}_{self.current_time.get():.2f}s.ps",
        )
        if filename:
            self.physics_view.export_postscript(filename)
            self.status.set(f"当前帧已导出：{Path(filename).name}")


def main() -> None:
    app = VideoTutorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
