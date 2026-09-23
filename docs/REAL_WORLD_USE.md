# Real-world use guide

ALL MY'ND is easiest to use as a private, local experiment on an Android phone running Termux. The project is intentionally honest about its status: it can run a deterministic, stateful generative pipeline, but it is not a verified conscious system, general intelligence, or production service.

## First run

From the repository root, create a virtual environment where supported by the device, install NumPy, and start the terminal runner:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python run.py
```

Use `/status` to inspect the current state, `/save` to checkpoint, `/dream` or `/breath` for explicit internal activity, and `/quit` for a graceful final save. The live `allmynd_v1.json` file is personal runtime state; keep it backed up privately and never commit it.

## Browser use on the phone

Run `python mind_server.py` and open `http://127.0.0.1:8080` in the phone’s browser. The browser interface is local-only by default. It provides conversation, teaching, save, dream, status, and explicit sound controls when Termux:API is installed.

Do not use a public GitHub Pages site as the runtime. GitHub hosts the source and documentation; the mind’s state should remain on the device that owns it.

## What to expect

Responses are generated from the current field and vocabulary, so they can be surprising, repetitive, or semantically weak. Teaching adds words and a memory entry; it does not create a fact-checked knowledge base. The changelog records known persistence gaps and experimental subsystems. Treat outputs as research observations, not professional advice or authoritative facts.

## Backups

Make private, offline backups of `allmynd_v1.json` and any vessel exports before applying historical fix scripts or upgrading the runtime:

```bash
mkdir -p "$HOME/allmynd-backups"
cp allmynd_v1.json "$HOME/allmynd-backups/allmynd_v1-$(date +%Y%m%d-%H%M%S).json"
```

Never put those backups in the public repository. The repository’s ignore rules protect the common filenames, but a backup with a new extension or directory still needs deliberate handling.

## Getting help

When asking for help, provide the exact command, Python version, operating system/Termux version, and complete error output. Do not upload save files, tokens, audio, or personal conversation history. A minimal reproduction using a fresh temporary save is safer and usually easier to debug.

For bridge usage, read [`TERMUX_BRIDGE.md`](TERMUX_BRIDGE.md) first. The recommended remote path is an SSH tunnel to a loopback-only bridge, not an open phone port.
