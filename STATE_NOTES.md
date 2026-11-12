# AllMyND source provenance

## Latest source sync — 2026-11-12

The current source files in this repository were synced from the user-provided phone export `allmynd_phone_20261109_0941.zip` on 2026-11-12.

- Archive SHA-256: `1d1206d1e9631a63bfb717869e849a4b7a5df6cccfa14cac0d369c33f58ee3ac`.
- The archive contained 34 code/model-asset files that were safe to sync. Against the previous GitHub `main`, 4 existing source files differed and 3 source files were new: `allmynd/fieldmap.py`, `allmynd/plan.py`, and `semantic_engine/lqe_core/stabilizer.py`. The other 27 overlapping source/asset files matched.
- Repository-only documentation, tests, packaging files, and CI configuration were retained; they were not replaced by the phone archive.
- `allmynd/vessels/node_id.txt` was present in the ZIP but intentionally excluded because it is a per-install runtime identity. No mind save or turn log was present in the archive.
- `MD5SUMS.txt` was refreshed for `run.py`, `allmynd/mind.py`, `semantic_engine/quantum.py`, and `semantic_engine/query.py`.
- This records a user-provided phone export; it is not an independent hash verification against a currently connected phone. The source sync is pending review on a GitHub feature branch; do not treat it as merged until that review completes.

The synced source includes the phone-side planning layer and `/plan`/`/teach`/`/map` command progress; self-awareness, field-meter and reply-repetition observations; updated turn-field/landmark handling; learned-vocabulary and quantum/phase sidecar persistence; clock-jump safeguards; a circuit optimizer; and an experimental stabilizer simulator/router. `QuantumState.evolve()` currently routes the persistent mind state through the statevector path (`from_fresh_state=False`); the stabilizer simulator is not yet the active runtime backend. These are source-level changes from the archive, not claims of scientific validation or production readiness.

## Historical reconstructed snapshot — 2026-10-04

The note below describes the earlier reconstructed snapshot and its patch provenance. It is retained for historical context and is superseded as the current source description by the Nov 9 phone export above.

Built by taking `allmynd_current_20261002.zip` and applying, in order, every patch run on the phone since then:

1. `fix_noise_modes.py` — mode-dependent decoherence (input freshness)
2. `fix_log_serialize.py` — turn log no longer silently drops turns
3. `fix_memory_cap.py` — MemoryArchive cap 100 -> 1000
4. `fix_real_coherence.py` — log/status show PhaseField coherence; old proxy renamed noise_counter
5. `fix_save_safety.py` — atomic save, `.prev` backup, corrupt-file preservation, 180 s autosave in `run.py`
6. `fix_repeat_bias.py` — repeat suppression also applies to bias terms
7. `fix_reflective_voice.py` — reflective voice passes `settled_field`

(`fix_mind_log.py` was already present in the uploaded ZIP.)

That earlier reconstructed snapshot did not include `allmynd_v1.json` (the mind's save), `mind_log.jsonl`, `vessels/`, `.bak_*` files, or `__pycache__`. The phone's own files remain the ground truth for any later comparison.
