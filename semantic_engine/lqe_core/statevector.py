# ─── vendored from Legitimate Quantum Engine ────────────────────────────
# Source: legitimate_quantum_engine/core/statevector.py, from the LQE
# repo commit referenced in lqe_project_notes_full.txt (LQE v5.0,
# 28/28 tests / 26/26 synthetic benchmarks passing at vendor time,
# 2026-09-18). Vendored byte-identical, logic untouched — this file is
# "the LQE core" that Phase 4 build-plan item #14 specified wrapping,
# not reimplementing. If LQE's own statevector.py changes upstream,
# re-vendor by replacing this file wholesale (diff against the source
# above first) rather than hand-editing drift in here.
#
# The measure()/reset() qubit-indexing note in the class itself (search
# "BUGFIX" below) is LQE's own documented fix, kept as-is — it explains
# why qubit index q maps to flat-array bit (n-1-q), which matters if
# anything ever reasons about raw flat indices directly instead of
# going through .apply()/.measure().
# ─────────────────────────────────────────────────────────────────────

import numpy as np

class StatevectorSim:
    """Fast statevector simulator using tensordot (not Kronecker)."""
    def __init__(self, num_qubits):
        self.n = num_qubits
        self.dim = 2 ** num_qubits
        self.state = np.zeros(self.dim, dtype=complex)
        self.state[0] = 1.0

    def copy(self):
        new = StatevectorSim.__new__(StatevectorSim)
        new.n = self.n
        new.dim = self.dim
        new.state = self.state.copy()
        return new

    def _apply_1q(self, gate, q):
        shape = [2] * self.n
        psi = self.state.reshape(shape)
        psi = np.moveaxis(psi, q, 0)
        psi = np.tensordot(gate, psi, axes=(1, 0))
        psi = np.moveaxis(psi, 0, q)
        self.state = psi.reshape(self.dim)

    def _apply_2q(self, gate, c, t):
        shape = [2] * self.n
        psi = self.state.reshape(shape)
        order = [c, t] + [i for i in range(self.n) if i not in (c, t)]
        psi = np.transpose(psi, order)
        psi = psi.reshape(4, -1)
        U = gate.reshape(4, 4)
        psi = U @ psi
        psi = psi.reshape([2, 2] + [2] * (self.n - 2))
        inv_order = [0] * self.n
        for new_pos, old_pos in enumerate(order):
            inv_order[old_pos] = new_pos
        psi = np.transpose(psi, inv_order)
        self.state = psi.reshape(self.dim)

    def apply(self, name, *args):
        if name == "H":
            g = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
            self._apply_1q(g, args[0])
        elif name == "X":
            g = np.array([[0, 1], [1, 0]], dtype=complex)
            self._apply_1q(g, args[0])
        elif name == "Y":
            g = np.array([[0, -1j], [1j, 0]], dtype=complex)
            self._apply_1q(g, args[0])
        elif name == "Z":
            g = np.array([[1, 0], [0, -1]], dtype=complex)
            self._apply_1q(g, args[0])
        elif name == "CNOT":
            g = np.zeros((2, 2, 2, 2), dtype=complex)
            g[0, 0, 0, 0] = g[0, 1, 0, 1] = g[1, 1, 1, 0] = g[1, 0, 1, 1] = 1
            self._apply_2q(g, args[0], args[1])
        elif name == "SWAP":
            g = np.zeros((2, 2, 2, 2), dtype=complex)
            g[0, 0, 0, 0] = g[0, 1, 1, 0] = g[1, 0, 0, 1] = g[1, 1, 1, 1] = 1
            self._apply_2q(g, args[0], args[1])
        elif name in ("RX", "RY", "RZ"):
            theta = args[0]
            q = args[1]
            c, s = np.cos(theta / 2), np.sin(theta / 2)
            if name == "RX":
                g = np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)
            elif name == "RY":
                g = np.array([[c, -s], [s, c]], dtype=complex)
            else:
                g = np.array([[c - 1j * s, 0], [0, c + 1j * s]], dtype=complex)
            self._apply_1q(g, q)
        else:
            raise ValueError(f"Unknown gate: {name}")

    def probabilities(self):
        return np.real(self.state * np.conj(self.state))

    def measure(self, qubit):
        # This statevector carries qubit q at flat-index bit (n-1-q) (see
        # apply/_apply_1q: axis q of the n-qubit tensor becomes flat bit
        # n-1-q under C-order flattening).  Indexing flat bit `qubit`
        # directly would read the wrong qubit for asymmetric states, so the
        # BUGFIX projects on bit (n-1-qubit).
        bit = self.n - 1 - qubit
        probs = self.probabilities()
        p0 = sum(probs[i] for i in range(self.dim) if ((i >> bit) & 1) == 0)
        outcome = 0 if np.random.random() < p0 else 1
        self.state = np.array([
            self.state[i] if ((i >> bit) & 1) == outcome else 0
            for i in range(self.dim)
        ], dtype=complex)
        nrm = np.linalg.norm(self.state)
        if nrm > 0:
            self.state /= nrm
        return outcome

    def reset(self, qubit):
        if self.measure(qubit) == 1:
            self.apply("X", qubit)
        return 0
