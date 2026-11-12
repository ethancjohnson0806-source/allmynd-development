import os
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from allmynd.fieldmap import build as build_fieldmap, render as render_fieldmap
from allmynd.mind import AllMynd
from allmynd.plan import PosTagger
from semantic_engine.lqe_core.stabilizer import StabilizerSim, choose_backend
from semantic_engine.quantum import QuantumState


class PhoneProgressTests(unittest.TestCase):
    def test_stabilizer_bell_pair_measurements_match_and_collapse(self):
        sim = StabilizerSim(2, rng=random.Random(17))
        sim.h(0)
        sim.cnot(0, 1)
        first = sim.measure(0)
        second = sim.measure(1)
        self.assertIn(first, (0, 1))
        self.assertEqual(first, second)
        self.assertTrue(sim.is_deterministic(0))
        self.assertEqual(sim.measure(0), first)
        self.assertEqual(sim.measure(1), second)

    def test_backend_router_only_selects_stabilizer_for_clifford_fresh_state(self):
        self.assertEqual(
            choose_backend([("H", 0), ("CNOT", 0, 1)], from_fresh_state=True)[0],
            "stabilizer",
        )
        self.assertEqual(
            choose_backend([("RY", np.pi / 4, 0)], from_fresh_state=True)[0],
            "statevector",
        )
        self.assertEqual(
            choose_backend([("H", 0)], from_fresh_state=False)[0],
            "statevector",
        )

    def test_circuit_optimizer_merges_rotations_and_cancels_matching_cnot(self):
        gates = [
            ("RY", 0.2, 0),
            ("RY", 0.3, 0),
            ("CNOT", 0, 1),
            ("CNOT", 0, 1),
            ("RZ", 1e-14, 2),
        ]
        self.assertEqual(QuantumState.optimize_circuit(gates), [("RY", 0.5, 0)])

    def test_pos_tagger_keeps_seeded_multilingual_planning_lexicon_labels(self):
        tagger = PosTagger()
        self.assertEqual(tagger.tag("ocean"), "NOUN")
        self.assertEqual(tagger.tag("remember"), "VERB")
        self.assertEqual(tagger.tag("quiet"), "ADJ")
        tags = tagger.learn_sentence(["the", "lantern"])
        self.assertEqual(tags, ["FUNC", "NOUN"])

    def test_fieldmap_build_and_render_are_json_safe_and_read_only(self):
        words = ("ocean", "whale", "water", "harbor", "sing", "walk", "think", "remember")
        vectors = {word: np.eye(128, dtype=np.float32)[i] for i, word in enumerate(words)}
        mind = SimpleNamespace(
            word_vectors=vectors,
            word_strength={word: float(i + 1) for i, word in enumerate(words)},
            memory_archive=SimpleNamespace(entries=[]),
            turn_count=3,
        )
        before = {word: vector.copy() for word, vector in vectors.items()}
        result = build_fieldmap(mind)
        html = render_fieldmap({"safe": np.float32(1.25), "bad": float("nan"), "text": "</script>"})
        self.assertEqual(len(result["words"]), len(words))
        self.assertTrue(result["meta"]["turn"] == 3)
        self.assertIn("1.25", html)
        self.assertNotIn(":NaN", html)
        self.assertIn("<\\/script>", html)
        for word in words:
            np.testing.assert_array_equal(vectors[word], before[word])

    def test_quantum_phase_sidecar_round_trips_in_temporary_workspace(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory(prefix="allmynd-sidecar-test-") as td:
            try:
                os.chdir(td)
                first = AllMynd()
                first.quantum_body.sim.apply("H", 0)
                expected = first.quantum_body.sim.state.copy()
                save_path = Path(td) / "state.json"
                first.save(str(save_path), quiet=True)
                sidecar = Path(str(save_path) + ".quantum.npz")
                self.assertTrue(sidecar.is_file())

                second = AllMynd()
                second.quantum_body.sim.apply("X", 0)
                second.load(str(save_path))
                np.testing.assert_allclose(second.quantum_body.sim.state, expected, atol=1e-12)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
