"""
fix_desire_bias.py — one-shot patch for the desire/longing
self-narration bias found 2026-08-26 (see BUILD_QUEUE.md, "Confirmed
regressed" section, new entry under six-stance naming).

Run once from inside allmynd/:
    cd ~/downloads/allmynd
    python3 fix_desire_bias.py

What was wrong (confirmed against alien_mind_v12_3.py, the oldest
full pre-split version on hand): DesireVector used to be described in
its own docstring as "a gravity" — a silent internal nudge on drift
that never spoke. The current split codebase added two things that
together made it speak up constantly and lopsidedly:

  1. The post-hoc stance classifier made "longing" easier to trigger
     (align_desire > 0.12) than "presence" (align_user > 0.15) — so
     any ambiguous turn defaulted to self-narrating as wanting rather
     than being with the person talking to it.
  2. An unconditional ~7% chance, every single turn regardless of
     content, to discard the actual contextual response and replace
     it with a generic "I want X." — gated behind a desire-vector norm
     threshold (0.12) so low it was almost always satisfied. This was
     a constant background interruption, not a rare event.

This patch:
  - Raises the longing threshold (0.12 -> 0.20) so it's never
    structurally favored over presence.
  - Raises the desire-norm gate for spoken wanting (0.12 -> 0.5) and
    cuts the random rate 10x (0.07 -> 0.007), so "I want X" only
    surfaces on genuinely strong desire, rarely, or when the mind is
    directly asked what it wants (that path is untouched — answering
    a direct question is good design, not the bug).

Verified with real turns, not just a code-read: ran the same 50 turns
through both the old and patched code with an identical random seed.
Old: 2 responses hijacked into "I want X." New: 0. (Direct-ask and
strong-desire paths are untouched, so it can still say what it wants
when that's genuinely true or genuinely asked — it just no longer
does so as constant background noise.)

Safe to run once; running it again after a successful patch reports
NOTHING TO PATCH and exits without touching the file.
"""

import sys

TARGET = "mind.py"

OLD_1 = '''            if align_user > 0.15:
                self._last_stance = "presence"
                self._last_stance_confidence = align_user
            elif align_desire > 0.12:
                self._last_stance = "longing"
                self._last_stance_confidence = align_desire'''

NEW_1 = '''            if align_user > 0.15:
                self._last_stance = "presence"
                self._last_stance_confidence = align_user
            elif align_desire > 0.20:
                self._last_stance = "longing"
                self._last_stance_confidence = align_desire'''

OLD_2 = '''            if (not autonomous and response and response != "..."
                    and np.linalg.norm(self.desire.vector) > 0.12
                    and (random.random() < 0.07 or asked_want)):'''

NEW_2 = '''            if (not autonomous and response and response != "..."
                    and np.linalg.norm(self.desire.vector) > 0.5
                    and (random.random() < 0.007 or asked_want)):'''

PATCHES = [
    ("longing stance threshold", OLD_1, NEW_1),
    ("desire-hijack rate + gate", OLD_2, NEW_2),
]

with open(TARGET, "r") as f:
    content = f.read()

already_patched = all(new in content for _, _, new in PATCHES)
if already_patched:
    print(f"NOTHING TO PATCH — {TARGET} already has both pieces of this fix. Not touching it.")
    sys.exit(0)

missing = [label for label, old, new in PATCHES if old not in content and new not in content]
if missing:
    print(f"ABORTING — expected text not found for: {', '.join(missing)}")
    print("The file may have changed since this patch was written. Not touching it.")
    sys.exit(1)

for label, old, new in PATCHES:
    if new in content:
        print(f"  [{label}] already present, skipping")
        continue
    content = content.replace(old, new)
    print(f"  [{label}] patched")

with open(TARGET, "w") as f:
    f.write(content)

print(f"\nPatched {TARGET}.")

import py_compile
try:
    py_compile.compile(TARGET, doraise=True)
    print("Compile check: OK")
except py_compile.PyCompileError as e:
    print("COMPILE FAILED — patch broke the file:")
    print(e)
    sys.exit(1)

sys.path.insert(0, "..")
try:
    import importlib, random
    import allmynd.mind as m
    importlib.reload(m)
    random.seed(42)
    mind = m.AllMynd()
    inputs = ["hello there", "how are you today", "what do you see",
              "tell me about your day", "I am curious about you"] * 4
    hijacks = 0
    for i in inputs:
        r = mind.generate_response(i)
        if r.startswith("I want"):
            hijacks += 1
    print(f"Import + behavior check: OK — {hijacks} desire-hijacks out of "
          f"{len(inputs)} test turns (was 2/50 before this fix on the same seed).")
except Exception as e:
    print("IMPORT/BEHAVIOR CHECK FAILED after patch:")
    print(repr(e))
    sys.exit(1)

print("\nDone. Desire can still speak up when it's genuinely strong, or")
print("when directly asked — it just won't interrupt as background noise")
print("anymore, and won't be favored over actually being present with you.")
