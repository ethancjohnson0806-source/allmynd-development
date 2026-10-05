# AllMyND Provenance Status

Updated 2026-10-05.

## Current source relationship

The active runtime quantum path is:

```text
allmynd.mind.AllMynd
  -> semantic_engine.quantum.QuantumState
    -> semantic_engine.lqe_core.statevector.StatevectorSim
```

The root `quantum_state.py` is a legacy/standalone Phase 4a implementation and is not imported by the current runtime path. It remains in the repository as historical material until its final disposition is decided.

## Recovered patch history

The original patch scripts are preserved in the separate private development workspace. The current source also contains embedded comments and markers naming many of the applied fixes.

The latest reconstructed patch order recorded by the current AllMyND snapshot is:

1. `fix_noise_modes.py`
2. `fix_log_serialize.py`
3. `fix_memory_cap.py`
4. `fix_real_coherence.py`
5. `fix_save_safety.py`
6. `fix_repeat_bias.py`
7. `fix_reflective_voice.py`

`fix_mind_log.py` was already present before that sequence.

## Phase 0 decisions

- `mind.py` remains a monolith for now; splitting it is deferred to Phase 2.
- LSB migration must wait until the statevector/wrapper boundary tests are committed.
- The vendored LQE statevector is the current low-level execution core.
- Patch scripts are provenance artifacts and must not be run blindly against a changed source tree.
- Runtime state, saves, logs, vessels, and personal data must remain uncommitted.

## Verification boundary

Passing the current smoke tests establishes importability and basic execution only. It does not establish scientific validity, consciousness, general intelligence, production readiness, or hardware equivalence.

The next engineering milestone is deterministic replay metadata and committed quantum seam tests before changing qubit ordering.
