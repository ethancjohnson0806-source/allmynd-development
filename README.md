# ALL MY'ND Development

This repository is the **active development workspace** for ALL MY'ND (also called Alien Mind in the historical lineage). It is a research and engineering codebase, not a finished autonomous agent or a production-secure network service.

## What is included

The archive preserves the split project as received:

- `allmynd/` contains the identity-facing runtime, bridge, and historical one-shot fix scripts.
- `semantic_engine/` contains the text, vector, ternary, settling, and optional quantum subsystems.
- `run.py` provides a terminal interface.
- `mind_server.py` provides a small local browser interface.
- `quantum_state.py` is retained as a top-level compatibility module.
- `ALLMYND_CHANGELOG.md` is the historical handoff and audit record.

The code is intentionally preserved rather than rewritten during repository creation. Existing behavior and open issues must be verified against the source before changes are made.

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

Then open <http://127.0.0.1:8080>. The server binds to localhost by default. Do not use `--host 0.0.0.0` on an untrusted network without adding authentication, authorization, transport security, request limits, and an explicit threat model.

## Development checks

Run the repository checks from the project root:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```

The smoke tests are intentionally small. Passing them means the package imports and its basic semantic pipeline executes; it does **not** establish scientific validity, consciousness, general intelligence, or production readiness.

## Security and bridge boundary

The initial development repository does not expose an MCP endpoint or a remote command-execution bridge. A Termux connection should be implemented as a narrow, authenticated IPC adapter around the `Bridge` API—not by exposing Python evaluation, shell commands, arbitrary file access, or the full `AllMynd` object.

Until that adapter exists and is reviewed:

1. Keep `mind_server.py` bound to `127.0.0.1`.
2. Treat `allmynd_v1.json` and any exported vessel files as private runtime state.
3. Never commit API keys, phone credentials, private save files, audio recordings, or generated personal data.
4. Review every historical `fix_*.py` script before running it; they are retained for provenance and are not automatically executed.
5. Prefer a local Unix-domain socket or an authenticated loopback client for development. Any phone-to-host transport should use an encrypted channel and a least-privilege allowlist.

See [`SECURITY.md`](SECURITY.md) for the reporting and hardening boundary.

## Project status

This is a build repository. The changelog contains both verified work and open findings, so it must not be treated as a release checklist. Before claiming a fix, add a focused regression test and record the verification method in the changelog.

## License

No license was supplied with the source archive. Until the project owner chooses and adds a license, the source remains available for repository collaboration but is not granted an open-source reuse license.
