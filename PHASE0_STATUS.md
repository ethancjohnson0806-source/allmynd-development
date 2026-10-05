# Phase 0 Handoff

## What this project is

AllMyND is the mind layer: identity, memory, values, desire, presence, language, and persistence.

LQE is the execution substrate: statevectors, circuits, optimization, backend contracts, replay, and compilation.

The emerging cognitive compiler belongs in a separate private workspace so experimental compiler work does not destabilize the public AllMyND runtime.

## Current active boundary

```text
AllMyND mind
  -> semantic_engine.quantum.QuantumState
    -> vendored LQE StatevectorSim
```

The active snapshot uses a 12-qubit AllMyND body and a vendored LQE statevector. The root `quantum_state.py` is legacy/standalone and is not on the active import path.

## Before changing qubit ordering

1. Pin the ownership of the three quantum homes.
2. Preserve patch provenance.
3. Add committed baseline tests for measurement/reset alignment, wrapper behavior, and replay metadata.
4. Then implement deterministic RNG/replay.
5. Only after that migrate to the explicit LSB convention.

## Scope boundary

The Phase 1 effort does not split `mind.py`. That refactor is deferred until the runtime contract is stable and seam tests can protect it.
