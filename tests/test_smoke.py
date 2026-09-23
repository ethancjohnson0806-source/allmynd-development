import tempfile
import unittest
from pathlib import Path

from allmynd.bridge import Bridge
from allmynd.mind import AllMynd
from semantic_engine.engine import SemanticEngine


class ImportAndPipelineTests(unittest.TestCase):
    def test_semantic_engine_processes_text(self):
        engine = SemanticEngine()
        response = engine.process("hello world")
        self.assertIsInstance(response, str)
        self.assertTrue(response.strip())

    def test_bridge_exposes_stable_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = Bridge(path=str(Path(directory) / "state.json"))
            self.assertIsInstance(bridge.status(), str)
            self.assertIsInstance(bridge.stance(), dict)
            self.assertGreaterEqual(bridge.learn("courage means acting", source="test"), 1)
            response = bridge.speak("hello")
            self.assertIsInstance(response, str)
            bridge.save()
            self.assertTrue(Path(directory, "state.json").exists())

    def test_final_message_handles_expanded_quantum_body(self):
        mind = AllMynd()
        mind.generate_response("hello, are you there?")
        self.assertGreaterEqual(mind.quantum_body.dim, 128)
        mind.write_final_message()
        self.assertTrue((mind.state[120:128] != 0).any())


if __name__ == "__main__":
    unittest.main()
