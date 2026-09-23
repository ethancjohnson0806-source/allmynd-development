#!/usr/bin/env python3
"""
─── semantic_engine.embeddings — real word meaning ─────────────────────
The original word vectors were deterministic random hashes: every word
was a random direction in the 128-dim field, so the mind could never
know what a word meant. This module gives words real meaning by loading
GloVe (Wikipedia) 50-dim vectors for the vocabulary and projecting them
into the 128-dim field space with a fixed random projection.

Words not in the table fall back to the original hash vectors, so
nothing ever crashes. The table lives in word_vectors.bin.gz next to
this file (compact float16 binary; the older word_vectors.json.gz is
still supported as a fallback).
"""

import gzip
import hashlib
import json
import os
import struct

import numpy as np

DIM = 128
EMBED_DIM = 100
NORMALIZED_VECTOR_THRESHOLD = 0.09

_PATH_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "word_vectors.json")
_PATH_GZ = _PATH_JSON + ".gz"
_PATH_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "word_vectors.bin.gz")

# Fixed 128x100 random projection (GloVe 100d -> field 128d). Johnson-Lindenstrauss:
# cosine similarity in 50d is approximately preserved in 128d, and the
# activation spreads across all dims so ternary dot products stay well-behaved.
_rng = np.random.RandomState(42)
_PROJECTION = (_rng.randn(DIM, EMBED_DIM) / np.sqrt(EMBED_DIM)).astype(np.float32)

_EMBEDDINGS = None


def _load():
    global _EMBEDDINGS
    if _EMBEDDINGS is not None:
        return _EMBEDDINGS
    _EMBEDDINGS = {}
    bin_path = _PATH_BIN if os.path.exists(_PATH_BIN) else None
    if bin_path:
        try:
            with gzip.open(bin_path, "rb") as f:
                raw = f.read()
            if raw[:5] == b"AMWV1":
                n, dim = struct.unpack("<II", raw[5:13])
                pos = 13
                for _ in range(n):
                    ln = struct.unpack("<H", raw[pos:pos+2])[0]
                    pos += 2
                    w = raw[pos:pos+ln].decode("utf-8")
                    pos += ln
                    arr = np.frombuffer(raw[pos:pos+dim*2], dtype=np.float16)
                    pos += dim*2
                    _EMBEDDINGS[w] = arr.astype(np.float32)
                return _EMBEDDINGS
        except Exception:
            _EMBEDDINGS = {}
    path = _PATH_GZ if os.path.exists(_PATH_GZ) else _PATH_JSON
    if not os.path.exists(path):
        return _EMBEDDINGS
    try:
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        for w, v in data.items():
            arr = np.asarray(v, dtype=np.float32)
            if arr.shape == (EMBED_DIM,):
                _EMBEDDINGS[w] = arr
    except Exception:
        _EMBEDDINGS = {}
    return _EMBEDDINGS


def has_vector(word):
    return word.lower() in _load()


def embed_float(word):
    """128-dim unit-norm float vector for a word, or None if not covered."""
    v50 = _load().get(word.lower())
    if v50 is None:
        return None
    v = _PROJECTION @ v50
    n = np.linalg.norm(v)
    if n < 1e-8:
        return None
    return (v / n).astype(np.float32)


def embed_ternary(word):
    """128-dim int8 ternary {-1,0,1} for a word, or None if not covered."""
    v = embed_float(word)
    if v is None:
        return None
    t = np.zeros(DIM, dtype=np.int8)
    t[v > NORMALIZED_VECTOR_THRESHOLD] = 1
    t[v < -NORMALIZED_VECTOR_THRESHOLD] = -1
    return t


def hash_float(word, dim=DIM):
    """Original deterministic hash vector (fallback for unknown words)."""
    h = int(hashlib.md5(word.encode()).hexdigest(), 16)
    rng = np.random.RandomState(h % (2**31))
    v = rng.randn(dim).astype(np.float32)
    v /= np.linalg.norm(v) + 1e-8
    return v


def word_vector(word, dim=DIM):
    """Float vector: real embedding when available, hash fallback otherwise."""
    if dim == DIM:
        v = embed_float(word)
        if v is not None:
            return v
    return hash_float(word, dim)


def word_vector_ternary(word):
    """Ternary vector: real embedding when available, hash fallback otherwise."""
    t = embed_ternary(word)
    if t is not None:
        return t
    return _hash_ternary(word)


def _hash_ternary(word):
    """Original hash ternary (raw randn quantized at 0.4, as in core.py)."""
    h = int(hashlib.md5(word.encode()).hexdigest(), 16)
    rng = np.random.RandomState(h % (2**31))
    v = rng.randn(DIM).astype(np.float32)
    t = np.zeros(DIM, dtype=np.int8)
    t[v > 0.4] = 1
    t[v < -0.4] = -1
    return t
