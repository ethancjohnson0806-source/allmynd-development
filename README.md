# ALL MY'ND

A rule-based generative mind that runs locally and is designed for private, offline-first use.

## What it is

ALL MY'ND is a research system for exploring a persistent computational mind. It combines:

- a 128-dimensional ternary semantic field;
- layered memory across short-, medium-, slow-, and deep-timescale state;
- speaker regions and identity separation;
- presence and engagement signals;
- mood, desire, values, and reflective processing;
- a statevector-based quantum body used to perturb and shape the semantic field;
- optional phase-field, ambiguity, entanglement-memory, audio, and GhostMesh subsystems;
- local persistence and terminal/browser interfaces.

The generation process is rule-based. It is not an LLM, does not call a cloud model, and does not require an API key. The semantic field settles first; candidate words are then selected according to the settled state and the mind's current context.

The central design boundary is:

> The math layer does not decide what it wants. The mind layer owns identity, memory, values, desire, and action.

## Current quantum path

The active runtime path is:

```text
allmynd.mind.AllMynd
  -> semantic_engine.quantum.QuantumState
    -> semantic_engine.lqe_core.statevector.StatevectorSim
```

The active AllMyND body is currently 12 qubits, organized into intention, attention, and memory registers. The vendored LQE statevector supplies gate execution; the AllMyND wrapper owns registers, noise profiles, partial measurement, field bias, and projection into the ternary field.

The root `quantum_state.py` is a legacy standalone implementation retained for historical comparison. It is not imported by the current mind runtime.

## Status

This is a research artifact, not a finished agent or production system. It runs and has been tested through source-level smoke checks, but passing those checks does not establish scientific validity, consciousness, general intelligence, or production readiness.

The current supplied snapshot includes the latest merged AllMyND fixes recorded in `STATE_NOTES.md`, including noise modes, logging serialization, memory capacity, coherence reporting, save safety, repeat-bias suppression, and reflective voice behavior.

## Quick start

Python 3.10+ and NumPy are required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python run.py
```

The terminal runner persists state to `allmynd_v1.json`. Runtime state is private and should not be committed.

For the local browser interface:

```bash
python mind_server.py
```

Then open <http://127.0.0.1:8080>.

## Development checks

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```

The repository also retains historical fix scripts. Review them before running; they are provenance artifacts and are not executed automatically.

## Security and local-runtime boundary

1. Keep `mind_server.py` bound to `127.0.0.1` unless a separately reviewed deployment adds authentication and transport security.
2. Treat `allmynd_v1.json`, logs, vessel data, audio, and exported runtime state as private.
3. Never commit API keys, private saves, personal data, or recordings.
4. Review historical patch scripts before running them against a changed source tree.
5. Keep GhostMesh disabled unless you intentionally want network communication; inspect its security settings before using it beyond a trusted local network.

See [`SECURITY.md`](SECURITY.md) for the security boundary.

## Provenance

`STATE_NOTES.md` records the snapshot reconstruction and subsequent reviewed changes. `MD5SUMS.txt` preserves the original baseline checksums; later clock-resilience edits are documented in `STATE_NOTES.md` and intentionally do not match that baseline.

`semantic_engine/lqe_core/statevector.py` is vendored from the [Legitimate Quantum Engine](https://github.com/ethancjohnson0806-source/Legitimate-Quantum-Engine) project. If that upstream file changes, re-vendor it as a whole after comparing behavior and tests rather than hand-editing drift.

## License

MIT. See [`LICENSE`](LICENSE).
