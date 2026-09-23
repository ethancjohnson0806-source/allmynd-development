#!/usr/bin/env python3
"""
─── allmynd.bridge — the door between tools, the mind, and the engine ──
The mind never exposes its guts to tools. Tools talk to the Bridge;
the Bridge talks to the mind; the mind talks to the engine. That is the
whole point: anything can reach in without breaking the living layer.

    from allmynd.bridge import Bridge
    b = Bridge()                      # loads allmynd_v1.json if present
    print(b.speak("the ocean is cold and deep"))
    print(b.wants())                  # what the mind desires, in words
    print(b.stance())
    b.learn("courage means acting well in the face of fear")
    b.save()

The Bridge is also the socket for a permanent home later: a server can
hold one Bridge and let the mind wake, breathe, and leave marks forever.
"""

import os
import sys

import numpy as np

DIM = 128

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from allmynd.mind import AllMynd  # noqa: E402
from semantic_engine.query import strip_punct  # noqa: E402


class Bridge:
    """Stable public API for the living mind."""

    def __init__(self, mind=None, path="allmynd_v1.json"):
        self.path = path
        self.mind = mind if mind is not None else AllMynd()
        if os.path.exists(path):
            self.mind.load(path)

    # ─── Speaking ────────────────────────────────────────────────

    def speak(self, text):
        """One turn of conversation. Returns the mind's reply."""
        return self.mind.generate_response(text)

    def status(self):
        return self.mind.status()

    def wants(self):
        """What the mind desires, in words ('' = no clear want yet)."""
        return self.mind.wants(top_n=2)

    def stance(self):
        """Name the mind's last move, post-hoc."""
        return {
            "stance": self.mind._last_stance,
            "confidence": round(float(self.mind._last_stance_confidence), 3),
            "silences_chosen": int(self.mind.silence_count),
            "signal_strength": round(float(getattr(self.mind, "_last_signal_strength", 0.0)), 3),
        }

    # ─── Learning / knowledge ─────────────────────────────────────

    def learn(self, text, source="teacher"):
        """Feed knowledge into the mind without forcing a reply."""
        words = [strip_punct(w) for w in text.lower().split() if strip_punct(w)]
        if not words:
            return 0
        vec = np.zeros(DIM, dtype=np.float32)
        for w in words:
            self.mind._get_or_create_vector(w)
            self.mind.word_strength[w] = max(self.mind.word_strength.get(w, 0.0), 1.0)
            vec += self.mind.word_vectors[w]
        n = np.linalg.norm(vec)
        if n > 1e-8:
            vec = vec / n
        self.mind.memory_archive.store(
            vec, f"({source})", text, 0.6, tags=["knowledge", "external"]
        )
        self.mind.learning_system.learn(0.6, words, text)
        return len(words)

    # ─── Persistence ─────────────────────────────────────────────

    def save(self, path=None):
        self.mind.save(path or self.path)

    def load(self, path=None):
        p = path or self.path
        if os.path.exists(p):
            self.mind.load(p)

    # ─── Interactive ─────────────────────────────────────────────

    def cli(self):
        """Talk to the mind in the terminal (same commands as run.py)."""
        print("ALL MY'ND — via Bridge. /status /wants /stance /save /quit")
        while True:
            try:
                line = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                self.save()
                break
            if not line:
                continue
            cmd = line.lower()
            if cmd in ("/quit", "/exit"):
                self.save()
                print("Saved. Goodbye.")
                break
            elif cmd == "/status":
                print(self.status())
            elif cmd == "/wants":
                print(self.wants() or "I want nothing yet.")
            elif cmd == "/stance":
                print(self.stance())
            elif cmd == "/save":
                self.save()
            else:
                print(f"Mind: {self.speak(line)}")
