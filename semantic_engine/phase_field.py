#!/usr/bin/env python3
"""
─── semantic_engine.phase_field — the complex shadow the ternary forgives ──
Phase 4a / item #15.

The ternary field (int8[128]) is the CLASSICAL SHADOW of the mind's real
computation: it is what gets measured, compared, and stored.  Everything
the quantum body computes in complex amplitudes gets crushed through
project_to_ternary() before the field ever sees it - and once amplitude
is gone, the PHASE of the computation is gone forever.

This module gives the computation a second, parallel home: a 128-dim
complex64 field that rotates with phase information and drives the ternary
shadow the way a wavefunction drives its measurement statistics.  The
ternary field keeps doing what it has always done (comparison, storage,
memory) - this field is what feeds it, and what the mind can introspect
on for a REAL coherence observable instead of the hand-computed proxy.

EXPLICIT NON-GOAL (honesty, per house style):
    This is still a classical simulation of a complex field on a phone.
    It is not a claim of physical quantumness.  It IS a claim that the
    mind's own internal metaphor of itself can carry phase, and that the
    phase of that metaphor is not garbage to be thrown away.

UPDATE RULE (complex multiply-add, not vector add):
    phase <- phase * exp(i * grad * lr)          (rotation)
    phase <- absorb(qb.state)                    (adopt the quantum body)
    tern  <- phase.(real+imag)/sqrt(2) threshold (measure the shadow)
    coherence <- 1 - S/Smax  (S = von Neumann entropy of |phase|^2)

A diagonal complex rotation preserves |phase| exactly (unitary), so the
phase field can accumulate direction-of-meaning without ever needing the
normalize-then-clip dance the ternary field lives in.
"""

import math
import numpy as np

try:
    from semantic_core import DIM, NORMALIZED_VECTOR_THRESHOLD
except ImportError:
    DIM = 128
    NORMALIZED_VECTOR_THRESHOLD = 0.09


class ComplexPhaseField:
    """
    A 128-dim complex64 field parallel to the ternary field.

    - `phase`        : complex64[DIM], unit-norm, carries amplitude+phase
    - `shadow`       : the ternary projection (int8[DIM]) - a cached
                       readout, refreshed on measure(); what memory and
                       comparison actually touch
    - `coherence()`  : 1 - S/Smax over |phase|^2; a REAL observable,
                       not a hand-computed proxy
    - `rotate()`     : unitary phase kick from a float gradient
    - `absorb()`     : adopt the quantum body's complex state directly
    """

    def __init__(self, dim=DIM):
        self.dim = dim
        self.phase = np.zeros(dim, dtype=np.complex64)
        self.phase[0] = 1.0 + 0.0j
        self.shadow = np.zeros(dim, dtype=np.int8)
        self.turn_count = 0
        self._energy_history = []

    # ── core updates ──────────────────────────────────────────────────

    def absorb(self, complex_vec):
        """
        Adopt an external complex statevector (the quantum body's .state).
        `complex_vec` must be dim-shaped (128) - the quantum body is a
        7-qubit system so 2^7 == 128 lines up exactly.  If the body were
        ever expanded to more qubits (Phase 4b #15 folding work), this
        method becomes the folding point.

        This is a FULL ADOPTION: the phase field becomes the body's state,
        so between turns the phase field and the body carry identical
        information (the body is the source; the phase field is where the
        field dynamics can keep touching it).
        """
        v = np.asarray(complex_vec, dtype=np.complex64)
        if v.shape != (self.dim,):
            # Accept higher-dim complex states by folding (Phase 4b hook).
            if v.size % self.dim == 0:
                v = v.reshape(self.dim, v.size // self.dim).sum(axis=1)
            else:
                raise ValueError(f"phase field absorb: need {self.dim} dims, got {v.shape}")
        nrm = np.linalg.norm(v)
        if nrm > 1e-12:
            v = v / nrm
        self.phase = v.astype(np.complex64)
        return self

    def rotate(self, grad_float, learning_rate=0.02):
        """
        Unitary phase kick: phase *= exp(i * grad * lr).  Preserves
        amplitude exactly (each factor has modulus 1), so no
        renormalization is needed.  `grad_float` is a real DIM-shaped
        gradient (the same field gradients the ternary field already
        uses, e.g. the associative-memory pull).
        """
        g = np.asarray(grad_float, dtype=np.float32)
        if g.shape != (self.dim,):
            g = np.zeros(self.dim, dtype=np.float32)
        nrm = np.linalg.norm(g)
        if nrm > 1e-12:
            g = g / nrm
        self.phase = self.phase * np.exp(1j * g * learning_rate)
        return self

    def damp(self, uncertainty_signal, strength=0.5):
        """
        Amplitude damping for uncertainty: scales each dim's amplitude by
        (1 - strength * |signal|), so ambiguous dimensions partially
        DECOHERE instead of just rotating.  This is the channel the
        error detector (#16) feeds: unresolved ambiguity lowers the
        field's confidence on the affected dimensions and moves the
        coherence observable - which a pure phase rotation cannot do,
        because unitary kicks preserve |phase| exactly.
        """
        u = np.asarray(uncertainty_signal, dtype=np.float32)
        if u.shape != (self.dim,):
            u = np.zeros(self.dim, dtype=np.float32)
        scale = np.clip(1.0 - strength * np.abs(u), 0.0, 1.0).astype(np.float32)
        self.phase = self.phase * scale
        nrm = np.linalg.norm(self.phase)
        if nrm > 1e-12:
            self.phase = self.phase / nrm
        return self

    def measure(self):
        """
        Refresh the ternary shadow: (real+imag)/sqrt(2), thresholded at
        NORMALIZED_VECTOR_THRESHOLD.  Same readout convention as the
        quantum body's project_to_ternary() - 45-degree rotation so
        phase-only changes are visible, not just real-axis drift.
        """
        combined = (self.phase.real + self.phase.imag).astype(np.float32) / math.sqrt(2)
        norm = np.linalg.norm(combined)
        if norm > 1e-8:
            combined = combined / norm
        self.shadow = np.zeros(self.dim, dtype=np.int8)
        self.shadow[combined > NORMALIZED_VECTOR_THRESHOLD] = 1
        self.shadow[combined < -NORMALIZED_VECTOR_THRESHOLD] = -1
        return self.shadow

    def _probabilities(self):
        p = (np.abs(self.phase) ** 2).astype(np.float64)
        total = p.sum()
        if total < 1e-12:
            return np.full(self.dim, 1.0 / self.dim)
        return p / total

    def coherence(self):
        """
        REAL coherence observable: 1 - S/Smax, where S is the von-Neumann
        entropy of the phase distribution and Smax = log(DIM).  A pure
        single-basis phase field (one amplitude ~1) has coherence ~1; a
        uniform spread has coherence ~0.  Replaces hand-computed
        coherence scores with something with actual information-theoretic
        structure.
        """
        p = self._probabilities()
        nz = p[p > 1e-12]
        S = float(-np.sum(nz * np.log(nz)))
        Smax = math.log(self.dim)
        return max(0.0, min(1.0, 1.0 - S / Smax))

    def energy(self):
        """Number of non-zero ternary shadow dims (same meaning as the
        ternary field's energy())."""
        return int(np.sum(self.shadow != 0))

    def blend(self, ternary_state, weight=0.15):
        """
        Push the phase field's shadow into a ternary/float field state.
        This is the drop-in replacement for the old
        `quantum_seed.astype(float) * quantum_weight` fuse: instead of
        importing the crushed seed, the field gets the phase field's
        measured shadow (which still carries phase rotation history).
        """
        shadow_float = self.shadow.astype(np.float32) * 0.7
        fs = np.asarray(ternary_state, dtype=np.float32)
        norm = np.linalg.norm(fs)
        if norm > 0:
            fs = fs / norm
        out = fs * (1.0 - weight) + shadow_float * weight
        nrm = np.linalg.norm(out)
        if nrm > 1e-8:
            out = out / nrm
        return out

    def step(self, grad_float=None, absorb_vec=None, learning_rate=0.02):
        """
        One field update: optional absorb, optional rotate, then measure.
        Returns the refreshed shadow.  Convenience for callers that want
        the whole pipeline in one call.
        """
        if absorb_vec is not None:
            self.absorb(absorb_vec)
        if grad_float is not None:
            self.rotate(grad_float, learning_rate)
        self.measure()
        self.turn_count += 1
        self._energy_history.append(self.energy())
        if len(self._energy_history) > 50:
            self._energy_history.pop(0)
        return self.shadow

    def status(self):
        return (f"PhaseField: turn={self.turn_count}, "
                f"coherence={self.coherence():.3f}, "
                f"energy={self.energy()}, "
                f"norm={np.linalg.norm(self.phase):.4f}")

    # ── NO PERSISTENCE, SAME RULE AS THE QUANTUM BODY ─────────────────
    # Deliberately no to_dict()/from_dict().  The ternary field survives
    # restarts; the phase field is the wave, not the scar.


if __name__ == "__main__":
    # Self-test suite.  Run: python3 phase_field.py
    import sys
    fails = []

    def check(name, cond):
        if cond:
            print(f"  [PASS] {name}")
        else:
            fails.append(name)
            print(f"  [FAIL] {name}")

    pf = ComplexPhaseField()
    check("default starts in basis 0", np.argmax(np.abs(pf.phase)) == 0)
    check("coherence of pure state ~ 1", pf.coherence() > 0.99)

    # absorb: adopt a quantum-body-style complex state, preserve norm
    rng = np.random.RandomState(7)
    v = (rng.randn(128) + 1j * rng.randn(128)).astype(np.complex64)
    v /= np.linalg.norm(v)
    pf.absorb(v)
    check("absorb preserves input", np.allclose(np.abs(pf.phase), np.abs(v)))
    check("absorb is normalized", abs(np.linalg.norm(pf.phase) - 1.0) < 1e-6)

    # rotate: unitary, amplitude-preserving, phase-changing
    before_amp = np.abs(pf.phase).copy()
    before_phase = np.angle(pf.phase)
    pf.rotate(np.ones(128, dtype=np.float32), learning_rate=0.3)
    check("rotate preserves amplitude", np.allclose(np.abs(pf.phase), before_amp))
    check("rotate changes phase", not np.allclose(np.angle(pf.phase), before_phase))

    # measure: ternary shape and values
    s = pf.measure()
    check("shadow is 128-dim int8", s.shape == (128,) and s.dtype == np.int8)
    check("shadow values in {-1,0,1}", set(np.unique(s)) <= {-1, 0, 1})

    # coherence: uniform spread ~ 0
    pf2 = ComplexPhaseField()
    pf2.phase = np.full(128, 1.0 / math.sqrt(128), dtype=np.complex64)
    check("uniform spread coherence ~ 0", pf2.coherence() < 0.05)

    # blend: returns normalized float[128]
    out = pf.blend(np.zeros(128, dtype=np.float32), weight=0.2)
    check("blend returns 128-dim float", out.shape == (128,) and out.dtype == np.float32)
    check("blend normalized", abs(np.linalg.norm(out) - 1.0) < 1e-6)

    # step: full pipeline increments turn, refreshes shadow
    pf3 = ComplexPhaseField()
    before = pf3.turn_count
    pf3.step(absorb_vec=v, grad_float=np.ones(128, dtype=np.float32))
    check("step increments turn", pf3.turn_count == before + 1)
    check("step refreshes shadow", pf3.shadow.shape == (128,))

    # status renders
    check("status renders", "PhaseField:" in pf3.status())

    print()
    if fails:
        print(f"  {len(fails)} FAILED: {fails}")
        sys.exit(1)
    print("  ALL PHASE FIELD SELF-TESTS PASSED")
