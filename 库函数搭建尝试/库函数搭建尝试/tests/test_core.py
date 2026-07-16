from __future__ import annotations

import json
import math
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from ai_service import OllamaClient
from data_interface import ProblemFileLoader, ProblemParser
from physics_engine import ExpressionError, PhysicsEngine, evaluate_expression


class ParserTests(unittest.TestCase):
    def test_ai_json_and_legacy_protocol(self):
        spec = ProblemParser.parse_ai_output({
            "masses": [2, 1], "sizes": [[1, 1], [1, 1]],
            "positions": [[-2, 0], [2, 0]], "velocities": [[1, 0], [-1, 0]],
            "elasticity": 0.9,
        })
        self.assertEqual(spec.problem_type, "collision_1d")
        self.assertEqual(len(spec.objects), 2)

    def test_markdown_wrapped_json(self):
        raw = "```json\n" + json.dumps(ProblemParser._circular_template("demo")) + "\n```"
        self.assertEqual(ProblemParser.parse_ai_output(raw).problem_type, "circular")

    def test_text_file_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "problem.txt"
            path.write_text("circular motion", encoding="utf-8")
            self.assertEqual(ProblemFileLoader.load(path), "circular motion")

    def test_ollama_http_contract(self):
        scene = ProblemParser._projectile_template("mock problem")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                payload = json.dumps({"models": [{"name": "mock:latest"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                request_body = json.loads(self.rfile.read(length))
                self.server.received = request_body
                payload = json.dumps({"response": json.dumps(scene, ensure_ascii=False)}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = OllamaClient(f"http://127.0.0.1:{server.server_port}", "mock:latest")
            self.assertEqual(client.list_models(), ["mock:latest"])
            result = client.analyze("mock problem")
            self.assertEqual(result.spec.problem_type, "projectile")
            self.assertEqual(server.received["format"], "json")
            self.assertFalse(server.received["stream"])
        finally:
            server.shutdown()
            server.server_close()


class PhysicsTests(unittest.TestCase):
    def test_safe_expression(self):
        result = evaluate_expression("x0 + vx*t + 0.5*ax*t**2", {"x0": 0, "vx": 2, "ax": 1, "t": 3})
        self.assertAlmostEqual(result, 10.5)
        with self.assertRaises(ExpressionError):
            evaluate_expression("__import__('os').system('echo bad')", {})

    def test_circular_motion(self):
        spec = ProblemParser.parse_ai_output(ProblemParser._circular_template("demo"))
        state = PhysicsEngine(spec).state_at(0)["ball"]
        self.assertAlmostEqual(state.x, 3)
        self.assertAlmostEqual(state.y, 0)
        self.assertAlmostEqual(math.hypot(state.vx, state.vy), 3.6)

    def test_semicircle_launch_is_continuous(self):
        spec = ProblemParser.parse_ai_output(ProblemParser._semicircle_template("demo"))
        engine = PhysicsEngine(spec)
        launch = spec.objects[0].motion.parameters["arc_duration"]
        before = engine.state_at(launch)["ball"]
        after = engine.state_at(launch + 1e-6)["ball"]
        self.assertLess(math.hypot(after.x - before.x, after.y - before.y), 1e-3)
        self.assertEqual(after.phase, "离轨抛体运动")

    def test_block_just_not_fall_condition(self):
        spec = ProblemParser.parse_ai_output(ProblemParser._block_plank_template("demo"))
        metrics = PhysicsEngine(spec).special_metrics()
        self.assertEqual(metrics["判断"], "恰好不冲出")
        self.assertAlmostEqual(metrics["最大相对位移"], metrics["可用行程"], places=4)

    def test_elastic_collision_conserves_momentum_and_energy(self):
        spec = ProblemParser.parse_ai_output(ProblemParser._collision_template("demo"))
        engine = PhysicsEngine(spec)
        states = engine.state_at(3)
        a, b = spec.objects
        momentum_before = a.mass * a.initial_velocity[0] + b.mass * b.initial_velocity[0]
        momentum_after = a.mass * states[a.id].vx + b.mass * states[b.id].vx
        energy_before = 0.5 * a.mass * a.initial_velocity[0] ** 2 + 0.5 * b.mass * b.initial_velocity[0] ** 2
        energy_after = 0.5 * a.mass * states[a.id].vx ** 2 + 0.5 * b.mass * states[b.id].vx ** 2
        self.assertAlmostEqual(momentum_before, momentum_after)
        self.assertAlmostEqual(energy_before, energy_after)


if __name__ == "__main__":
    unittest.main()
