#!/usr/bin/env python3
"""
─── semantic_engine.core — ternary field representation ─────────────────
Pure move from semantic_core.py (itself extracted verbatim from
alien_mind_v13.5.py). No identity. No desire. No mood. Represents ternary
vectors, measures similarity between them, and serializes them - nothing
else.
"""

import hashlib
import json
import numpy as np

DIM = 128

# Ternary threshold for normalized vectors (calibrated for unit vectors)
# Raw word vectors use ~0.4; normalized state vectors need ~0.09
NORMALIZED_VECTOR_THRESHOLD = 0.09


def word_vector_ternary(word, dim=DIM):
    """Deterministic ternary vector from word hash. int8 array, values {-1,0,1}."""
    h = int(hashlib.md5(word.encode()).hexdigest(), 16)
    rng = np.random.RandomState(h % (2**31))
    v = rng.randn(dim).astype(np.float32)
    result = np.zeros(dim, dtype=np.int8)
    result[v > 0.4] = 1
    result[v < -0.4] = -1
    return result


def phrase_vector_ternary(words, dim=DIM):
    """Average of ternary word vectors, re-ternarized. Lossy by design."""
    if not words:
        return np.zeros(dim, dtype=np.int8)
    summed = np.zeros(dim, dtype=np.int16)
    for w in words:
        summed += word_vector_ternary(w, dim)
    result = np.zeros(dim, dtype=np.int8)
    result[summed > 1] = 1
    result[summed < -1] = -1
    return result


def ternary_dot(a, b):
    """Ternary similarity: agreements minus disagreements, normalized to [-1,1]."""
    pos_pos = np.sum((a == 1) & (b == 1))
    neg_neg = np.sum((a == -1) & (b == -1))
    pos_neg = np.sum((a == 1) & (b == -1))
    neg_pos = np.sum((a == -1) & (b == 1))
    active_both = np.sum((a != 0) & (b != 0))
    if active_both == 0:
        return 0.0
    score = (pos_pos + neg_neg - pos_neg - neg_pos)
    return float(score) / float(active_both)


def weighted_ternary_dot(a, b, weights):
    """Same ternary similarity, but each dim's contribution is scaled by
    weights[i] before summing, with a weighted (not plain) normalizer.
    All-ones weights => numerically identical to ternary_dot."""
    agree = ((a == 1) & (b == 1)) | ((a == -1) & (b == -1))
    disagree = ((a == 1) & (b == -1)) | ((a == -1) & (b == 1))
    active_both = (a != 0) & (b != 0)
    if not np.any(active_both):
        return 0.0
    signed = np.where(agree, 1.0, np.where(disagree, -1.0, 0.0)).astype(np.float32)
    denom = float(np.sum(weights[active_both]))
    if denom <= 1e-8:
        return 0.0
    return float(np.sum(signed[active_both] * weights[active_both]) / denom)


def ternary_similarity_matrix(vectors_dict):
    """All pairwise similarities in a vocabulary. {word: [(other, sim), ...]}."""
    words = list(vectors_dict.keys())
    vecs = [vectors_dict[w] for w in words]
    similarities = {}
    for i, w in enumerate(words):
        sims = []
        for j, other in enumerate(words):
            if i != j:
                sim = ternary_dot(vecs[i], vecs[j])
                if sim > 0.1:
                    sims.append((other, sim))
        sims.sort(key=lambda x: x[1], reverse=True)
        similarities[w] = sims[:20]
    return similarities


def pack_ternary(vec):
    """Pack ternary vector into compact bytes. 4 values/byte. 128 dims -> 32 bytes."""
    mapped = vec.astype(np.uint8) + 1  # -1->0, 0->1, 1->2
    n = len(mapped)
    pad = (4 - n % 4) % 4
    padded = np.pad(mapped, (0, pad), constant_values=1)
    packed = np.zeros(len(padded) // 4, dtype=np.uint8)
    for i in range(0, len(padded), 4):
        packed[i // 4] = (
            (padded[i]   << 6) |
            (padded[i+1] << 4) |
            (padded[i+2] << 2) |
            padded[i+3]
        )
    return packed


def unpack_ternary(packed_bytes, dim=DIM):
    """Unpack compact bytes back to ternary vector. 32 bytes -> 128 dims."""
    result = np.zeros(dim, dtype=np.int8)
    idx = 0
    for byte in packed_bytes:
        for shift in [6, 4, 2, 0]:
            if idx >= dim:
                break
            val = int((byte >> shift) & 0x3)
            result[idx] = val - 1
            idx += 1
    return result


class TernaryFieldState:
    """The field's state as a ternary vector. Drifts via thresholded gradient steps."""

    def __init__(self, dim=DIM):
        self.dim = dim
        self.state = np.zeros(dim, dtype=np.int8)
        self.gradient_momentum = np.zeros(dim, dtype=np.float32)

    def set_from_float(self, float_vec):
        v = float_vec.astype(np.float32)
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        self.state = np.zeros(self.dim, dtype=np.int8)
        self.state[v > NORMALIZED_VECTOR_THRESHOLD] = 1
        self.state[v < -NORMALIZED_VECTOR_THRESHOLD] = -1

    def to_float(self):
        return self.state.astype(np.float32) * 0.7

    def apply_gradient(self, grad_float, learning_rate=0.02):
        self.gradient_momentum = self.gradient_momentum * 0.9 + grad_float * 0.1
        current_float = self.to_float()
        new_float = current_float + learning_rate * self.gradient_momentum
        self.set_from_float(new_float)

    def energy(self):
        return int(np.sum(self.state != 0))

    def pack(self):
        return pack_ternary(self.state)

    def unpack(self, packed_bytes):
        self.state = unpack_ternary(packed_bytes, self.dim)


class TernaryAssociativeMemory:
    """Sparse Hebbian memory using ternary outer products."""

    def __init__(self, dim=DIM, max_entries=5000):
        self.dim = dim
        self.max_entries = max_entries
        self.entries = {}
        self.total_writes = 0
        self.decay_rate = 0.0005

    def observe(self, pattern_vec, presence):
        signal = max(-1.0, min(1.0, (presence - 0.5) * 2.0))
        nz = np.where(pattern_vec != 0)[0]
        for i in nz:
            for j in nz:
                key = (int(i), int(j))
                weight = float(pattern_vec[i] * pattern_vec[j]) * signal * 0.04
                if key in self.entries:
                    self.entries[key] += weight
                else:
                    if len(self.entries) < self.max_entries:
                        self.entries[key] = weight
        self.total_writes += 1
        self._maintain()

    def recall(self, field_state):
        pull = np.zeros(self.dim, dtype=np.float32)
        nz = np.where(field_state != 0)[0]
        for i in nz:
            for j in range(self.dim):
                key = (int(i), j)
                if key in self.entries:
                    pull[j] += self.entries[key] * field_state[i]
        norm = np.linalg.norm(pull)
        if norm > 0:
            pull = pull / norm
        return pull

    def apply_to_field(self, field_state, weight=0.15):
        pull = self.recall(field_state)
        result = field_state.astype(np.float32) + pull * weight
        norm = np.linalg.norm(result)
        if norm > 0:
            result = result / norm
        return result.astype(np.float32)

    def _maintain(self):
        to_remove = []
        for key, weight in self.entries.items():
            self.entries[key] *= (1.0 - self.decay_rate)
            if abs(self.entries[key]) < 0.01:
                to_remove.append(key)
        for key in to_remove:
            del self.entries[key]

    def status(self):
        return f"Ternary Associative Memory: {len(self.entries)} sparse entries | {self.total_writes} writes"

    def to_dict(self):
        return {
            "entries": {f"{i},{j}": w for (i, j), w in self.entries.items()},
            "total_writes": self.total_writes
        }

    def from_dict(self, data):
        if "entries" in data:
            for key_str, w in data["entries"].items():
                i, j = map(int, key_str.split(","))
                self.entries[(i, j)] = float(w)
        self.total_writes = data.get("total_writes", 0)


class NumpyEncoder(json.JSONEncoder):
    """
    JSON encoder for numpy types. Use as json.dump(..., cls=NumpyEncoder).

    Bug fix: this used to be a bare placeholder (`class NumpyEncoder: pass`)
    alongside a separate make_numpy_encoder() factory that returned the
    real working class - meaning the exported name `NumpyEncoder` (the one
    a caller would naturally reach for, since it matches the working
    class's name in the original alien_mind_v13_6-1.py) was silently
    broken. json.dump(..., cls=NumpyEncoder) has json internally call
    `NumpyEncoder(indent=..., ensure_ascii=..., ...)`, and the placeholder
    had no __init__ accepting those - confirmed on real hardware as
    "[Warning: Save failed - NumpyEncoder() takes no arguments]" the first
    time mind.py actually called save(). Fixed by making NumpyEncoder
    itself the real encoder, not a decoy.
    """
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return super().default(obj)


def make_numpy_encoder():
    """Kept only for backward compatibility with any code that already
    calls make_numpy_encoder() instead of using NumpyEncoder directly.
    NumpyEncoder no longer needs a factory - it IS the real encoder now."""
    return NumpyEncoder

