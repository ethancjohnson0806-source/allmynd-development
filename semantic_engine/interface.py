#!/usr/bin/env python3
"""
─── semantic_engine.interface — the nerve cord ───────────────────────────
SemanticPacket and GrammarConfig: the boundary contract between the
engine and anything that uses it (a mind, or a tool like a coding
assistant). Both sides agree on this shape; neither needs to know the
other's internals.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np

from .core import DIM


@dataclass
class SemanticPacket:
    state: np.ndarray                      # float32[128] - live field
    ternary: Optional[np.ndarray] = None   # int8[128] - snapped state
    energy: float = 0.0
    entropy: float = 0.0
    quantum_seed: Optional[np.ndarray] = None       # from QuantumState.project_to_ternary()
    quantum_stance: str = "silence"
    quantum_coherence: float = 0.0
    resonance_map: Dict[str, float] = field(default_factory=dict)
    attractors: List[np.ndarray] = field(default_factory=list)
    derivative: Optional[np.ndarray] = None
    integral: Optional[np.ndarray] = None

    def snap_ternary(self, threshold=0.09):
        t = np.zeros(DIM, dtype=np.int8)
        t[self.state > threshold] = 1
        t[self.state < -threshold] = -1
        self.ternary = t
        return t

    def recompute_stats(self):
        self.energy = float(np.linalg.norm(self.state))
        self.entropy = float(np.std(self.state))
        return self


@dataclass
class GrammarConfig:
    voice_mode: str = "fluent"          # fluent | poetic | reflective | exploratory | playful
    output_length: str = "medium"       # short | medium | long
    temperature: float = 0.35
    emotion_sensitivity: float = 0.25
    repulsion_strength: float = 0.08
    beam_width: Optional[int] = None
