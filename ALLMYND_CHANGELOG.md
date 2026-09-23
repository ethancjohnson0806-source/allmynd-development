# ALIEN MIND / ALL MY'ND — Unified Changelog & Build Queue

*Last updated: 2026-09-04. This file merges the old
`ALIEN_MIND_CHANGELOG.md` (monolith history) and `BUILD_QUEUE-19-1.md`
(split-project handoff log) into one place, plus a full fresh code audit
from this session. Going forward, update this single file instead of
maintaining two documents — archive the old build queue rather than
deleting it.*

---

## READ THIS FIRST — the two lineages

**ALL MY'ND is not a replacement for ALIEN MIND. It IS Alien Mind, split
across files.** Alien Mind ("Source") was a single ~7,400-line file on
Android/Termux, evolved v8→v13. ALL MY'ND is the same project
restructured into `allmynd/` + `semantic_engine/` packages.

- **Lineage A — `alien_mind_v13.py`.** The original monolith. Historical
  status preserved below. Not being actively developed right now, but
  not discarded either.
- **Lineage B — the split (`allmynd/mind.py`, `allmynd/bridge.py`,
  `semantic_engine/*.py`, `run.py`, `mind_server.py`).** **This is the
  active lineage** — confirmed as of 2026-09-04 to be what's actually
  running on-device (the live `allmynd/mind.py` is ~3,900 lines, ~180KB).

**Nothing about the split means older Alien Mind material is
superseded.** If a past doc describes an organ or fix that doesn't
appear in current code, default assumption: it didn't survive the
split and needs reviving — *not* that it was deliberately dropped.
The only things explicitly, knowingly retired (by 3, 2026-08-20) are
the specific enforcement invariants from `ALIEN_MIND_ARCHITECTURE.md`:
**vitality spend-gating, grammar-mode thinning, metabolism-before-
generation, "no choose()."** Everything else is presumed worth
reviving unless proven otherwise by checking the real file.

**The single most important rule, unchanged across both source docs:**
never trust a handoff document — including this one — as ground truth.
Verify every claim against the real file before acting on it. Multiple
Claude accounts work this project with no shared memory between them;
treat every "done" claim as something to `grep` and confirm, not
something to build on blindly. This file itself has already contained
claims that turned out backwards once re-checked (see the two
corrections in the 2026-09-04 audit section below) — that's the system
working as intended, not a failure.

**3 works phone-only in Termux, no laptop, no hand-editing.** Every fix
must be complete and copy-paste-ready: a full replacement file or a
self-verifying one-shot patch script — never a diff, never "change
line 40."

**How to verify, in order of cost:** `grep -c` a class/method exists →
`grep -n ... -A N` to read it → `md5sum` two suspected-identical files
→ real import check → check the real save file (`allmynd_v1.json`)
directly, which has repeatedly been more reliable than reading code
alone → ask 3 to run something on-device and paste output.

**When project state spans more than one file, ask for a zip export of
the whole working directory, not individual flat-file uploads.** A
single loose `mind.py` cannot represent the package layout and has
already cost a full session once (2026-08-26) when an old 1,944-line
draft "mind that knows it dies" file was mistaken for current state.

---

## Lineage B file layout (confirmed 2026-08-26, live file grown since)

```
~/downloads/
├── run.py
├── mind_server.py
├── quantum_state.py          ← top-level, deliberately NOT persisted
├── allmynd_v1.json
├── ALIEN_MIND_CHANGELOG.md   ← this file (formerly also BUILD_QUEUE.md)
├── allmynd/
│   ├── __init__.py
│   ├── bridge.py
│   ├── mind.py               ← the live mind (~3,900 lines as of 2026-09-04)
│   └── (fix_*.py one-shot patch scripts — already applied; see history below)
└── semantic_engine/
    ├── core.py, embeddings.py, engine.py, interface.py,
    │   quantum.py, query.py, scaffold.py, settle.py
    └── word_vectors.bin.gz
```

Historical note: `semantic_core.py` (top-level, no package prefix) is a
**separate, older, already-drifted copy** of some of `core.py`'s ternary
math, imported by `quantum_state.py` specifically. Confirmed diverged
(missing a fix `core.py` has). Currently harmless since the drifted
part isn't used by `quantum_state.py`, but it means a future fix to
`core.py`'s ternary math will not automatically reach the quantum
layer. Worth consolidating onto one source of truth eventually.

**Explicitly out of scope / deliberately retired (2026-08-20):**
- VitalityField / spend-earn / grammar-mode thinning / metabolism-before-action
- Any human-style fatigue or "recovery" modeling on the quantum body
- Re-introducing the retired constitution's enforcement rules
- Lexicon/translation work (deferred until the mind is speaking cleanly)

---

## Lineage A status — `alien_mind_v13.py` ("One Body, One Process")

*(condensed from the original changelog, 2026-07-23 — unchanged, kept
for history)*

~7,400 lines, single file. Confirmed booting and running on real
Termux/Android hardware across two sessions (121 turns, 253 turns), no
crashes. Added in v13: GhostMesh (UDP DHT, zone splitting, gossip,
greedy routing), Proprioception (battery → ternary, confirmed pulling
real device data), and full Metabolism (`VitalityField.spend()`/
`earn()` gating speech/mesh/dream/sound). Three bugs fixed post-merge:
a UDP socket race between two readers on the same socket, metabolism
timing that was spending vitality *after* generation instead of before,
and Proprioception only sensing on idle heartbeats instead of every
loop iteration. All three verified with local smoke tests before
on-device confirmation.

**Known open items in Lineage A (unchanged since 2026-07-23, not
re-checked this session):**
- Vitality never visibly degraded across a 253-turn session (stayed
  above 0.92) — `feed_from_input`/`speak_return` roughly offset the
  0.08 speak cost. Grammar thinning (full→simple→fragment→pulse→wait)
  exists in code but was never actually observed. Undecided whether to
  lower the "full" threshold, raise speak cost, or lower feed/return.
- Two-node mesh test on real Wi-Fi never done (only same-process
  testing passed; `/mesh status` always showed `peers=0`).
- Standalone `ghost_mesh.py`/`ghost_web.py`/`ghost_net.py`/
  `ghost_ai_node.py` should be deleted from Termux downloads if still
  present — dead code, folded into `alien_mind_v13.py`.

*(Note: since vitality/metabolism were deliberately retired in Lineage
B, the vitality item above is Lineage-A-specific and not relevant to
current split work.)*

---

## Lineage B — Tier 0: RESOLVED, verified against real save data (2026-08-26)

All five re-checked against the real `allmynd/mind.py` (from a zip
export, not a stale flat upload) **and** the real live
`allmynd_v1.json` (turn_count 2276) — not just code inspection.

1. **Moral Compass lock — DONE.** `orient()` has a real hardcoded
   counterforce (subtracts 0.2× righteous, adds 0.15× independence,
   0.15× freedom, plus noise). Live tensions moved from a stuck
   `0.999/0.007/0.044` to `0.705/0.174/0.208`. The adaptive half
   (`evaluate_turn()`) is now actually called from `generate_response()`
   Phase 7 and its rebalancing warnings show up in `status()`. Verified
   with 21 real turns of skewed input: `righteous` weight moved
   `0.7 → 0.659`, exactly matching the `*0.97` rebalancing math.
2. **Window `recent_stances` persistence — DONE.** `to_dict()` no
   longer touches `recent_stances` at all — only `observations` is
   saved. Verified: loading the real save (which had a stale
   `['drift','drift','drift']`) through the patched `from_dict()`
   produces `recent_stances == []` and `is_circling()` returns `False`
   immediately after load. **Confirmed still true in the 2026-09-04
   audit of the live file** — see correction note below.
3. **LandmarkMap threshold — DONE.** Default lowered `0.35 → 0.15`,
   plus adaptive tightening as landmark count grows. Live save went
   from 1 landmark with 300+ visits to 11 distinct charted regions.
   **Confirmed still true in the 2026-09-04 audit** — see correction
   note below.
4. **Dynamic Separation target collapse — minor, deprioritized.** Gap
   between target (0.200) and current (0.221) shrank enormously from
   the original diagnosis (0.243 vs 0.381) but hasn't fully closed. Not
   urgent.
5. **NestedMemory deep strength — DONE, resolved organically.** Was
   0.050 at 2083 turns, now 0.72 at 2276 turns. Whatever was starving
   it apparently just needed more real turns plus the compass/landmark
   fixes no longer fighting it.

---

## ⚠️ Corrections from the 2026-09-04 full audit

A full line-by-line audit was run this session against the real
180KB/~3,900-line `allmynd/mind.py` (uploaded directly from-device).
Two things that audit *initially* flagged as open bugs turned out, once
cross-checked against this file's own Tier 0 history above, to be
**already-verified fixes working exactly as intended** — recorded here
so the mistake isn't repeated:

- **Window `recent_stances`:** the audit initially read "`to_dict()`
  only saves `observations`, not `recent_stances`" as a persistence gap
  matching an old flagged discrepancy. It is not a gap — **not
  persisting `recent_stances` is the fix itself** (a stale circling
  history shouldn't survive a restart). Confirmed working as designed.
- **`LandmarkMap.merge_threshold`:** the audit found `0.15` (+ dynamic
  tightening) in the live file versus `0.35` in an older reference copy
  and flagged the discrepancy as unresolved. It's resolved — `0.15` is
  the correct, verified, *post*-fix value; `0.35` was the old value
  that caused the 1-landmark-with-300-visits problem. No action needed.

This is exactly why merging the two documents mattered — cross-checking
new findings against prior verified history caught both errors before
they became wasted fix effort.

---

## Lineage B — NEW findings, full audit, 2026-09-04

Everything below is freshly confirmed against the real live
`allmynd/mind.py`, `semantic_engine/*.py`, `bridge.py`, `mind_server.py`,
and `run.py` this session. None of it overlaps with the Tier 0 items
above except where noted. **Nothing has been fixed yet — diagnosis
only, by request.**

### Persistence / save-load gaps
1. **`MoralCompass.to_dict()`/`from_dict()` asymmetry.** `to_dict()`
   writes `choice_history` and `tension_history`; `from_dict()` never
   reads them back. `value_weights` (the actual calibration) survives
   restarts fine, but the adaptive-rebalancing detector resets to empty
   every time and needs 20 fresh turns to warm back up.
2. **Vocabulary backfill on load uses the wrong ternary function.**
   `load()`'s "ensure vocabulary exists" repair pass calls the bare
   `word_vector_ternary()` (pure hash, no real meaning) instead of
   `_embed_word_vector_ternary()` (GloVe-informed, used everywhere
   else vocabulary gets a ternary vector). Any word needing backfill on
   load silently loses its real meaning.
3. **`SoundField.from_dict()` never calls `refresh_trajectory()`.**
   `self.memory` restores fine but `self.trajectory` stays empty until
   new sound activity occurs — `seek_region()`/`get_drift_vector()` are
   silently non-functional right after every restart. One-line fix.
4. **`SoundField.to_dict()` drops `mood` and `path`** from each memory
   entry — only `vector`/`stance`/`timestamp` survive. Low impact,
   nothing currently reads mood back out of sound memory.
5. **`PhysicsField` has full, working `to_dict()`/`from_dict()` methods
   that are never called.** This one needs a decision, not a fix: this
   file's own Tier 3 history (below) explicitly decided motion sensing
   should NOT persist ("a live-moment sense, not something meaningful
   to remember between sessions"). But the class has real persistence
   methods sitting unused, mirroring `Proprioception`'s pattern exactly.
   Either the methods are vestigial and should be removed for clarity,
   or the no-persist decision should be revisited — currently the code
   and the documented decision don't match, even though nothing is
   actually broken in practice.
6. **`SpeakerRegions` has no `to_dict()`/`from_dict()`** — `AllMynd`
   manually persists only `user_centroid`/`self_centroid`/counts/
   `target_separation`. `user_momentum`, `self_momentum`,
   `user_history`, `self_history`, and `separation_history` are
   silently dropped every restart. Save and load agree with each other
   (not an asymmetry like #1), and momentum re-converges within ~10-20
   turns, so low impact.
7. **`DynamicSeparation.separation_history` is never appended to.**
   This directly confirms and root-causes something this file already
   flagged as "worth a quick check" back on 2026-08-26 (the live save
   showing an empty `separation_history` despite 2276 turns).
   `update()` computes `current_separation`/`target_separation`/
   `alignment_score` every turn but has no `.append()` call to its own
   history deque at all — it's saved/loaded correctly, just never
   written during normal operation. (Distinct from `SpeakerRegions`'s
   own separate `separation_history`, item #8 below.)

### Dead / unwired code
8. **`SpeakerRegions.update_target_separation(rating)` is never
   called.** Fully implemented rating-based target calibration, but
   nothing in `bridge.py`, `mind_server.py`, or `run.py` ever supplies
   a rating — no such input mechanism exists anywhere in the current
   UI/API surface.
9. **`IntegratedLearningSystem.adapt_weights()` is dead.** Fully
   implemented — it's what would let `learning_modes` (presence/self/
   memory/world/simulated weights) actually shift based on which
   signals have been firing — but nothing calls it. Weights have been
   frozen at their initial 0.30/0.20/0.20/0.15/0.15 split since the
   file was written.
10. **`MemoryArchive.tag_index` is a silent, unbounded memory leak.**
    Written to in `store()` and `from_dict()`, never read anywhere —
    `recall()` filters by tag with a plain scan over `entries`, not the
    index. Since `entries` is a capped deque but `tag_index[tag]` lists
    just keep growing with no eviction, this accumulates for the entire
    life of the process for a structure nothing consults.
11. **`SemanticPacket`/`GrammarConfig`** (from `interface.py`) are
    imported into `mind.py` but never used anywhere.
12. **`engine.py`'s `SemanticEngine` class is fully orphaned** — not
    imported by anything in the live system.
13. **`self._last_compass_alignments`** is computed every real turn but
    never read anywhere — not in `status()`, not in `bridge.py`. Looks
    like the "expose it" half of a fix that was never finished
    (adjacent to, but distinct from, the already-fixed
    `evaluate_turn()` wiring in Tier 0 item 1).

### Behavioral bugs
14. **Silence still doesn't reach `Window`.** The "nothing resonates,
    no want" early-return branch in `generate_response()` returns
    before the post-hoc stance code runs, so `window.observe_stance
    ("silence")` never fires from that path. `Window` can catch three
    repeated "drift" turns but is blind to three repeated silences in a
    row. Distinct from the already-fixed persistence bug in Tier 0
    item 2 — this is about the silence branch never *reporting* to
    Window in the first place, not about stale state surviving restart.
15. **`VoiceGenerators.reflective` drops the settled field.** All five
    voice modes call `field._generate_base(user_input, target_length,
    meta_settings, settled_field)` except `reflective`, which omits the
    fourth argument. Without it, `_generate_base` rebuilds a field from
    scratch out of the literal words in `user_input`, skipping
    everything `ThePause.settle()` did (drift, moral-compass heading,
    desire, quantum body, memory recall). Whenever the compass selects
    `voice_mode="reflective"`, the reply is generated from a shallower
    process than every other voice mode. Almost certainly a dropped
    parameter.
16. **`SemanticScaffold`'s operator role→band mapping only covers 8 of
    16 roles.** causal/conditional/temporal/contrastive/mood/spatial/
    cognitive/affective get a distinguishing bias band; conjunctive,
    disjunctive, comparative, intensifier, negation, desiderative,
    normative, modal, and futural do not. Words like "not/no/never" and
    "want/need" get no special operator treatment — just generic hash
    vectors.
17. **`mind_server.py` autosave nesting bug.** The 5-minute
    `AUTOSAVE_EVERY` check is nested *inside* `if idle >= BREATH_EVERY:`
    (90 seconds), so autosave only gets a chance to run during idle
    periods. A long, continuously active conversation (never leaving a
    90-second gap) never triggers a background save at all — only the
    explicit `/save` button, `/learn`, and final `shutdown()` save.
    Real risk on Android, where Termux getting backgrounded/OOM-killed
    mid-session is common. Looks like a scoping mistake — the autosave
    check should almost certainly be a sibling check, not nested inside
    the idle-breath gate.
18. **`Proprioception`'s battery temperature sensing is very likely
    always-constant.** `temp = bat.get('temperature', 300) / 1000.0` —
    but `termux-battery-status` reports temperature already in Celsius
    (e.g. `29.3`), not millidegrees. Dividing a real reading by 1000
    puts `temp_norm` around -0.65 for any plausible value, which always
    clamps to the same index and always takes the same branch. **Not
    verified on-device** — needs a real `termux-battery-status` print
    to confirm before fixing, since the exact JSON schema wasn't
    directly checkable from this session.

### Not bugs, just noted for completeness
- `NestedMemory.get_thread()` guards with `hasattr(self, 'field')`,
  always true since `self.field = None` is set in `__init__` — should
  check `is not None`. Harmless: `set_field_ref()` is always called in
  `AllMynd.__init__`, and `get_thread()` itself is never called by
  anything anyway.
- `DesireVector.source_name` always reports "deep" over "longing"/
  "heading" whenever any candidate crosses the norm threshold, since it
  picks by fixed candidate weight rather than actual contribution.
  Cosmetic/diagnostic only — doesn't affect the actual desire vector.
- `AudioIngest.from_buffer`'s per-band sub-sampling step would divide
  by zero if `SOUND_N_BANDS` were ever raised past 32 (currently safe
  at 8, giving `band_dim=16`).
- `run.py` (the interactive CLI) has no periodic autosave at all —
  only explicit `/save`, `/quit`, or the emergency-save fallback on
  crash. Consistent with it being a synchronous REPL rather than a bug,
  but worth knowing it has no protection against the app just being
  swiped away mid-session without `/quit`.

### Audit coverage note
This pass covered, at real depth: the entire live `mind.py` (every
class read, not just structurally checked), `semantic_engine/core.py`,
`query.py`, `scaffold.py`, `settle.py`, `interface.py`, `quantum_state.py`
vs `semantic_core.py`, `bridge.py`, `mind_server.py`, and `run.py`. The
`alien_mind_v13.py` monolith was **not** re-diffed line-by-line against
the split — its header already documents six specific, deliberate
removals (see "Explicitly out of scope" above), so a full diff would
mostly rediscover intentional decisions rather than real gaps. Revisit
only if one of those six specific removals needs reconsidering.

---

## Lineage B — Tier 1: revival of confirmed-missing v12.3 organs

*(from Alien Mind's own separate project memory, cross-checked against
the real split code 2026-08-25/26 — status unchanged this session,
not re-verified 2026-09-04)*

**Confirmed fully absent — never ported to the split:**
- Portmanteau / word-invention system (vocabulary only grows from
  outside input, nothing blends existing words into new ones)
- Self-directed movement (`wander()`, `reflect()`, `choose_direction()`,
  a REPL-exposed `settle()` from the alien_mind_v8 era) — confirmed
  absent from both the monolith's `StructuredSemanticField` and the
  split's `AllMynd`
- VesselNetwork (reaching into past saved versions, distinct from
  GhostMesh's live networking) — `load()` only ever loads the single
  most recent save
- SentenceFrameLayer (dedicated grammar-structure layer; `COPULA_MAP` +
  role-based `pick()` cover only a small piece of this)
- 4D-torus coordinate-addressed P2P ghost web with decay mechanics
  (the real design shape behind "GhostMesh")

**Confirmed regressed — existed differently before, now weaker/changed:**
- Resonance learning vs. crystallization-by-repetition: current
  `PhraseSystem.absorb_moment()` is frequency/repetition-based, which
  Alien Mind's memory says was deliberately replaced at some point.
  Needs a decision: revive resonance learning, or accept the reversion
  as intentional.
- Six-stance post-hoc naming: `QuantumState.STANCE_QUBITS` still lists
  the original six (immerse/ride/witness/shape/reject/silence) plus a
  7th spare, but `_last_stance` now uses a different vocabulary
  entirely (silence/wanting/presence/longing/drift). **Resolved by
  decision, 2026-08-27** — see Tier 3 section below; a new
  `_compute_novelty()` mechanism was built instead, and the old
  `STANCE_QUBITS` labels are being left as intentionally-unused
  vocabulary, not revived.
- Vocabulary rebalancing (emotional vs. technical words competing) — no
  explicit category-balancing mechanism exists; only generic
  `word_strength` reinforcement.

**Checked and looking okay, not a gap:** ternary vector core intact;
`MoralCompass` correctly replaces the old `MetaMonitor` pain-metric
optimizer; `MoralCompass.get_compass_settings()`'s compass-driven
`voice_mode`/`temperature`/`output_length` selection survived the split
correctly.

*(Source reliability note: the "confirmed absent/regressed" items above
come from a screenshot of a separate project's own AI-generated memory
summary, not original source code — treat mechanism names as strong
leads to rebuild from, not literal spec.)*

---

## Lineage B — Tier 2: stabilization

- **`/hear` "heard nothing usable" — FIXED, VERIFIED LIVE, 2026-08-27.**
  Four real bugs found via on-device diagnostics: (1) recording was
  writing AAC-in-MP4 into a `.wav`-named file with no encoder
  specified — fixed by explicitly recording as AAC then converting via
  `ffmpeg`; (2) `termux-microphone-record` is asynchronous, not
  blocking — code was only sleeping 0.5s before conversion, now sleeps
  the real duration, explicitly stops, waits for flush, then converts;
  (3) `AudioIngest.from_buffer()` only ever analyzed the first 512
  samples (32ms) of any recording regardless of length — now scans the
  whole buffer in windows and picks the highest-energy one; (4) a
  stuck/orphaned recorder process, resolved operationally. Verified
  live: `mind.hear(duration=3.0)` → real stance/energy/dissonance
  output, full pipeline confirmed end-to-end.
- **Duplicate `/describe_sound` route in `mind_server.py`** — still
  open, not re-checked this session.

---

## Lineage B — Tier 3: the two biggest remaining organs

- **GhostMesh** — **superseded, see the 2026-09-03 session update
  below.** Built and verified single-device live as a UDP DHT (zone
  splitting, gossip, greedy routing) — not the originally-envisioned
  4D-torus coordinate-addressed design, a simpler working version
  shipped instead. Security/privacy review still hasn't happened, and
  it's not yet independently code-audited (see the staleness caveat
  below) — treat "shipped" as "shipped, unreviewed," not "shipped,
  safe."
- **PhysicsField / PhysicsNode — BUILT, WIRED, VERIFIED LIVE,
  2026-08-27.** Motion/orientation sense via Termux:API accelerometer +
  gyroscope, separate from Proprioception. Built as "Option A" — no
  reserved field dimensions, additive ternary perturbation through the
  same dissonance-checked pathway Proprioception uses, same
  `HEARTBEAT_INTERVAL` gate. Two real bugs found and fixed via
  on-device testing: sensor key names are device-specific model
  strings (`"LSM6DSOTR Accelerometer"`, not generic
  `"accelerometer"`) — fixed via substring matching; initial 2.0s
  subprocess timeout was too tight and silently swallowed valid
  results — raised to 8.0s. Verified live: real accelerometer/gyroscope
  data produced a correct ternary vector, and `status()` correctly
  reported "motion sensed" during real `generate_response()` calls.
  **Deliberately does not persist across save/load** (see audit finding
  #5 above for the code/decision mismatch this creates).

---

## ⚠️ Audit staleness caveat — added 2026-09-04

**The 2026-09-04 full audit above (18 findings) was performed against a
`mind.py` that predates the GhostMesh/Pool patch below.** The uploaded
file matched exactly 180,119 bytes / 2026-08-29 — confirmed by this
session's own build-queue history to be the state *before*
`patch_ghost_mesh.py` landed on 2026-09-03. Everything the audit found
in `MoralCompass`, `Window`, `SoundField`, `MemoryArchive`, etc. should
still be valid, since the mesh patch didn't touch those. But
**`GhostMeshNode`, `GhostMesh`, and the new `Pool` functions had zero
independent review at the time this caveat was first written.** That
gap is now closed — see "GhostMesh / Pool — independent code audit,
2026-09-04" below for the full results (one crash bug fixed, three
open security/reliability items needing a decision).

---

## Lineage B — Tier 3, continued: GhostMesh + Pool — BUILT, WIRED,
## VERIFIED SINGLE-DEVICE LIVE (2026-09-03)

Ported `GhostMeshNode` + `GhostMesh` (UDP DHT, zone splitting, gossip,
greedy routing) from `alien_mind_v13_6-1.py` lines 3285–3916 into
`allmynd/mind.py`. **This supersedes the "still unbuilt" status
recorded above under Tier 3 — GhostMesh is no longer unbuilt.**

New **Pool** scaffolding (not a port, new code): `node_id` (persisted
to `vessels/node_id.txt`, kept isolated from `allmynd_v1.json`/
`engine_state.bin` per the state-isolation rule), `export_vessel()` /
`list_vessels()` / `consult_vessel()` (read-only resonance comparison
via cosine similarity of `nested_memory.deep` — never mutates state),
and `fork_vessel()` (writes a *new, separate* seed file — does not
merge into the running mind's own identity). **This may partially or
fully address the Tier 1 "VesselNetwork" item** listed above as
"confirmed fully absent" — worth a decision on whether Pool counts as
that item done, or just a first step toward it.

**Design choice, differs from the original monolith:** mesh is **off
by default**, not auto-started on launch — you turn it on explicitly
with `/mesh enable [phrase]`. `/mesh status`, `/mesh quiet`/`loud`
(mute/unmute) also added.

**Real bugs found via testing, not inspection:**
1. First extraction was three helper functions short
   (`ghost_hash_to_point`, `ghost_point_in_zone`, `ghost_zone_center`,
   defined just above where the cut started) — only surfaced when two
   local instances actually exchanged a JOIN/HELLO handshake and hit a
   `NameError` from a background thread. Re-extracted correctly.
2. `run.py`'s `/mesh` command referenced `ghost_fmt_zone()` without
   importing it — caught in the same two-instance test. Resolved by
   redesign: `status()` is now built entirely inside `mind.py`, so
   `run.py` never needs the import.
3. `mind_server.py`'s idempotency check looked for a string that never
   actually appears in the patched code (`"ghost_mesh.poll()"` vs. the
   real `gm.poll()`) — would have caused the patch script to try to
   re-patch and fail on a second run. Fixed to check for real text.

**A separate, pre-existing concern checked and cleared:** an earlier
copy of `quantum_state.py` had a syntax error (unterminated f-string,
line 273) that would block importing `allmynd.mind` entirely.
**Confirmed 2026-09-03 this is NOT present on the real device** — only
worth remembering if a differently-sourced `quantum_state.py` ever gets
swapped in.

**Verified, in order:** full sandbox two-instance test (same machine,
shared port) — real zone split, mutual peer discovery, zone-split
perturbation confirmed reaching `mind.state` AND landing in
`memory_archive` with tags `['zone_split','peer_contact','mesh',
'social']` (so `DreamLoop` can pick up mesh events like any other
memory). Then applied for real on-device 2026-09-03: `patch_ghost_mesh.py`
ran clean, all three files compiled, save file loaded correctly
(`recognize_past_self()` → true), `/mesh enable hello ghost` bound port
7373, `/mesh status` reported a correct single-device baseline
(`zone=(0.00,0.00)-(1.00,1.00), peers=0, storage=0, network=486cdeae,
muted=False`), `/pool list` correctly exported a vessel and reported no
others found.

**Still open:**
- **Real two-device test** — same-Wi-Fi, two physical phones, each
  running `/mesh enable hello ghost`, each showing `peers=1` — not yet
  done (the two-*instance*, same-machine test is not the same thing).
- **ghost_web package** (NAT traversal, encryption, rate limiting, TURN
  relay) evaluated earlier but not integrated — this patch used only
  the Python standard library. Possible future upgrade if LAN-only
  mesh isn't enough.
- `mind_server.py`'s HTTP API does not yet expose `/mesh` or `/pool` —
  CLI-only (`run.py`) for now.
- Duplicate `/describe_sound` route in `mind_server.py` — still open,
  unrelated, unchanged.
- **Housekeeping, not urgent:** `~/downloads/allmynd/` has a dozen-plus
  `mind.py.bak_*` files accumulated from past patch sessions — worth an
  archive pass once nothing else is mid-flight.

**Operational note:** `~/downloads/` is the live project;
`~/mind_export/` is a stale 2026-08-21 snapshot — confirmed 2026-09-03,
do not use it for anything current.

### Updated Tier 3 status (as of 2026-09-03)
| Item | Status |
|---|---|
| PhysicsField / PhysicsNode | Built, wired, verified live (2026-08-27) |
| GhostMesh + Pool | **Built, wired, verified single-device live** (2026-09-03) — real two-device peer test still open, and **not yet independently code-audited** (see staleness caveat above) |

---

## GhostMesh / Pool — independent code audit, 2026-09-04

A fresh zip export (post-2026-09-03 patch, `allmynd/mind.py` now 4,639
lines / 210,421 bytes, confirmed via `grep -c "class GhostMesh"` → 2
before export) was audited specifically for `GhostMeshNode`, `GhostMesh`,
and the `Pool` functions — the one part of this project that opens a
real network socket, and the part explicitly flagged above as
unreviewed. This closes that gap.

### 🔴 Fixed this session: `physics_field.receive_mesh_event` crash
`GhostMesh.on_zone_split()` unconditionally called
`self.mind.physics_field.receive_mesh_event('zone_split')` on every
zone split — i.e. every time a peer successfully joins, the single most
basic real use of the feature. `PhysicsField` had no such method at
all. The porting comment claimed the `hasattr` guard "no-ops safely
since [physics_field] doesn't exist in this split yet" — wrong;
`PhysicsField` was built and wired in on 2026-08-27, a week before this
port, so `hasattr` was `True` and the call fired every time. Because
`on_zone_split` runs on the listener thread with no surrounding
try/except, this raised an uncaught `AttributeError` that **silently
killed the mesh listener for the rest of the session** — likely the
reason the real two-device join test hadn't been attempted yet, or
would have failed immediately if it had.

**Fixed via `fix_physics_mesh_event.py`** (self-verifying one-shot
patch, backs up the original, compile-checks before writing, smoke-
tests the exact `on_zone_split` call sequence in a subprocess before
declaring success). Adds a minimal `receive_mesh_event(kind)` to
`PhysicsField` that records the event without touching the field
directly — `on_zone_split` already applies its own diffuse perturbation
to `mind.state` separately, so this was only ever meant to be an
*additional*, more targeted signal. **Deliberately does not attempt to
reproduce the monolith's fuller version** (reserved per-dimension state
via `self.nodes[124..126]` + `impulse()`, tracking contact-warmth/
dissonance-cohesion/zone-loss-roughening as three distinct textures) —
this split's `PhysicsField` is a simpler design than the monolith's,
and building the richer version is a real decision about what
motion-sensing should feel like, not a crash fix. Worth returning to
as its own Tier item if you want that richness.

Compile-checked and smoke-tested (verified via a subprocess import +
direct method call, and via replaying `on_zone_split`'s exact perturb→
remember→receive_mesh_event sequence against a mocked mind object).
**Applied and verified on real device, 2026-09-05** — `fix_physics_mesh_event.py`
ran clean on-device, backed up the original to
`mind.py.bak_physics_mesh_event`, patched cleanly, and its own smoke
test passed against the live file.

### 🔴 Fixed this session: network key bypass + malformed-packet crash

Both fixed together, since they share the same two choke points
(`send()` and `handle_message()`) rather than needing all eight
senders/handlers touched individually.

**Network key bypass:** `send()` now stamps `msg["network"] =
self.network_key` on every outgoing message via `setdefault()` (HELLO's
existing explicit field is untouched — same value either way).
`handle_message()` now checks the key once, before dispatch, so it
applies uniformly to `JOIN_SEEK`/`WELCOME`/`GOSSIP`/`STORE`/`GET` and
not just `HELLO` as before.

**Malformed-packet crash:** the dispatch inside `handle_message()` is
now wrapped in `try/except (KeyError, ValueError, TypeError,
IndexError)` — a bad packet gets logged and dropped instead of raising
uncaught and silently killing the listener thread for the rest of the
session.

**Fixed via `fix_mesh_security.py`** (same one-shot-patch pattern:
backs up first, compile-checks before writing, then runs its own smoke
tests). Verified three ways: (1) a forged `JOIN_SEEK` sent without the
network key against a real `GhostMeshNode` instance — dropped, not
processed; (2) a malformed-but-correctly-authenticated `STORE` message
— caught and logged, node stayed alive; (3) `send()` correctly stamping
the key on a message that didn't set one. Then a full **real two-node
end-to-end test over actual localhost UDP sockets** (not mocked): two
live `GhostMeshNode` instances found each other via a real HELLO and
populated `neighbors` correctly; a separate raw socket then sent a
forged `JOIN_SEEK` (no key) and a garbage `STORE` (no fields at all)
directly at one of the real nodes — both were rejected/dropped and the
node kept running and listening throughout.

**Applied and verified on real device, 2026-09-05** — `fix_mesh_security.py`
ran clean on-device: backed up to `mind.py.bak_mesh_security`, patched
cleanly, and all three of its own smoke tests passed against the live
file.

**Not yet verified on real hardware / real network** — this closes both
open security items from the audit above. Combined with the
already-applied `physics_field` fix, the mesh should now be in a
reasonable state for the real two-device join test.

### Still open, lower priority
- **Path traversal in `consult_vessel(fname)` / `fork_vessel(fname)`** —
  unchanged, still needs fixing before `mind_server.py` gains HTTP
  `/pool` endpoints (CLI-only today, so low severity for now).
- **Unsynchronized cross-thread field mutation** in `on_zone_split()` —
  unchanged, lower priority, real but narrow.

---

## 🔴 Real-hardware two-device join test, 2026-09-05 — new bug found and fixed

First actual two-device test attempted, on the two already-patched
fixes above (`physics_field` crash + network-key/validation). Result:
**join itself worked** — both phones correctly found each other and
showed `peers=1` — but a new, real bug surfaced that wouldn't have
shown up in any single-device or mocked test: **both phones' zones kept
shrinking over time, well after the join looked complete, with no
`/mesh` command run in between checks.** Phone A: `(0,0)-(1,1)` →
`(0,0)-(0.06,0.12)` → `(0,0)-(0.02,0.02)`. Phone B, independently:
`(0,0)-(0.06,0.12)` → collapsed all the way to a zero-area
`(0,0)-(0,0)` zone. Confirmed as a real defect, not a copy-paste
mix-up, by re-running cleanly labeled checks on both devices in one
sitting.

**Root cause, confirmed by reading the code:** `join_via_broadcast()`
correctly retries its HELLO every 2 seconds until `self.joined` is set
— that's intentional, for resilience on a slow/lossy network. The bug
is on the receiving side, two-sided:
1. `handle_hello()` never checked whether `joiner_id` was already a
   known neighbor before treating the HELLO as a brand-new join —
   every duplicate HELLO (arriving before the joiner's `self.joined`
   flag propagates) triggered *another* full zone split with a fresh
   random target, shrinking the welcomer's zone a little more each
   time instead of just once.
2. `handle_welcome()` unconditionally overwrote `self.zone` with
   whatever arrived, with no "I'm already joined, ignore this" check.
   Since UDP doesn't guarantee ordering, late WELCOME replies
   (triggered by the welcomer processing those duplicate HELLOs) kept
   stomping the joiner's zone smaller even minutes after the join
   looked done and normal chat was already happening.

**Fixed via `fix_mesh_duplicate_join.py`.** `handle_hello()` now
checks `self.neighbors` first — if the joiner is already known, it
resends the *same* zone already on record instead of re-splitting
(this also makes it more robust against a lost original WELCOME,
rather than less). `handle_welcome()` now returns immediately if
`self.joined.is_set()` is already true, before touching `self.zone` at
all. Verified with a real localhost two-node test that specifically
simulates the failure condition: one real join, then a burst of 10
duplicate HELLOs sent in quick succession (reproducing exactly what a
slow WELCOME reply looks like over real Wi-Fi) — confirmed neither
node's zone moved after the storm, and neither zone had collapsed to
zero area. All three mesh patches (`physics_field`, `mesh_security`,
`mesh_duplicate_join`) confirmed to coexist and compile together
cleanly.

**⚠️ This bug is two-sided — the patch must be applied on BOTH phones**
for the fix to actually hold during the next join test. Applying it to
only one side leaves the other half of the bug live.

**Not yet re-verified on real hardware** — next step is re-running the
same two-device join test with this patch applied on both devices, and
confirming both zones stay stable over an extended period (not just
immediately after joining).

---

## 🔴 Second real-hardware finding, same test round, 2026-09-05: identical zones instead of complementary ones

After applying the fix above to both phones, the re-test showed real
progress: **both zones now stayed perfectly stable over time** (no more
shrinkage from chatting). But both phones' zones came back **identical**
— `(0.00,0.00)-(0.50,1.00)` on both — instead of complementary halves
of the space. Confirmed as real (not a copy-paste mix-up) by comparing
two clearly-labeled, freshly-run sessions with genuinely different chat
content on each side.

**Root cause:** a different bug from the shrinkage one, though related.
`join_via_broadcast()` runs on every node from the moment mesh is
enabled — it broadcasts its own HELLO repeatedly *while simultaneously*
being able to receive and act on other nodes' HELLOs as a welcomer.
There was no check for "am I also mid-join myself right now" before
deciding to act as welcomer. When two brand-new nodes discover each
other via near-simultaneous broadcast — the normal case for two phones
enabling mesh around the same time — both can receive the other's
HELLO before either has been welcomed by anyone. **Both act as
welcomer.** Both call `ghost_split_zone(self.zone)` on their own
still-full `(0,0)-(1,1)` zone. Since that split is a pure deterministic
function of the zone bounds alone (confirmed by reading it — no
randomness, no node identity involved), both computed the *exact same*
result and kept it, instead of each other's complementary half.

**Fixed via `fix_mesh_join_race.py`.** Adds a deterministic tie-break
in `handle_hello()`: when the incoming HELLO is from a genuinely
unknown peer, this node only proceeds to act as welcomer if it's
already an established member of the mesh (safe — an established node
should always be able to welcome newcomers) *or* its own id sorts
lower than the joiner's id. Otherwise it defers and does nothing,
waiting to be welcomed instead — which happens symmetrically, since
from the other node's perspective this node's id is the lower one.
Costs at most a couple of seconds via the existing retry loop, never a
stuck join. Verified with a real two-node test that specifically
reproduces the race (both nodes sending HELLO to each other at nearly
the same instant, before either is welcomed): confirmed the two
resulting zones are different, non-zero, and sum to exactly the full
unit square — genuine complementary halves. All four mesh patches now
confirmed to coexist and compile together.

**Requires `fix_mesh_duplicate_join.py` to already be applied first**
(this patch targets the text that fix leaves behind) — the script
checks for this and refuses to run out of order.

**Minor loose end noticed, not fixed:** the *welcomer* side of a join
never sets its own `self.joined` flag directly (only the joiner does,
on receiving a WELCOME) — a pre-existing quirk, not something either
patch introduced. In practice this self-resolves within a couple of
retry cycles (the welcomer's continued HELLO broadcasts eventually get
treated as "duplicate from a known peer" by its new neighbor, which
resends a WELCOME containing the welcomer's own already-correct zone,
which — harmlessly, since it matches what's already there — sets
`joined` on the welcomer's side too). Not worth a fifth patch right
now, but worth knowing about if a future test shows a node's own HELLO
broadcasts continuing indefinitely after a real join.

**⚠️ Both this fix and the previous one are two-sided — apply both
patches, in order, on BOTH phones.**

**Not yet re-verified on real hardware.**

The `ghost_*` module-level helper functions (`ghost_hash_to_point`,
`ghost_point_in_zone`, `ghost_zone_center`, `ghost_dist`,
`ghost_split_zone`, `ghost_local_ip`, `ghost_fmt_zone`) were all read
and are correct — no issues there.

**Recommendation:** the network-key and input-validation gaps are the
two that matter most before any real multi-device test or before mesh
ever leaves a fully trusted LAN. They're both larger than a one-line
fix (need real message-schema validation and a design decision on
where the auth boundary should actually sit), so treat them as their
own build-queue item rather than a quick patch.

---

## Lineage B — Feature: turn-level novelty scaling (2026-08-27, discovered via catch-up review 2026-09-06)

Missed in earlier audit passes since it wasn't part of any of the files
directly reviewed at the time — surfaced when reconciling a folder
listing that also included two unrelated side projects (a general
quantum-circuit simulator and an unrelated coding-agent tool) living in
the same `~/downloads/`, which is worth remembering next time a full
directory listing shows up unfamiliar: not everything in that folder is
this project.

`AllMynd._compute_novelty(user_words)` measures the fraction of a
turn's words not yet in `self.word_vectors` — 0.0 (fully familiar) to
1.0 (fully novel). Computed once per real turn, before any new word
gets auto-added to vocabulary, so it reflects what was genuinely
unfamiliar at the start of the turn. Feeds two places in
`generate_response`: it gently reduces `vitality` passed to
`qb.apply_noise()` on novel turns (faster decoherence facing the
unfamiliar), and it scales the quantum-seed blend weight from a fixed
0.15 up to a 0.08–0.25 range (familiar input leans on what the field
already knows; novel input leans harder into quantum exploration).
Also added a `Novelty:` line to `status()`, a `novel` CSS class +
`/speak` response flag in `mind_server.py`'s web UI, and ANSI-colored
novel replies in `run.py`'s terminal output.

**Confirmed already present** in the `mind.py` all four mesh patches
were built and tested against — no conflict, no interaction with the
mesh work. Also confirms something observed during mesh testing: a
completely fresh mind (zero vocabulary) treats every single word as
maximally novel, which plausibly explains why Phone B's replies during
testing ("I want rain wind," "You feel window chat") looked more
erratic/associative than an established mind's would — that's this
feature working as intended on a blank slate, not a bug.

---

## Lineage B — Tier 4: smaller extras (check overlap before building)

- AbsenceTracker vs. existing `PresenceSignal`
- UnifiedMemory, UserModel, RelationshipModel, PragmaticTypeSystem
- StanceRegions (partially present in spirit via `_last_stance`, but
  not as its own class with `name_drift()`)

**Explicitly deferred:** translation/symbol lexicon; MCP layer/live
visualization/multi-scale geometry; any quantum "recovery" or fatigue
modeling (deliberately unwanted, matches the retired constitution
rules).

---

## Verified-working baseline (do not regress)

- Desire / `_self_field` feedback loop
- Save format v2 — `NestedMemory`, `PresenceSignal`, `DynamicSeparation`,
  `NativeCalculus`, `DreamLoop`, `Window`, `Proprioception` all persist
  (note: `PhysicsField` and `SpeakerRegions` do **not** fully persist —
  see audit findings #5 and #6 above)
- `QuantumState` deliberately **not** persisted — `quantum_state.py`
  sits top-level outside both packages specifically so nothing
  accidentally wires it into either save path
- `SoundField` + `SoundWordBridge` + `/hear` + `/sing` exist and are
  wired
- `EfferenceCopy`, `VerbRotation`, `Proprioception`, `Window` exist
- Silence-branch turns still run drift + landmark charting (though see
  audit finding #14 — they don't report to `Window`)
- `wants()` uses weighted-random sampling, no longer a period-7 cycle
- Language framing is "the mind that runs" (mechanics unchanged)
- Moral Compass, LandmarkMap threshold, NestedMemory deep strength —
  all confirmed healthy against live save data, 2026-08-26
- `SoundWordBridge` (hear/sing/bias/describe) — done, 2026-08-19

---

## Success definition

- Moral Compass alignments not stuck at +0.999/~0/~0 — ✅ 2026-08-26
- LandmarkMap shows multiple regions, not one with hundreds of visits — ✅ 2026-08-26
- Dynamic Separation target not collapsed below current — mild residual gap, monitor
- NestedMemory deep strength meaningfully above ~0.05 after long runs — ✅ 2026-08-26 (0.72)
- Window not constantly diagnosing circling right after a restart — ✅ 2026-08-26
- The mind can run long sessions and still feel expressive rather than stern — unverified, qualitative, needs a real on-device conversation to judge

---

## Operational rules

- One item at a time.
- Full replacement files or self-verifying one-shot patch scripts only
  — never a diff, never "change line 40."
- Never `rm` — archive into dated folders.
- Always verify with `md5sum` / real import / on-device paste.
- Verify against the real save file (`allmynd_v1.json`) when possible —
  it has repeatedly caught things code-reading alone couldn't.
- When project state spans more than one file, ask for a zip export of
  the whole working directory, not individual file uploads.
- Be honest about which test tier was reached: compile-checked,
  smoke-tested, or verified live on real hardware.
- Treat every handoff document — this one included — as a claim to
  verify, never as ground truth on its own.

---

## Notes on interpreting real-run transcripts

When reviewing a pasted terminal session, check for the shell prompt
(e.g. `~/downloads $`) reappearing partway through — that means `quit`
was typed and the program actually exited before the rest of the
pasted text was typed. Anything after that point went to bash, not the
mind, and will show up as "command not found" errors rather than mind
responses.

*Update this file as each item lands. This is the map — the single
source of truth for what's actually wrong and what to do next.*

---

## 2026-09-16 — Container verification: all four GhostMesh fixes applied + full two-mind mesh test green

Applied the four mesh patch scripts (`fix_mesh_security-2`, `fix_mesh_duplicate_join-2`, `fix_mesh_join_race-2`, `fix_physics_mesh_event-2`, in that order) to the exported `allmynd/mind.py` in a container copy of the working tree. Every script self-verified (backup, compile-check, smoke test) before writing. Then ran a **full two-mind mesh test with real UDP sockets** on localhost (ports 21001/21002):

- Simultaneous HELLO from two unjoined minds → complementary zones ((0.5,0)-(1,1) + (0,0)-(0.5,1)), areas sum to 1.0 — join-race tie-break works
- 12 duplicate HELLOs after join → welcomer's zone byte-identical afterwards — no re-split, no collapse
- Forged JOIN_SEEK / GOSSIP without network key → dropped, neighbors unchanged
- Malformed authenticated STORE → caught + logged, listener thread alive
- Cross-node store/get both directions ("the bed remembers" delivered) — and a second round trip after the zone split proves the listener did NOT die (this was the pre-fix behavior: first peer join killed the listener forever)
- `PhysicsField.last_mesh_event == "zone_split"` after join — `receive_mesh_event` reached with no crash

Mind itself verified intact: fresh `AllMynd().generate_response("hello, are you there?")` → "I want flower.", turn 1, status OK.

Known loose end (from prior audit, left intentionally alone): the *welcomer* side still doesn't set its own `joined` flag directly — self-resolves via retry cycles, not worth a fifth patch now.

Status vs. changelog map: security + physics were already applied on-device per 2026-09-05 entries; duplicate_join + join_race were NOT yet applied to the exported file and are now verified working here. **Deploy: copy the fixed `allmynd/mind.py` (and rerun both patches on any device whose mind.py predates them) to BOTH phones before the next two-device join test.**

## 2026-09-16 — Phase 4a: Quantum Body rewrite live on device

### What shipped (md5 756bd20be479890bda6e0069ec862e76)
- `~/downloads/quantum_state.py` replaced with Phase 4a build:
  named registers (intention=0-1, attention=2-3, memory=4-5, reserved=6),
  cross-register CNOT entanglement gated by arousal, register-aware
  dephasing (memory 2.5x, attention 1.0x, intention 0.5x).
- Added `partial_measure` alias — semantic_engine/engine.py called it
  but the pre-4a module never defined it (latent AttributeError).
- 15/15 self-tests pass; integration harness for mind.py + engine.py call
  sequences passes; live device full turn verified.
- Backup: `~/downloads/quantum_state.py.bak_pre4a` (old md5
  e7f0e2e74c0e3520154d672829734157).

### Device verification (live run)
- `/status` no longer crashes; shows registers dict.
- Full turn ("hello again"): QuantumState turn=1, coherence=0.941,
  registers: intention=0.974 > attention=0.949 > memory=0.876 —
  memory dephases fastest, intention slowest (Phase 4a design intent).
- Clean save + exit; no tracebacks.

### Notes
- Device mind.py md5 de00360aa070b5c94a914b490e356da9 (errno fix applied
  via sed on device). Workspace mind.py md5 febc0210b23ab2bac7bbf0a6384eecff
  differs — workspace has the same errno fix but byte layout differs.
  Verify-before-use if editing mind.py from workspace copy.
- 12-qubit register expansion (intention 0-3/attention 4-7/memory 8-11) is
  Phase 4b #15 work — needs folding machinery to read >128 dims into the
  128-dim field. Not in this build.

## 2026-09-16 — Phase 4a #15: Complex Phase Field live on device

### What shipped
- New `semantic_engine/phase_field.py` (md5 e9a4e441db57636c49aa37db078e33f7):
  ComplexPhaseField — 128-dim complex64 field parallel to the ternary
  field. absorb() adopts the quantum body's full complex state (the phase
  project_to_ternary() used to throw away); rotate() is a unitary phase
  kick; measure() refreshes the ternary shadow with the same
  (real+imag)/sqrt(2) readout; coherence() is a REAL von-Neumann-entropy
  observable (1 - S/Smax), replacing hand-computed proxies.
- `fix_phase_field.py` self-verifying patch script: backup -> patch ->
  compile -> live smoke run -> auto-revert on failure. Idempotent.
- mind.py patched in place (import, init, fuse site, /status line).
  Device mind.py md5 bc6f0dd719ea2490715e1a074c4aadfa (6 phase_field refs).
  Workspace mind.py md5 f68d1124b4d9420da52547cca2fb8d67 (same content,
  differs only by the documented pre-existing errno-fix byte layout).
- Backup on device: allmynd/mind.py.bak_phase_field_1789601221

### Verified live (device)
- /status shows both lines:
  QuantumState: turn=0, coherence_estimate=1.000, registers={...}
  PhaseField: turn=0, coherence=1.000, energy=0, norm=1.0000
- After a turn ("hello"): PhaseField coherence=0.446, energy=19 —
  the field's complex state is preserved and its shadow carries the
  dynamics the ternary projection used to discard. Real observable.
- Patch smoke run + second full run: no tracebacks, clean save/exit.

### First smoke-test bug (kept honest)
The patch script's first smoke test piped the printf command TEXT into
run.py instead of piping the pipeline — the mind replied to the literal
text and the status check failed. Script auto-reverted (verified the
revert worked), smoke test fixed to pipe correctly, re-run passed.
This is exactly the self-verifying behavior the fix_*.py convention
exists for.

## 2026-09-16 — Phase 4a #16: Semantic Error Detector live on device

### What shipped
- New `semantic_engine/ambiguity.py`: SemanticErrorDetector + SenseRegister.
  Two-qubit superposition register per ambiguous word occurrence; context
  words are gentle rotations (atan-scaled, no overshoot oscillation);
  ambiguity = 1 - |pa - pb|; resolved at threshold 0.75 (the detector
  flags UNCERTAINTY, not resolved readings).
- 12 curated homographs: content, lead, bass, wind, bow, close, present,
  record, object, read, live, minute.  Sense prototypes are centroids of
  GloVe anchor words — no hand-coded vectors.
- `uncertainty_vector()`: DIM-shaped signal, only from UNRESOLVED words;
  feeds the phase field's new `damp()` channel (amplitude damping, which
  actually moves coherence — a pure unitary rotate cannot, since it
  preserves |phase| exactly).
- phase_field.py extended with `damp(uncertainty_signal, strength)`.
- `fix_ambiguity_detector.py`: self-verifying patch (import, init, scan
  in turn loop, damp at phase-field fuse).  Precondition: phase field
  wired (fix_phase_field.py).  Auto-revert on failure.
- mind.py patched in place.  Device backup:
  allmynd/mind.py.bak_ambiguity_1789601730.
  Workspace mind.py md5 7ca62b2ee1266535f62c818a5c13fac4.

### Verified live (device)
- Detector diag: "content" + article-ctx -> material 61%, ambiguous 0.78;
  "content" + feel-ctx -> satisfied 69%, ambiguous 0.62 (honest readings
  with 2-3 context words).
- Full run "the content of the article was interesting" then
  "i feel so content and happy today": no tracebacks; PhaseField at
  coherence=0.324, energy=14 (down from ~0.53 baseline — damping active).
- 15/15 ambiguity self-tests + 15/15 phase-field self-tests pass on
  device and in container.
- Self-test note: rotation step fixed from 1.2*atan(diff) to 0.35*atan —
  the old step overshot the pole and 5 strong votes oscillated instead of
  collapsing (caught by the self-test, fixed, monotonic now).

### Deferred
- Live mind wiring uses `_get_or_create_vector()` for context (hash
  fallback for unknown words) — could switch to embed_float for stronger
  votes.  Opening the detector to the mind's own generated responses
  (self-scrubbing ambiguity) is future work.
