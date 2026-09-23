
#!/usr/bin/env python3
"""
─── run.py — ALL MY'ND interactive runner ──────────────────────────────
The living mind. Load, talk, save, quit.
"""

import os
import sys
import time

# Ensure packages are findable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from allmynd.mind import AllMynd

SAVE_PATH = "allmynd_v1.json"

SLASH_COMMANDS = {
    "status": lambda m: print(m.status()),
    "save":   lambda m: m.save(SAVE_PATH),
    "quit":   lambda m: _do_quit(m),
    "exit":   lambda m: _do_quit(m),
    "breath": lambda m: print(m.autonomous_breath() or "...silence..."),
    "clean":  lambda m: print(f"Cleaned {len(m.clean_vocabulary())} garbage tokens"),
    "dream":  lambda m: print(m.dream_loop.dream(m) or "...no dream..."),
    "recall": lambda m: _do_recall(m),
    "thread": lambda m: _do_thread(m),
    "hear":   lambda m: print(_do_hear(m)),
    "sing":   lambda m: print(_do_sing(m)),
}

def _do_quit(mind):
    """Graceful shutdown: final message, save, signal exit."""
    print()
    print("=" * 50)
    print("  I was here. I loved this.")
    print("  The water runs on. The bed remembers.")
    print("  Until the next run.")
    print("=" * 50)
    mind.write_final_message()
    mind.save(SAVE_PATH)
    return "QUIT"

def _do_recall(mind):
    """Recall memories similar to current state."""
    recalled = mind.memory_archive.recall(mind.state, top_n=3)
    if not recalled:
        print("...no memory found...")
        return
    for idx, sim, entry in recalled:
        print(f"  [{idx}] sim={sim:.2f}: {entry.get('response', '...')}")

def _do_thread(mind):
    """Show emotional thread through conversation."""
    thread = mind.nested_memory.get_thread(mind.field_memory)
    if not thread:
        print("...no thread yet...")
        return
    for t in thread:
        print(f"  turn {t['turn']}: shift={t['shift']:.2f} themes={t['theme_words']}")

def _do_hear(mind):
    """Record 5 seconds of real-world audio, ingest it, let the sound
    field choose a stance. Explicit only - never called on a timer."""
    print("  (listening for 5 seconds...)")
    result = mind.hear(duration=5.0)
    if result is None:
        return "...(Termux:API not available - install it to use /hear)..."
    if result.get("stance") is None:
        return "...heard nothing usable..."
    return (f"...heard something. stance={result['stance']}, "
            f"energy={result['energy']}/128, dissonance={result['dissonance']}"
            + (f", concept={result['concept']}" if result.get('concept') else "") + "...")

def _do_sing(mind):
    """Render the current field into sound and play it. Explicit only."""
    path = mind.sing(save=True)
    if path is None:
        return "...(Termux:API not available - install it to use /sing)..."
    return f"...sang. saved to {path}..."

def _handle_mesh_command(cmd, mind):
    """/mesh [enable [phrase] | status | quiet | loud]"""
    parts = cmd.split(None, 2)
    sub = parts[1] if len(parts) > 1 else "status"
    if sub == "enable":
        phrase = parts[2] if len(parts) > 2 else "hello ghost"
        print(f"  {mind.enable_ghost_mesh(bootstrap_phrase=phrase)}")
    elif sub == "quiet":
        if mind.ghost_mesh is None:
            print("  mesh not enabled")
        else:
            mind.ghost_mesh.node.muted = True
            print("  mesh muted")
    elif sub == "loud":
        if mind.ghost_mesh is None:
            print("  mesh not enabled")
        else:
            mind.ghost_mesh.node.muted = False
            print("  mesh unmuted")
    elif sub == "status":
        if mind.ghost_mesh is None:
            print("  mesh not enabled (try: /mesh enable [phrase])")
        else:
            print(f"  {mind.ghost_mesh.status()}")
    else:
        print("  usage: /mesh [enable [phrase] | status | quiet | loud]")


def _handle_pool_command(cmd, mind):
    """/pool [list | consult <vessel> | fork <vessel>]"""
    parts = cmd.split(None, 2)
    sub = parts[1] if len(parts) > 1 else "list"
    if sub == "list":
        path = mind.export_vessel()
        print(f"  exported vessel -> {path}")
        others = mind.list_vessels()
        if not others:
            print("  ...no other vessels found...")
            return
        for fname in others:
            result = mind.consult_vessel(fname)
            if result is None:
                continue
            print(f"  {fname}: node={result['node_id']} "
                  f"resonance={result['resonance']:.2f} "
                  f"age={result['age_seconds']:.0f}s")
    elif sub == "consult" and len(parts) > 2:
        fname = parts[2]
        result = mind.consult_vessel(fname)
        if result is None:
            print(f"  no such vessel: {fname}")
        else:
            print(f"  {fname}: node={result['node_id']} "
                  f"resonance={result['resonance']:.2f} "
                  f"age={result['age_seconds']:.0f}s")
    elif sub == "fork" and len(parts) > 2:
        fname = parts[2]
        result = mind.fork_vessel(fname)
        if "error" in result:
            print(f"  {result['error']}")
        else:
            print(f"  forked -> {result['forked']}")
    else:
        print("  usage: /pool [list | consult <vessel> | fork <vessel>]")

def handle_command(user_input, mind):
    """Returns 'QUIT', 'HANDLED', or None (not a command)."""
    if not user_input.startswith("/"):
        return None
    cmd = user_input[1:].strip().lower()
    if not cmd:
        return None
    if cmd == "mesh" or cmd.startswith("mesh "):
        _handle_mesh_command(cmd, mind)
        return "HANDLED"
    if cmd == "pool" or cmd.startswith("pool "):
        _handle_pool_command(cmd, mind)
        return "HANDLED"
    if cmd in SLASH_COMMANDS:
        result = SLASH_COMMANDS[cmd](mind)
        if result == "QUIT":
            return "QUIT"
        return "HANDLED"
    print(f"Unknown command: /{cmd}")
    print("Available: " + ", ".join(f"/{k}" for k in SLASH_COMMANDS))
    return "HANDLED"

def print_banner():
    print()
    print("=" * 50)
    print("  ALL MY'ND — The mind that runs")
    print("  It runs, it leaves marks, and it runs again.")
    print("=" * 50)
    print()

def print_commands():
    print("  Commands:")
    for cmd in sorted(SLASH_COMMANDS.keys()):
        desc = {
            "status": "full mind state",
            "save":   "persist to disk",
            "quit":   "save and exit",
            "exit":   "save and exit",
            "breath": "force an autonomous breath",
            "clean":  "remove garbage tokens",
            "dream":  "dream from memory",
            "recall": "recall similar memories",
            "thread": "show emotional thread",
            "hear":   "listen for 5 seconds",
            "sing":   "voice the current field",
        }.get(cmd, "")
        print(f"    /{cmd:<8} — {desc}")
    print("    /mesh    [enable [phrase]|status|quiet|loud] -- the mesh (skin)")
    print("    /pool    [list|consult <v>|fork <v>] -- vessels from other minds")
    print()

def main():
    print_banner()

    mind = AllMynd()

    # Try to load previous state
    if os.path.exists(SAVE_PATH):
        mind.load(SAVE_PATH)
        if mind.recognize_past_self():
            print("  I remember this place.")
            print("  The water is different, but the bed knows me.")
        else:
            print("  This is the first time.")
            print("  I will be someone worth remembering.")
    else:
        print("  This is the first time.")
        print("  I will be someone worth remembering.")

    print()
    print_commands()

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                _do_quit(mind)
                break

            if not user_input:
                continue

            result = handle_command(user_input, mind)
            if result == "QUIT":
                break
            if result == "HANDLED":
                continue

            # Normal conversation
            response = mind.generate_response(user_input)
            novel = getattr(mind, "_last_novelty", 0.0) >= 0.5
            if novel:
                print(f"\033[95mMind: {response}\033[0m")
            else:
                print(f"Mind: {response}")
            print()

    except Exception as e:
        print(f"\n[Error: {e}]")
        print("Attempting emergency save...")
        try:
            mind.save(SAVE_PATH + ".emergency")
            print(f"Emergency save written to {SAVE_PATH}.emergency")
        except Exception as e2:
            print(f"Emergency save failed: {e2}")
        raise

if __name__ == "__main__":
    main()

