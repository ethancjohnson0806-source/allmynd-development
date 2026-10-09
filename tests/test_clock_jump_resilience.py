import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

import numpy as np

from allmynd.mind import DreamLoop, FieldMemory
from semantic_engine.query import Phrase, PhraseSystem


class ClockJumpResilienceTests(unittest.TestCase):
    def test_field_memory_future_timestamp_is_treated_as_current(self):
        def inject(timestamp):
            memory = FieldMemory(capacity=1, dim=2)
            memory.buffer.append({
                "field_state": np.array([1.0, 0.0], dtype=np.float32),
                "mood": {"valence": 0.0, "arousal": 0.5},
                "timestamp": timestamp,
            })
            with patch("allmynd.mind.time.time", return_value=100.0):
                return memory.inject(np.array([0.0, 1.0], dtype=np.float32))

        np.testing.assert_allclose(inject(10**9), inject(100.0))

    def test_dream_loop_future_timestamp_does_not_overflow_recency(self):
        entry = {
            "field_state": np.array([1.0, 0.0], dtype=np.float32),
            "timestamp": 10**9,
            "presence": 0.5,
            "user_input": "clock changed",
        }
        memory_archive = type("MemoryArchiveStub", (), {"entries": [entry]})()
        loop = DreamLoop(dim=2)

        with patch("allmynd.mind.time.time", return_value=100.0):
            selected, dream = loop.select_memory(
                memory_archive, np.array([1.0, 0.0], dtype=np.float32)
            )

        self.assertIs(selected, entry)
        self.assertEqual(dream.shape, (2,))
        self.assertTrue(np.isfinite(dream).all())

    def test_phrase_decay_does_not_overflow_for_future_last_used(self):
        phrase = Phrase(
            surface="future phrase",
            vector=np.array([1.0], dtype=np.float32),
            frequency=2.0,
            last_used=10**9,
        )
        system = PhraseSystem()
        system.phrases["future phrase"] = phrase

        with patch("semantic_engine.query.time.time", return_value=100.0):
            system.decay()

        self.assertEqual(phrase.frequency, 2.0)
        self.assertIn("future phrase", system.phrases)

    def test_wall_clock_jump_does_not_trigger_elapsed_autosave(self):
        import run

        mind = Mock()
        mind._last_novelty = 0.0
        with ExitStack() as stack:
            stack.enter_context(patch("run.AllMynd", return_value=mind))
            stack.enter_context(patch("builtins.input", side_effect=["hello", EOFError]))
            stack.enter_context(patch("run.time.monotonic", side_effect=[0.0, 1.0]))
            wall_clock = stack.enter_context(
                patch("run.time.time", side_effect=[100.0, 10000.0])
            )
            stack.enter_context(patch("run.AUTOSAVE_SECONDS", 180.0))
            stack.enter_context(redirect_stdout(StringIO()))
            run.main()

        # The one save is graceful shutdown; wall-clock time did not cause an
        # additional autosave after the conversation turn.
        self.assertEqual(wall_clock.call_count, 0)
        mind.save.assert_called_once_with(run.SAVE_PATH)


if __name__ == "__main__":
    unittest.main()
