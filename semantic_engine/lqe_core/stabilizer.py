"""
Stabilizer (CHP) simulator -- roadmap #18 (fix_stabilizer.py).

Aaronson & Gottesman, "Improved simulation of stabilizer circuits" (2004).
Tracks 2n generators (n destabilizers + n stabilizers) plus a scratch row.
Gate cost O(n), measurement O(n^2) worst case -- polynomial, no 2^n vector.
Only Clifford operations: H, S, Sdg, X, Y, Z, CNOT, and rotations whose angle
is a multiple of pi/2 (up to global phase).
"""
import math
import random
import numpy as np

CLIFFORD_1Q = {"H", "S", "SDG", "X", "Y", "Z"}


class StabilizerSim:
    def __init__(self, n, rng=None):
        self.n = n
        self.rng = rng or random.Random()
        N = 2 * n + 1
        self.x = np.zeros((N, n), dtype=np.uint8)
        self.z = np.zeros((N, n), dtype=np.uint8)
        self.r = np.zeros(N, dtype=np.uint8)
        for i in range(n):
            self.x[i, i] = 1          # destabilizer i = X_i
            self.z[n + i, i] = 1      # stabilizer i   = Z_i

    # ── gates ──────────────────────────────────────────────────────────
    def h(self, a):
        self.r ^= self.x[:, a] & self.z[:, a]
        t = self.x[:, a].copy(); self.x[:, a] = self.z[:, a]; self.z[:, a] = t

    def s(self, a):
        self.r ^= self.x[:, a] & self.z[:, a]
        self.z[:, a] ^= self.x[:, a]

    def cnot(self, a, b):
        self.r ^= self.x[:, a] & self.z[:, b] & (self.x[:, b] ^ self.z[:, a] ^ 1)
        self.x[:, b] ^= self.x[:, a]
        self.z[:, a] ^= self.z[:, b]

    def sdg(self, a):
        self.s(a); self.s(a); self.s(a)

    def zgate(self, a):
        self.s(a); self.s(a)

    def xgate(self, a):
        self.h(a); self.zgate(a); self.h(a)

    def ygate(self, a):               # Y = i X Z : global phase irrelevant
        self.zgate(a); self.xgate(a)

    def apply(self, name, *args):
        nm = name.upper()
        if nm == "H": self.h(args[0])
        elif nm == "S": self.s(args[0])
        elif nm == "SDG": self.sdg(args[0])
        elif nm == "X": self.xgate(args[0])
        elif nm == "Y": self.ygate(args[0])
        elif nm == "Z": self.zgate(args[0])
        elif nm == "CNOT": self.cnot(args[0], args[1])
        elif nm in ("RZ", "RY"):
            k = _quarter_turns(args[0])
            if k is None:
                raise ValueError("%s(%r) is not Clifford" % (nm, args[0]))
            q = args[1]
            if nm == "RZ":
                for _ in range(k % 4): self.s(q)          # RZ(k*pi/2) ~ S^k
            else:                                          # RY(k*pi/2)
                k %= 4
                if k == 1: self.zgate(q); self.h(q)
                elif k == 2: self.ygate(q)
                elif k == 3: self.h(q); self.zgate(q)
        else:
            raise ValueError("%s is not a supported Clifford gate" % name)

    # ── measurement (Z basis) ──────────────────────────────────────────
    def _rowsum(self, h, i):
        x1, z1 = self.x[i].astype(np.int64), self.z[i].astype(np.int64)
        x2, z2 = self.x[h].astype(np.int64), self.z[h].astype(np.int64)
        g = np.where((x1 == 1) & (z1 == 1), z2 - x2,
            np.where((x1 == 1) & (z1 == 0), z2 * (2 * x2 - 1),
            np.where((x1 == 0) & (z1 == 1), x2 * (1 - 2 * z2), 0)))
        tot = 2 * int(self.r[h]) + 2 * int(self.r[i]) + int(g.sum())
        self.r[h] = 1 if (tot % 4) == 2 else 0
        self.x[h] ^= self.x[i]
        self.z[h] ^= self.z[i]

    def measure(self, a, forced=None):
        n = self.n
        p = next((i for i in range(n, 2 * n) if self.x[i, a]), None)
        if p is not None:                              # random outcome
            for i in range(2 * n):
                if i != p and self.x[i, a]:
                    self._rowsum(i, p)
            self.x[p - n] = self.x[p]; self.z[p - n] = self.z[p]; self.r[p - n] = self.r[p]
            self.x[p] = 0; self.z[p] = 0
            self.z[p, a] = 1
            self.r[p] = self.rng.randint(0, 1) if forced is None else forced
            return int(self.r[p])
        m = 2 * n                                      # deterministic outcome
        self.x[m] = 0; self.z[m] = 0; self.r[m] = 0
        for i in range(n):
            if self.x[i, a]:
                self._rowsum(m, i + n)
        return int(self.r[m])

    def is_deterministic(self, a):
        return not any(self.x[i, a] for i in range(self.n, 2 * self.n))

    def copy(self):
        c = StabilizerSim(self.n, self.rng)
        c.x = self.x.copy(); c.z = self.z.copy(); c.r = self.r.copy()
        return c

    def generators(self):
        """Stabilizer generators as (sign, [(x,z) per qubit]); sign +1/-1."""
        out = []
        for i in range(self.n, 2 * self.n):
            out.append((-1 if self.r[i] else 1, [(int(self.x[i, j]), int(self.z[i, j])) for j in range(self.n)]))
        return out


def _quarter_turns(angle):
    k = float(angle) / (math.pi / 2)
    kr = round(k)
    return int(kr) if abs(k - kr) < 1e-9 else None


def is_clifford_gate(g):
    """g: ("H"|"S"|...,q) / ("CNOT",c,t) / ("RY"|"RZ",angle,q)."""
    name = g[0].upper()
    if name == "CNOT":
        return True
    if name in CLIFFORD_1Q:
        return True
    if name in ("RY", "RZ"):
        return _quarter_turns(g[1]) is not None
    return False


def choose_backend(gates, from_fresh_state=False):
    """Roadmap #18 router. Returns (backend, reason).
    Stabilizer only if EVERY gate is Clifford AND the state starts as a
    stabilizer state (|0..0> or a previous all-Clifford result)."""
    for g in gates:
        if not is_clifford_gate(g):
            return "statevector", "non-Clifford gate %s" % (g[0],)
    if not from_fresh_state:
        return "statevector", "state is not a stabilizer state"
    return "stabilizer", "Clifford-only circuit from a stabilizer state"
