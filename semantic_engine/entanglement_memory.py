#!/usr/bin/env python3
"""
─── semantic_engine.entanglement_memory — concepts that lean on each other ──
Phase 4b / item #17.  Standalone module, per the project's own build
practice (see quantum_state.py's Phase 4a docstring): built and
self-tested in isolation first.  NOT wired into mind.py's turn pipeline
yet — that's a separate, deliberate step once this is verified.

WHAT THIS IS: a small quantum register PER BOUND CONCEPT PAIR (2 qubits,
4 complex amplitudes each), not a shared register spanning many concepts.
Two words that keep showing up together (fire/truck, alarm/smoke) get
their own independent Bell-like state; recalling one gives a confidence
readout on its partner WITHOUT collapsing the stored state, so recall is
repeatable, not one-shot.

WHY FRESH SLOTS PER BOND, NOT ONE SHARED REGISTER (monogamy of
entanglement): a single qubit cannot be maximally entangled with two
different partners at once — entangling "alarm" with a "fire" qubit and
then with a "truck" qubit on the SAME qubit necessarily disturbs the
first bond to make room for the second. Giving every bond its own
private 2-qubit slot sidesteps this by construction: bonds never share
a qubit, so binding a new pair cannot disturb an existing one. Verified
below (test: binding (fire, truck) leaves (alarm, fire)'s confidence
byte-for-byte unchanged).

REPRESENTATION: each bond is a 4-dim complex vector over basis
|00>,|01>,|10>,|11> (qubit0 = concept A, qubit1 = concept B). A fresh
bond of strength s in [0,1] is prepared as
    cos(s*pi/4)|00> + sin(s*pi/4)|11>
(s=1 -> a maximal Bell pair (|00>+|11>)/sqrt2; s=0 -> the product state
|00>, no entanglement at all) via RY(s*pi/2) on qubit0 then CNOT(0->1).

CONFIDENCE = CONCURRENCE x DECAY ENVELOPE, not a measurement. For
a|00>+b|01>+c|10>+d|11>, concurrence = 2|ad-bc|, computed straight from
the stored amplitudes and discounted by an analytic decoherence
envelope (see DECAY below). This is why recall is non-destructive:
reading it doesn't require collapsing anything, just an amplitude
readout — call it as many times as you want, the bond doesn't change.

DECAY — two layers, deliberately not one (found by this module's own
self-test, the honest way): the obvious design applies a random Pauli
kick per qubit per decay() call and calls it decoherence. That's wrong,
and provably so, not just empirically — concurrence (like every
entanglement measure) is INVARIANT under local unitaries by definition,
and a single-qubit Pauli is exactly a local unitary. Kicking either
qubit of a bond can rotate WHICH basis pair carries the correlation
(a Bell pair living on |00>/|11> can drift to |01>/|10>) but can never
change HOW MUCH correlation there is, in any single trajectory, no
matter how many kicks land. The self-test that catches this is
`test population-average confidence drops under repeated decay` — it
failed honestly on the first version of this module.

The fix mirrors quantum_state.py's own honesty about this exact
limitation ("within a single trajectory, purity is always 1... an
ANALYTIC proxy"): each bond carries the real state (still genuinely
Pauli-kicked every decay() call, because which-basis drift is real and
worth keeping) PLUS an `accumulated_noise` scalar that grows
unconditionally by `rate` every decay() call, the same way
quantum_state.py's `_accumulated_noise` does. Reported confidence is
`concurrence(state) * exp(-accumulated_noise)` — the structural
entanglement times an analytic decoherence envelope. Reinforcing a bond
(bind() on an existing pair) resets its accumulated_noise to 0: a
re-noticed association is remembered fresh, not blended with how faded
it had become.
"""

import cmath
import math
import random

import numpy as np

# ── 2-qubit gate plumbing (hand-rolled: these are always exactly 2
#    qubits per bond, so the general n-qubit einsum machinery in
#    quantum_state.py would be pure overhead here) ──────────────────────

_PAULI_X = np.array([[0, 1], [1, 0]], dtype=complex)
_PAULI_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_PAULI_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_PAULIS = [_PAULI_X, _PAULI_Y, _PAULI_Z]

# CNOT(control=qubit0, target=qubit1) over basis |00>,|01>,|10>,|11>.
_CNOT = np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
    [0, 0, 1, 0],
], dtype=complex)


def _apply_1q(state4, gate, target):
    """Apply a 2x2 gate to qubit `target` (0 or 1) of a 4-dim bond state."""
    psi = state4.reshape(2, 2)
    if target == 0:
        psi = gate @ psi
    else:
        psi = psi @ gate.T
    return psi.flatten()


def _renormalize(state4):
    n = np.linalg.norm(state4)
    if n > 1e-12:
        return state4 / n
    fresh = np.zeros(4, dtype=complex)
    fresh[0] = 1.0
    return fresh


def _concurrence(state4):
    """2|ad - bc| for a|00>+b|01>+c|10>+d|11>. Range [0, 1] for a
    normalized pure state; 0 = product state, 1 = maximal Bell pair."""
    a, b, c, d = state4
    return float(min(1.0, 2.0 * abs(a * d - b * c)))


def _bond_key(word_a, word_b):
    """Canonical, order-independent key for a concept pair."""
    return tuple(sorted((word_a, word_b)))


class EntanglementMemory:
    """
    A collection of independent 2-qubit bonds between concept pairs.

    - bind(a, b, strength)   : create or reinforce the (a, b) bond
    - recall(word, min_confidence) : non-destructive lookup of word's
                                      strongest surviving partner
    - decay(rate)            : one MC Pauli-noise step over every bond
    - status()                : human-readable summary
    - to_dict()/from_dict()  : this IS long-term memory (unlike the
                                quantum body / phase field), so unlike
                                those two, it persists.
    """

    def __init__(self, max_bonds=500):
        self.max_bonds = max_bonds
        # key: (word_a, word_b) canonical tuple -> {"state": complex4,
        # "reinforcements": int, "turn_bound": int}
        self.bonds = {}
        self.turn_count = 0

    # ── formation ─────────────────────────────────────────────────────

    def bind(self, word_a, word_b, strength=1.0):
        """
        Create a fresh bond, or reinforce an existing one, between two
        concepts. `strength` in [0, 1] sets how entangled a FRESH bond
        starts (1.0 = maximal Bell pair). Reinforcing an existing bond
        re-prepares it at the reinforced strength rather than averaging
        amplitudes with the decayed state (amplitude-mixing can't
        represent recovery any better than it can represent decay) —
        a recalled/re-noticed association is remembered fresh, not
        blended with how faded it had become.
        """
        if word_a == word_b:
            return None
        strength = max(0.0, min(1.0, strength))
        key = _bond_key(word_a, word_b)

        if key not in self.bonds and len(self.bonds) >= self.max_bonds:
            self._evict_weakest()

        theta = strength * math.pi / 2
        state = np.zeros(4, dtype=complex)
        state[0] = 1.0  # |00>
        state = _apply_1q(state, np.array([[math.cos(theta / 2), -math.sin(theta / 2)],
                                            [math.sin(theta / 2), math.cos(theta / 2)]], dtype=complex), 0)
        state = _CNOT @ state
        state = _renormalize(state)

        existing = self.bonds.get(key)
        reinforcements = existing["reinforcements"] + 1 if existing else 0
        self.bonds[key] = {
            "state": state,
            "accumulated_noise": 0.0,  # (re)binding clears the decay envelope
            "reinforcements": reinforcements,
            "turn_bound": self.turn_count,
        }
        return key

    def _effective(self, bond):
        """Structural concurrence times the analytic decoherence envelope."""
        return _concurrence(bond["state"]) * math.exp(-bond["accumulated_noise"])

    def _evict_weakest(self):
        if not self.bonds:
            return
        weakest = min(self.bonds, key=lambda k: self._effective(self.bonds[k]))
        del self.bonds[weakest]

    # ── recall (non-destructive) ─────────────────────────────────────

    def recall(self, word, min_confidence=0.15):
        """
        Return (partner_word, confidence) for word's strongest surviving
        bond, or None if it has no bond above min_confidence. Reads
        concurrence straight off the stored amplitudes — the bond's
        state is untouched, so calling this repeatedly is safe and
        returns the same answer until bind() or decay() changes it.
        """
        best = None
        best_conf = min_confidence
        for (a, b), bond in self.bonds.items():
            if word not in (a, b):
                continue
            conf = self._effective(bond)
            if conf >= best_conf:
                best_conf = conf
                best = b if a == word else a
        if best is None:
            return None
        return best, best_conf

    def confidence(self, word_a, word_b):
        """Effective confidence for a specific pair (0.0 if unbound) —
        structural concurrence discounted by the decay envelope."""
        bond = self.bonds.get(_bond_key(word_a, word_b))
        return self._effective(bond) if bond else 0.0

    # ── decay (single-trajectory MC Pauli noise, per bond) ────────────

    def decay(self, rate=0.05):
        """
        One decay step across every bond. Per qubit, per bond,
        independently: with probability `rate`, apply a random Pauli
        kick. Same quantum-trajectory style as quantum_state.py's
        apply_noise — a stochastic realization, not an ensemble
        average, so any single call may leave a bond's confidence
        unchanged (a Z kick, or no kick at all) even though the
        population-level trend is downward.
        """
        rate = max(0.0, min(1.0, rate))
        kicked = 0
        for bond in self.bonds.values():
            # Analytic envelope: grows unconditionally, same as
            # quantum_state.py's _accumulated_noise. This is what
            # actually carries the decay — see module docstring.
            bond["accumulated_noise"] += rate
            state = bond["state"]
            for qubit in (0, 1):
                if random.random() < rate:
                    pauli = random.choice(_PAULIS)
                    state = _apply_1q(state, pauli, qubit)
                    kicked += 1
            bond["state"] = _renormalize(state)
        self.turn_count += 1
        return kicked

    def prune(self, min_confidence=0.05):
        """Drop bonds that have decayed past usefulness. Returns count dropped."""
        dead = [k for k, bond in self.bonds.items() if self._effective(bond) < min_confidence]
        for k in dead:
            del self.bonds[k]
        return len(dead)

    # ── introspection ─────────────────────────────────────────────────

    def status(self):
        if not self.bonds:
            return "Entanglement Memory: 0 bonds"
        confidences = [self._effective(b) for b in self.bonds.values()]
        strongest_key = max(self.bonds, key=lambda k: self._effective(self.bonds[k]))
        strongest_conf = self._effective(self.bonds[strongest_key])
        return (f"Entanglement Memory: {len(self.bonds)} bonds, "
                f"avg_confidence={sum(confidences) / len(confidences):.3f}, "
                f"strongest={strongest_key[0]}~{strongest_key[1]}(conf={strongest_conf:.3f})")

    # ── persistence (this IS memory, unlike the quantum body/phase field) ─

    def to_dict(self):
        return {
            "bonds": {
                f"{a}\u241F{b}": {
                    "state": [[c.real, c.imag] for c in bond["state"]],
                    "accumulated_noise": bond["accumulated_noise"],
                    "reinforcements": bond["reinforcements"],
                    "turn_bound": bond["turn_bound"],
                }
                for (a, b), bond in self.bonds.items()
            },
            "turn_count": self.turn_count,
        }

    def from_dict(self, data):
        self.bonds = {}
        for key_str, bond in data.get("bonds", {}).items():
            a, b = key_str.split("\u241F")
            state = np.array([complex(re, im) for re, im in bond["state"]], dtype=complex)
            self.bonds[(a, b)] = {
                "state": _renormalize(state),
                "accumulated_noise": bond.get("accumulated_noise", 0.0),
                "reinforcements": bond.get("reinforcements", 0),
                "turn_bound": bond.get("turn_bound", 0),
            }
        self.turn_count = data.get("turn_count", 0)


if __name__ == "__main__":
    import sys
    fails = []

    def check(name, cond):
        if cond:
            print(f"  [PASS] {name}")
        else:
            fails.append(name)
            print(f"  [FAIL] {name}")

    em = EntanglementMemory()

    # Fresh bind: maximal strength gives near-maximal concurrence
    em.bind("alarm", "fire", strength=1.0)
    conf = em.confidence("alarm", "fire")
    check("fresh maximal bind has high concurrence", conf > 0.95)

    # Partial strength gives partial concurrence
    em.bind("cup", "saucer", strength=0.3)
    partial_conf = em.confidence("cup", "saucer")
    check("partial strength gives partial concurrence", 0.0 < partial_conf < 0.9)

    # Order independence
    check("bond lookup is order-independent", em.confidence("fire", "alarm") == conf)

    # recall finds the partner both directions
    r = em.recall("alarm")
    check("recall finds partner", r is not None and r[0] == "fire")
    r2 = em.recall("fire")
    check("recall works from either concept", r2 is not None and r2[0] == "alarm")

    # Non-destructive: repeated recall doesn't change confidence
    conf_before = em.confidence("alarm", "fire")
    em.recall("alarm")
    em.recall("alarm")
    em.recall("fire")
    conf_after = em.confidence("alarm", "fire")
    check("recall is non-destructive (confidence unchanged)", conf_before == conf_after)

    # MONOGAMY FIX: binding a new pair must not disturb an existing bond
    # that doesn't share a qubit slot with it.
    before_af = em.confidence("alarm", "fire")
    em.bind("fire", "truck", strength=1.0)
    after_af = em.confidence("alarm", "fire")
    check("binding (fire,truck) leaves (alarm,fire) byte-identical",
          before_af == after_af)
    check("(fire,truck) is itself a real bond", em.confidence("fire", "truck") > 0.95)

    # Reinforcement: re-binding resets a decayed bond back up
    em.decay(rate=1.0)  # force heavy decay
    decayed_conf = em.confidence("cup", "saucer")
    em.bind("cup", "saucer", strength=1.0)
    reinforced_conf = em.confidence("cup", "saucer")
    check("reinforcement raises a decayed bond back up",
          reinforced_conf > decayed_conf)
    check("reinforcement count increments", em.bonds[_bond_key("cup", "saucer")]["reinforcements"] >= 1)

    # Decay trend: over many steps, population-average confidence drops
    em2 = EntanglementMemory()
    pairs = [("dog", "leash"), ("rain", "umbrella"), ("key", "lock"),
             ("salt", "pepper"), ("needle", "thread")]
    for a, b in pairs:
        em2.bind(a, b, strength=1.0)
    start_avg = sum(em2.confidence(a, b) for a, b in pairs) / len(pairs)
    for _ in range(60):
        em2.decay(rate=0.15)
    end_avg = sum(em2.confidence(a, b) for a, b in pairs) / len(pairs)
    check("population-average confidence drops under repeated decay",
          end_avg < start_avg)

    # Z-only dephasing leaves concurrence of this state family unchanged
    em3 = EntanglementMemory()
    em3.bind("a", "b", strength=1.0)
    conf3_before = em3.confidence("a", "b")
    state = em3.bonds[_bond_key("a", "b")]["state"]
    state = _apply_1q(state, _PAULI_Z, 0)
    state = _apply_1q(state, _PAULI_Z, 1)
    em3.bonds[_bond_key("a", "b")]["state"] = _renormalize(state)
    conf3_after = em3.confidence("a", "b")
    check("pure Z dephasing leaves concurrence unchanged for this state family",
          abs(conf3_before - conf3_after) < 1e-9)

    # prune drops dead bonds
    em4 = EntanglementMemory()
    em4.bind("x", "y", strength=0.0)  # product state, concurrence 0
    dropped = em4.prune(min_confidence=0.05)
    check("prune drops a zero-concurrence bond", dropped == 1 and len(em4.bonds) == 0)

    # persistence round-trip
    em5 = EntanglementMemory()
    em5.bind("moon", "tide", strength=0.8)
    em5.decay(rate=0.1)
    d = em5.to_dict()
    em6 = EntanglementMemory()
    em6.from_dict(d)
    check("persistence round-trip preserves confidence exactly",
          abs(em6.confidence("moon", "tide") - em5.confidence("moon", "tide")) < 1e-12)
    check("persistence round-trip preserves reinforcement count",
          em6.bonds[_bond_key("moon", "tide")]["reinforcements"] ==
          em5.bonds[_bond_key("moon", "tide")]["reinforcements"])

    # eviction at capacity
    em7 = EntanglementMemory(max_bonds=3)
    em7.bind("p1", "p2", strength=1.0)
    em7.bind("p3", "p4", strength=0.05)  # weakest
    em7.bind("p5", "p6", strength=1.0)
    check("at capacity", len(em7.bonds) == 3)
    em7.bind("p7", "p8", strength=1.0)  # should evict the weakest (p3,p4)
    check("eviction keeps bond count at cap", len(em7.bonds) == 3)
    check("eviction removed the weakest bond", _bond_key("p3", "p4") not in em7.bonds)

    # status renders
    check("status renders", "Entanglement Memory:" in em.status())
    check("empty status renders", "0 bonds" in EntanglementMemory().status())

    print()
    if fails:
        print(f"  {len(fails)} FAILED: {fails}")
        sys.exit(1)
    print("  ALL ENTANGLEMENT MEMORY SELF-TESTS PASSED")
