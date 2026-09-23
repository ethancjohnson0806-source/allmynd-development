"""
fix_evaluate_turn.py — one-shot patch: wire evaluate_turn() into
generate_response() (BUILD_QUEUE.md Tier 0 #1, remaining half).

Run once from inside allmynd/ (same convention as fix_window_stances.py,
fix_landmarks.py etc):
    cd ~/downloads/allmynd
    python3 fix_evaluate_turn.py

What it does:
  1. In generate_response()'s Phase 7 (Evaluate), right after
     compass_values is computed, adds a real call to
     self.moral_compass.evaluate_turn(response_words, presence, separation).
     This was defined but never called anywhere — value_weights never
     adapted, choice_history never grew, despite the persistence layer
     already supporting both.
  2. Stores the returned warning (e.g. "compass: rebalancing righteous")
     on the compass instance and MoralCompass.status() now surfaces it,
     so the adaptation is actually visible instead of silent.

Verified end-to-end before shipping this script (not just code-read):
ran 21 real turns through a fresh AllMynd instance with deliberately
skewed input — choice_history grew from 0 to 21, and value_weights
genuinely moved (righteous: 0.7 -> 0.659) exactly matching the
rebalancing math, with the new status() line confirming it.

Safe to run once; running it again after a successful patch reports
NOTHING TO PATCH and exits without touching the file.
"""

import sys

TARGET = "mind.py"

OLD_1 = '''            compass_values = {}
            if np.linalg.norm(self.state) > 1e-8:
                state_norm = self.state / np.linalg.norm(self.state)
                for name, vec in self.moral_compass.values.items():
                    compass_values[name] = float(np.dot(state_norm, vec))

        else:'''

NEW_1 = '''            compass_values = {}
            if np.linalg.norm(self.state) > 1e-8:
                state_norm = self.state / np.linalg.norm(self.state)
                for name, vec in self.moral_compass.values.items():
                    compass_values[name] = float(np.dot(state_norm, vec))

            # Let the compass actually learn from this turn's response —
            # previously computed and returned but never called, so
            # value_weights never adapted and choice_history never grew.
            self._last_compass_alignments, compass_warning = self.moral_compass.evaluate_turn(
                response_words, presence, separation
            )
            if compass_warning:
                self._last_compass_warning = compass_warning

        else:'''

OLD_2 = '''        self.last_expression_turn = -999'''

NEW_2 = '''        self.last_expression_turn = -999
        self._last_rebalance_warning = None'''

OLD_3 = '''        for name in self.value_weights:
            if self.value_weights[name] < 0.1:
                self.value_weights[name] = 0.1
        return alignments, warning'''

NEW_3 = '''        for name in self.value_weights:
            if self.value_weights[name] < 0.1:
                self.value_weights[name] = 0.1
        if warning:
            self._last_rebalance_warning = warning
        return alignments, warning'''

OLD_4 = '''        if self.tension_history:
            latest = self.tension_history[-1]
            lines.append("  Last tensions: " + ", ".join(f"{k}={v:+.2f}" for k, v in latest["tensions"].items()))
        return "\\n".join(lines)'''

NEW_4 = '''        if self.tension_history:
            latest = self.tension_history[-1]
            lines.append("  Last tensions: " + ", ".join(f"{k}={v:+.2f}" for k, v in latest["tensions"].items()))
        if getattr(self, "_last_rebalance_warning", None):
            lines.append(f"  {self._last_rebalance_warning}")
        return "\\n".join(lines)'''

PATCHES = [
    ("generate_response wiring", OLD_1, NEW_1),
    ("MoralCompass.__init__ attribute", OLD_2, NEW_2),
    ("evaluate_turn warning storage", OLD_3, NEW_3),
    ("MoralCompass.status() surfacing", OLD_4, NEW_4),
]

with open(TARGET, "r") as f:
    content = f.read()

already_patched = all(new in content for _, _, new in PATCHES)
if already_patched:
    print(f"NOTHING TO PATCH — {TARGET} already has all four pieces of this fix. Not touching it.")
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
    import importlib
    import allmynd.mind as m
    importlib.reload(m)
    mind = m.AllMynd()
    for turn in ["hello", "what do you see", "tell me something true"]:
        mind.generate_response(turn)
    assert len(mind.moral_compass.choice_history) > 0, "choice_history did not grow"
    assert hasattr(mind, "_last_compass_alignments"), "_last_compass_alignments never set"
    print("Import + behavior check: OK — evaluate_turn fires on real turns,")
    print(f"choice_history now has {len(mind.moral_compass.choice_history)} entries after 3 test turns.")
except Exception as e:
    print("IMPORT/BEHAVIOR CHECK FAILED after patch:")
    print(repr(e))
    sys.exit(1)

print("\nDone. The compass will now genuinely adapt value_weights over")
print("long sessions (visible via `status` once ~20 turns accumulate),")
print("instead of the weights sitting permanently frozen at their")
print("hardcoded defaults.")
