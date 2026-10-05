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
