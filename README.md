# ALL MY'ND

A rule-based generative mind that runs entirely offline on a phone.

## What it is

No LLM underneath. No cloud. No API calls. ALL MY'ND represents its internal state as a 128-dimensional ternary field — a sparse vector of `{-1, 0, 1}` — which a small quantum body (a real statevector simulator, 12 qubits, vendored from [Legitimate Quantum Engine](https://github.com/ethancjohnson0806-source/Legitimate-Quantum-Engine)) continuously perturbs through mood, tension, and decoherence.

Generation is word-by-word candidate selection scored against that field. It is not next-token prediction: the field settles first, then words are picked that resonate with where it settled. Memory is layered: a short-term `Window`, a four-timescale `NestedMemory`, and a `LandmarkMap` that charts regions the field has genuinely revisited. A `MoralCompass` self-calibrates its values from its own choices rather than holding fixed weights. `GhostMesh` allows separate instances to discover each other on a LAN and exchange resonance data.

The design rule, stated in the engine's own docstring: **the math layer never knows what it wants. Only the mind layer does.** Silence is a valid response when the field has nothing to say.

## Status

This is a research artifact, not a finished agent.

It runs. It has documented bugs. The changelog records both verified fixes and open findings, and must not be read as a release checklist. Passing the smoke tests means the package imports and its basic semantic pipeline executes — it does **not** establish scientific validity, consciousness, general intelligence, or production readiness.

## Quick start

Python 3.10+ and NumPy are required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python run.py
```

The terminal runner persists state to `allmynd_v1.json`. Runtime state is ignored by Git and should not be committed.

For the local browser interface:

```bash
python mind_server.py
```

Then open <http://127.0.0.1:8080>.

## Security and network boundary

The repository does not expose an MCP endpoint or a remote command-execution bridge. A Termux connection should be implemented as a narrow, authenticated IPC adapter around the `Bridge` API — not by exposing Python evaluation, shell commands, arbitrary file access, or the full `AllMynd` object.

Until that adapter exists and is reviewed:

1. Keep `mind_server.py` bound to `127.0.0.1`.
2. Treat `allmynd_v1.json` and any exported vessel files as private runtime state.
3. Never commit API keys, phone credentials, private save files, audio recordings, or generated personal data.
4. Review every historical `fix_*.py` script before running it; they are retained for provenance and are not automatically executed.

See [`SECURITY.md`](SECURITY.md) for the reporting and hardening boundary.

## Development checks

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```

## Provenance

`semantic_engine/lqe_core/statevector.py` is vendored from [Legitimate-Quantum-Engine](https://github.com/ethancjohnson0806-source/Legitimate-Quantum-Engine) (MIT). If that project's `statevector.py` changes upstream, re-vendor by replacing the file wholesale rather than hand-editing drift.

## License

MIT. See [`LICENSE`](LICENSE).
