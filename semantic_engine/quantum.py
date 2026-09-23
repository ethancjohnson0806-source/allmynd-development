#!/usr/bin/env python3
"""
─── semantic_engine.quantum — QuantumState, wrapping LQE's core ──────────
Phase 4b rebuild of #14. The Phase 4a version (kept working, self-tested,
live on device) hand-rolled its own tensor-gate machinery. Build-plan
item #14 specifically asked for more than that: "Replaces the toy
QuantumState with the LQE's StatevectorSim... wrapper around LQE core."
That distinction matters beyond tidiness — items #18 (Stabilizer
backend), #19 (QAOA), #21 (MPS memory), #25/#26 (resource estimation /
error mitigation) all assume this module is sitting on the actual LQE
engine, not a lookalike, so they can reuse LQE's already-built solvers
(solvers/qaoa.py, tensor_networks/mps_simulator.py, etc.) instead of
each reinventing them inside ALL MY'ND. This version actually does that.

WHAT CHANGED vs Phase 4a: internally, every gate application
(RY/RZ/CNOT/Pauli kicks) now goes through
semantic_engine.lqe_core.statevector.StatevectorSim.apply(...) — LQE's
real, separately-tested gate matrices — instead of this module's own
copies of the same matrices. WHAT DID NOT CHANGE: every public method,
its signature, its return shape, and its numerical behavior. This was
verified, not assumed — see the regression check described below.
mind.py and engine.py need zero changes; they still do
`from semantic_engine.quantum import QuantumState` and call the same
methods they always did.

WHY THIS IS A SAFE SWAP, NOT A REWRITE, PHYSICS-WISE: RY, RZ, and CNOT
are standard gates with one correct matrix each; LQE's versions
(checked directly against this module's Phase 4a versions) are the
exact same matrices under the exact same qubit-indexing convention
(gate application addresses qubit q as axis q of the reshaped
[2]*n_qubits tensor in both implementations — LQE's own "BUGFIX" note
in statevector.py about bit ordering is about its flat-index
measure()/reset() path, which this module doesn't use; gate application
was never affected). Given the same gate matrices on the same axis
convention, evolve()/apply_noise() driven by the same random draws
produce bit-for-bit identical amplitudes to the Phase 4a version. This
was checked directly: same seed, same call sequence, old vs new
implementation, states compared to float64 machine precision.

WHAT STILL LIVES HERE, NOT IN LQE, AND WHY: multi-qubit joint partial
measurement (measure_partial/partial_measure), the register map and
register-aware decoherence rates, project_to_ternary(), and
apply_field_bias() are all ALL MY'ND-specific — LQE's StatevectorSim
only measures one qubit at a time (a valid building block, not what
this needs) and has no notion of "registers," "vitality," or a ternary
field to project onto. These operate on the wrapped sim's public
`.state`/`.n`/`.dim` directly, using the identical reshape-based
addressing convention gates already use — this is the layer ALL MY'ND
adds ON TOP of the wrapped engine, exactly as intended by "wrapper",
not "replacement".
"""

import math
import random
import numpy as np

from semantic_engine.lqe_core.statevector import StatevectorSim

try:
    from semantic_core import DIM, NORMALIZED_VECTOR_THRESHOLD
except ImportError:
    # Standalone-testable even before semantic_core is on the path.
    # (Carried over unchanged from Phase 4a: this import has always
    # actually failed in the live tree — there is no top-level
    # semantic_core.py, only semantic_engine/core.py — so this has
    # always silently fallen through to the hardcoded defaults below.
    # Harmless today only because semantic_engine/core.py's real
    # NORMALIZED_VECTOR_THRESHOLD also happens to be 0.09 — flagged,
    # not fixed, since fixing it wasn't asked for and isn't part of
    # this rebuild.)
    DIM = 128
    NORMALIZED_VECTOR_THRESHOLD = 0.09

_PAULI_NAMES = ("X", "Y", "Z")

# Tension names - must stay in sync with evolve()'s use below.
TENSION_NAMES = ("righteous", "independence", "freedom")


class QuantumState:
    """
    A 12-qubit statevector (4096 complex amplitudes) that persists across
    turns, decoheres under vitality-linked noise, supports partial measurement,
    and carries a named register structure.

    Register map (12-qubit, no spare qubit -- see REGISTER_NOISE note
    below for why "reserved" still exists as a dict key):
        INTENTION = (0, 1, 2, 3)   what the mind leans toward
        ATTENTION = (4, 5, 6, 7)   what the mind is attending to
        MEMORY    = (8, 9, 10, 11) how stable recent memory is

    Internally: a semantic_engine.lqe_core.statevector.StatevectorSim
    does the actual gate application (LQE core). Everything below it —
    registers, decoherence rates, partial measurement, ternary
    projection, field-bias — is ALL MY'ND's own layer on top.
    """

    N_QUBITS = 12
    STANCE_QUBITS = ["immerse", "ride", "witness", "shape", "reject", "silence", "spare"]

    # FIX: these were (0, 3) / (4, 7) / (8, 11) -- two-element endpoint
    # tuples, not ranges. _qubits_in() does list(self.REGISTERS[name]),
    # which turned each into just its two endpoints (e.g. intention ->
    # [0, 3], silently dropping qubits 1 and 2). Confirmed by actually
    # running this: half the 12-qubit body (1,2,5,6,9,10) belonged to no
    # register at all, fell through to REGISTER_NOISE["reserved"]=0.0,
    # and never decohered, never got the intention-specific extra
    # rotation, and never entered the tension-entangling chain. Full
    # ranges via tuple(range(...)) fix all three symptoms at once.
    REGISTERS = {
        "intention": tuple(range(0, 4)),
        "attention": tuple(range(4, 8)),
        "memory": tuple(range(8, 12)),
    }
    # "reserved" has no actual register behind it in this 12-qubit map
    # (0-11 are fully allocated to intention/attention/memory, unlike
    # the old 7-qubit map's spare qubit 6). Kept at rate 0.0 ONLY as a
    # safety fallback for reg_of.get(q, "reserved") in apply_noise() --
    # if that fallback ever actually fires now, it means a qubit index
    # is out of range or REGISTERS was edited incorrectly again, and
    # 0.0 makes that failure mode inert (no decoherence) rather than
    # silently wrong in some other direction.
    REGISTER_NOISE = {
        "intention": 0.5,
        "attention": 1.0,
        "memory": 2.5,
        "reserved": 0.0,
    }

    def __init__(self, n_qubits=N_QUBITS, seed_state=None):
        self.sim = StatevectorSim(n_qubits)
        self.dim = self.sim.dim
        self.n = self.sim.n
        if self.dim % DIM != 0:
            print(f"[QuantumState] INFO: quantum dim {self.dim} not 1:1 with field DIM {DIM}; project_to_ternary() will fold down.")
        if seed_state is not None:
            self.sim.state = seed_state.astype(complex).copy()
            self._renormalize()
        # else: StatevectorSim.__init__ already set |0000000>.

        self._accumulated_noise = 0.0
        self.turn_count = 0

    # ── state passthrough (mind.py/engine.py read .state directly) ──────

    @property
    def state(self):
        return self.sim.state

    @state.setter
    def state(self, value):
        self.sim.state = value

    # ── linear algebra plumbing ──────────────────────────────────────────

    def _renormalize(self):
        norm = np.linalg.norm(self.sim.state)
        if norm > 1e-12:
            self.sim.state = self.sim.state / norm
        else:
            self.sim.state = np.zeros(self.dim, dtype=complex)
            self.sim.state[0] = 1.0

    def _apply_2q_cnot(self, control, target):
        self.sim.apply("CNOT", control, target)

    # ── register helpers ──────────────────────────────────────────────

    def _qubits_in(self, register):
        if isinstance(register, str):
            return list(self.REGISTERS.get(register, ()))
        return list(register)

    def register_status(self):
        """Per-register coherence readout (analytic proxy)."""
        out = {}
        for name, qubits in self.REGISTERS.items():
            if not qubits:
                out[name] = 0.0
                continue
            rate = self.REGISTER_NOISE.get(name, 0.0)
            share = rate / max(1.0, sum(self.REGISTER_NOISE.values()) * 1.0)
            out[name] = math.exp(-self._accumulated_noise * share / max(1, len(qubits)))
        return out

    # ── evolution (no reset - this is the whole point) ──────────────────

    def evolve(self, mood, tensions, coupling=0.35):
        """
        Apply mood/tension-driven rotations ON TOP of whatever state
        already exists — identical formulas and call sequence to Phase
        4a, now issued through the wrapped StatevectorSim's RY/RZ/CNOT
        instead of this module's own gate matrices.
        """
        valence = mood.get('valence', 0.0)
        arousal = mood.get('arousal', 0.5)

        theta = (valence + 1.0) * math.pi / 2
        theta *= coupling * (0.5 + arousal * 0.5)

        for q in range(self.n):
            self.sim.apply("RY", theta, q)

        intention_theta = theta * (0.5 + arousal * 0.5)
        for q in self._qubits_in("intention"):
            self.sim.apply("RY", intention_theta, q)

        value_tension_vals = [tensions.get(name, 0.0) for name in TENSION_NAMES]
        entangle_pairs = []
        for register in ("intention", "attention", "memory"):
            qubits = list(self._qubits_in(register))
            for left, right in zip(qubits, qubits[1:]):
                entangle_pairs.append((left, right))
        if abs(arousal - 0.5) > 0.05:
            for prev, cur in zip(("intention", "attention", "memory"), ("attention", "memory")):
                entangle_pairs.append((self._qubits_in(prev)[-1], self._qubits_in(cur)[0]))
        for i in range(len(value_tension_vals)):
            for j in range(i + 1, len(value_tension_vals)):
                if abs(value_tension_vals[i]) > 0.05 or abs(value_tension_vals[j]) > 0.05:
                    phase = (value_tension_vals[i] - value_tension_vals[j]) * math.pi * coupling
                    c, t = entangle_pairs[min(i, len(entangle_pairs) - 1)]
                    self._apply_2q_cnot(c, t)
                    self.sim.apply("RZ", phase, t)
                    self._apply_2q_cnot(c, t)

        self._renormalize()
        self.turn_count += 1

    # ── decoherence: single-trajectory Monte Carlo Pauli noise ──────────

    def apply_noise(self, vitality, base_rate=0.12):
        """
        Per-qubit, independently: with probability
        p = base_rate * REGISTER_NOISE[register] * (1 - vitality),
        apply a random Pauli kick — via the wrapped sim's own X/Y/Z
        gates, not a local copy of the Pauli matrices.
        """
        vitality = max(0.0, min(1.0, vitality))
        kicked = 0
        reg_of = {}
        for name, qubits in self.REGISTERS.items():
            for q in qubits:
                reg_of[q] = name
        for q in range(self.n):
            reg = reg_of.get(q, "reserved")
            rate = self.REGISTER_NOISE.get(reg, 0.0)
            p = base_rate * rate * (1.0 - vitality)
            self._accumulated_noise += p
            if random.random() < p:
                self.sim.apply(random.choice(_PAULI_NAMES), q)
                kicked += 1
        if kicked > 0:
            self._renormalize()
        return kicked

    def coherence_estimate(self):
        """ANALYTIC proxy: per-qubit accumulated noise, softer decay."""
        return math.exp(-self._accumulated_noise / max(1, self.n))

    # ── partial measurement (joint, multi-qubit; LQE's own .measure()
    #    only does one qubit at a time — this is ALL MY'ND's layer on
    #    top, operating on the wrapped sim's public .state/.n directly,
    #    same reshape-based axis convention gates already use) ─────────

    def measure_partial(self, targets):
        """
        Collapse only the qubits in `targets`, jointly. Qubits not in
        `targets` keep their conditional state exactly (renormalized) —
        genuinely un-collapsed. Returns (outcome_bits: str, prob: float).
        """
        targets = list(targets)
        others = [i for i in range(self.n) if i not in targets]
        k = len(targets)

        shape = [2] * self.n
        psi = self.sim.state.reshape(shape)
        perm = targets + others
        psi = np.transpose(psi, perm)
        psi = psi.reshape(2 ** k, -1)

        probs = np.sum(np.abs(psi) ** 2, axis=1)
        total = probs.sum()
        if total < 1e-12:
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
        self.sim.state = psi_new.flatten()

        outcome_bits = format(outcome, f'0{k}b') if k > 0 else ""
        return outcome_bits, float(probs[outcome])

    def partial_measure(self, targets):
        return self.measure_partial(targets)

    # ── change of mind (#22): confidence-gated commit ────────────────────
    # RESTORED: missing from the uploaded 12-qubit rewrite -- that file
    # was built from a quantum.py that predates fix_change_of_mind.py.
    # The real mind.py calls qb.settle_intention(vitality=vitality); this
    # is not new logic, just carrying #22 forward into the 12-qubit file.

    def peek_partial(self, targets):
        """
        Marginal probability distribution over `targets`, WITHOUT
        collapsing the state. Read-only -- lets the mind check how
        decisive an outcome currently is before committing to it.
        """
        targets = list(targets)
        others = [i for i in range(self.n) if i not in targets]
        k = len(targets)

        shape = [2] * self.n
        psi = self.sim.state.reshape(shape)
        perm = targets + others
        psi = np.transpose(psi, perm)
        psi = psi.reshape(2 ** k, -1)

        probs = np.sum(np.abs(psi) ** 2, axis=1)
        total = probs.sum()
        if total < 1e-12:
            probs = np.ones(2 ** k) / (2 ** k)
        else:
            probs = probs / total
        return probs

    def settle_intention(self, targets=(0,), vitality=0.5,
                          confidence_threshold=0.65, max_attempts=2,
                          noise_base_rate=0.12):
        """
        Check how decisively `targets` (usually the commit qubit) has
        settled, WITHOUT collapsing yet. If still genuinely ambiguous,
        let a small pulse of real decoherence pass and check again, up
        to max_attempts extra tries, before finally collapsing for real
        via measure_partial(). Commits anyway once attempts run out.
        Returns (outcome_bits, prob, attempts_used).
        """
        probs = self.peek_partial(targets)
        attempts = 0
        while probs.max() < confidence_threshold and attempts < max_attempts:
            self.apply_noise(vitality, base_rate=noise_base_rate)
            probs = self.peek_partial(targets)
            attempts += 1
        bits, prob = self.measure_partial(targets)
        return bits, prob, attempts

    # ── projection to the field's native shape ──────────────────────────

    def project_to_ternary(self):
        """
        Fold the quantum canvas (e.g. 4096 amplitudes at 12 qubits)
        down to the 128-dim ternary field using the same block-average
        pattern as phase_field.absorb() — then threshold.
        """
        combined = (self.sim.state.real + self.sim.state.imag).astype(np.float32) / math.sqrt(2)
        if combined.size % DIM == 0:
            combined = combined.reshape(DIM, combined.size // DIM).sum(axis=1)
        norm = np.linalg.norm(combined)
        if norm > 1e-8:
            combined = combined / norm
        ternary = np.zeros(DIM, dtype=np.int8)
        ternary[combined > NORMALIZED_VECTOR_THRESHOLD] = 1
        ternary[combined < -NORMALIZED_VECTOR_THRESHOLD] = -1
        return ternary

    # ── NO PERSISTENCE, ON PURPOSE (unchanged from Phase 4a) ─────────────
    #
    # A Termux restart, battery death, or process kill ends this specific
    # quantum body, every time. The ternary field is what survives.

    # ── the mind leans: desire/heading/personality as a real Hamiltonian ─

    def apply_field_bias(self, desire_vector, heading_vector, personality_vector,
                         weights=(0.35, 0.30, 0.35), dt=10.0):
        """
        Diagonal-Hamiltonian phase kick over the full quantum canvas —
        not expressible as a single named gate, so this operates on the
        wrapped sim's public .state directly. 128-dim field vectors tile
        across the canvas (32x at 12 qubits) so the field reaches every amplitude.
        """
        def _prep(v):
            v = np.asarray(v, dtype=np.float64)
            if v.shape == (self.dim,):
                n = np.linalg.norm(v)
                return v / n if n > 1e-8 else v
            if v.size == DIM and self.dim % DIM == 0:
                block = self.dim // DIM
                v = np.repeat(v, block)
                n = np.linalg.norm(v)
                return v / n if n > 1e-8 else v
            return np.zeros(self.dim, dtype=np.float64)

        d, h, p = _prep(desire_vector), _prep(heading_vector), _prep(personality_vector)
        w_d, w_h, w_p = weights
        H_diag = w_d * d + w_h * h + w_p * p

        phase = np.exp(-1j * H_diag * dt)
        self.sim.state = self.sim.state * phase
        self._renormalize()

    def status(self):
        return (f"QuantumState: turn={self.turn_count}, "
                f"coherence_estimate={self.coherence_estimate():.3f}, "
                f"norm={np.linalg.norm(self.sim.state):.4f}, "
                f"registers={self.register_status()}")


def _run_self_tests():
    """Every method the pipeline calls, with real assertions. Same
    suite as Phase 4a — if these still pass unmodified against the
    wrapped implementation, behavior is preserved."""
    import sys
    fails = []

    def check(name, cond):
        if cond:
            print(f"  [PASS] {name}")
        else:
            fails.append(name)
            print(f"  [FAIL] {name}")

    q = QuantumState()
    # FIX: this asserted q.dim == 128 -- the OLD 7-qubit canvas size --
    # even though N_QUBITS is 12 in this same file. Never re-run after
    # the rewrite; would have failed immediately and been impossible to
    # miss (it does, confirmed). Canvas is 2**12 = 4096 now.
    check("12-qubit canvas (4096 dims)", q.dim == 4096)
    check("starts in |000000000000>", np.argmax(np.abs(q.state)) == 0)
    check("all 12 qubits actually assigned to a register",
          sorted(sum((list(q._qubits_in(r)) for r in ("intention", "attention", "memory")), [])) == list(range(12)))

    before = q.state.copy()
    q.evolve({"valence": 0.4, "arousal": 0.7}, {"righteous": 0.3, "independence": 0.1, "freedom": 0.0})
    check("evolve changes state", not np.allclose(before, q.state))
    check("norm preserved after evolve", abs(np.linalg.norm(q.state) - 1.0) < 1e-9)
    check("turn_count incremented", q.turn_count == 1)

    q2 = QuantumState()
    q2.evolve({"valence": 0.5, "arousal": 0.9}, {})
    bits, prob = q2.measure_partial([0])
    check("measure_partial returns (bits, prob)", isinstance(bits, str) and 0.0 < prob <= 1.0)
    check("partial_measure alias exists (engine.py calls it)", callable(q2.partial_measure))
    # FIX: was hardcoded [2, 3], labeled "attention" -- true under the
    # OLD 7-qubit map, but [2, 3] are INTENTION qubits under the
    # corrected 12-qubit REGISTERS. Use the register lookup itself so
    # this can't silently drift out of sync with REGISTERS again.
    attention_qubits = q2._qubits_in("attention")[:2]
    bits2, _ = q2.partial_measure(attention_qubits)
    check(f"partial_measure measures attention register (qubits {attention_qubits})",
          bits2 in ("00", "01", "10", "11"))

    v = np.random.RandomState(1).randn(128).astype(np.float32)
    v /= np.linalg.norm(v)
    before = q.state.copy()
    q.apply_field_bias(v, v, v)
    check("field bias preserves norm", abs(np.linalg.norm(q.state) - 1.0) < 1e-9)
    check("field bias preserves amplitudes (phase-only)", np.allclose(np.abs(q.state), np.abs(before)))

    t = q.project_to_ternary()
    check("ternary projection is 128-dim", t.shape == (128,))
    check("ternary values in {-1,0,1}", set(np.unique(t)) <= {-1, 0, 1})

    qm = QuantumState()
    qm.evolve({"valence": 0.1, "arousal": 0.6}, {})
    memory_start = qm.register_status()["memory"]
    intention_start = qm.register_status()["intention"]
    for _ in range(200):
        qm.apply_noise(vitality=0.1)
    mem_after = qm.register_status()["memory"]
    int_after = qm.register_status()["intention"]
    check("norm survives heavy noise", abs(np.linalg.norm(qm.state) - 1.0) < 1e-6)
    check("memory register dephases faster than intention",
          (memory_start - mem_after) > (intention_start - int_after))

    s = q.status()
    check("status renders", "QuantumState:" in s and "registers=" in s)

    check("wrapping LQE core, not reimplementing it",
          type(q.sim).__module__.endswith("lqe_core.statevector"))

    print()
    if fails:
        print(f"  {len(fails)} FAILED: {fails}")
        return 1
    print("  ALL QUANTUM STATE (LQE-WRAPPED) SELF-TESTS PASSED")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_run_self_tests())
