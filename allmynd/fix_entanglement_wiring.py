#!/usr/bin/env python3
"""
fix_entanglement_wiring.py — wires EntanglementMemory (#17) into the real
turn pipeline. Run once from inside allmynd/ (same convention as the
other fix_*.py scripts):

    cd ~/downloads/allmynd
    python3 fix_entanglement_wiring.py

Requires semantic_engine/entanglement_memory.py to already be in place
(copy it in before running this).

What it does, in order:
  1. import EntanglementMemory
  2. __init__: self.entanglement_memory = EntanglementMemory()
  3. generate_response: bind co-occurring content words each turn, and
     nudge initial_field toward recalled partners (mirrors the
     associative_memory pattern already in the file)
  4. Phase 2.5: decay every bond once per turn, rate tied to vitality
     the same way quantum noise already is (low vitality -> faster fade)
  5. save()/load(): persist bonds (this IS long-term memory, unlike the
     quantum body / phase field, which opt out on purpose)
  6. status(): one line, same place the other Phase 4 items report

Self-verifying: checks each anchor is present before touching anything,
aborts without writing if any anchor is missing or already patched,
compiles the result, and re-imports + instantiates AllMynd() afterward
to confirm the wiring doesn't crash construction.
"""

import sys

TARGET = "mind.py"

EDITS = [
    (
        "import EntanglementMemory",
        "from semantic_engine.ambiguity import SemanticErrorDetector\n",
        "from semantic_engine.ambiguity import SemanticErrorDetector\n"
        "from semantic_engine.entanglement_memory import EntanglementMemory\n",
    ),
    (
        "__init__: construct entanglement_memory",
        "        self.quantum_body = QuantumState()\n"
        "        self.phase_field = ComplexPhaseField()\n"
        "        self.ambiguity_detector = SemanticErrorDetector()\n",
        "        self.quantum_body = QuantumState()\n"
        "        self.phase_field = ComplexPhaseField()\n"
        "        self.ambiguity_detector = SemanticErrorDetector()\n"
        "        self.entanglement_memory = EntanglementMemory()\n",
    ),
    (
        "generate_response: bind + recall-bias on user words",
        "            initial_field = _normalize_field(initial_field)\n"
        "            for word in user_words:\n"
        "                initial_field = self.scaffold.apply(initial_field, word)\n"
        "\n"
        "            # ─── Ambiguity scan (#16)",
        "            initial_field = _normalize_field(initial_field)\n"
        "            for word in user_words:\n"
        "                initial_field = self.scaffold.apply(initial_field, word)\n"
        "\n"
        "            # ─── Entanglement memory (#17): co-occurring content words\n"
        "            # this turn get bound as Bell pairs (fresh slot per pair, so\n"
        "            # binding one pair can't disturb another). Any word already\n"
        "            # holding a confident bond nudges its recalled partner into\n"
        "            # the field too -- same weight convention as associative_memory\n"
        "            # below, non-destructive (recall() never collapses the bond).\n"
        "            try:\n"
        "                content_words = [w for w in user_words\n"
        "                                 if w not in STRUCTURAL_WORDS and w not in FUNCTION_WORDS]\n"
        "                for i in range(len(content_words)):\n"
        "                    for j in range(i + 1, len(content_words)):\n"
        "                        self.entanglement_memory.bind(content_words[i], content_words[j], strength=0.6)\n"
        "                for w in content_words:\n"
        "                    hit = self.entanglement_memory.recall(w, min_confidence=0.3)\n"
        "                    if hit is not None:\n"
        "                        partner, conf = hit\n"
        "                        pv = self._get_or_create_vector(partner)\n"
        "                        if np.linalg.norm(pv) > 1e-8:\n"
        "                            initial_field = initial_field + pv * conf * 0.05\n"
        "                initial_field = _normalize_field(initial_field)\n"
        "            except Exception:\n"
        "                pass\n"
        "\n"
        "            # ─── Ambiguity scan (#16)",
    ),
    (
        "Phase 2.5: decay bonds, vitality-scaled",
        "        qb.apply_noise(vitality)\n",
        "        qb.apply_noise(vitality)\n"
        "\n"
        "        # Entanglement memory (#17): same vitality-scaled logic as the\n"
        "        # quantum body's own decoherence -- low vitality, faster fade.\n"
        "        try:\n"
        "            self.entanglement_memory.decay(rate=0.05 * (1.0 - vitality))\n"
        "        except Exception:\n"
        "            pass\n",
    ),
    (
        "save(): persist bonds",
        '                "associative_memory": self.associative_memory.to_dict(),\n',
        '                "associative_memory": self.associative_memory.to_dict(),\n'
        '                "entanglement_memory": self.entanglement_memory.to_dict(),\n',
    ),
    (
        "load(): restore bonds",
        '        if "associative_memory" in data:\n'
        '            self.associative_memory.from_dict(data["associative_memory"])\n',
        '        if "associative_memory" in data:\n'
        '            self.associative_memory.from_dict(data["associative_memory"])\n'
        '        if "entanglement_memory" in data:\n'
        '            self.entanglement_memory.from_dict(data["entanglement_memory"])\n',
    ),
    (
        "status(): report bonds",
        "            self.ambiguity_detector.status(),\n"
        '            "=" * 50,\n',
        "            self.ambiguity_detector.status(),\n"
        "            self.entanglement_memory.status(),\n"
        '            "=" * 50,\n',
    ),
]

with open(TARGET, "r") as f:
    content = f.read()

if "self.entanglement_memory = EntanglementMemory()" in content:
    print(f"NOTHING TO PATCH — {TARGET} already has entanglement memory wired in. Not touching it.")
    sys.exit(0)

for name, old, new in EDITS:
    if old not in content:
        print(f"ABORTING before any write — anchor for [{name}] not found in {TARGET}.")
        print("The file may have changed since this patch was written. Nothing touched.")
        sys.exit(1)
    if content.count(old) > 1:
        print(f"ABORTING before any write — anchor for [{name}] is not unique in {TARGET}.")
        sys.exit(1)

for name, old, new in EDITS:
    content = content.replace(old, new)

with open(TARGET, "w") as f:
    f.write(content)

print(f"Patched {TARGET}: entanglement memory wired into init, turn pipeline, decay, save/load, status.")

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
    assert hasattr(mind, "entanglement_memory")
    r = mind.generate_response("the fire alarm is loud tonight")
    assert isinstance(r, str) and len(r) > 0
    s = mind.status()
    assert "Entanglement Memory:" in s
    d = mind.entanglement_memory.to_dict()
    mind.entanglement_memory.from_dict(d)  # round-trip sanity
    print("Import + instantiate + one real turn + status + save/load round-trip: OK")
except Exception as e:
    print("BEHAVIOR CHECK FAILED after patch:")
    print(repr(e))
    sys.exit(1)

print("\nDone. Entanglement memory is live: bound on co-occurring content")
print("words each turn, decayed each turn (vitality-scaled), persisted in")
print("allmynd_v1.json, and reported in /status.")
