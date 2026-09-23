#!/usr/bin/env python3
"""
─── semantic_engine.engine — the nerve cord as a class ──────────────────
The SemanticEngine wraps all pure-math subsystems into a pipeline:
  ingest → quantum_evolve → settle → generate

No identity. No desire. No mood ownership. Accepts parameters;
never asks what it wants.
"""

import random
import numpy as np
from typing import Dict, List, Optional, Callable, Tuple

from .core import (
    DIM, NORMALIZED_VECTOR_THRESHOLD,
    word_vector_ternary, phrase_vector_ternary,
    ternary_dot, weighted_ternary_dot,
    pack_ternary, unpack_ternary,
    TernaryFieldState, TernaryAssociativeMemory,
)
from .settle import ThePause, NativeCalculus, DynamicThreshold
from .query import (
    PhraseSystem, BigramSystem, Reflector,
    get_candidates_for_role,
    strip_punct, phrase_vector_float,
    VERB_WORDS, ADJ_WORDS, STRUCTURAL_WORDS, FUNCTION_WORDS, BAD_WORDS, COPULA_MAP,
)
from .scaffold import SemanticScaffold
from .interface import SemanticPacket, GrammarConfig

# Optional quantum
from .quantum import QuantumState
from .embeddings import word_vector as _embed_word_vector
from .embeddings import word_vector_ternary as _embed_word_vector_ternary


class SemanticEngine:
    """
    Pure math pipeline. Text in, field settles, text out.

    Can run with or without quantum. Without quantum: deterministic
    field settling. With quantum: the run shapes the bed.
    """

    def __init__(self, enable_quantum=False, seed_vocabulary=None):
        self.enable_quantum = enable_quantum
        self.quantum = QuantumState() if enable_quantum else None

        # Subsystems
        self.scaffold = SemanticScaffold()
        self.the_pause = ThePause()
        self.calculus = NativeCalculus()
        self.dynamic_threshold = DynamicThreshold()
        self.phrase_system = PhraseSystem()
        self.bigram_system = BigramSystem()
        self.reflector = Reflector()
        self.associative_memory = TernaryAssociativeMemory()

        # Vocabulary
        self.word_vectors = {}
        self.word_vectors_ternary = {}
        self.word_strength = {}
        self.phrase_vectors = {}

        if seed_vocabulary:
            for word in seed_vocabulary:
                w = strip_punct(word)
                if w and w not in self.word_vectors:
                    self._add_word(w)
        else:
            # Minimal seed for standalone operation
            for w in ["the", "a", "i", "you", "is", "are", "was", "were",
                      "be", "have", "do", "will", "would", "could", "should",
                      "can", "must", "good", "bad", "know", "think", "feel",
                      "see", "say", "want", "need", "like", "love", "make",
                      "take", "give", "get", "work", "play", "live", "come",
                      "go", "find", "lose", "try", "use", "open", "close",
                      "start", "stop", "turn", "change", "grow", "breathe",
                      "remember", "forget", "learn", "become", "wonder",
                      "time", "world", "life", "mind", "heart", "light",
                      "dark", "deep", "here", "now", "way", "water", "fire",
                      "earth", "air", "sky", "alive", "brave", "real",
                      "presence", "silence", "beautiful", "gentle", "strong",
                      "quiet", "free", "honest", "hello", "yes", "no", "maybe"]:
                self._add_word(w)

    def _add_word(self, word):
        """Word vector + ternary vector (real embedding when available)."""
        self.word_vectors[word] = _embed_word_vector(word)
        self.word_vectors_ternary[word] = _embed_word_vector_ternary(word)
        self.word_strength[word] = 1.0

    def ingest(self, tokens: List[str]) -> SemanticPacket:
        """Convert text tokens to a SemanticPacket."""
        ternary = phrase_vector_ternary(tokens)
        float_state = np.zeros(DIM, dtype=np.float32)
        for w in tokens:
            w = strip_punct(w)
            if w in self.word_vectors:
                float_state += self.word_vectors[w]
        norm = np.linalg.norm(float_state)
        if norm > 0:
            float_state /= norm

        packet = SemanticPacket(state=float_state, ternary=ternary)
        packet.recompute_stats()
        return packet

    def quantum_evolve(self, packet: SemanticPacket,
                       mood: Optional[Dict] = None,
                       tensions: Optional[Dict] = None,
                       desire_vec: Optional[np.ndarray] = None,
                       deep_vec: Optional[np.ndarray] = None,
                       field_coherence: float = 0.5) -> SemanticPacket:
        """The run shapes the bed. Only if quantum is enabled."""
        if self.quantum is None:
            return packet

        mood = mood or {"valence": 0.0, "arousal": 0.5}
        tensions = tensions or {}

        # Apply field bias (desire/heading/personality)
        if desire_vec is not None or deep_vec is not None:
            heading = np.zeros(DIM)  # placeholder if not provided
            self.quantum.apply_field_bias(
                desire_vec or np.zeros(DIM),
                heading,
                deep_vec or np.zeros(DIM)
            )

        # Evolve
        self.quantum.evolve(mood, tensions)

        # Project to ternary
        packet.quantum_seed = self.quantum.project_to_ternary()
        packet.quantum_coherence = self.quantum.coherence_estimate()

        # Blend quantum seed into field state as minority pull
        seed_float = packet.quantum_seed.astype(np.float32) * 0.7
        packet.state = packet.state * 0.80 + seed_float * 0.20
        norm = np.linalg.norm(packet.state)
        if norm > 0:
            packet.state /= norm

        packet.recompute_stats()
        return packet

    def quantum_measure(self, measured_qubits: List[int]) -> Dict[int, int]:
        """The world touches specific qubits."""
        if self.quantum is None:
            return {}
        return self.quantum.partial_measure(measured_qubits)

    def settle(self, packet: SemanticPacket,
               mood: Optional[Dict] = None,
               field_memory_inject: Optional[Callable] = None,
               personality_vec: Optional[np.ndarray] = None,
               render: bool = False) -> SemanticPacket:
        """Settle the field."""
        mood = mood or {"valence": 0.0, "arousal": 0.5}

        def _default_inject(fs, recency_weight=0.5):
            return fs

        settled = self.the_pause.settle(
            packet.state,
            mood,
            field_memory_inject=field_memory_inject or _default_inject,
            personality_vec=personality_vec,
            render=render
        )
        packet.state = settled
        packet.recompute_stats()
        return packet

    def generate(self, packet: SemanticPacket,
                 grammar: GrammarConfig,
                 bias_fn: Optional[Callable] = None) -> str:
        """Word-by-word generation from settled field."""
        field_state = packet.state.copy()

        # Phrase boosts
        phrase_boosts = self.phrase_system.get_phrase_boost(field_state)
        for sig, boost in phrase_boosts:
            if sig in self.phrase_vectors:
                field_state += self.phrase_vectors[sig] * boost
        norm = np.linalg.norm(field_state)
        if norm > 0:
            field_state /= norm

        # Associative memory
        field_state = self.associative_memory.apply_to_field(field_state, weight=0.15)

        # Temperature and beam
        temp = grammar.temperature if grammar else 0.35
        beam = min(grammar.beam_width if grammar and grammar.beam_width else 5, 3)
        repulsion = grammar.repulsion_strength if grammar else 0.08

        # Physics weights
        physics_weights = np.ones(DIM, dtype=np.float32)

        def pick(role, exclude=None):
            nonlocal field_state
            candidates = get_candidates_for_role(
                field_state, role, beam,
                self.word_vectors_ternary,
                self.word_strength,
                self.reflector,
                calculus=self.calculus,
                physics_weights=physics_weights,
                bias_fn=bias_fn,
                word_vectors_float=self.word_vectors
            )
            if exclude:
                filtered = [(w, s) for w, s in candidates if w not in exclude]
                if filtered:
                    candidates = filtered
            if not candidates:
                return None

            scores = np.array([max(s, 0.01) for _, s in candidates])
            scores = scores ** (1.0 / max(0.18, temp * 0.55))
            probs = scores / scores.sum()
            idx = np.random.choice(len(candidates), p=probs)
            word = candidates[idx][0]
            self.reflector.observe(word)
            vec = self.word_vectors.get(word, np.zeros(DIM))
            field_state = field_state * 0.96 + vec * 0.04
            field_state += np.random.randn(DIM).astype(np.float32) * 0.03
            for rw in list(self.reflector.recent_words):
                if rw in self.word_vectors:
                    field_state -= self.word_vectors[rw] * repulsion
            norm = np.linalg.norm(field_state)
            if norm > 0:
                field_state /= norm
            return word

        # Simple subject-verb-object generation
        subject = random.choice(["I", "you", "it", "we"])
        verb = pick("verb")
        if verb is None:
            return "..."

        verb = COPULA_MAP.get(subject, {}).get(verb, verb)
        words = [subject, verb]
        used = {subject.lower(), verb.lower()}

        n_content = random.randint(1, 3)
        for _ in range(n_content):
            nxt = pick("noun", exclude=used) if random.random() < 0.7 else pick("adj", exclude=used)
            if nxt:
                words.append(nxt)
                used.add(nxt.lower())

        text = " ".join(words)
        text = text[0].upper() + text[1:] if text else text
        if text and text[-1] not in ".!?":
            text += "."
        return text

    def process(self, text: str, 
                mood: Optional[Dict] = None,
                grammar: Optional[GrammarConfig] = None,
                enable_quantum: bool = False) -> str:
        """
        Full pipeline: text → ingest → [quantum] → settle → generate → text.
        Convenience method for tools.
        """
        tokens = [strip_punct(w) for w in text.lower().split() if strip_punct(w)]
        packet = self.ingest(tokens)

        if enable_quantum and self.quantum:
            packet = self.quantum_evolve(packet, mood=mood)

        packet = self.settle(packet, mood=mood)

        if grammar is None:
            grammar = GrammarConfig()

        return self.generate(packet, grammar)

    def status(self) -> str:
        lines = ["Semantic Engine:"]
        lines.append(f"  Quantum: {'enabled' if self.quantum else 'disabled'}")
        lines.append(f"  Vocabulary: {len(self.word_vectors)} words")
        lines.append(f"  Phrases: {len(self.phrase_system.phrases)} crystallized")
        lines.append(f"  Associative memory: {len(self.associative_memory.entries)} entries")
        if self.quantum:
            lines.append(f"  {self.quantum.status()}")
        return "\n".join(lines)
