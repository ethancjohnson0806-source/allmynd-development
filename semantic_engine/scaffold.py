#!/usr/bin/env python3
"""
─── semantic_engine.scaffold — semantic operator application ─────────────
SemanticScaffold, stripped per the extraction blueprint: this keeps only
the operator vectors (because->causal, if->conditional, dark->mood, etc.)
and the apply() method that blends them into a field state. `mood` state
and `update_mood()`/`emotional_bias()` move to the mind side (allmynd's
MoodTracker) - those ask "how do I feel", which is identity, not operator
math.
"""

import hashlib
import numpy as np

from .core import DIM


def _word_vector(word, dim=DIM):
    h = int(hashlib.md5(word.encode()).hexdigest(), 16)
    rng = np.random.RandomState(h % (2**31))
    v = rng.randn(dim).astype(np.float32)
    v /= np.linalg.norm(v) + 1e-8
    return v


class SemanticScaffold:
    """Operator vectors only. `apply()` blends an operator's role-biased
    vector into a field state when that operator word appears."""

    def __init__(self):
        self.operators = {
            "because": "causal", "so": "causal", "therefore": "causal",
            "if": "conditional", "then": "conditional", "when": "temporal",
            "before": "temporal", "after": "temporal", "while": "temporal",
            "and": "conjunctive", "or": "disjunctive", "but": "contrastive",
            "although": "contrastive", "however": "contrastive",
            "dark": "mood", "light": "mood", "deep": "depth", "shallow": "depth",
            "above": "spatial", "below": "spatial", "within": "spatial",
            "beyond": "spatial", "inside": "spatial", "outside": "spatial",
            "more": "comparative", "less": "comparative", "very": "intensifier",
            "not": "negation", "no": "negation", "never": "negation",
            "think": "cognitive", "know": "cognitive", "feel": "affective",
            "want": "desiderative", "need": "desiderative", "should": "normative",
            "must": "normative", "can": "modal", "might": "modal", "will": "futural"
        }
        self.operator_vectors = {}
        self._build_operator_vectors()

    def _build_operator_vectors(self):
        for op, role in self.operators.items():
            base = _word_vector(op)
            role_bias = np.zeros(DIM, dtype=np.float32)
            slot = {
                "causal": (0, 16), "conditional": (16, 32), "temporal": (32, 48),
                "contrastive": (48, 64), "mood": (64, 80), "spatial": (80, 96),
                "cognitive": (96, 112), "affective": (112, 128),
            }.get(role)
            if slot:
                role_bias[slot[0]:slot[1]] = 0.3
            v = base + role_bias
            v /= np.linalg.norm(v) + 1e-8
            self.operator_vectors[op] = v

    def apply(self, field_state, word, strength=1.0):
        from .query import strip_punct
        word_lower = strip_punct(word)
        if word_lower in self.operator_vectors:
            op_vec = self.operator_vectors[word_lower]
            field_state = field_state * 0.7 + op_vec * strength * 0.3
        return field_state
