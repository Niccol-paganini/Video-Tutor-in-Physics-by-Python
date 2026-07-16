"""题目文件读取、AI JSON校验和无模型时的规则解析。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.etree import ElementTree

from models import ProblemSpec


class FileLoadError(ValueError):
    pass


class ProblemFileLoader:
    """读取常见题目文件；DOCX使用标准库直接提取正文。"""

    TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json"}

    @classmethod
    def load(cls, filename: str | Path) -> str:
        path = Path(filename)
        if not path.exists():
            raise FileLoadError(f"文件不存在：{path}")
        suffix = path.suffix.lower()
        if suffix in cls.TEXT_SUFFIXES:
            for encoding in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    return path.read_text(encoding=encoding)
                except UnicodeDecodeError:
                    continue
            raise FileLoadError("无法识别文本编码，请转换为UTF-8后重试。")
        if suffix == ".docx":
            return cls._load_docx(path)
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore
            except ImportError as exc:
                raise FileLoadError("读取PDF需要安装 pypdf：pip install pypdf") from exc
            return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        raise FileLoadError("支持 TXT、MD、JSON、CSV、DOCX；安装pypdf后可读取PDF。")

    @staticmethod
    def _load_docx(path: Path) -> str:
        try:
            with ZipFile(path) as archive:
                raw = archive.read("word/document.xml")
        except Exception as exc:
            raise FileLoadError(f"DOCX读取失败：{exc}") from exc
        root = ElementTree.fromstring(raw)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{namespace}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
            if text.strip():
                paragraphs.append(text.strip())
        return "\n".join(paragraphs)


class ProblemParser:
    """将AI输出或自然语言题目统一为ProblemSpec。"""

    @staticmethod
    def extract_json(raw: str) -> dict[str, Any]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            value = json.loads(raw[start : end + 1])
            if isinstance(value, dict):
                return value
        raise ValueError("AI输出中没有可解析的JSON对象。")

    @classmethod
    def parse_ai_output(cls, ai_output: str | dict[str, Any]) -> ProblemSpec:
        data = cls.extract_json(ai_output) if isinstance(ai_output, str) else dict(ai_output)
        if "masses" in data:  # 兼容原草稿协议
            data = cls._convert_legacy(data)
        spec = ProblemSpec.from_dict(data)
        cls._validate(spec)
        return spec

    @classmethod
    def parse_question(cls, question: str) -> ProblemSpec:
        text = question.strip()
        if not text:
            raise ValueError("请先输入或选择一道物理题。")
        if text.startswith("{"):
            return cls.parse_ai_output(text)
        if "半圆" in text and any(k in text for k in ("抛", "离开", "飞出")):
            data = cls._semicircle_template(text)
        elif "滑块" in text and any(k in text for k in ("木板", "长板", "平板")):
            data = cls._block_plank_template(text)
        elif any(k in text for k in ("圆周运动", "圆周", "转动", "角速度")):
            data = cls._circular_template(text)
        elif "碰撞" in text:
            data = cls._collision_template(text)
        elif any(k in text for k in ("平抛", "斜抛", "抛体", "抛出")):
            data = cls._projectile_template(text)
        else:
            data = cls._linear_template(text)
        data["parser_mode"] = "offline"
        data["warnings"] = ["当前为规则解析结果；请在中栏核对参数，也可连接本地Ollama重新分析。"]
        return ProblemSpec.from_dict(data)

    @staticmethod
    def _numbers(text: str) -> list[float]:
        return [float(x) for x in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", text)]

    @classmethod
    def _linear_template(cls, text: str) -> dict[str, Any]:
        nums = cls._numbers(text)
        speed = nums[0] if nums else 2.0
        return {
            "title": "直线运动演示",
            "source_question": text,
            "problem_type": "linear",
            "objects": [{
                "id": "object_1", "name": "运动物体", "shape": "square",
                "size": [0.8, 0.8], "initial_position": [-4, 0],
                "initial_velocity": [speed, 0], "motion": {"kind": "linear"},
            }],
            "duration": 6,
            "explanation": ["以物体初始位置为原点。", "采用匀变速运动公式计算每一时刻的位置。"],
        }

    @staticmethod
    def _projectile_template(text: str) -> dict[str, Any]:
        return {
            "title": "抛体运动演示", "source_question": text, "problem_type": "projectile",
            "objects": [{
                "id": "ball", "name": "抛体", "shape": "circle", "radius": 0.28,
                "initial_position": [-4, 0], "initial_velocity": [4.5, 6.5],
                "acceleration": [0, -9.8], "motion": {"kind": "projectile"},
            }],
            "duration": 2.2,
            "explanation": ["水平方向做匀速运动。", "竖直方向做加速度为-g的匀变速运动。"],
        }

    @staticmethod
    def _circular_template(text: str) -> dict[str, Any]:
        return {
            "title": "圆周运动演示", "source_question": text, "problem_type": "circular",
            "objects": [{
                "id": "ball", "name": "圆周运动质点", "shape": "point", "radius": 0.14,
                "initial_position": [3, 0], "motion": {
                    "kind": "circular", "x": "cx + r*cos(omega*t + phase)",
                    "y": "cy + r*sin(omega*t + phase)",
                    "parameters": {"cx": 0, "cy": 0, "r": 3, "omega": 1.2, "phase": 0},
                },
            }],
            "duration": 6,
            "special_case": {"kind": "centripetal_acceleration", "condition": "a=v²/r=ω²r"},
            "explanation": ["轨迹为以(cx,cy)为圆心、r为半径的圆。", "速度方向沿圆周切线，向心加速度始终指向圆心。"],
        }

    @staticmethod
    def _semicircle_template(text: str) -> dict[str, Any]:
        return {
            "title": "半圆轨道抛出演示", "source_question": text, "problem_type": "semicircle_launch",
            "objects": [{
                "id": "ball", "name": "小球", "shape": "circle", "radius": 0.24,
                "initial_position": [-3, 0], "motion": {
                    "kind": "semicircle_launch",
                    "parameters": {"cx": 0, "cy": 0, "r": 3, "start_angle": 3.141593,
                                   "omega": -1.25, "arc_duration": 2.513274, "gravity": 9.8},
                },
            }],
            "duration": 4.5,
            "special_case": {"kind": "semicircle_launch", "condition": "离开轨道后沿切线方向做抛体运动"},
            "explanation": ["小球先沿半圆轨道运动。", "到达轨道端点后，以端点切向速度进入抛体阶段。"],
        }

    @staticmethod
    def _block_plank_template(text: str) -> dict[str, Any]:
        return {
            "title": "滑块—木板恰好不冲出演示", "source_question": text, "problem_type": "block_plank",
            "objects": [
                {"id": "plank", "name": "木板", "shape": "rectangle", "role": "plank",
                 "size": [6, 0.45], "initial_position": [0, -1.2], "color": "#a16207",
                 "motion": {"kind": "linear"}},
                {"id": "slider", "name": "滑块", "shape": "square", "size": [0.7, 0.7],
                 "initial_position": [-2.65, -0.62], "initial_velocity": [4, 0], "color": "#dc2626",
                 "motion": {"kind": "block_plank", "parameters": {
                     "plank_id": 0, "plank_length": 6, "start_relative_x": -2.65,
                     "relative_velocity": 4, "relative_acceleration": -1.509434,
                     "just_not_fall": 1,
                 }}},
            ],
            "duration": 4,
            "special_case": {"kind": "block_plank", "condition": "最大相对位移等于滑块可用行程，恰好停在右端"},
            "explanation": ["以木板中心为相对坐标原点。", "由相对速度降为0时的最大相对位移判断滑块是否冲出木板。"],
        }

    @staticmethod
    def _collision_template(text: str) -> dict[str, Any]:
        return {
            "title": "一维碰撞演示", "source_question": text, "problem_type": "collision_1d",
            "objects": [
                {"id": "A", "name": "物体A", "shape": "square", "mass": 2, "size": [0.8, 0.8],
                 "initial_position": [-3, 0], "initial_velocity": [2.5, 0], "color": "#2563eb",
                 "motion": {"kind": "collision_1d"}},
                {"id": "B", "name": "物体B", "shape": "square", "mass": 1, "size": [0.8, 0.8],
                 "initial_position": [2, 0], "initial_velocity": [-1, 0], "color": "#dc2626",
                 "motion": {"kind": "collision_1d"}},
            ],
            "duration": 5,
            "special_case": {"kind": "collision_1d", "elasticity": 1.0, "condition": "完全弹性碰撞"},
            "explanation": ["碰撞前后系统动量守恒。", "完全弹性碰撞还满足机械能守恒。"],
        }

    @staticmethod
    def _convert_legacy(data: dict[str, Any]) -> dict[str, Any]:
        objects = []
        masses = data.get("masses", [])
        positions = data.get("positions", [])
        velocities = data.get("velocities", [])
        sizes = data.get("sizes", [[0.8, 0.8] for _ in masses])
        for i, mass in enumerate(masses):
            objects.append({
                "id": f"object_{i + 1}", "name": f"物体{i + 1}", "shape": "rectangle",
                "mass": mass, "size": sizes[i], "initial_position": positions[i],
                "initial_velocity": velocities[i], "motion": {"kind": "collision_1d"},
            })
        return {
            "title": "碰撞演示", "problem_type": "collision_1d", "objects": objects,
            "special_case": {"kind": "collision_1d", "elasticity": data.get("elasticity", 0.9)},
            "duration": 6,
        }

    @staticmethod
    def _validate(spec: ProblemSpec) -> None:
        ids = [obj.id for obj in spec.objects]
        if len(ids) != len(set(ids)):
            raise ValueError("objects中的id不能重复。")
        if spec.problem_type == "collision_1d" and len(spec.objects) < 2:
            raise ValueError("一维碰撞至少需要两个物体。")
