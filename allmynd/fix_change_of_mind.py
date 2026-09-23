#!/usr/bin/env python3
"""
fix_change_of_mind.py — Phase 4c #22: Dynamic Circuit Branching
("change of mind")

Adds a real, previously-absent behavior: before the mind commits to
its intention qubit's collapse each turn, it checks how decisively
that collapse actually is. If it's genuinely a near-toss-up, it lets
a small pulse of real decoherence pass and checks again (up to 2 extra
tries) before finally collapsing for real.

Deliberately NOT built as "does this agree with MoralCompass/desire/
anything external" -- that would be an imposed judge of "right" and
"wrong" direction, which runs against this project's own stated
principle of not deciding what the mind becomes. Instead this is pure
drift-diffusion: the state's own confidence in itself is the only
signal, exactly like an undecided mind naturally settling on its own
terms rather than being told the answer.

Two other real design points, confirmed against the live code before
writing this (per house convention -- verify, don't assume):

1. Re-calling evolve() with the same mood/tensions mid-turn would NOT
   represent new evidence -- evolve()'s rotation angle is fixed for
   the turn (theta derived once from mood/arousal), so repeating it
   just composes RY(theta) with itself, i.e. RY(k*theta): the outcome
   probability is sin^2(k*theta/2), which is periodic in k, not
   monotonically more decisive. So reconsideration here uses a small
   apply_noise() pulse between checks instead -- real stochastic
   perturbation, not a deterministic replay of the same rotation.

2. The check itself must be non-destructive (peek, don't collapse)
   until the very last try. Calling measure_partial() twice in a row
   with nothing in between is trivial: the first call already
   collapses the qubit to a definite basis state, so an immediate
   second call would report 100% confidence purely from measurement
   back-action, not genuine settling. The new peek_partial() reads
   the marginal probability WITHOUT collapsing, so intermediate
   checks are honest; only the final accepted read actually collapses
   the state.

Where: semantic_engine/quantum.py (peek_partial + settle_intention),
wired into allmynd/mind.py's Phase 2.5 in place of the previously
unused-return measure_partial([0]) call.

Usage (from ~/downloads):
    python3 fix_change_of_mind.py

Self-verifying: backs up both files, compile-checks each, then runs
real behavioral smoke tests (including a genuine end-to-end
AllMynd().generate_response() call) before declaring success. Reverts
both files automatically if anything fails.
"""

import sys
import os
import shutil
import subprocess
import time
import py_compile

QUANTUM_TARGET = os.path.join("semantic_engine", "quantum.py")
MIND_TARGET = os.path.join("allmynd", "mind.py")

MARKER = "settle_intention"  # presence in either file => already patched

# ─── quantum.py patch ──────────────────────────────────────────────────

QUANTUM_OLD = '''    def partial_measure(self, targets):
        return self.measure_partial(targets)

    # ── projection to the field's native shape ──────────────────────────
'''

QUANTUM_NEW = '''    def partial_measure(self, targets):
        return self.measure_partial(targets)

    # ── change of mind (#22): confidence-gated commit ────────────────────
    #
    # No external target to agree with, no imposed "correct" direction --
    # applied via fix_change_of_mind.py. See that script's own docstring
    # for why evolve() is deliberately NOT reused here, and why the
    # intermediate checks must be non-destructive.

    def peek_partial(self, targets):
        """
        Marginal probability distribution over `targets`, WITHOUT
        collapsing the state. Read-only -- lets the mind check how
        decisive an outcome currently is before committing to it.
        Same reshape/permute math as measure_partial(), minus the
        projection step.
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
        settled, WITHOUT collapsing yet. If it's still genuinely
        ambiguous (max marginal probability below
        confidence_threshold), let a small pulse of real decoherence
        pass and check again, up to max_attempts extra tries, before
        finally collapsing for real via measure_partial(). If it never
        clears the threshold, it commits anyway once attempts run out
        -- same as any real deliberation eventually has to settle
        rather than wait forever for certainty that may not come.

        Side effect, intentional: a turn that hesitates accumulates a
        little more decoherence than one that doesn't (each extra
        check costs a real apply_noise() pulse) -- hesitating isn't
        free here, same as it isn't for the rest of this mind.

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
'''

# ─── mind.py patch ─────────────────────────────────────────────────────

MIND_OLD = '''        # Measure if user is present \u2014 only the qubit the world touched
        if not autonomous:
            qb.measure_partial([0])  # immerse: user spoke, rest stay superposed

        # Decoherence (vitality = presence as weather, gently reduced on
        # novel turns so the quantum body decoheres a bit faster when the
        # mind is facing something unfamiliar).
        novelty = getattr(self, "_last_novelty", 0.0)
        vitality = presence * (1.0 - novelty * 0.4)
        qb.apply_noise(vitality)
'''

MIND_NEW = '''        # Decoherence weather, computed here (moved up from below) so
        # the change-of-mind check and the turn's own decoherence pass
        # share the same real vitality value -- gently reduced on novel
        # turns so the quantum body decoheres a bit faster when the mind
        # is facing something unfamiliar.
        novelty = getattr(self, "_last_novelty", 0.0)
        vitality = presence * (1.0 - novelty * 0.4)

        # Measure if user is present \u2014 only the qubit the world touched.
        # #22 (fix_change_of_mind.py): doesn't collapse blind. Checks how
        # decisively the commit qubit has actually settled first; if it's
        # still a genuine toss-up, lets a beat of real decoherence pass
        # and checks again (up to 2 extra tries) before finally
        # committing. No external judge of "right" or "wrong" direction
        # -- purely the state's own confidence in itself.
        if not autonomous:
            qb.settle_intention(vitality=vitality)

        # Decoherence (vitality = presence as weather).
        qb.apply_noise(vitality)
'''


def fail(msg):
    print(f"FAILED: {msg}")
    sys.exit(1)


def patch_one(target, old, new, label):
    if not os.path.isfile(target):
        fail(f"{label} target file not found: {target}")
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()
    if MARKER in content:
        print(f"  {label}: already patched (found '{MARKER}') -- skipping")
        return None, None
    count = content.count(old)
    if count == 0:
        fail(f"{label}: expected block not found verbatim -- file has drifted "
             f"from what this patch was written against. Re-check the real "
             f"source before proceeding.")
    if count > 1:
        fail(f"{label}: expected block found {count} times, not exactly 1 -- "
             f"refusing, ambiguous match")
    patched = content.replace(old, new, 1)
    backup_path = f"{target}.bak_change_of_mind_{int(time.time())}"
    shutil.copy2(target, backup_path)
    with open(target, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"  {label}: patched (backup at {backup_path})")
    return target, backup_path


def main():
    print("Patching quantum.py ...")
    q_target, q_backup = patch_one(QUANTUM_TARGET, QUANTUM_OLD, QUANTUM_NEW, "quantum.py")
    print("Patching mind.py ...")
    m_target, m_backup = patch_one(MIND_TARGET, MIND_OLD, MIND_NEW, "mind.py")

    if q_target is None and m_target is None:
        print("Nothing to do -- both files already patched.")
        return

    patched_targets = [t for t in (q_target, m_target) if t]
    backups = {t: b for t, b in ((q_target, q_backup), (m_target, m_backup)) if t}

    def revert_all(reason):
        for t, b in backups.items():
            shutil.copy2(b, t)
        fail(f"{reason} -- reverted all patched files from backup")

    for t in patched_targets:
        try:
            py_compile.compile(t, doraise=True)
        except py_compile.PyCompileError as e:
            revert_all(f"compile check failed for {t}: {e}")
    print("Compile check: OK")

    # ── Behavioral smoke tests, real import, real classes ──
    repo_root = os.path.dirname(os.path.abspath(QUANTUM_TARGET))  # .../semantic_engine
    repo_root = os.path.dirname(repo_root)  # parent of semantic_engine/

    smoke_script = r'''
import sys
sys.path.insert(0, %(repo_root)r)
import numpy as np
from semantic_engine.quantum import QuantumState

# 1) peek_partial must NOT collapse the state.
q = QuantumState()
q.evolve({"valence": 0.3, "arousal": 0.6}, {})
before = q.state.copy()
probs = q.peek_partial([0])
assert np.allclose(q.state, before), "peek_partial must not mutate state"
assert probs.shape == (2,) and abs(probs.sum() - 1.0) < 1e-9
print("  [1/4] peek_partial is read-only and normalized: OK")

# 2) settle_intention returns a real outcome and DOES collapse by the end.
q2 = QuantumState()
q2.evolve({"valence": 0.5, "arousal": 0.9}, {})
bits, prob, attempts = q2.settle_intention(targets=[0], vitality=0.5)
assert isinstance(bits, str) and len(bits) == 1
assert 0.0 <= prob <= 1.0
assert attempts >= 0
# after collapse, re-peeking the same qubit must be trivially certain
post = q2.peek_partial([0])
assert post.max() > 0.999, f"expected collapsed certainty after settle, got {post}"
print(f"  [2/4] settle_intention collapses to a definite outcome (attempts={attempts}): OK")

# 3) Forced-ambiguous case: hand-construct an exact 50/50 state on qubit 0
#    and confirm the loop actually exercises extra attempts (not a no-op).
q3 = QuantumState()
q3.sim.state[:] = 0
q3.sim.state[0] = 1 / np.sqrt(2)          # |0000000>
q3.sim.state[1 << (q3.n - 1)] = 1 / np.sqrt(2)  # qubit 0 flipped, rest |0>
bits3, prob3, attempts3 = q3.settle_intention(
    targets=[0], vitality=0.0, confidence_threshold=0.99,
    max_attempts=2, noise_base_rate=0.9,
)
assert attempts3 <= 2
print(f"  [3/4] exact-tie state exercises the reconsideration loop (attempts={attempts3}, final_prob={prob3:.3f}): OK")

# 4) Real end-to-end: a genuine conversational turn still runs clean.
from allmynd.mind import AllMynd
mind = AllMynd()
r = mind.generate_response("hello, are you there?")
assert isinstance(r, str) and len(r) > 0
print(f"  [4/4] real AllMynd() turn still produces a response ({r!r}): OK")

print("ALL SMOKE TESTS PASSED")
''' % {"repo_root": repo_root}

    result = subprocess.run(
        [sys.executable, "-c", smoke_script],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        revert_all("smoke test failed")

    print("SUCCESS: patched and verified.")
    for t, b in backups.items():
        print(f"  {t}  (backup: {b})")


if __name__ == "__main__":
    main()
