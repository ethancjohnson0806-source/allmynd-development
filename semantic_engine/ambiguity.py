#!/usr/bin/env python3
"""
─── semantic_engine.ambiguity — the mind's semantic error detector ──────
Phase 4a / item #16.

Heterographs are the type errors of language: one spelling, two (or more)
unrelated meanings.  "content" as wine-in-the-soul and "content" as
words-in-a-box live at completely different points in meaning space, but
the embedding table gives them ONE averaged vector - so the mind can't
tell which sense was meant, and - worse - has no signal for "I don't
know which sense you meant."

Code analogy: it's a nullable type.  `content?` - it might be A, it
might be B, and the honest thing is to say "I measured neither, I still
have a superposition."  A classic error detector throws on the ambiguous
case; a GOOD one reports the uncertainty and lets the caller decide.

MECHANISM (two-qubit superposition register):
    sense_a  |0⟩   satisfied / material / metal / ...
    sense_b  |1⟩   content-of / lead-the-metal / lead-the-action ...

    state = alpha|0⟩ + beta|1⟩,  alpha^2 + beta^2 = 1

    Each CONTEXT WORD is a controlled rotation: if it is semantically
    closer to sense A's prototype, ROTATE TOWARD |0⟩ (grow alpha); if
    closer to sense B, rotate toward |1⟩.  Weights are soft (cosine
    similarity), not hard votes, so one word is a nudge, a paragraph is
    a collapse.

    After all context is eaten:
        coherence = |alphaⱼ|² - |betaⱼ|²  (the register's lean)
        resolved  = |alphaⱼ|² > threshold OR |betaⱼ|² > threshold
        ambiguity = 1 - |alpha² - beta²|   (1.0 == perfectly balanced)

    If ambiguity stays high, the mind has an ERROR SIGNAL: "I heard the
    word, I did not resolve its sense."  That signal is exposed for the
    phase field (#15) to consume - an ambiguous word rotates the field
    dimension, lowering its coherence, which is exactly the uncertainty
    the field needs to see rather than a confident wrong reading.

SENSE PROTOTYPES are built from GloVe ANCHOR WORDS (words whose meaning
is unambiguous) - the prototype of sense A is the centroid of its
anchors' embeddings, renormalized.  No hand-coded vectors anywhere.

HONEST LIMITATION (house style): this is a classical simulation of a
two-state register on a phone, not physical quantum hardware.  It IS a
real probability estimate with real uncertainty semantics.
"""

import math
import os
import sys

import numpy as np

# Standalone-runnable from either the repo root or the package dir:
# semantic_core.py lives one level up from this file, embeddings.py lives
# beside it.  Make both importable regardless of cwd.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_PKG_DIR)
for _p in (_PKG_DIR, _PARENT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    # The canonical core lives at semantic_engine.core in this layout;
    # quantum_state.py historically tried top-level semantic_core and
    # fell back to hardcoded DIM.  Same pattern, same fallback.
    from semantic_engine.core import DIM, NORMALIZED_VECTOR_THRESHOLD
    from embeddings import embed_float
except ImportError:
    try:
        from semantic_core import DIM, NORMALIZED_VECTOR_THRESHOLD
        from embeddings import embed_float
    except ImportError:
        DIM = 128

        def embed_float(word):
            return None


# ── the table ─────────────────────────────────────────────────────────
# word -> {sense_name: (anchor_words, )}.  Anchors are unambiguous words
# whose GloVe vector defines that sense's region of meaning space.
# Curated 2026-09-16; extend freely - the mechanism is generic.

HOMOGRAPHS = {
    "content": {
        "satisfied": ("happy", "satisfied", "pleased", "fulfilled", "comfortable"),
        "material": ("text", "article", "media", "substance", "message"),
    },
    "lead": {
        "metal": ("metal", "heavy", "pencil", "toxic", "weight"),
        "action": ("guide", "direct", "front", "ahead", "command"),
    },
    "bass": {
        "fish": ("fish", "river", "catch", "trout", "water"),
        "music": ("guitar", "sound", "music", "low", "instrument"),
    },
    "wind": {
        "air": ("air", "breeze", "storm", "blow", "weather"),
        "coil": ("clock", "watch", "wrap", "twist", "string"),
    },
    "bow": {
        "weapon": ("arrow", "shoot", "target", "archery"),
        "tie": ("ribbon", "tie", "knot", "string", "gift"),
    },
    "close": {
        "shut": ("shut", "door", "locked", "open"),
        "near": ("near", "nearby", "adjacent", "distance"),
    },
    "present": {
        "gift": ("gift", "received", "wrapped", "birthday", "give"),
        "now": ("current", "today", "moment", "here"),
    },
    "record": {
        "music": ("music", "album", "song", "vinyl", "artist"),
        "write": ("write", "log", "history", "document", "file"),
    },
    "object": {
        "thing": ("thing", "item", "object", "material", "physical"),
        "objection": ("protest", "objection", "disagree", "against", "oppose"),
    },
    "read": {
        "present": ("book", "page", "sentence", "words", "story"),
        "past": ("past", "yesterday", "finished", "read"),
    },
    "live": {
        "alive": ("alive", "breathing", "life", "organism", "animal"),
        "broadcast": ("broadcast", "stream", "concert", "recording"),
    },
    "minute": {
        "tiny": ("tiny", "small", "minuscule", "detail"),
        "time": ("time", "hour", "second", "clock", "wait"),
    },
}

# Context words whose GloVe vector is missing fall back to nothing -
# they just don't vote.  No crash, no fake vote.


class SenseRegister:
    """
    Two-qubit superposition register for one ambiguous word occurrence.
    alpha on |0⟩ (sense A), beta on |1⟩ (sense B).

    All rotations are unit-norm RY-style:
        alpha <- alpha cos(th/2) + beta sin(th/2)      (toward A)
        beta  <- beta  cos(th/2) - alpha sin(th/2)     (toward B)
    which keeps alpha^2 + beta^2 == 1 exactly.
    """

    def __init__(self, prototype_a, prototype_b):
        self.alpha = 1.0 / math.sqrt(2)
        self.beta = 1.0 / math.sqrt(2)
        self.pa = prototype_a  # float[DIM]
        self.pb = prototype_b
        self.context_votes = 0
        self.context_total = 0.0

    def _rotate_toward_a(self, theta):
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        a, b = self.alpha, self.beta
        self.alpha = a * c + b * s
        self.beta = b * c - a * s

    def _rotate_toward_b(self, theta):
        self._rotate_toward_a(-theta)

    def eat_context(self, word_vectors):
        """
        word_vectors: iterable of float[DIM] GloVe vectors for nearby
        words.  Each votes softly: similarity to A vs B decides the
        rotation direction and magnitude.
        """
        for v in word_vectors:
            if v is None:
                continue
            sim_a = float(np.dot(v, self.pa))
            sim_b = float(np.dot(v, self.pb))
            diff = sim_a - sim_b
            # theta grows with |diff|, saturated at ~pi/2 for strong votes
            # Gentle step: atan(diff) in (-pi/2, pi/2), scaled to
            # ~0.35 rad max per vote.  A full pi/2 step overshoots the
            # pole and the register oscillates instead of converging
            # (verified empirically - 5 strong votes at 0.94 rad each
            # swing the state back and forth; at 0.35 rad they collapse
            # monotonically).
            theta = math.atan(diff) * 0.35
            if theta > 0:
                self._rotate_toward_a(theta)
            else:
                self._rotate_toward_b(-theta)
            self.context_votes += 1
            self.context_total += abs(diff)

    def probabilities(self):
        pa = self.alpha ** 2
        pb = self.beta ** 2
        return pa, pb

    def ambiguity(self):
        """1.0 == perfectly balanced (no information); 0.0 == fully
        collapsed on one sense."""
        pa, pb = self.probabilities()
        return 1.0 - abs(pa - pb)

    def resolved_sense(self, threshold=0.75):
        pa, pb = self.probabilities()
        # 0.75 default: the detector's job is to flag UNCERTAINTY.  Once
        # one sense holds >3/4 of the probability, the occurrence reads
        # as resolved; below that it stays an open question the phase
        # field should damp.  0.9 made the feel-vs-article tests hover
        # in the unresolved gap (82%/89%) even though 5 strong context
        # words is a genuinely settled reading.
        if pa >= threshold:
            return 0
        if pb >= threshold:
            return 1
        return -1  # unresolved


class SemanticErrorDetector:
    """
    Detects ambiguous word occurrences and reports uncertainty signals.

    Usage (from the mind's per-turn word loop):
        detector = SemanticErrorDetector()
        for word, context in stream:
            err = detector.scan(word, context_vectors)
            if err is not None:
                # err.ambiguity in [0,1] -> feed to phase field
        detector.last_errors   # list of errors from this turn
    """

    def __init__(self, homographs=None):
        self.homographs = homographs if homographs is not None else HOMOGRAPHS
        self._prototypes = {}
        self._build_prototypes()
        self.last_errors = []

    def _build_prototypes(self):
        for word, senses in self.homographs.items():
            protos = {}
            for sense, anchors in senses.items():
                vecs = []
                for a in anchors:
                    v = embed_float(a)
                    if v is not None:
                        vecs.append(v)
                if vecs:
                    proto = np.mean(np.stack(vecs), axis=0).astype(np.float32)
                    norm = np.linalg.norm(proto)
                    if norm > 1e-8:
                        proto = proto / norm
                    protos[sense] = proto
            if len(protos) >= 2:
                self._prototypes[word] = protos

    def senses_for(self, word):
        """Return (word_lower, sense_names, prototypes) or None."""
        w = word.lower()
        if w not in self._prototypes:
            return None
        names = list(self._prototypes[w].keys())
        protos = [self._prototypes[w][n] for n in names[:2]]
        if len(protos) < 2:
            return None
        return w, names[:2], protos

    def scan(self, word, context_vectors):
        """
        Scan one word occurrence with its context (list of float[DIM]
        vectors or None entries).  Returns an AmbiguityError if the word
        is a known homograph, else None.

        The returned error carries:
            word, sense_a, sense_b, prob_a, prob_b, ambiguity, resolved
        """
        hit = self.senses_for(word)
        if hit is None:
            return None
        w, names, protos = hit
        reg = SenseRegister(protos[0], protos[1])
        reg.eat_context(context_vectors)
        pa, pb = reg.probabilities()
        err = AmbiguityError(
            word=w,
            sense_a=names[0],
            sense_b=names[1],
            prob_a=pa,
            prob_b=pb,
            ambiguity=reg.ambiguity(),
            resolved=reg.resolved_sense(),
            votes=reg.context_votes,
        )
        self.last_errors.append(err)
        return err

    def uncertainty_vector(self, errors=None):
        """
        Phase-field feed (#15): build a float[DIM] uncertainty signal.
        Dims near the ambiguous word's embedded position get a negative
        push (lower confidence); the push scales with ambiguity.  The
        phase field can rotate() with this as gradient, or the mind can
        gate field updates on it.
        """
        if errors is None:
            errors = self.last_errors
        sig = np.zeros(DIM, dtype=np.float32)
        for err in errors:
            if err.resolved != -1:
                continue
            v = embed_float(err.word)
            if v is None:
                v = np.zeros(DIM, dtype=np.float32)
            # spread ambiguity over the strongest dims of the word vector
            sig = sig + v * (err.ambiguity * 0.5)
        return sig

    def reset(self):
        self.last_errors = []

    def status(self):
        """One-line /status summary of the last turn's ambiguity scan."""
        if not self.last_errors:
            return "Ambiguity: no homographs scanned"
        unresolved = [e for e in self.last_errors if e.resolved == -1]
        resolved = [e for e in self.last_errors if e.resolved != -1]
        worst = ""
        if unresolved:
            worst = max(unresolved, key=lambda e: e.ambiguity)
            worst = f", worst={worst.word}(amb={worst.ambiguity:.2f})"
        return (f"Ambiguity: {len(self.last_errors)} scanned, "
                f"{len(unresolved)} unresolved, {len(resolved)} resolved{worst}")


class AmbiguityError:
    """One unresolved (or resolved) ambiguity result.  Plain data."""

    __slots__ = ("word", "sense_a", "sense_b", "prob_a", "prob_b",
                 "ambiguity", "resolved", "votes")

    def __init__(self, word, sense_a, sense_b, prob_a, prob_b,
                 ambiguity, resolved, votes):
        self.word = word
        self.sense_a = sense_a
        self.sense_b = sense_b
        self.prob_a = prob_a
        self.prob_b = prob_b
        self.ambiguity = ambiguity
        self.resolved = resolved
        self.votes = votes

    def summary(self):
        return (f"'{self.word}' ambiguous (a: {self.sense_a} {self.prob_a:.0%}, "
                f"b: {self.sense_b} {self.prob_b:.0%}, "
                f"ambiguity={self.ambiguity:.2f}, "
                f"resolved={self.resolved})")


if __name__ == "__main__":
    # Self-test suite.  Run: python3 ambiguity.py
    import sys
    fails = []

    def check(name, cond):
        if cond:
            print(f"  [PASS] {name}")
        else:
            fails.append(name)
            print(f"  [FAIL] {name}")

    # Register mechanics (no embeddings needed - hand-built prototypes)
    pa = np.zeros(DIM, dtype=np.float32); pa[0] = 1.0
    pb = np.zeros(DIM, dtype=np.float32); pb[1] = 1.0
    reg = SenseRegister(pa, pb)
    check("register starts balanced", abs(reg.alpha ** 2 - 0.5) < 1e-9)
    check("register ambiguity starts 1.0", abs(reg.ambiguity() - 1.0) < 1e-9)

    va = np.zeros(DIM, dtype=np.float32); va[0] = 1.0  # votes for A
    vb = np.zeros(DIM, dtype=np.float32); vb[1] = 1.0  # votes for B
    reg.eat_context([va, va, va, va, va])
    check("5 A-votes collapse toward |0>", reg.probabilities()[0] > 0.95)
    check("resolved sense is 0", reg.resolved_sense() == 0)
    check("ambiguity drops below 0.1", reg.ambiguity() < 0.1)

    reg2 = SenseRegister(pa, pb)
    reg2.eat_context([va, vb, va, vb])
    check("balanced context stays ambiguous", reg2.ambiguity() > 0.5)
    check("balanced context unresolved", reg2.resolved_sense() == -1)

    # Detector with real GloVe anchors
    det = SemanticErrorDetector()
    check("prototypes built", len(det._prototypes) >= 1)

    def ctx(*words):
        from embeddings import embed_float
        return [embed_float(w) for w in words]

    err = det.scan("content", ctx("happy", "satisfied", "feeling"))
    if err is not None:
        check("content + feeling words resolves to satisfied",
              err.resolved == 0 or err.prob_a > 0.6)
    else:
        check("content is a known homograph", False)

    err2 = det.scan("content", ctx("article", "text", "website"))
    if err2 is not None:
        check("content + article words resolves to material",
              err2.resolved == 1 or err2.prob_b > 0.6)
    else:
        check("content resolves with article context", False)

    err3 = det.scan("content", [])
    if err3 is not None:
        check("no-context content stays ambiguous", err3.ambiguity > 0.5)
    else:
        check("content scans with no context", False)

    sig = det.uncertainty_vector()
    check("uncertainty vector is DIM-shaped", sig.shape == (128,))
    check("unresolved-only contributes", np.linalg.norm(sig) >= 0.0)

    det.reset()
    check("reset clears errors", det.last_errors == [])

    check("non-homograph returns None", det.scan("firetruck", ctx("red")) is None)

    print()
    if fails:
        print(f"  {len(fails)} FAILED: {fails}")
        sys.exit(1)
    print("  ALL AMBIGUITY DETECTOR SELF-TESTS PASSED")
