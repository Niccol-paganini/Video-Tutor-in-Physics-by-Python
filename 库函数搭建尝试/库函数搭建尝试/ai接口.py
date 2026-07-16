"""兼容原工程中文文件名的本地大模型入口。"""

from ai_service import AIServiceError, OllamaClient


class AIProblemSolver:
    def __init__(self, model_name: str = "qwen2.5:7b", base_url: str = "http://127.0.0.1:11434"):
        self.client = OllamaClient(base_url=base_url, model=model_name)

    def solve_problem(self, question: str):
        return self.client.analyze(question).spec.to_dict()


__all__ = ["AIProblemSolver", "AIServiceError", "OllamaClient"]

