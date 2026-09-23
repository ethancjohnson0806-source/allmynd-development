#!/usr/bin/env python3
"""
─── semantic_engine.query — candidate generation & pattern detection ─────
PhraseSystem (crystallization), BigramSystem (transition stats),
Reflector (repulsion/suppression), and get_candidates_for_role() (ternary
similarity scoring for word-slot filling). Extracted from the
monkey-patched v13.6 mind file and stripped of mood/identity/moral-compass
coupling per the extraction blueprint: "The engine never asks what it
wants."

Where the original `_get_candidates_for_role` read `self.scaffold.mood`,
`self.speaker_regions.get_identity_boost(vec)`, and
`self.moral_compass.current_heading` directly, this version takes a
single optional `bias_fn(word, vec) -> float` callable instead - the mind
computes identity/emotion/heading bias however it wants and hands the
engine one number per word. The engine still owns: ternary similarity,
role filtering (verb/adj/noun via the POS lexicon below), word_strength
weighting, suppression, and physics-weighted resonance (all pure
structural properties of the field/vocabulary, not "what do I want").
"""

import time
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field as dataclass_field
from typing import List

import numpy as np

from .core import DIM, word_vector_ternary, ternary_dot, weighted_ternary_dot

MAX_PHRASES = 500
DECAY_RATE = 0.0003

STRUCTURAL_WORDS = {"am", "is", "are", "be", "been", "being", "was", "were",
                     "do", "does", "did", "have", "has", "had"}

VERB_WORDS = {
    "know", "think", "feel", "see", "hear", "say", "tell", "ask", "answer",
    "want", "need", "like", "love", "hate", "fear", "hope", "dream",
    "make", "take", "give", "get", "put", "set", "keep", "let", "help",
    "work", "play", "live", "die", "come", "go", "move", "stay", "leave",
    "find", "lose", "win", "fail", "try", "use", "show", "hide", "open",
    "close", "start", "stop", "begin", "end", "turn", "change", "grow",
    "breathe", "rest", "reach", "hold", "carry", "build", "break", "heal",
    "remember", "forget", "learn", "become", "remain", "wonder", "trust",
    "listen", "shape", "resonate", "pulse", "drone",
}

ADJ_WORDS = {
    "good", "bad", "great", "small", "big", "old", "new", "alive", "brave",
    "real", "lost", "found", "beautiful", "gentle", "strong", "soft", "hard",
    "warm", "cold", "quiet", "loud", "bright", "clear", "free", "safe",
    "wild", "calm", "heavy", "light", "sharp", "worn", "whole", "broken",
    "tender", "raw", "steady", "uncertain", "familiar", "strange", "honest",
    "hidden", "deep", "high", "far", "near",
}

FUNCTION_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "because",
    "i", "you", "it", "we", "they", "he", "she", "this", "that", "what",
    "will", "would", "could", "should", "may", "might", "can", "must", "shall",
    "each", "both", "neither", "every", "some", "enough", "other",
    "please", "always", "never", "already", "again", "once", "sometimes",
    "today", "tonight", "now", "soon", "still", "away", "here", "there",
    "often", "even", "almost", "really", "quite", "just", "very", "maybe",
    "perhaps", "also", "too", "then", "soon", "somehow", "anyway", "thus",
    "yet", "ever", "else",
    "my", "your", "his", "her", "its", "our", "their", "me", "him", "us",
    "them", "mine", "yours", "hers", "ours", "theirs",
    "no", "yes", "not", "non", "none", "nothing", "nobody",
    "to", "of", "in", "on", "at", "with", "for", "from", "by", "as",
    "into", "onto", "upon", "about", "up", "down", "out", "over", "under",
    "through", "between", "against", "without", "within", "beyond", "around",
    "before", "after", "during", "off", "across", "along", "behind", "below",
    "beneath", "inside", "outside", "among",
}

BAD_WORDS = {"die", "death", "kill", "hate", "ugly", "evil", "pain", "hurt", "damn"}

COPULA_MAP = {
    "I": {"is": "am", "are": "am", "was": "was", "were": "was", "does": "do", "has": "have"},
    "you": {"is": "are", "am": "are", "was": "were", "were": "were", "does": "do", "has": "have"},
}

PUNCTUATION = '.,!?;:"\''


def strip_punct(word):
    return word.lower().strip(PUNCTUATION)


def phrase_vector_float(words, dim=DIM, word_vector_fn=None):
    """Float (non-ternary) phrase vector, used by PhraseSystem/BigramSystem
    scoring. `word_vector_fn` defaults to a deterministic hash-based vector
    (same math as the ternary generator, but pre-threshold float)."""
    if word_vector_fn is None:
        import hashlib
        def word_vector_fn(w):
            h = int(hashlib.md5(w.encode()).hexdigest(), 16)
            rng = np.random.RandomState(h % (2**31))
            v = rng.randn(dim).astype(np.float32)
            v /= np.linalg.norm(v) + 1e-8
            return v
    if not words:
        return np.zeros(dim, dtype=np.float32)
    vecs = [word_vector_fn(w) for w in words]
    v = np.mean(vecs, axis=0)
    v /= np.linalg.norm(v) + 1e-8
    return v


@dataclass
class Phrase:
    surface: str
    vector: np.ndarray
    frequency: float = 1.0
    last_used: float = dataclass_field(default_factory=time.time)
    rating_history: List[float] = dataclass_field(default_factory=list)


class PhraseSystem:
    """Crystallization: recurring word groups become named phrases whose
    vectors boost future field states that resonate with them."""

    def __init__(self, max_phrases=MAX_PHRASES):
        self.phrases = {}
        self.max_phrases = max_phrases

    def _phrase_signature(self, words):
        return " ".join(words)

    def absorb_moment(self, words, presence, word_vectors, phrase_vectors):
        core = [w for w in words if w not in STRUCTURAL_WORDS and w not in BAD_WORDS]
        if len(core) < 2:
            core = words
        if len(core) < 2:
            return
        sig = self._phrase_signature(core)
        if sig in self.phrases:
            self.phrases[sig].frequency = min(self.phrases[sig].frequency + presence, 6.0)
            self.phrases[sig].rating_history.append(presence * 5.0)
            return
        if len(self.phrases) >= self.max_phrases:
            weakest = min(self.phrases, key=lambda s: self.phrases[s].frequency)
            del self.phrases[weakest]
            phrase_vectors.pop(weakest, None)
        pvec = phrase_vector_float(core)
        self.phrases[sig] = Phrase(surface=sig, vector=pvec, frequency=presence * 2.0,
                                    rating_history=[presence * 5.0])
        phrase_vectors[sig] = pvec

    def get_phrase_boost(self, field_state):
        boosts = []
        for sig, phrase in self.phrases.items():
            sim = np.dot(field_state, phrase.vector)
            if sim > 0.3:
                boosts.append((sig, sim * 0.3))
        return boosts

    def decay(self):
        now = time.time()
        to_remove = []
        for sig, phrase in self.phrases.items():
            age = now - phrase.last_used
            phrase.frequency *= math.exp(-DECAY_RATE * age)
            if phrase.frequency < 0.1:
                to_remove.append(sig)
        for sig in to_remove:
            del self.phrases[sig]


class BigramSystem:
    """Word-to-word transition statistics, weighted by how well-received
    the transition was (rating)."""

    def __init__(self):
        self.transitions = defaultdict(lambda: defaultdict(float))

    def observe(self, word1, word2, rating):
        w1, w2 = strip_punct(word1), strip_punct(word2)
        if w1 and w2 and w1 not in STRUCTURAL_WORDS and w2 not in STRUCTURAL_WORDS:
            weight = 1.0 + max(0, rating - 3) * 0.3
            self.transitions[w1][w2] += weight

    def get_transition_boost(self, prev_word, candidate):
        w1, w2 = strip_punct(prev_word), strip_punct(candidate)
        if w1 in self.transitions and w2 in self.transitions[w1]:
            total = sum(self.transitions[w1].values())
            return (self.transitions[w1][w2] / total) * 0.2
        return 0.0

    def decay(self):
        for w1 in list(self.transitions.keys()):
            for w2 in list(self.transitions[w1].keys()):
                self.transitions[w1][w2] *= 0.999
                if self.transitions[w1][w2] < 0.01:
                    del self.transitions[w1][w2]
            if not self.transitions[w1]:
                del self.transitions[w1]


class Reflector:
    """Tracks recently-spoken words and suppresses repeats - the field's
    short-term memory of its own speech, preventing loops."""

    def __init__(self, window_size=24):
        self.recent_words = deque(maxlen=window_size)
        self.suppression = defaultdict(float)

    def observe(self, word):
        w = strip_punct(word)
        if w and len(w) > 2:
            self.recent_words.append(w)
            counts = defaultdict(int)
            for rw in self.recent_words:
                counts[rw] += 1
            threshold = 2 if len(self.recent_words) < 20 else 3
            for rw, count in counts.items():
                if count >= threshold:
                    self.suppression[rw] = 0.9
                else:
                    self.suppression[rw] *= 0.85

    def get_suppression(self, word):
        return self.suppression.get(strip_punct(word), 0.0)

    def reset(self):
        self.recent_words.clear()
        self.suppression.clear()


def get_candidates_for_role(field_state, role, beam, word_vectors_ternary,
                             word_strength, reflector, calculus=None,
                             physics_weights=None, bias_fn=None,
                             word_vectors_float=None):
    """
    Pure candidate scoring: similarity + word_strength + suppression
    + (optional) calculus derivative shaping + (optional) physics
    weighting + (optional) mind-supplied bias_fn(word, vec) -> float for
    everything identity/mood/moral-compass related.

    When `word_vectors_float` is provided, scoring uses float cosine
    similarity (real embedding meaning); otherwise it falls back to the
    original ternary similarity. Returns a list of (word, score) sorted
    descending, truncated to `beam`.
    """
    if physics_weights is None:
        physics_weights = np.ones(DIM, dtype=np.float32)

    use_float = word_vectors_float is not None
    if use_float:
        fs_norm = field_state
        n = np.linalg.norm(fs_norm)
        if n > 1e-8:
            fs_norm = fs_norm / n
    else:
        fs_ternary = field_state
        if isinstance(field_state, np.ndarray) and field_state.dtype != np.int8:
            fs_ternary = np.zeros(DIM, dtype=np.int8)
            fs_ternary[field_state > 0.09] = 1
            fs_ternary[field_state < -0.09] = -1

    candidates = []
    for word, vec in word_vectors_ternary.items():
        if len(word) < 2 or word in BAD_WORDS:
            continue
        if role == "verb":
            if word not in VERB_WORDS and word not in STRUCTURAL_WORDS:
                continue
        elif role == "adj":
            if word not in ADJ_WORDS:
                continue
        elif role == "noun":
            if word in STRUCTURAL_WORDS or word in VERB_WORDS or word in ADJ_WORDS or word in FUNCTION_WORDS:
                continue
        elif word in STRUCTURAL_WORDS:
            continue

        if use_float:
            fvec = word_vectors_float.get(word)
            if fvec is None:
                continue
            vn = np.linalg.norm(fvec)
            if vn <= 1e-8:
                continue
            sim = float(fs_norm @ (fvec / vn))
        else:
            sim = weighted_ternary_dot(fs_ternary, vec, physics_weights)

        if calculus is not None and np.linalg.norm(calculus.derivative) > 0:
            deriv_float = calculus.derivative / np.linalg.norm(calculus.derivative)
            if use_float:
                vn = np.linalg.norm(fvec)
                deriv_sim = float(deriv_float @ (fvec / vn)) * 0.3
            else:
                deriv_ternary = np.zeros(DIM, dtype=np.int8)
                deriv_ternary[deriv_float > 0.09] = 1
                deriv_ternary[deriv_float < -0.09] = -1
                deriv_sim = ternary_dot(deriv_ternary, vec) * 0.3
        else:
            deriv_sim = 0.0
        sim = sim * 0.6 + deriv_sim

        strength = word_strength.get(word, 1.0) if hasattr(word_strength, "get") else word_strength[word]
        suppression = reflector.get_suppression(word) if reflector is not None else 0.0
        bias = bias_fn(word, vec) if bias_fn is not None else 0.0

        score = sim * strength * (1.0 - suppression) + bias
        candidates.append((word, score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:beam]
