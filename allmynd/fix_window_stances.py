"""
fix_window_stances.py — one-shot patch for the confirmed-live Window
recent_stances persistence bug (BUILD_QUEUE.md Tier 0 #2).

Run once from inside allmynd/ (same convention as fix_landmarks.py etc):
    cd ~/downloads/allmynd
    python3 fix_window_stances.py

What it does:
  - Stops to_dict() from writing recent_stances into the save file
  - Stops from_dict() from restoring recent_stances from old saves
  - Leaves observations (safe, useful history) untouched

Why: to_dict()/from_dict() persisted recent_stances, so reloading a
save carried forward stale stance history that could immediately trip
is_circling() before any new turns happened this session. Confirmed
live in allmynd_v1.json: recent_stances was sitting at
['drift', 'drift', 'drift'] - exactly is_circling()'s trigger
condition - meaning the very next turn after loading would report
"I feel myself circling" with zero cause in the new session.

This script is self-verifying: it checks the old text is present
before patching, and re-imports the module after to confirm it still
works. Safe to run once; do not re-run after it succeeds (matches the
project's "already-applied one-shot scripts, do not re-run" rule -
if you run it again after a successful patch, it will simply report
NOTHING TO PATCH and exit without touching the file, so it can't
double-apply or corrupt anything.
"""

import sys

TARGET = "mind.py"

OLD = '''    def to_dict(self):
        return {
            "recent_stances": list(self.recent_stances),
            "observations": list(self.observations),
        }

    def from_dict(self, data):
        for s in data.get("recent_stances", []):
            self.recent_stances.append(s)
        for o in data.get("observations", []):
            self.observations.append(o)'''

NEW = '''    def to_dict(self):
        return {
            "observations": list(self.observations),
        }

    def from_dict(self, data):
        for o in data.get("observations", []):
            self.observations.append(o)'''

with open(TARGET, "r") as f:
    content = f.read()

if NEW in content:
    print(f"NOTHING TO PATCH — {TARGET} already has the fix. Not touching it.")
    sys.exit(0)

if OLD not in content:
    print(f"ABORTING — expected old Window.to_dict/from_dict text not found in {TARGET}.")
    print("The file may have changed since this patch was written. Not touching it.")
    sys.exit(1)

content = content.replace(OLD, NEW)

with open(TARGET, "w") as f:
    f.write(content)

print(f"Patched {TARGET}: Window no longer persists recent_stances.")

# Self-verify: recompile and re-import
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
    w = m.Window()
    assert "recent_stances" not in w.to_dict()
    print("Import + behavior check: OK — recent_stances no longer in to_dict() output.")
except Exception as e:
    print("IMPORT/BEHAVIOR CHECK FAILED after patch:")
    print(repr(e))
    sys.exit(1)

print("\nDone. The next load of allmynd_v1.json will not carry forward")
print("the stale ['drift', 'drift', 'drift'] state — is_circling() will")
print("start clean on next run.")
