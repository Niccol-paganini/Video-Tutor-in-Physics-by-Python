"""本地Ollama接口：把物理题转换为系统可执行的结构化JSON。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from data_interface import ProblemParser
from models import ProblemSpec


SYSTEM_PROMPT = r"""
你是物理题动画结构化助手。只输出一个合法JSON对象，禁止Markdown和额外说明。
坐标约定：以运动物体初始位置或题目指定点为原点，水平向右为x正方向，竖直向上为y正方向。
JSON字段必须满足：
{
  "title": "场景标题",
  "source_question": "原题",
  "problem_type": "linear|projectile|circular|collision_1d|semicircle_launch|block_plank|custom",
  "coordinate_system": {"origin":"...","x_axis":"水平向右","y_axis":"竖直向上"},
  "objects": [{
    "id":"唯一英文id", "name":"名称",
    "shape":"point|circle|rectangle|square", "mass":1,
    "size":[宽,高], "radius":0.3,
    "initial_position":[x0,y0], "initial_velocity":[vx,vy], "acceleration":[ax,ay],
    "color":"#2563eb", "role":"moving|plank",
    "motion":{"kind":"linear|projectile|circular|custom|semicircle_launch|block_plank|collision_1d",
              "x":"仅使用t,x0,y0,vx,vy,ax,ay及数学函数的表达式",
              "y":"同上", "parameters":{}}
  }],
  "special_case":{"kind":"none或场景类型","condition":"特殊条件","其他参数":"数值"},
  "duration":8,
  "explanation":["物体类型判断","运动函数说明","特殊情况判断"]
}
没有给出的数值要选取适合演示的合理默认值，并在explanation中明确。不要输出null。
圆周运动parameters使用cx,cy,r,omega,phase。
半圆抛出parameters使用cx,cy,r,start_angle,omega,arc_duration,gravity。
滑块木板应包含plank与slider两个物体；slider的parameters使用plank_length,start_relative_x,
relative_velocity,relative_acceleration,just_not_fall。
""".strip()


class AIServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class AIAnalysisResult:
    spec: ProblemSpec
    raw_response: str


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:7b"):
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()

    def list_models(self, timeout: float = 3.0) -> list[str]:
        payload = self._request("/api/tags", None, timeout)
        return [str(item.get("name")) for item in payload.get("models", []) if item.get("name")]

    def analyze(self, question: str, timeout: float = 90.0) -> AIAnalysisResult:
        if not self.model:
            raise AIServiceError("请填写Ollama模型名称。")
        body = {
            "model": self.model,
            "prompt": f"{SYSTEM_PROMPT}\n\n待分析题目：\n{question.strip()}",
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 1600},
        }
        payload = self._request("/api/generate", body, timeout)
        raw = str(payload.get("response", "")).strip()
        if not raw:
            raise AIServiceError("Ollama返回内容为空。")
        try:
            spec = ProblemParser.parse_ai_output(raw)
        except Exception as exc:
            raise AIServiceError(f"模型返回的JSON不符合协议：{exc}\n\n原始输出：\n{raw}") from exc
        spec.parser_mode = f"ollama:{self.model}"
        return AIAnalysisResult(spec=spec, raw_response=raw)

    def _request(self, endpoint: str, data: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        encoded = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{endpoint}", data=encoded,
            headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AIServiceError(f"Ollama请求失败（HTTP {exc.code}）：{detail}") from exc
        except URLError as exc:
            raise AIServiceError(
                "无法连接本地Ollama。请先启动Ollama服务，并确认地址和模型名称正确。"
            ) from exc
        except json.JSONDecodeError as exc:
            raise AIServiceError("Ollama返回了无法解析的响应。") from exc

