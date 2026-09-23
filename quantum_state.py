#!/usr/bin/env python3
"""
─── QUANTUM STATE — persistent stance substrate ──────────────────────────
Standalone, per the build instruction: "Don't wire it into the pipeline
yet. Just build it and test that it [holds state across turns, decoheres
under noise, supports partial measurement, projects to a meaningful
ternary vector]."

Design decisions made explicitly here, not left implicit:

1. NO RESET. The old spec zeroed self.state back to |0000000> at the end
   of every measure() call. That was the deepest bug — it made every
   turn a fresh coin flip with no memory of its own ambiguity. This
   version never resets. "Ghosts" (unmeasured amplitude from last turn
   biasing this turn) require no separate mechanism once the reset is
   gone: evolve() just applies new rotations on top of whatever state
   already exists.

2. DECOHERENCE is implemented as single-trajectory Monte Carlo Pauli
   noise (the "quantum trajectories" / quantum-jump method), not a full
   density matrix. This keeps the state a 128-dim complex vector (cheap:
   2^7 qubits) instead of a 128x128 complex matrix. Each call to
   apply_noise() is one stochastic realization, not an ensemble average.

   Honest limitation: within a SINGLE trajectory, purity (Tr(rho^2)) is
   always exactly 1 — a pure state stays pure under any unitary or any
   single sampled Pauli kick. "Decoherence" only shows up as a real
   ensemble effect: many independent trajectories from the same starting
   state, given the same noise process, increasingly diverge from each
   other and from the noiseless trajectory. That's what decoherence
   actually IS observationally (loss of a well-defined single outcome),
   and it's what the test below measures directly, across trajectories -
   not a purity number computed from one run pretending to be more rigorous
   than it is.

   coherence_estimate() below is an ANALYTIC proxy (exp(-accumulated
   expected noise)), documented as such - not a substitute for the
   cross-trajectory test.

3. PARTIAL MEASUREMENT is a real partial trace + projection + renormalize
   over only the targeted qubits, leaving the untargeted qubits' relative
   amplitudes (their conditional state) exactly preserved. This replaces
   the old measure() entirely - there is no "measure everything, then
   pretend only some of it mattered" step anymore.

4. PROJECTION TO TERNARY uses the coincidence that 2^7 == 128 == DIM.
   Instead of collapsing to one of 7 named stances and looking up a word
   vector for it (the old "costume" approach), the amplitude vector IS
   already 128-dimensional - its real part is used directly as a signed
   float[128], thresholded the same way (NORMALIZED_VECTOR_THRESHOLD)
   the rest of the ternary core already thresholds normalized floats.
   No stance vocabulary lookup, no hardcoded stance->word mapping.
"""

import math
import random
import numpy as np

try:
    from semantic_core import DIM, NORMALIZED_VECTOR_THRESHOLD
except ImportError:
    # Standalone-testable even before semantic_core is on the path.
    DIM = 128
    NORMALIZED_VECTOR_THRESHOLD = 0.09

_PAULI_X = np.array([[0, 1], [1, 0]], dtype=complex)
_PAULI_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_PAULI_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_PAULIS = [_PAULI_X, _PAULI_Y, _PAULI_Z]


class QuantumState:
    """
    A 7-qubit statevector (128 complex amplitudes, matching DIM exactly)
    that persists across turns, decoheres under vitality-linked noise,
    and supports partial measurement.
    """

    N_QUBITS = 7
    STANCE_QUBITS = ["immerse", "ride", "witness", "shape", "reject", "silence", "spare"]

    def __init__(self, n_qubits=N_QUBITS, seed_state=None):
        self.n = n_qubits
        self.dim = 2 ** n_qubits
        if self.dim != DIM:
            # Not fatal, but the "project directly onto DIM dims" trick
            # only holds at n=7. Warn loudly rather than silently producing
            # a wrong-shaped ternary vector later.
            print(f"[QuantumState] WARNING: 2^{n_qubits}={self.dim} != DIM={DIM}. "
                  f"project_to_ternary() will not line up with the field 1:1.")
        if seed_state is not None:
            self.state = seed_state.astype(complex).copy()
            self._renormalize()
        else:
            self.state = np.zeros(self.dim, dtype=complex)
            self.state[0] = 1.0  # |0000000>

        # Analytic decoherence proxy (see module docstring, point 2).
        # This is cumulative EXPECTED noise applied, not measured purity.
        self._accumulated_noise = 0.0

        # For inspection/debugging only - not consumed by any pipeline.
        self.turn_count = 0

    # ── linear algebra plumbing ─────────────────────────────────────────

    def _renormalize(self):
        norm = np.linalg.norm(self.state)
        if norm > 1e-12:
            self.state = self.state / norm
        else:
            # Degenerate (shouldn't happen in practice) - reinitialize
            # rather than divide by ~0 and propagate NaNs.
            self.state = np.zeros(self.dim, dtype=complex)
            self.state[0] = 1.0

    def _apply_1q(self, gate, target):
        shape = [2] * self.n
        psi = self.state.reshape(shape)
        axes = list(range(self.n))
        axes[0], axes[target] = axes[target], axes[0]
        psi = np.transpose(psi, axes)
        psi = psi.reshape(2, -1)
        psi = gate @ psi
        psi = psi.reshape([2] * self.n)
        psi = np.transpose(psi, axes)  # axes is its own inverse (single swap)
        self.state = psi.flatten()

    def _apply_2q_cnot(self, control, target):
        shape = [2] * self.n
        psi = self.state.reshape(shape)
        axes = list(range(self.n))
        axes[0], axes[control] = axes[control], axes[0]
        axes[1], axes[target] = axes[target], axes[1]
        psi = np.transpose(psi, axes)
        flat = psi.reshape(2, 2, -1)
        out = flat.copy()
        out[1, 0, :] = flat[1, 1, :]
        out[1, 1, :] = flat[1, 0, :]
        out = out.reshape([2] * self.n)
        inv_axes = [0] * self.n
        for i, a in enumerate(axes):
            inv_axes[a] = i
        out = np.transpose(out, inv_axes)
        self.state = out.flatten()

    def _apply_h(self, target):
        H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
        self._apply_1q(H, target)

    def _apply_ry(self, theta, target):
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        self._apply_1q(np.array([[c, -s], [s, c]], dtype=complex), target)

    def _apply_rz(self, theta, target):
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        self._apply_1q(np.array([[c - 1j * s, 0], [0, c + 1j * s]], dtype=complex), target)

    # ── evolution (no reset - this is the whole point) ──────────────────

    def evolve(self, mood, tensions, coupling=0.35):
        """
        Apply mood/tension-driven rotations ON TOP of whatever state
        already exists. Ghosts from last turn are automatic: nothing
        here zeros self.state first.

        `coupling` keeps each turn's push gentle relative to whatever
        superposition already exists, so one turn doesn't just overwrite
        the last - it perturbs it. (0.35 chosen so ~3 turns of a
        consistent mood meaningfully reshape the state, matching roughly
        the pace nested_memory.deep already accumulates at.)
        """
        valence = mood.get('valence', 0.0)
        arousal = mood.get('arousal', 0.5)

        theta = (valence + 1.0) * math.pi / 2  # -1 -> 0, 0 -> pi/2, 1 -> pi
        theta *= coupling * (0.5 + arousal * 0.5)

        for q in range(self.n):
            self._apply_ry(theta, q)

        tension_vals = [tensions.get(name, 0.0) for name in self.STANCE_QUBITS[:-1]]
        for i in range(len(tension_vals)):
            for j in range(i + 1, len(tension_vals)):
                if abs(tension_vals[i]) > 0.05 or abs(tension_vals[j]) > 0.05:
                    phase = (tension_vals[i] - tension_vals[j]) * math.pi * coupling
                    self._apply_2q_cnot(i, j)
                    self._apply_rz(phase, j)
                    self._apply_2q_cnot(i, j)

        self._renormalize()
        self.turn_count += 1

    # ── decoherence: single-trajectory Monte Carlo Pauli noise ──────────

    def apply_noise(self, vitality, base_rate=0.12):
        """
        Per-qubit, independently: with probability
        p = base_rate * (1 - vitality), apply a random Pauli kick.
        Low vitality -> higher p -> the quantum body degrades faster
        than the ternary mind (which only thins its grammar, doesn't
        get directly perturbed by vitality itself).

        Returns the number of qubits actually kicked this call.
        """
        vitality = max(0.0, min(1.0, vitality))
        p = base_rate * (1.0 - vitality)
        kicked = 0
        for q in range(self.n):
            self._accumulated_noise += p  # analytic proxy, see docstring
            if random.random() < p:
                pauli = random.choice(_PAULIS)
                self._apply_1q(pauli, q)
                kicked += 1
        if kicked > 0:
            self._renormalize()
        return kicked

    def coherence_estimate(self):
        """
        ANALYTIC proxy only: exp(-accumulated expected noise). This is
        NOT a measured density-matrix purity - see module docstring
        point 2. Useful as a monotonically-decreasing dial for e.g.
        "how much ambiguity is left to lose", not as a rigorous physical
        quantity.
        """
        return math.exp(-self._accumulated_noise)

    # ── partial measurement ──────────────────────────────────────────────

    def measure_partial(self, targets):
        """
        Collapse only the qubits in `targets`. Qubits not in `targets`
        keep their conditional state exactly (same relative amplitudes,
        renormalized) - they remain in whatever superposition they had,
        genuinely un-collapsed, not just cosmetically untouched.

        Returns (outcome_bits: str, outcome_probability: float).
        """
        targets = list(targets)
        others = [i for i in range(self.n) if i not in targets]
        k = len(targets)

        shape = [2] * self.n
        psi = self.state.reshape(shape)
        perm = targets + others
        psi = np.transpose(psi, perm)
        psi = psi.reshape(2 ** k, -1)  # (2^k, 2^(n-k))

        probs = np.sum(np.abs(psi) ** 2, axis=1)
        total = probs.sum()
        if total < 1e-12:
            # Degenerate; fall back to uniform rather than crash.
            probs = np.ones(2 ** k) / (2 ** k)
        else:
            probs = probs / total

        outcome = int(np.random.choice(2 ** k, p=probs))

        projected = np.zeros_like(psi)
        projected[outcome] = psi[outcome]
        norm = np.linalg.norm(projected)
        if norm > 1e-12:
            projected = projected / norm

        psi_new = projected.reshape([2] * k + [2] * (self.n - k))
        inv_perm = list(np.argsort(perm))
        psi_new = np.transpose(psi_new, inv_perm)
        self.state = psi_new.flatten()

        outcome_bits = format(outcome, f'0{k}b') if k > 0 else ""
        return outcome_bits, float(probs[outcome])

    # ── projection to the field's native shape ──────────────────────────

    def project_to_ternary(self):
        """
        Real part of the amplitude vector, thresholded the same way the
        rest of the ternary core thresholds any normalized float[128].
        No stance-name lookup, no word_vector_ternary() detour - the
        statevector already lives in a DIM-dimensional space (2^7==128
        is why n=7 was chosen), so this is a direct read of the body,
        not a translation through a 7-word vocabulary.
        """
        real_part = self.state.real.astype(np.float32)
        norm = np.linalg.norm(real_part)
        if norm > 1e-8:
            real_part = real_part / norm
        ternary = np.zeros(self.dim, dtype=np.int8)
        ternary[real_part > NORMALIZED_VECTOR_THRESHOLD] = 1
        ternary[real_part < -NORMALIZED_VECTOR_THRESHOLD] = -1
        return ternary

    # ── persistence: a snapshot, not a measurement (see module docstring) ─

    def to_dict(self):
        return {
            "n_qubits": self.n,
            "state_real": self.state.real.tolist(),
            "state_imag": self.state.imag.tolist(),
            "accumulated_noise": self._accumulated_noise,
            "turn_count": self.turn_count,
        }

    def from_dict(self, data):
        n = data.get("n_qubits", self.n)
        if n != self.n:
            print(f"[QuantumState] WARNING: loaded n_qubits={n} != current {self.n}; keeping current.")
        else:
            real = np.array(data["state_real"], dtype=np.float64)
            imag = np.array(data["state_imag"], dtype=np.float64)
            if real.shape == (self.dim,):
                self.state = real + 1j * imag
                self._renormalize()
        self._accumulated_noise = data.get("accumulated_noise", 0.0)
        self.turn_count = data.get("turn_count", 0)

    def status(self):
        return (f"QuantumState: turn={self.turn_count}, "
                f"coherence_estimate={self.coherence_estimate():.3f}, "
                f"norm={np.linalg.norm(self.state):.4f}")
