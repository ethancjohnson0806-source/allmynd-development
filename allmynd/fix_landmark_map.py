#!/usr/bin/env python3
"""
fix_landmark_map.py — LandmarkMap: dwell-time gate + eviction tie-break fix

Two real bugs found by reading the live LandmarkMap class in
allmynd/mind.py (not inferred from the changelog):

1. NO DWELL-TIME GATE. observe() turns ANY single novel field state into
   a full, persistent landmark on the very first sighting — directly
   contradicting the class's own docstring ("a centroid the field has
   genuinely lingered near"). Confirmed live: a single call to
   AllMynd().generate_response(...) on a totally fresh mind produces
   "1/40 regions charted" after exactly one turn.

2. BACKWARDS EVICTION TIE-BREAK. When at capacity, the old code evicted
   by key=(visits, -last_turn). Among landmarks tied on the lowest visit
   count, -last_turn ranks the MOST RECENTLY touched one as "weakest" and
   evicts it first — protecting the stalest landmark and killing the
   newest one instead. A brand-new real landmark could be evicted before
   it ever got a second visit, while an old, rarely-revisited one sat
   protected indefinitely.

Fix: a single-slot "pending candidate" buffer. A genuinely novel state
does NOT become a landmark immediately — it becomes self._pending. Only
if the field revisits that same region within `pending_window` turns
does it get promoted to a real, persistent landmark (visits=2 from
birth). A pending candidate that's never revisited in time is simply
replaced by whatever comes next — it never touches self.landmarks or
counts against max_landmarks. The eviction tie-break is also flipped to
ascending last_turn, so among tied-lowest-visit landmarks the STALEST is
evicted, not the newest.

self._pending is intentionally NOT persisted across save/load (same
convention as QuantumState) — losing one in-flight candidate on restart
is harmless.

Usage (from ~/downloads):
    python3 fix_landmark_map.py [path/to/mind.py]

Self-verifying: backs up the original, applies the patch, compile-checks
it, then runs real behavioral smoke tests (including a genuine
AllMynd().generate_response() call) before declaring success. Reverts
automatically if anything fails.
"""

import sys
import os
import shutil
import subprocess
import time
import py_compile

DEFAULT_TARGET = os.path.join("allmynd", "mind.py")

OLD_BLOCK = '''    def __init__(self, dim=DIM, max_landmarks=40, merge_threshold=0.15):
        self.dim = dim
        self.max_landmarks = max_landmarks
        self.merge_threshold = merge_threshold  # cosine sim above this = "same place"
        self.landmarks = []  # list of dicts: vec, visits, first_turn, last_turn, valence_sum, presence_sum

    def observe(self, field_state, turn, mood, presence):
        """Call once per real turn with the settled field state. Merges
        into the nearest landmark if close enough, otherwise plants a
        new one (evicting the weakest if at capacity)."""
        norm = np.linalg.norm(field_state)
        if norm < 1e-8:
            return None
        vec = field_state / norm

        best_idx, best_sim = None, -1.0
        for i, lm in enumerate(self.landmarks):
            sim = float(np.dot(vec, lm["vec"]))
            if sim > best_sim:
                best_sim, best_idx = sim, i

                # Dynamic threshold: if we have few landmarks, use a lower threshold
        dynamic_threshold = self.merge_threshold - min(0.1, (1.0 - len(self.landmarks) / 10) * 0.05)
        if best_idx is not None and best_sim >= dynamic_threshold:
            lm = self.landmarks[best_idx]
            n = lm["visits"]
            lm["vec"] = (lm["vec"] * n + vec) / (n + 1)
            lm["vec"] /= (np.linalg.norm(lm["vec"]) + 1e-8)
            lm["visits"] += 1
            lm["last_turn"] = turn
            lm["valence_sum"] += mood.get("valence", 0.0)
            lm["presence_sum"] += presence
            return {"index": best_idx, "similarity": best_sim, "new": False}

        if len(self.landmarks) >= self.max_landmarks:
            weakest = min(
                range(len(self.landmarks)),
                key=lambda i: (self.landmarks[i]["visits"], -self.landmarks[i]["last_turn"]),
            )
            del self.landmarks[weakest]

        self.landmarks.append({
            "vec": vec.copy(),
            "visits": 1,
            "first_turn": turn,
            "last_turn": turn,
            "valence_sum": float(mood.get("valence", 0.0)),
            "presence_sum": float(presence),
        })
        return {"index": len(self.landmarks) - 1, "similarity": max(best_sim, 0.0), "new": True}
'''

NEW_BLOCK = '''    def __init__(self, dim=DIM, max_landmarks=40, merge_threshold=0.15, pending_window=20):
        self.dim = dim
        self.max_landmarks = max_landmarks
        self.merge_threshold = merge_threshold  # cosine sim above this = "same place"
        self.landmarks = []  # list of dicts: vec, visits, first_turn, last_turn, valence_sum, presence_sum
        # FIX (dwell-time gate, applied via fix_landmark_map.py): a
        # landmark used to become persistent on the very first sighting,
        # no matter how fleeting -- contradicting this class's own
        # docstring ("genuinely lingered near"). self._pending holds one
        # unconfirmed candidate; it only becomes a real landmark if the
        # field revisits it within pending_window turns. Not persisted
        # across save/load (same convention as QuantumState) -- losing
        # an in-flight candidate on restart is harmless.
        self.pending_window = pending_window
        self._pending = None  # {"vec", "turn", "valence", "presence"} or None

    def observe(self, field_state, turn, mood, presence):
        """Call once per real turn with the settled field state. Merges
        into the nearest CONFIRMED landmark if close enough. Otherwise,
        checks whether this matches an unconfirmed candidate from a
        recent turn (within pending_window) -- if so, that candidate is
        promoted to a real, persistent landmark (evicting the weakest
        existing one if at capacity). A state with no confirmed match
        and no matching pending candidate becomes the new pending
        candidate itself; it is NOT added to self.landmarks and does not
        count toward max_landmarks unless (until) something revisits
        it."""
        norm = np.linalg.norm(field_state)
        if norm < 1e-8:
            return None
        vec = field_state / norm

        best_idx, best_sim = None, -1.0
        for i, lm in enumerate(self.landmarks):
            sim = float(np.dot(vec, lm["vec"]))
            if sim > best_sim:
                best_sim, best_idx = sim, i

                # Dynamic threshold: if we have few landmarks, use a lower threshold
        dynamic_threshold = self.merge_threshold - min(0.1, (1.0 - len(self.landmarks) / 10) * 0.05)
        if best_idx is not None and best_sim >= dynamic_threshold:
            lm = self.landmarks[best_idx]
            n = lm["visits"]
            lm["vec"] = (lm["vec"] * n + vec) / (n + 1)
            lm["vec"] /= (np.linalg.norm(lm["vec"]) + 1e-8)
            lm["visits"] += 1
            lm["last_turn"] = turn
            lm["valence_sum"] += mood.get("valence", 0.0)
            lm["presence_sum"] += presence
            self._pending = None  # a real hit makes any stale candidate moot
            return {"index": best_idx, "similarity": best_sim, "new": False}

        # No confirmed landmark matched. Does this revisit the pending
        # candidate within the dwell window? If so, the field has
        # genuinely lingered near this region twice now -- promote it.
        if self._pending is not None and (turn - self._pending["turn"]) <= self.pending_window:
            pending_sim = float(np.dot(vec, self._pending["vec"]))
            if pending_sim >= dynamic_threshold:
                merged_vec = (self._pending["vec"] + vec) / 2
                merged_vec /= (np.linalg.norm(merged_vec) + 1e-8)

                if len(self.landmarks) >= self.max_landmarks:
                    # FIX (eviction tie-break, applied via
                    # fix_landmark_map.py): the old key was
                    # (visits, -last_turn), which -- among landmarks
                    # tied on the lowest visit count -- evicted the MOST
                    # recently touched one first and protected the
                    # stalest. That meant a brand-new real landmark
                    # could be evicted before it ever got a second
                    # visit, while an old, cold, rarely-revisited one
                    # sat protected. Ascending last_turn now evicts the
                    # stalest of the tied-lowest group instead, giving
                    # young landmarks a real chance to accumulate visits
                    # before they're at risk again.
                    weakest = min(
                        range(len(self.landmarks)),
                        key=lambda i: (self.landmarks[i]["visits"], self.landmarks[i]["last_turn"]),
                    )
                    del self.landmarks[weakest]

                self.landmarks.append({
                    "vec": merged_vec,
                    "visits": 2,
                    "first_turn": self._pending["turn"],
                    "last_turn": turn,
                    "valence_sum": self._pending["valence"] + float(mood.get("valence", 0.0)),
                    "presence_sum": self._pending["presence"] + float(presence),
                })
                self._pending = None
                return {"index": len(self.landmarks) - 1, "similarity": pending_sim, "new": True}

        # Not a revisit (or the old candidate expired) -- this state
        # becomes the new pending candidate. Nothing persistent yet.
        self._pending = {
            "vec": vec.copy(),
            "turn": turn,
            "valence": float(mood.get("valence", 0.0)),
            "presence": float(presence),
        }
        return None
'''

MARKER = "pending_window"  # presence => already patched (self._pending_echo elsewhere is unrelated)


def fail(msg):
    print(f"FAILED: {msg}")
    sys.exit(1)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    if not os.path.isfile(target):
        fail(f"target file not found: {target}")

    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    if MARKER in content:
        fail("already patched (found 'self._pending' in file) -- refusing to double-patch")

    count = content.count(OLD_BLOCK)
    if count == 0:
        fail("expected LandmarkMap.__init__/observe block not found verbatim -- "
             "file has likely drifted from what this patch was written against. "
             "Re-check the real source before proceeding.")
    if count > 1:
        fail(f"expected block found {count} times, not exactly 1 -- refusing, ambiguous match")

    patched = content.replace(OLD_BLOCK, NEW_BLOCK, 1)

    backup_path = f"{target}.bak_landmark_map_{int(time.time())}"
    shutil.copy2(target, backup_path)
    print(f"Backed up original to {backup_path}")

    with open(target, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"Patched {target}")

    def revert(reason):
        shutil.copy2(backup_path, target)
        fail(f"{reason} -- reverted {target} from backup")

    # ── Compile check ──
    try:
        py_compile.compile(target, doraise=True)
    except py_compile.PyCompileError as e:
        revert(f"compile check failed: {e}")
    print("Compile check: OK")

    # ── Behavioral smoke tests, real import, real class ──
    target_dir = os.path.dirname(os.path.abspath(target)) or "."
    repo_root = os.path.dirname(target_dir)  # parent of allmynd/

    smoke_script = r'''
import sys, os
sys.path.insert(0, %(repo_root)r)
import numpy as np
from allmynd.mind import LandmarkMap

def mood(v=0.0):
    return {"valence": v}

# 1) A single novel sighting must NOT become a persistent landmark.
lm = LandmarkMap(dim=8, max_landmarks=2, merge_threshold=0.5, pending_window=10)
a = np.zeros(8); a[0] = 1.0
r = lm.observe(a, turn=0, mood=mood(), presence=0.5)
assert r is None, f"expected None (pending only), got {r!r}"
assert len(lm.landmarks) == 0, f"expected 0 confirmed landmarks, got {len(lm.landmarks)}"
assert lm._pending is not None, "expected a pending candidate to exist"
print("  [1/5] single sighting stays pending, not a landmark: OK")

# 2) Revisiting the SAME region within the window promotes it (visits=2).
r = lm.observe(a, turn=3, mood=mood(), presence=0.5)
assert r is not None and r["new"] is True, f"expected promotion, got {r!r}"
assert len(lm.landmarks) == 1 and lm.landmarks[0]["visits"] == 2, "expected 1 landmark, visits=2"
assert lm._pending is None, "pending should clear after promotion"
print("  [2/5] revisit within window promotes to a real landmark (visits=2): OK")

# 3) A novel sighting that is NEVER revisited within the window does not
#    promote -- it is simply replaced by whatever comes next.
lm2 = LandmarkMap(dim=8, max_landmarks=2, merge_threshold=0.5, pending_window=5)
b = np.zeros(8); b[1] = 1.0
lm2.observe(b, turn=0, mood=mood(), presence=0.5)
c = np.zeros(8); c[2] = 1.0
r = lm2.observe(c, turn=100, mood=mood(), presence=0.5)  # window long expired
assert r is None, f"expected no promotion after window expiry, got {r!r}"
assert len(lm2.landmarks) == 0, "expected 0 landmarks -- expired candidate must not promote"
print("  [3/5] expired pending candidate never promotes: OK")

# 4) Eviction tie-break: among tied-lowest-visits landmarks, the STALEST
#    (lowest last_turn) is evicted, not the most recently touched one.
lm3 = LandmarkMap(dim=8, max_landmarks=2, merge_threshold=0.9, pending_window=50)
d1 = np.zeros(8); d1[3] = 1.0
d2 = np.zeros(8); d2[4] = 1.0
d3 = np.zeros(8); d3[5] = 1.0
# Confirm two landmarks, both ending at visits=2, at different last_turn.
lm3.observe(d1, turn=0, mood=mood(), presence=0.5)
lm3.observe(d1, turn=1, mood=mood(), presence=0.5)   # landmark A: last_turn=1 (stale)
lm3.observe(d2, turn=10, mood=mood(), presence=0.5)
lm3.observe(d2, turn=11, mood=mood(), presence=0.5)  # landmark B: last_turn=11 (recent)
assert len(lm3.landmarks) == 2, "setup expected exactly 2 landmarks before eviction test"
# Now force an eviction by promoting a third, brand-new candidate.
lm3.observe(d3, turn=20, mood=mood(), presence=0.5)
r = lm3.observe(d3, turn=21, mood=mood(), presence=0.5)
assert r is not None and r["new"] is True, "expected the third candidate to promote and evict"
remaining_last_turns = sorted(lm["last_turn"] for lm in lm3.landmarks)
assert 1 not in remaining_last_turns, (
    f"stale landmark (last_turn=1) should have been evicted, remaining={remaining_last_turns}"
)
assert 11 in remaining_last_turns, (
    f"recent landmark (last_turn=11) should have survived, remaining={remaining_last_turns}"
)
print("  [4/5] eviction protects the recent landmark, drops the stale one: OK")

# 5) Real end-to-end: a single conversational turn on a fresh mind must
#    NOT immediately chart a landmark (this was the exact live bug).
from allmynd.mind import AllMynd
mind = AllMynd()
mind.generate_response("hello, are you there?")
assert len(mind.landmarks.landmarks) == 0, (
    f"expected 0 charted landmarks after one real turn, got "
    f"{len(mind.landmarks.landmarks)} -- dwell-time gate not effective"
)
print("  [5/5] real AllMynd() turn no longer instant-charts a landmark: OK")

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
        revert("smoke test failed")

    print(f"SUCCESS: {target} patched and verified.")
    print(f"Backup kept at: {backup_path}")


if __name__ == "__main__":
    main()
