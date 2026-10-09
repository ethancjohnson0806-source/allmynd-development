# AllMynd code snapshot, 2026-10-04 (RECONSTRUCTED, not copied from the phone)

Built by taking `allmynd_current_20261002.zip` and applying, in order, every
patch run on the phone since then:

1. fix_noise_modes.py       - mode-dependent decoherence (input freshness)
2. fix_log_serialize.py     - turn log no longer silently drops turns
3. fix_memory_cap.py        - MemoryArchive cap 100 -> 1000
4. fix_real_coherence.py    - log/status show PhaseField coherence; old proxy renamed noise_counter
5. fix_save_safety.py       - atomic save, .prev backup, corrupt-file preservation, 180 s autosave in run.py
6. fix_repeat_bias.py       - repeat suppression also applies to bias terms
7. fix_reflective_voice.py  - reflective voice passes settled_field

(fix_mind_log.py was already present in the uploaded zip.)

NOT included: allmynd_v1.json (the mind's save), mind_log.jsonl, vessels/,
.bak_* files, __pycache__.

The phone's own files are the truth. To check this snapshot matches the phone:
  cd ~/downloads && md5sum run.py allmynd/mind.py semantic_engine/quantum.py semantic_engine/query.py
and compare with MD5SUMS.txt in this zip.

## 2026-10-07 phone-snapshot comparison and clock-resilience port

The user supplied `allmynd_phone_20261007_1324.zip` for comparison. Its SHA-256
is `ddd7e450c522ce57d6439e6a309c4eda7105681e7de1dd8033ebd0fc05545ac4`.
The archive contained 31 files and passed `unzip -t`. It did not include a
runtime save, log, vessel, audio file, credential, or checksum manifest.

The phone snapshot was compared with the public checkout at `47f99b7`. The
runtime source differences were in `run.py`, `allmynd/mind.py`, and
`semantic_engine/query.py`. Only the reviewed clock-resilience behavior was
ported: monotonic elapsed-time autosave timing; non-negative FieldMemory and
phrase-decay ages; and absolute-age DreamLoop recency. Focused regressions were
added in `tests/test_clock_jump_resilience.py`.

No recovered `fix_*.py` script was run, and no files were copied wholesale.
The unrelated freshness-helper relocation and settle-intention expression
were not ported because the inspected differences did not establish a distinct
behavioral fix. The `MD5SUMS.txt` values remain the original baseline manifest;
they are not expected to match these subsequently edited files.
