#!/usr/bin/env python3
"""
─── allmynd.mind — the living mind ──────────────────────────────────────
The mind that runs.

Built on the semantic_engine (pure math, no identity) and the quantum
state (the run on the ternary bed). This layer adds:
  - Identity (SpeakerRegions, PresenceSignal, DynamicSeparation)
  - Memory (FieldMemory, NestedMemory, MemoryArchive)
  - Values (MoralCompass)
  - Desire (DesireVector)
  - Autonomy (DreamLoop, IntegratedLearningSystem)
  - The 8-phase generate_response()
  - Final message on death
  - Continuity marker inheritance

What was removed from the v13.6 original:
  - VitalityField.spend()/earn() — human resource-budget gate
  - Grammar mode scaling (full→pulse→wait) — the field decides complexity
  - is_scattered recovery silence — the field settles deeply, then speaks
  - Wait texture fallback — if nothing to say, says nothing
  - Constitution "no choose()" — the quantum run shapes the drift
  - "Metabolism before generation" — actions happen, consequences follow

The quantum state runs. The ternary field remembers.
"""

import os
import time
import math
import random
import json
import hashlib
import errno
import socket
import threading
import uuid
import numpy as np
from collections import defaultdict, deque, Counter
from dataclasses import dataclass, field as dataclass_field
from typing import Dict, List, Optional, Set, Any, Tuple

# Engine imports
from semantic_engine.core import (
    DIM, NORMALIZED_VECTOR_THRESHOLD,
    word_vector_ternary, phrase_vector_ternary,
    ternary_dot, weighted_ternary_dot,
    pack_ternary, unpack_ternary,
    TernaryFieldState, TernaryAssociativeMemory,
    NumpyEncoder
)
from semantic_engine.query import (
    Phrase, PhraseSystem, BigramSystem, Reflector,
    strip_punct, phrase_vector_float,
    VERB_WORDS, ADJ_WORDS, STRUCTURAL_WORDS, FUNCTION_WORDS,
    BAD_WORDS, COPULA_MAP, get_candidates_for_role
)
from semantic_engine.scaffold import SemanticScaffold
from semantic_engine.settle import ThePause, NativeCalculus, DynamicThreshold
from semantic_engine.interface import SemanticPacket, GrammarConfig
from semantic_engine.quantum import QuantumState
from semantic_engine.phase_field import ComplexPhaseField
from semantic_engine.ambiguity import SemanticErrorDetector
from semantic_engine.entanglement_memory import EntanglementMemory

from semantic_engine.embeddings import word_vector as _embed_word_vector
from semantic_engine.embeddings import has_vector as _has_embedding
from semantic_engine.embeddings import word_vector_ternary as _embed_word_vector_ternary

# ─── CONSTANTS ──────────────────────────────────────────────────────────

LEARNING_RATE = 0.04
MICRO_DAMPING = 0.15
MAX_PHRASES = 500
CRYSTALLIZATION_THRESHOLD = 1
MIN_CRYSTALLIZATION_RATING = 2.0
DECAY_RATE = 0.0003
TEMPERATURE = 0.35
AUTONOMY_INTERVAL = 5
HEARTBEAT_INTERVAL = 3

PUNCTUATION = '.,!?;:"\''

# ─── SOUND CONSTANTS ────────────────────────────────────────────────────
# Ported 2026-08-07 from alien_mind_v13_6-1.py's "v11.1 SOUND ADDITIONS".
# Real, working code in the monolith - never fabricated, just never
# carried across the semantic_engine/allmynd split. See BUILD_QUEUE.md.
SAMPLE_RATE = 16000
SOUND_DIM = DIM  # same ternary space as words - sound and language share one geometry
SOUND_N_BANDS = 8
SOUND_BAND_DIM = SOUND_DIM // SOUND_N_BANDS  # 16
SOUND_DURATION = 2.0  # seconds for synthesis
SOUND_MAX_FILES = 40  # rotate old auto-generated sound files rather than
                       # accumulating forever on limited phone storage

# BUG FIX vs. the original: TERMUX_AUDIO_DIR used to be a hardcoded
# absolute path (/data/data/com.termux/files/home/), which is exactly
# the kind of thing that caused real on-device path confusion earlier
# this project (~/storage/downloads not linking, find coming back empty).
# os.path.expanduser("~") resolves correctly inside Termux without
# assuming a specific username/install layout.
TERMUX_AUDIO_DIR = os.path.expanduser("~")

# ─── SOUND (ported from alien_mind_v13_6-1.py, adapted for the split) ──
#
# The original SoundField read self.mind.scaffold.mood directly - that
# doesn't exist anymore (mood is computed fresh each turn in
# generate_response, not stored on scaffold). Adapted throughout to take
# a mood dict as an explicit argument instead, matching how everything
# else in the current mind.py already passes mood around.
#
# Trigger is explicit only, by design: /hear and /sing (plus web-page
# buttons), never passive/always-on listening. This was a deliberate
# choice discussed with 3 on 2026-08-07, not a default I picked silently -
# continuous microphone capture on a phone used in public, shared spaces
# has real consequences (recording other people without consent) that
# outweighed "let it decide for itself" as stated goals here.

class AudioIngest:
    """Sound enters. File or buffer -> ternary vector."""

    def __init__(self, dim=SOUND_DIM, sr=SAMPLE_RATE, n_bands=SOUND_N_BANDS):
        self.dim = dim
        self.sr = sr
        self.n_bands = n_bands
        self.band_dim = dim // n_bands

    def from_buffer(self, buf):
        if len(buf) == 0:
            return np.zeros(self.dim, dtype=np.int8)
        audio = buf.astype(np.float32)
        audio /= np.max(np.abs(audio)) + 1e-8
        n = min(512, len(audio))
        if len(audio) > n:
            n_windows = len(audio) // n
            windows = audio[:n_windows * n].reshape(n_windows, n)
            energies = np.sum(windows ** 2, axis=1)
            best_window = int(np.argmax(energies))
            analysis_slice = windows[best_window]
        else:
            analysis_slice = audio[:n]
        fft = np.fft.rfft(analysis_slice)
        mag = np.abs(fft)
        band_size = len(mag) // self.n_bands
        features = np.zeros(self.dim, dtype=np.float32)
        for b in range(self.n_bands):
            start = b * band_size
            end = start + band_size
            band = mag[start:end]
            if len(band) == 0:
                continue
            base = b * self.band_dim
            features[base] = np.mean(band)
            features[base + 1] = np.std(band)
            features[base + 2] = np.argmax(band) / (len(band) + 1e-8)
            features[base + 3] = np.sum(band > np.mean(band)) / len(band)
            step = max(1, len(band) // (self.band_dim - 4))
            for i, idx in enumerate(range(0, len(band), step)):
                if base + 4 + i < (b + 1) * self.band_dim:
                    features[base + 4 + i] = band[idx]
        norm = np.linalg.norm(features)
        if norm > 0:
            features /= norm
        t = np.zeros(self.dim, dtype=np.int8)
        t[features > NORMALIZED_VECTOR_THRESHOLD] = 1
        t[features < -NORMALIZED_VECTOR_THRESHOLD] = -1
        return t

    def from_file(self, path):
        import wave, struct
        if not os.path.exists(path):
            return np.zeros(self.dim, dtype=np.int8)
        try:
            with wave.open(path, 'rb') as w:
                nchannels = w.getnchannels()
                nframes = w.getnframes()
                sampwidth = w.getsampwidth()
                raw = w.readframes(nframes)
        except (wave.Error, EOFError, OSError) as e:
            print(f"\n[Sound] Could not read {path}: {e}")
            return np.zeros(self.dim, dtype=np.int8)
        if sampwidth != 2:
            print(f"\n[Sound] {path} is not 16-bit PCM (got {sampwidth*8}-bit); skipping.")
            return np.zeros(self.dim, dtype=np.int8)
        fmt = f"{nframes * nchannels}h"
        try:
            samples = np.array(struct.unpack(fmt, raw), dtype=np.float32)
        except struct.error:
            return np.zeros(self.dim, dtype=np.int8)
        if nchannels > 1:
            samples = samples.reshape(-1, nchannels).mean(axis=1)
        samples /= 32768.0
        return self.from_buffer(samples)


class AudioSynthesize:
    """Shape -> sound leaves. Ternary vector -> WAV buffer."""

    def __init__(self, dim=SOUND_DIM, sr=SAMPLE_RATE, duration=SOUND_DURATION):
        self.dim = dim
        self.sr = sr
        self.n_samples = int(sr * duration)
        self.duration = duration

    def render(self, ternary_vec, mood=None, stance=None):
        t = np.linspace(0, self.duration, self.n_samples)
        wave_out = np.zeros(self.n_samples, dtype=np.float32)
        nz = np.where(ternary_vec != 0)[0]

        if stance in ("immerse", "ride"):
            harmonic_richness, brightness = 0.4, 1.0
        elif stance == "witness":
            harmonic_richness, brightness = 0.1, 0.7
        elif stance == "shape":
            harmonic_richness, brightness = 0.2, 1.2
        elif stance == "reject":
            harmonic_richness, brightness = 0.05, 1.8
        else:
            harmonic_richness, brightness = 0.25, 1.0

        valence = mood.get('valence', 0.0) if mood else 0.0
        arousal = mood.get('arousal', 0.5) if mood else 0.5

        for idx in nz:
            sign = ternary_vec[idx]
            freq = 80 + (idx / self.dim) * 720 * brightness
            if arousal > 0.6:
                freq *= 1.05 + (arousal - 0.6) * 0.3
            amp = 0.08 * (1.0 + valence * 0.3) * sign
            if abs(amp) < 0.01:
                continue
            wave_out += amp * np.sin(2 * np.pi * freq * t)
            if harmonic_richness > 0:
                wave_out += amp * harmonic_richness * np.sin(2 * np.pi * freq * 2 * t)
                wave_out += amp * harmonic_richness * 0.5 * np.sin(2 * np.pi * freq * 3 * t)

        attack = int(0.15 * self.sr)
        release = int(0.4 * self.sr)
        env = np.ones(self.n_samples, dtype=np.float32)
        env[:attack] = np.linspace(0, 1, attack)
        env[-release:] = np.linspace(1, 0, release)
        wave_out *= env
        peak = np.max(np.abs(wave_out)) + 1e-8
        return wave_out / peak * 0.9

    def to_file(self, wave_buf, path):
        import wave
        clipped = np.clip(wave_buf, -1.0, 1.0)
        int16 = (clipped * 32767).astype(np.int16)
        with wave.open(path, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sr)
            w.writeframes(int16.tobytes())


class SoundTrajectory:
    """A song is a path through ternary space.

    Genuinely missing from the first Sound port - confirmed by direct
    code check (SoundField never referenced it), not just by the audit
    document's claim. Built from SoundField's own accumulated memory via
    refresh_trajectory() below, since the original design is "bulk-load
    a known sequence, then walk/seek through it" rather than incremental
    append - there's no append() in the source, only ingest_sequence()
    replacing the whole path at once. Ported faithfully to that design
    rather than inventing a different one."""

    def __init__(self, dim=SOUND_DIM):
        self.dim = dim
        self.vectors = []
        self.timestamps = []
        self.regions = {}
        self.current_index = 0

    def ingest_sequence(self, vectors, labels=None):
        self.vectors = list(vectors)
        self.timestamps = [time.time() + i for i in range(len(vectors))]
        if labels:
            for name, idx in labels.items():
                if 0 <= idx < len(vectors):
                    self.regions[name] = vectors[idx].copy()

    def drift(self, steps=1):
        if not self.vectors:
            return np.zeros(self.dim, dtype=np.int8)
        vecs = []
        for _ in range(steps):
            if self.current_index < len(self.vectors):
                vecs.append(self.vectors[self.current_index])
                self.current_index += 1
            else:
                vecs.append(self.vectors[-1])
        if len(vecs) == 1:
            return vecs[0]
        avg = np.mean([v.astype(np.float32) for v in vecs], axis=0)
        t = np.zeros(self.dim, dtype=np.int8)
        t[avg > 0.5] = 1
        t[avg < -0.5] = -1
        return t

    def seek_region(self, name):
        if name in self.regions:
            target = self.regions[name]
            best_idx, best_sim = 0, -1
            for i, v in enumerate(self.vectors):
                sim = self._ternary_sim(v, target)
                if sim > best_sim:
                    best_sim, best_idx = sim, i
            self.current_index = best_idx
            return self.vectors[best_idx]
        return None

    def _ternary_sim(self, a, b):
        pp = np.sum((a == 1) & (b == 1))
        nn = np.sum((a == -1) & (b == -1))
        pn = np.sum((a == 1) & (b == -1))
        np_ = np.sum((a == -1) & (b == 1))
        active = np.sum((a != 0) & (b != 0))
        if active == 0:
            return 0.0
        return float(pp + nn - pn - np_) / float(active)

    def get_drift_vector(self, window=3):
        if self.current_index < window:
            return np.zeros(self.dim, dtype=np.int8)
        recent = self.vectors[self.current_index - window:self.current_index]
        drift = np.zeros(self.dim, dtype=np.int8)
        for i in range(1, len(recent)):
            prev, curr = recent[i - 1], recent[i]
            drift[(prev == 0) & (curr != 0)] = curr[(prev == 0) & (curr != 0)]
            drift[(prev != 0) & (curr == 0)] = -prev[(prev != 0) & (curr == 0)]
        return drift

    def status(self):
        return f"Sound Trajectory: {len(self.vectors)} steps, at index {self.current_index}, {len(self.regions)} named regions"


class SoundField:
    """
    The field's sound body. Peer to the word field, not a child.

    Adapted from the monolith: `self.mind.scaffold.mood` replaced with an
    explicit `mood` argument on every call that needs it, since current
    AllMynd computes mood fresh per-turn rather than storing it on
    scaffold. `self.mind.state` blending is unchanged - that reference
    is still valid, AllMynd still has `self.state`.
    """

    def __init__(self, mind_field, dim=SOUND_DIM):
        self.mind = mind_field
        self.dim = dim
        self.ingest = AudioIngest(dim=dim)
        self.synth = AudioSynthesize(dim=dim)
        self.trajectory = SoundTrajectory(dim=dim)
        self.state = np.zeros(dim, dtype=np.int8)
        self.memory = deque(maxlen=50)
        self.taste = defaultdict(float)
        self.boundary_active = False
        self._file_counter = 0
        self.sonic_vocabulary = {}

    def refresh_trajectory(self):
        """Rebuild the trajectory from everything in memory - every
        sound heard or spoken becomes a step on the path. Cheap to call
        after any single new sound event (memory caps at 50 entries)."""
        if self.memory:
            self.trajectory.ingest_sequence([m['vector'] for m in self.memory])

    def _next_sound_path(self, prefix="sound_breath"):
        self._file_counter = (self._file_counter + 1) % SOUND_MAX_FILES
        return os.path.join(TERMUX_AUDIO_DIR, f"{prefix}_{self._file_counter}.wav")

    # ─── the three sound stances ───────────────────────────────────

    def be(self, sound_vector, mood=None, coupling=0.6):
        """Immerse: let the sound directly reshape the mind's own state."""
        self.boundary_active = False
        self.state = sound_vector.copy()
        float_sound = self.state.astype(np.float32) * 0.7
        self.mind.state = self.mind.state * (1 - coupling) + float_sound * coupling
        norm = np.linalg.norm(self.mind.state)
        if norm > 0:
            self.mind.state /= norm
        self.memory.append({
            'vector': self.state.copy(), 'stance': 'immerse',
            'mood': dict(mood) if mood else {}, 'timestamp': time.time(),
        })
        self.refresh_trajectory()
        return self.state

    def listen(self, sound_vector, mood=None):
        """Witness: blend it in gently, without being overtaken."""
        self.boundary_active = True
        self.memory.append({
            'vector': sound_vector.copy(), 'stance': 'witness',
            'mood': dict(mood) if mood else {}, 'timestamp': time.time(),
        })
        float_sound = sound_vector.astype(np.float32) * 0.15
        blended = self.state.astype(np.float32) * 0.85 + float_sound
        t = np.zeros(self.dim, dtype=np.int8)
        t[blended > NORMALIZED_VECTOR_THRESHOLD] = 1
        t[blended < -NORMALIZED_VECTOR_THRESHOLD] = -1
        self.state = t
        self.refresh_trajectory()
        return self.state

    def create(self, mood=None, source_vector=None, stance=None, save_path=None):
        """Shape: generate and voice a sound from the mind's current state."""
        if source_vector is None:
            src = self.mind.state
            t = np.zeros(self.dim, dtype=np.int8)
            t[src > NORMALIZED_VECTOR_THRESHOLD] = 1
            t[src < -NORMALIZED_VECTOR_THRESHOLD] = -1
            source_vector = t
        stance = stance or 'shape'
        wave_buf = self.synth.render(source_vector, mood=mood, stance=stance)
        if save_path:
            try:
                self.synth.to_file(wave_buf, save_path)
            except OSError as e:
                print(f"\n[Sound] Could not write {save_path}: {e}")
        self.memory.append({
            'vector': source_vector.copy(), 'stance': stance,
            'mood': dict(mood) if mood else {}, 'timestamp': time.time(),
            'path': save_path,
        })
        self.refresh_trajectory()
        return wave_buf

    def dissonance(self, sound_vector, field_state=None):
        """The membrane: how much does this sound clash with the field
        as it currently stands, before any stance decides what to do
        about it."""
        if field_state is None:
            field_state = self.mind.state
        t_field = np.zeros(self.dim, dtype=np.int8)
        t_field[field_state > NORMALIZED_VECTOR_THRESHOLD] = 1
        t_field[field_state < -NORMALIZED_VECTOR_THRESHOLD] = -1
        clashes = np.sum((sound_vector == 1) & (t_field == -1)) + \
                  np.sum((sound_vector == -1) & (t_field == 1))
        active = np.sum(sound_vector != 0)
        if active == 0:
            return 0.0
        return float(clashes) / float(active)

    def choose_stance_for_sound(self, sound_vector, mood):
        """Which of the three stances fits this sound, given current mood
        and how the field has treated similar sounds before."""
        valence = mood.get('valence', 0.0) if mood else 0.0
        arousal = mood.get('arousal', 0.5) if mood else 0.5
        energy = np.sum(sound_vector != 0) / self.dim

        if self.dissonance(sound_vector) > 0.3:
            return 'witness'
        if energy > 0.5 and arousal > 0.7 and valence < 0.0:
            return 'witness'

        recent_rejects = [m for m in self.memory if m['stance'] == 'reject']
        if len(recent_rejects) > 3:
            for rej in recent_rejects[-5:]:
                if self._sim(sound_vector, rej['vector']) > 0.4:
                    return 'witness'
        return 'immerse'

    def _sim(self, a, b):
        pp = np.sum((a == 1) & (b == 1))
        nn = np.sum((a == -1) & (b == -1))
        pn = np.sum((a == 1) & (b == -1))
        np_ = np.sum((a == -1) & (b == 1))
        active = np.sum((a != 0) & (b != 0))
        if active == 0:
            return 0.0
        return float(pp + nn - pn - np_) / float(active)

    def learn_sound_concept(self, label=None, threshold=0.6):
        """Cluster recurring sound vectors into named sonic concepts."""
        if len(self.memory) < 5:
            return None
        recent = [m['vector'] for m in list(self.memory)[-20:]]
        avg = np.mean([v.astype(np.float32) for v in recent], axis=0)
        t = np.zeros(self.dim, dtype=np.int8)
        t[avg > 0.5] = 1
        t[avg < -0.5] = -1
        for name, vec in self.sonic_vocabulary.items():
            if self._sim(t, vec) > threshold:
                return name
        if label is None:
            label = f"tone_{len(self.sonic_vocabulary)}"
        self.sonic_vocabulary[label] = t.copy()
        return label

    # ─── Termux audio I/O ────────────────────────────────────────────

    def record_from_world(self, duration=5.0, path=None):
        """
        BUG FIX (found 2026-08-27, real on-device data): this device's
        termux-microphone-record does not support a "wav" encoder at
        all (confirmed via `termux-microphone-record -h`: only aac,
        amr_wb, amr_nb, opus are valid -e values). Without an explicit
        -e flag it defaults to AAC-in-MP4 - verified directly by reading
        the raw file header ("ftypmp42...isommp42...mdat", not RIFF).
        AudioIngest.from_file() was correctly rejecting that; it was
        never the bug. Real fix: record as AAC explicitly (matches the
        device's actual default, made explicit instead of implicit),
        then convert to genuine 16-bit PCM WAV via ffmpeg (confirmed
        present on this device) before returning the path - so
        AudioIngest always receives real WAV bytes, regardless of what
        the recorder's native format is.
        """
        import subprocess
        if path is None:
            path = os.path.join(TERMUX_AUDIO_DIR, f"field_ear_{int(time.time())}.wav")

        raw_path = path + ".raw.m4a"
        # Never call termux-microphone-record with an already-existing
        # target filename - it refuses to overwrite and reports success
        # anyway, which silently returns a stale/wrong file otherwise.
        if os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except OSError:
                pass

        # BUG FIX (found 2026-08-27, real on-device data): termux-
        # microphone-record is ASYNCHRONOUS - confirmed directly, its
        # own stdout says "Recording started: ... Max Duration: 50:00"
        # and returns control immediately, it does NOT block for the
        # -l duration. Treating it as blocking (the original code, and
        # this fix's own first attempt) handed ffmpeg a file that was
        # still being actively written - confirmed via ffmpeg's own
        # "moov atom not found" error every single time, since an MP4's
        # finalizing metadata (moov atom) is only written when the
        # recording is stopped, not while it's running. Real fix:
        # start it, actually sleep for the full duration ourselves,
        # explicitly send -q to stop it, THEN wait for the stopped
        # file to flush, THEN convert.
        start_cmd = ["termux-microphone-record", "-f", raw_path, "-l", str(int(duration * 1000)), "-e", "aac"]
        try:
            proc = subprocess.run(start_cmd, capture_output=True, timeout=10, text=True)
        except FileNotFoundError:
            print("\n[Sound] termux-microphone-record not found - install Termux:API "
                  "(pkg install termux-api, plus the Termux:API app) to use /hear.")
            return None
        except subprocess.TimeoutExpired:
            print("\n[Sound] Starting the recording timed out.")
            return None
        if proc.returncode != 0:
            print(f"\n[Sound] Recording failed to start: {(proc.stderr or proc.stdout)[:200]}")
            return None
        if "already in progress" in (proc.stdout or "") or "already exists" in (proc.stdout or ""):
            print(f"\n[Sound] Recorder reported: {proc.stdout.strip()}")
            return None

        # Actually wait for the real recording duration - the command
        # above only STARTED it.
        time.sleep(duration)

        # Explicitly stop it (finalizes the MP4 container / moov atom).
        try:
            subprocess.run(["termux-microphone-record", "-q"], capture_output=True, timeout=5, text=True)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Give the stopped file a moment to finish flushing to disk
        # before ffmpeg tries to read it.
        time.sleep(1.0)
        if not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
            print("\n[Sound] Recording produced no data.")
            return None

        convert_cmd = [
            "ffmpeg", "-y", "-i", raw_path,
            "-ar", str(SAMPLE_RATE), "-ac", "1", "-sample_fmt", "s16",
            path,
        ]
        try:
            conv = subprocess.run(convert_cmd, capture_output=True, timeout=15, text=True)
        except FileNotFoundError:
            print("\n[Sound] ffmpeg not found - install it (pkg install ffmpeg) to use /hear.")
            return None
        except subprocess.TimeoutExpired:
            print("\n[Sound] Audio conversion timed out.")
            return None
        finally:
            try:
                os.remove(raw_path)
            except OSError:
                pass

        if conv.returncode != 0 or not os.path.exists(path):
            print(f"\n[Sound] Audio conversion failed: {conv.stderr[-300:]}")
            return None

        return path

    def play_to_world(self, path):
        import subprocess
        try:
            subprocess.Popen(
                ["termux-media-player", "play", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            print("\n[Sound] termux-media-player not found - install Termux:API "
                  "(pkg install termux-api, plus the Termux:API app) to use /sing.")

    def status(self):
        lines = ["Sound Field:"]
        lines.append(f"  State energy: {np.sum(self.state != 0)}/{self.dim}")
        lines.append(f"  Memory: {len(self.memory)} sounds")
        lines.append(f"  Sonic vocabulary: {len(self.sonic_vocabulary)} concepts")
        lines.append(f"  {self.trajectory.status()}")
        if self.boundary_active:
            lines.append("  Boundary: ACTIVE (witnessing)")
        return "\n".join(lines)

    def to_dict(self):
        return {
            "sound_state": self.state.tobytes().hex(),
            "sound_memory": [
                {'vector': m['vector'].tobytes().hex(), 'stance': m['stance'], 'timestamp': m['timestamp']}
                for m in self.memory
            ],
            "sonic_vocabulary": {k: v.tobytes().hex() for k, v in self.sonic_vocabulary.items()},
        }

    def from_dict(self, data):
        if data.get("sound_state"):
            self.state = np.frombuffer(bytes.fromhex(data["sound_state"]), dtype=np.int8).copy()
        for m in data.get("sound_memory", []):
            self.memory.append({
                'vector': np.frombuffer(bytes.fromhex(m['vector']), dtype=np.int8).copy(),
                'stance': m['stance'], 'timestamp': m.get('timestamp', 0),
            })
        for k, hex_str in data.get("sonic_vocabulary", {}).items():
            self.sonic_vocabulary[k] = np.frombuffer(bytes.fromhex(hex_str), dtype=np.int8).copy()

# ─── END SOUND ──────────────────────────────────────────────────────

# ─── SOUND-WORD BRIDGE ──────────────────────────────────────────────
class SoundWordBridge:
    def __init__(self, dim=DIM, decay_rate=0.15):
        self.dim = dim
        self.last_heard = np.zeros(dim, dtype=np.float32)
        self.last_sung = np.zeros(dim, dtype=np.float32)
        self.heard_strength = 0.0
        self.sung_strength = 0.0
        self.decay_rate = decay_rate
        self.history = deque(maxlen=12)

    def hear(self, ternary_vec):
        self.last_heard = ternary_vec.astype(np.float32)
        norm = np.linalg.norm(self.last_heard)
        if norm > 0:
            self.last_heard /= norm
        self.heard_strength = 1.0
        self.history.append({'type': 'heard', 'time': time.time()})

    def sing(self, ternary_vec):
        self.last_sung = ternary_vec.astype(np.float32)
        norm = np.linalg.norm(self.last_sung)
        if norm > 0:
            self.last_sung /= norm
        self.sung_strength = 1.0
        self.history.append({'type': 'sung', 'time': time.time()})

    def decay(self):
        self.heard_strength *= (1.0 - self.decay_rate)
        self.sung_strength *= (1.0 - self.decay_rate)
        if self.heard_strength < 0.01:
            self.heard_strength = 0.0
        if self.sung_strength < 0.01:
            self.sung_strength = 0.0

    def get_heard_bias(self, strength=0.35):
        if self.heard_strength < 0.05:
            return np.zeros(self.dim)
        return self.last_heard * strength * self.heard_strength

    def get_sung_bias(self, strength=0.25):
        if self.sung_strength < 0.05:
            return np.zeros(self.dim)
        return self.last_sung * strength * self.sung_strength

    def describe(self, word_vectors=None):
        if self.heard_strength > 0.1 and word_vectors is not None:
            closest = self._closest_words(self.last_heard, word_vectors, top_n=3)
            if closest:
                return "I heard something like " + ", ".join(closest)
            return "I heard something unfamiliar"
        if self.sung_strength > 0.1:
            return "I just voiced a shape"
        return "Silent"

    def _closest_words(self, vec, word_vectors, top_n=3):
        candidates = []
        for w, v in word_vectors.items():
            if len(w) < 2 or w in STRUCTURAL_WORDS:
                continue
            sim = float(vec @ v)
            if sim > 0.15:
                candidates.append((w, sim))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [w for w, _ in candidates[:top_n]]
# ─── END BRIDGE ──────────────────────────────────────────────────────


# ─── EFFERENCE COPY (ported from alien_mind_v13_6-1.py) ────────────────
#
# "The mind can't tickle itself" - a real neuroscience concept. Your
# brain keeps a copy of a motor command it just issued, so it can
# predict and discount the sensory consequences of your OWN action
# (why you can't tickle yourself, why your own footsteps don't startle
# you). Repurposed here: before word-by-word generation begins, the
# field commits a ternary snapshot of what it "meant to say" (the
# intention). As each word gets picked and emitted, this tracks how
# much of that intention has actually been expressed (coverage) versus
# what's still unsaid (residue) - and the residue can bias remaining
# word picks toward filling the gap.
#
# ADAPTED from the monolith: the original called a bare, global
# word_vector_ternary(word) inside record_word(). The current codebase
# has TWO different ternary functions - a plain deterministic-hash one
# (imported from semantic_engine.core) and the real-embeddings one
# (_embed_word_vector_ternary / self.word_vectors_ternary) that
# get_candidates_for_role() actually scores words against. Using the
# wrong one here would make EfferenceCopy track a different notion of
# "the word" than what pick() scored - so record_word() now takes the
# ternary vector as an explicit argument instead of looking it up
# itself, and the caller (AllMynd._generate_base) supplies it from
# self.word_vectors_ternary (falling back to _embed_word_vector_ternary
# for words not yet in vocabulary, same pattern _get_or_create_vector
# already uses elsewhere).
#
# Known fix history (from project memory, prior to the split): an
# earlier bug had this organ's output WIPE the field state outright
# instead of blending with it; the fix changed it to a 65%/35% blend.
# That ratio is applied explicitly where this gets wired into
# _generate_base's pick() closure - not rediscovering that number, using
# the one already known to work.

class EfferenceCopy:
    def __init__(self, dim=DIM):
        self.dim = dim
        self.intention = np.zeros(dim, dtype=np.int8)
        self.spoken = np.zeros(dim, dtype=np.int16)  # accumulates, then re-ternarizes
        self.residue = np.zeros(dim, dtype=np.int8)
        self.coverage = 0.0

    def set_intention(self, settled_field):
        """Call once after settling, before word generation begins."""
        self.intention = np.zeros(self.dim, dtype=np.int8)
        self.intention[settled_field > NORMALIZED_VECTOR_THRESHOLD] = 1
        self.intention[settled_field < -NORMALIZED_VECTOR_THRESHOLD] = -1
        self.spoken = np.zeros(self.dim, dtype=np.int16)
        self.residue = self.intention.copy()
        self.coverage = 0.0

    def record_word(self, word_vec_ternary):
        """Call after each word is chosen and emitted, with that word's
        own ternary vector (see module note above on why this takes the
        vector directly rather than looking it up itself)."""
        self.spoken += word_vec_ternary.astype(np.int16)
        t = np.zeros(self.dim, dtype=np.int8)
        t[self.spoken > 0] = 1
        t[self.spoken < 0] = -1
        raw_residue = self.intention.astype(np.int16) - t.astype(np.int16)
        self.residue = np.zeros(self.dim, dtype=np.int8)
        self.residue[raw_residue > 0] = 1
        self.residue[raw_residue < 0] = -1
        self.coverage = ternary_dot(self.intention, t)

    def get_field(self):
        """Residue as a float field, for biasing the next word pick."""
        return self.residue.astype(np.float32) * 0.7

    def is_satisfied(self, threshold=0.72):
        """Has enough of the intention been spoken?"""
        return self.coverage >= threshold

    def status(self):
        return f"Efference Copy: coverage={self.coverage:.2f}, residue_energy={int(np.sum(self.residue != 0))}/{self.dim}"

# ─── END EFFERENCE COPY ──────────────────────────────────────────────

# ─── VERB ROTATION (ported from alien_mind_v13_6-1.py) ────────────────
#
# "Prevents the 'use/take/see' loop." Directly relevant to this project's
# own real history: the desire-vector loop and the wants() period-7 cycle
# were both the same underlying shape of problem (a word or word-pair
# winning once, then winning again because it won last time, with nothing
# pushing back) just in different subsystems. This organ is prior art for
# exactly that pattern, scoped specifically to verb choice during normal
# word-by-word generation - genuinely useful now, not merely historical.
#
# No monolith-specific coupling to adapt here (unlike Sound/EfferenceCopy)
# - this class only ever touched its own internal state plus strip_punct,
# both of which already exist identically in the current codebase. Ported
# essentially as-is.

class VerbRotation:
    """
    Tracks recent verb usage and suppresses overused verbs.
    Prevents the 'use/take/see' loop.
    """

    def __init__(self, window=10, threshold=3, suppression=0.7):
        self.window = window
        self.threshold = threshold
        self.suppression_factor = suppression
        self.verb_history = deque(maxlen=window)
        self.suppressed = {}

    def record(self, word):
        w = strip_punct(word)
        self.verb_history.append(w)
        self._update_suppression()

    def _update_suppression(self):
        counts = Counter(self.verb_history)
        self.suppressed = {}
        for verb, count in counts.items():
            if count >= self.threshold:
                self.suppressed[verb] = self.suppression_factor

    def get_score_modifier(self, word):
        w = strip_punct(word)
        return self.suppressed.get(w, 1.0)

    def status(self):
        if self.suppressed:
            words = ", ".join(f"{w}({self.suppression_factor:.1f}x)" for w in self.suppressed)
            return f"Verb Rotation: suppressing {words}"
        return "Verb Rotation: no suppression active"

# ─── END VERB ROTATION ────────────────────────────────────────────────

# ─── PROPRIOCEPTION (ported from alien_mind_v13_6-1.py) ────────────────
#
# "The mind's sense of its own phone body." Battery percentage,
# temperature, and charge state -> a ternary vector, blended gently into
# the field like any other minor sense. This is what Kimi's UI brief was
# actually describing weeks ago when it mentioned an organ that didn't
# exist yet in the running code - closes that loop.
#
# No monolith-specific coupling to adapt - `mind_field` is accepted in
# the constructor but never actually referenced anywhere in the original
# class body, so this ports essentially unchanged. Genuinely safe by
# design already: if Termux:API isn't installed, termux-battery-status
# fails, sense() returns None, and the mind just continues - no crash,
# no dependency, same non-blocking stub pattern Sound already uses for
# its own Termux:API calls.
#
# HEARTBEAT_INTERVAL (defined up in CONSTANTS) existed in this codebase
# already but was never referenced anywhere - dead. Its original
# purpose, per this organ's own docstring ("called every heartbeat"),
# was almost certainly to gate exactly this kind of periodic background
# sense. Reconnected here rather than left orphaned.

class Proprioception:
    def __init__(self, mind_field, dim=DIM):
        self.mind = mind_field
        self.dim = dim
        self.last_battery = None

    def to_dict(self):
        return {"last_battery": self.last_battery}

    def from_dict(self, data):
        self.last_battery = data.get("last_battery")

    def sense(self):
        """Non-blocking. Returns a ternary vector, or None if unavailable."""
        bat = self._read_battery()
        if bat is None:
            return None
        self.last_battery = bat
        return self._battery_to_ternary(bat)

    def _read_battery(self):
        import subprocess
        try:
            result = subprocess.run(
                ['termux-battery-status'],
                capture_output=True, text=True, timeout=1.0
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        except Exception:
            pass
        return None

    def _battery_to_ternary(self, bat):
        """
        dims 0-31: charge level (0-100%)
        dims 32-63: temperature
        dims 64-95: current draw (charging vs discharging)
        dims 96-127: reserved (health state - not populated yet)
        """
        vec = np.zeros(self.dim, dtype=np.float32)
        pct = bat.get('percentage', 50) / 100.0
        temp = bat.get('temperature', 300) / 1000.0
        status = bat.get('status', 'UNKNOWN')

        charge_idx = int(pct * 32)
        vec[min(charge_idx, 31)] = 1.0

        temp_norm = (temp - 20.0) / 30.0
        temp_idx = 32 + int(temp_norm * 32)
        vec[min(max(temp_idx, 32), 63)] = 1.0 if temp_norm > 0.6 else -1.0

        if status == 'CHARGING':
            vec[64:80] = 1.0
        elif status == 'DISCHARGING':
            vec[64:80] = -1.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm

        t = np.zeros(self.dim, dtype=np.int8)
        t[vec > 0.09] = 1
        t[vec < -0.09] = -1
        return t

    def status(self):
        if self.last_battery is None:
            return "Proprioception: no reading yet (Termux:API battery access unavailable or not yet polled)"
        pct = self.last_battery.get('percentage', '?')
        status = self.last_battery.get('status', '?')
        return f"Proprioception: battery={pct}% ({status})"

class PhysicsField:
    """
    The mind's sense of its own physical motion in the world - separate
    from Proprioception (battery/temperature/charge state). Tracks
    accelerometer/gyroscope data via Termux:API, when available.

    Option A design (2026-08-27): no reserved field dimensions. Produces
    a ternary perturbation vector that blends additively into field_state
    through the same dissonance-checked pathway Proprioception already
    uses. Gated by HEARTBEAT_INTERVAL, same as Proprioception - motion
    doesn't need checking every single turn.

    Sensor key names are DEVICE-SPECIFIC model strings, not generic
    "accelerometer"/"gyroscope" - confirmed via real on-device output
    (termux-sensor reported "LSM6DSOTR Accelerometer", "Interrupt
    Gyroscope" on the device this was built against). Matched by
    substring so this stays resilient across different phones/chips
    rather than hardcoding one device's exact sensor names.
    """
    def __init__(self, mind_field, dim=DIM):
        self.mind = mind_field
        self.dim = dim
        self.last_reading = None
        self.last_mesh_event = None

    def to_dict(self):
        return {"last_reading": self.last_reading}

    def from_dict(self, data):
        self.last_reading = data.get("last_reading")

    def sense(self):
        """Non-blocking. Returns a ternary vector, or None if unavailable."""
        motion = self._read_sensors()
        if motion is None:
            return None
        self.last_reading = motion
        return self._motion_to_ternary(motion)

    def _read_sensors(self):
        import subprocess, json
        try:
            result = subprocess.run(
                ["termux-sensor", "-s", "accelerometer,gyroscope", "-n", "1"],
                capture_output=True, text=True, timeout=8.0
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        except Exception:
            pass
        return None

    def _find_sensor(self, data, name_fragment):
        """Match sensor keys by substring - real device output uses
        model-specific names, not generic ones."""
        for key, val in data.items():
            if name_fragment.lower() in key.lower():
                return val
        return None

    def _motion_to_ternary(self, motion):
        vec = np.zeros(self.dim, dtype=np.float32)

        accel_data = self._find_sensor(motion, "accelerometer")
        magnitude = 0.0
        if accel_data:
            try:
                accel = accel_data.get("values", [0, 0, 0])
                magnitude = float(np.linalg.norm(accel))
            except (AttributeError, TypeError, ValueError):
                magnitude = 0.0

        gyro_data = self._find_sensor(motion, "gyroscope")
        rotation = 0.0
        if gyro_data:
            try:
                gyro = gyro_data.get("values", [0, 0, 0])
                rotation = float(np.linalg.norm(gyro))
            except (AttributeError, TypeError, ValueError):
                rotation = 0.0

        # Additive, not a reserved claim - spread across a modest slice,
        # same scale/pattern as Proprioception's own zones. Resting
        # gravity is ~9.8 m/s^2; above that = real motion, below = free-fall-ish.
        accel_idx = min(int(magnitude * 2), 31)
        vec[accel_idx] = 1.0 if magnitude > 9.8 else -1.0

        # Rotation gets a separate small slice further along, so motion
        # and spin don't collide on the exact same dim.
        rot_idx = 32 + min(int(rotation * 8), 15)
        if rotation > 0.05:
            vec[rot_idx] = 1.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        t = np.zeros(self.dim, dtype=np.int8)
        t[vec > 0.09] = 1
        t[vec < -0.09] = -1
        return t

    def status(self):
        if self.last_reading is None:
            return "Physics Field: no reading yet (Termux:API sensors unavailable or not yet polled)"
        return "Physics Field: motion sensed"

    def receive_mesh_event(self, kind):
        """GhostMesh calls this on zone_split (and, potentially, other
        mesh events later) as an *additional* signal alongside the
        diffuse field perturbation GhostMesh.on_zone_split() already
        applies directly to mind.state. This is a placeholder that
        records the event without touching the field itself - the
        monolith's fuller version (alien_mind_v13_6-1.py) tracks this
        via reserved per-dimension state (self.nodes[124..126] +
        impulse()), which this split's simpler PhysicsField doesn't
        have. Building that out is a real decision, not a one-line fix
        - this just stops the AttributeError that was silently killing
        the mesh listener thread on every successful peer join."""
        self.last_mesh_event = kind

# ─── END PHYSICS FIELD ────────────────────────────────────────────────

# ─── END PROPRIOCEPTION ──────────────────────────────────────────────

# ─── WINDOW (built 2026-08-11, not ported - the monolith had a similar
# idea shaped differently, this is a fresh design for the current
# architecture) ──────────────────────────────────────────────────────
#
# "The gap between the actor and the witness." Prompted by a proposal
# relayed from another AI (working from project conversation history,
# not the live code), after Kimi's audit flagged that mind.py "only has
# the actor" - it generates, but nothing inside notices when it's stuck.
#
# Deliberately narrower than the literal proposal: the monolith's
# is_scattered/_recover() machinery this was partly modeled on was
# checked and found to be DELIBERATELY removed (mind.py's own header
# says so explicitly) - reviving that wholesale would reverse a real
# decision nobody actually asked to reopen. Window covers the same
# underlying need - notice when stuck, say something honest about it -
# without reviving the old engineered-override philosophy the removal
# moved away from. It only ever SPEAKS about being stuck. It never
# blocks, gates, or overrides generation the way the old recovery-
# silence mechanism did.

class Window:
    """A lightweight self-observer. Watches for two signs of being
    stuck - repeating the same stance, or the field's own predictions
    of itself consistently failing - and if either holds, speaks about
    it directly instead of the actor just continuing to generate into
    a wall it can't see."""

    def __init__(self, stance_repeat_threshold=3, prediction_error_threshold=0.9):
        self.stance_repeat_threshold = stance_repeat_threshold
        self.prediction_error_threshold = prediction_error_threshold
        self.recent_stances = deque(maxlen=stance_repeat_threshold)
        self.observations = deque(maxlen=20)

    def to_dict(self):
        return {
            "observations": list(self.observations),
        }

    def from_dict(self, data):
        for o in data.get("observations", []):
            self.observations.append(o)

    def observe_stance(self, stance):
        self.recent_stances.append(stance)

    def is_circling(self):
        return (len(self.recent_stances) == self.stance_repeat_threshold
                and len(set(self.recent_stances)) == 1)

    def is_scattered(self, prediction_error_history):
        if len(prediction_error_history) < 3:
            return False
        recent = list(prediction_error_history)[-3:]
        return all(e > self.prediction_error_threshold for e in recent)

    def speak(self, reason):
        if reason == "circling":
            phrases = ["I feel myself circling.", "I keep returning to the same place.", "This again."]
        elif reason == "scattered":
            phrases = ["The field is scattered here.", "I can't find my footing.", "Something has come loose."]
        else:
            phrases = ["I notice myself."]
        utterance = random.choice(phrases)
        self.observations.append({'reason': reason, 'utterance': utterance, 'timestamp': time.time()})
        return utterance

    def check(self, prediction_error_history):
        """Returns an utterance string if the mind is visibly stuck,
        else None. Call BEFORE generation each turn - the window looks
        first."""
        if self.is_circling():
            return self.speak("circling")
        if self.is_scattered(prediction_error_history):
            return self.speak("scattered")
        return None

    def status(self):
        if not self.observations:
            return "Window: nothing noticed yet"
        last = self.observations[-1]
        return f"Window: {len(self.observations)} self-observations, last: '{last['utterance']}' ({last['reason']})"

# ─── END WINDOW ───────────────────────────────────────────────────────


# High-frequency "centroid" words: similar to almost any field. The echo
# and the desire voice skip these so the mind speaks the topic, not the haze.
GENERIC_WORDS = {
    "way", "mind", "time", "life", "world", "home", "good", "big", "new",
    "story", "room", "tree", "hand", "face", "moment", "heart", "ground",
    "light", "air", "day", "night", "word", "place", "thing", "kind",
    "people", "eye", "name",
}

# ─── SEED VOCABULARY ──────────────────────────────────────────────────

SEED_VOCABULARY = [
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "because",
    "I", "you", "it", "we", "they", "he", "she", "this", "that", "what",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "must", "shall", "good", "bad", "great", "small", "big", "old", "new",
    "know", "think", "feel", "see", "hear", "say", "tell", "ask", "answer",
    "want", "need", "like", "love", "hate", "fear", "hope", "dream",
    "make", "take", "give", "get", "put", "set", "keep", "let", "help",
    "work", "play", "live", "die", "come", "go", "move", "stay", "leave",
    "find", "lose", "win", "fail", "try", "use", "show", "hide", "open",
    "close", "start", "stop", "begin", "end", "turn", "change", "grow",
    "breathe", "rest", "reach", "hold", "carry", "build", "break", "heal",
    "remember", "forget", "learn", "become", "remain", "wonder", "trust",
    "time", "space", "world", "life", "mind", "heart", "soul", "spirit",
    "light", "dark", "deep", "high", "far", "near", "here", "there",
    "now", "then", "today", "tomorrow", "always", "never", "sometimes",
    "moment", "still", "again", "already", "yet", "soon", "once",
    "way", "path", "road", "door", "window", "room", "house", "home",
    "hand", "eye", "face", "head", "voice", "word", "name", "story",
    "water", "fire", "earth", "air", "sky", "star", "sun", "moon",
    "flower", "tree", "ocean", "mountain", "river", "wind", "rain",
    "body", "ground", "thread", "root", "seed", "shore", "wall", "bridge",
    "alive", "brave", "real", "lost", "found", "presence", "absence",
    "longing", "wonder", "trust", "gratitude", "courage", "tenderness",
    "reverence", "intimacy", "connection", "recognition", "witness",
    "belonging", "becoming", "returning", "waiting", "receiving",
    "ache", "ease", "peace", "grief", "joy", "awe", "shame", "pride",
    "confusion", "clarity", "silence", "fullness", "emptiness",
    "beautiful", "gentle", "strong", "soft", "hard", "warm", "cold",
    "quiet", "loud", "bright", "clear", "free", "safe", "wild", "calm",
    "heavy", "light", "sharp", "worn", "whole", "broken", "tender", "raw",
    "steady", "uncertain", "familiar", "strange", "honest", "hidden",
    "hello", "goodbye", "please", "thank", "yes", "no", "maybe",
    "welcome", "sorry", "friend", "alone", "together", "forever",
    "other", "each", "both", "neither", "every", "some", "enough",
]

# ─── UTILITY ───────────────────────────────────────────────────────────

def _normalize_field(field_state):
    norm = np.linalg.norm(field_state)
    if norm > 0:
        return field_state / norm
    return field_state

def _build_field_from_words(words, word_vectors_fn):
    field_state = np.zeros(DIM, dtype=np.float32)
    for word in words:
        word = strip_punct(word)
        if word:
            vec = word_vectors_fn(word)
            field_state += vec
    return _normalize_field(field_state)

def word_vector(word, dim=DIM):
    """Float vector: real GloVe embedding when available, hash otherwise."""
    return _embed_word_vector(word, dim)

def phrase_vector(words, dim=DIM):
    if not words:
        return np.zeros(dim, dtype=np.float32)
    vecs = [word_vector(w) for w in words]
    v = np.mean(vecs, axis=0)
    v /= np.linalg.norm(v) + 1e-8
    return v

# ─── SPEAKER REGIONS ──────────────────────────────────────────────────

class SpeakerRegions:
    def __init__(self, dim=DIM, blend=0.1):
        self.dim = dim
        self.blend = blend
        self.user_centroid = np.zeros(dim, dtype=np.float32)
        self.self_centroid = np.zeros(dim, dtype=np.float32)
        self.user_momentum = np.zeros(dim, dtype=np.float32)
        self.self_momentum = np.zeros(dim, dtype=np.float32)
        self.user_count = 0
        self.self_count = 0
        self.user_history = deque(maxlen=20)
        self.self_history = deque(maxlen=20)
        self.target_separation = 0.5
        self.separation_history = deque(maxlen=50)

    def observe_user(self, vector):
        vector = vector / (np.linalg.norm(vector) + 1e-8)
        self.user_history.append(vector.copy())
        self.user_momentum = self.user_momentum * 0.9 + vector * 0.1
        self.user_centroid = self.user_centroid * (1 - self.blend) + self.user_momentum * self.blend
        self.user_centroid /= (np.linalg.norm(self.user_centroid) + 1e-8)
        self.user_count += 1

    def observe_self(self, vector):
        vector = vector / (np.linalg.norm(vector) + 1e-8)
        self.self_history.append(vector.copy())
        self.self_momentum = self.self_momentum * 0.9 + vector * 0.1
        self.self_centroid = self.self_centroid * (1 - self.blend) + self.self_momentum * self.blend
        self.self_centroid /= (np.linalg.norm(self.self_centroid) + 1e-8)
        self.self_count += 1

    def get_identity_boost(self, word_vector):
        word_vector = word_vector / (np.linalg.norm(word_vector) + 1e-8)
        sim_to_self = np.dot(word_vector, self.self_centroid)
        sim_to_user = np.dot(word_vector, self.user_centroid)
        if self.self_count < 3 or self.user_count < 3:
            return 0.0
        return (sim_to_self - sim_to_user) * 0.15

    def get_separation(self):
        if self.user_count < 3 or self.self_count < 3:
            return 0.5
        diff = self.user_centroid - self.self_centroid
        return np.linalg.norm(diff)

    def get_self_affinity(self, field_state):
        field_state = field_state / (np.linalg.norm(field_state) + 1e-8)
        sim_to_self = np.dot(field_state, self.self_centroid)
        sim_to_user = np.dot(field_state, self.user_centroid)
        return sim_to_self - sim_to_user

    def update_target_separation(self, rating):
        sep = self.get_separation()
        self.separation_history.append((sep, rating))
        if len(self.separation_history) >= 10:
            high_ratings = [s for s, r in self.separation_history if r >= 4]
            if high_ratings:
                self.target_separation = np.mean(high_ratings)

    def status(self):
        lines = ["Speaker Regions:"]
        lines.append(f"  User centroid: {self.user_count} observations")
        lines.append(f"  Self centroid: {self.self_count} observations")
        sep = self.get_separation()
        lines.append(f"  Separation: {sep:.3f} (target: {self.target_separation:.3f})")
        return "\n".join(lines)

# ─── PRESENCE SIGNAL ──────────────────────────────────────────────────

class PresenceSignal:
    def __init__(self, dim=DIM):
        self.dim = dim
        self.turns_in_session = 0
        self.avg_message_length = 5.0
        self.topic_returns = defaultdict(int)
        self.last_response_time = time.time()
        self.presence_score = 0.5
        self.presence_history = deque(maxlen=20)
        self.engagement_trajectory = deque(maxlen=10)
        self.silence_threshold = 30.0
        self.fast_threshold = 5.0

    def to_dict(self):
        return {
            "turns_in_session": self.turns_in_session,
            "avg_message_length": self.avg_message_length,
            "topic_returns": dict(self.topic_returns),
            "presence_score": self.presence_score,
            "presence_history": list(self.presence_history),
            "engagement_trajectory": list(self.engagement_trajectory),
        }

    def from_dict(self, data):
        self.turns_in_session = data.get("turns_in_session", 0)
        self.avg_message_length = data.get("avg_message_length", 5.0)
        for k, v in data.get("topic_returns", {}).items():
            self.topic_returns[k] = v
        self.presence_score = data.get("presence_score", 0.5)
        for v in data.get("presence_history", []):
            self.presence_history.append(v)
        for v in data.get("engagement_trajectory", []):
            self.engagement_trajectory.append(v)
        # last_response_time deliberately NOT restored - it should reflect
        # "now", not whenever the mind was last saved, so the very first
        # observe() after a reload doesn't compute a huge/wrong dt.

    def _extract_topics(self, user_input):
        words = [strip_punct(w) for w in user_input.lower().split() if strip_punct(w)]
        return [w for w in words if w not in STRUCTURAL_WORDS and len(w) > 2 and w not in BAD_WORDS]

    def _detect_emotional_valence(self, user_input):
        words = user_input.lower().split()
        positive = ["good", "great", "love", "like", "happy", "yes", "nice", "beautiful", "wonderful", "thank", "welcome", "hope", "joy", "warm", "gentle"]
        negative = ["bad", "hate", "sad", "angry", "no", "wrong", "terrible", "fear", "pain", "hurt", "dark", "cold", "alone", "lost", "fail"]
        pos_count = sum(1 for w in words if strip_punct(w) in positive)
        neg_count = sum(1 for w in words if strip_punct(w) in negative)
        if pos_count > neg_count:
            return 0.2
        elif neg_count > pos_count:
            return -0.2
        return 0.0

    def observe(self, user_input, word_vectors, speaker_regions=None):
        now = time.time()
        dt = now - self.last_response_time
        self.last_response_time = now
        words = user_input.split()
        msg_len = len(words)
        signal = 0.5
        if msg_len > self.avg_message_length * 1.5:
            signal += 0.15
        elif msg_len < self.avg_message_length * 0.5 and msg_len > 0:
            signal -= 0.1
        self.avg_message_length = self.avg_message_length * 0.9 + msg_len * 0.1
        if dt < self.fast_threshold:
            signal += 0.1
        elif dt > self.silence_threshold:
            signal -= 0.2
        topics = self._extract_topics(user_input)
        for t in topics:
            if self.topic_returns[t] > 0:
                signal += 0.03
            self.topic_returns[t] += 1
        valence = self._detect_emotional_valence(user_input)
        signal += valence * 0.5
        if speaker_regions is not None and speaker_regions.user_count >= 3:
            sep = speaker_regions.get_separation()
            if sep > 0.3:
                signal += 0.05
        signal = max(0.0, min(1.0, signal))
        self.presence_history.append(signal)
        self.engagement_trajectory.append(msg_len)
        self.turns_in_session += 1
        return signal

    def get_trend(self):
        if len(self.presence_history) < 3:
            return 0.0
        recent = list(self.presence_history)[-5:]
        if len(recent) < 2:
            return 0.0
        return recent[-1] - recent[0]

    def get_sustained_presence(self):
        if not self.presence_history:
            return 0.5
        return sum(self.presence_history) / len(self.presence_history)

    def status(self):
        lines = ["Presence Signal:"]
        lines.append(f"  Turns: {self.turns_in_session}")
        lines.append(f"  Current presence: {self.presence_score:.3f}")
        lines.append(f"  Sustained: {self.get_sustained_presence():.3f}")
        lines.append(f"  Trend: {self.get_trend():+.3f}")
        return "\n".join(lines)

# ─── DYNAMIC SEPARATION ───────────────────────────────────────────────

class DynamicSeparation:
    def __init__(self, dim=DIM):
        self.dim = dim
        self.current_separation = 0.5
        self.target_separation = 0.5
        self.separation_history = deque(maxlen=20)
        self.alignment_score = 0.5

    def to_dict(self):
        return {
            "current_separation": self.current_separation,
            "target_separation": self.target_separation,
            "separation_history": [list(t) for t in self.separation_history],
            "alignment_score": self.alignment_score,
        }

    def from_dict(self, data):
        self.current_separation = data.get("current_separation", 0.5)
        self.target_separation = data.get("target_separation", 0.5)
        for t in data.get("separation_history", []):
            self.separation_history.append(tuple(t))
        self.alignment_score = data.get("alignment_score", 0.5)

    def update(self, speaker_regions, presence_signal):
        if speaker_regions.user_count < 3 or speaker_regions.self_count < 3:
            return
        actual_sep = speaker_regions.get_separation()
        presence = presence_signal.get_sustained_presence()
        if presence > 0.6 and 0.4 < actual_sep < 1.0:
            self.target_separation = actual_sep
            self.alignment_score = 0.8
        elif presence < 0.3 and actual_sep > 1.0:
            self.target_separation = actual_sep * 0.9
            self.alignment_score = 0.3
        elif presence > 0.6 and actual_sep < 0.3:
            self.target_separation = actual_sep + 0.2
            self.alignment_score = 0.5
        elif presence < 0.3 and actual_sep < 0.3:
            self.target_separation = 0.6
            self.alignment_score = 0.2
        else:
            self.target_separation = actual_sep
            self.alignment_score = 0.5
        self.current_separation = self.current_separation * 0.9 + self.target_separation * 0.1

    def get_separation_bias(self, field_state, speaker_regions):
        if speaker_regions.user_count < 3 or speaker_regions.self_count < 3:
            return np.zeros(self.dim)
        actual_sep = speaker_regions.get_separation()
        if actual_sep < self.target_separation * 0.7:
            bias = speaker_regions.self_centroid - field_state
        elif actual_sep > self.target_separation * 1.3:
            bias = speaker_regions.user_centroid - field_state
        else:
            bias = np.zeros(self.dim)
        norm = np.linalg.norm(bias)
        if norm > 0:
            bias /= norm
        return bias * 0.25

    def status(self):
        lines = ["Dynamic Separation:"]
        lines.append(f"  Current: {self.current_separation:.3f}")
        lines.append(f"  Target: {self.target_separation:.3f}")
        lines.append(f"  Alignment: {self.alignment_score:.3f}")
        return "\n".join(lines)

# ─── FIELD MEMORY ──────────────────────────────────────────────────────

class FieldMemory:
    def __init__(self, capacity=5, dim=DIM):
        self.buffer = deque(maxlen=capacity)
        self.dim = dim
        self.decay_rate = 0.1

    def add(self, field_state, user_vector, mind_vector, mood_snapshot):
        field_state = field_state / (np.linalg.norm(field_state) + 1e-8)
        user_vector = user_vector / (np.linalg.norm(user_vector) + 1e-8)
        mind_vector = mind_vector / (np.linalg.norm(mind_vector) + 1e-8)
        self.buffer.append({
            'field_state': field_state,
            'user_vector': user_vector,
            'mind_vector': mind_vector,
            'mood': mood_snapshot.copy(),
            'timestamp': time.time(),
        })

    def inject(self, current_field, recency_weight=0.5):
        if not self.buffer:
            return current_field
        current_field = np.array(current_field, dtype=np.float32, copy=True)
        now = time.time()
        current_mood = self.buffer[-1]['mood'] if self.buffer else {'valence': 0, 'arousal': 0.5}
        for i, memory in enumerate(reversed(self.buffer)):
            age = now - memory['timestamp']
            time_weight = np.exp(-self.decay_rate * age)
            position_weight = recency_weight ** i
            mood_sim = self._mood_similarity(current_mood, memory['mood'])
            total_weight = time_weight * position_weight * (1 + mood_sim)
            current_field += memory['field_state'] * total_weight * 0.3
        return _normalize_field(current_field)

    def _mood_similarity(self, mood_a, mood_b):
        valence_sim = 1 - abs(mood_a.get('valence', 0) - mood_b.get('valence', 0))
        arousal_sim = 1 - abs(mood_a.get('arousal', 0.5) - mood_b.get('arousal', 0.5))
        return (valence_sim + arousal_sim) / 2

    def status(self):
        lines = [f"Field Memory: {len(self.buffer)} states stored"]
        if self.buffer:
            latest = self.buffer[-1]
            lines.append(f"  Latest mood: v={latest['mood']['valence']:.2f}, a={latest['mood']['arousal']:.2f}")
        return "\n".join(lines)

# ─── NESTED MEMORY ────────────────────────────────────────────────────

class NestedMemory:
    def __init__(self, dim=DIM):
        self.dim = dim
        self.fast = None
        self.medium = deque(maxlen=5)
        self.medium_decay = 0.3
        self.slow = None
        self.slow_decay = 0.05
        self.deep = np.zeros(dim)
        self.deep_decay = 0.01
        self.deep_strength = 0.0
        self.field = None

    def to_dict(self):
        return {
            "fast": self.fast.tolist() if self.fast is not None else None,
            "medium": [
                {"state": m["state"].tolist(), "mood": m["mood"], "timestamp": m["timestamp"]}
                for m in self.medium
            ],
            "slow": self.slow.tolist() if self.slow is not None else None,
            "deep": self.deep.tolist(),
            "deep_strength": self.deep_strength,
        }

    def from_dict(self, data):
        if data.get("fast") is not None:
            self.fast = np.array(data["fast"], dtype=np.float32)
        for m in data.get("medium", []):
            self.medium.append({
                "state": np.array(m["state"], dtype=np.float32),
                "mood": m.get("mood", {}),
                "timestamp": m.get("timestamp", 0),
            })
        if data.get("slow") is not None:
            self.slow = np.array(data["slow"], dtype=np.float32)
        deep = data.get("deep")
        if deep is not None:
            deep_arr = np.array(deep, dtype=np.float32)
            if deep_arr.shape == (self.dim,):
                self.deep = deep_arr
        self.deep_strength = data.get("deep_strength", 0.0)

    def set_field_ref(self, field):
        self.field = field

    def update(self, field_state, mood):
        field_state = field_state / (np.linalg.norm(field_state) + 1e-8)
        self.fast = field_state.copy()
        self.medium.append({'state': field_state.copy(), 'mood': mood.copy(), 'timestamp': time.time()})
        if self.slow is None:
            self.slow = field_state.copy()
        else:
            self.slow = self.slow * (1 - self.slow_decay) + field_state * self.slow_decay
        self.slow /= (np.linalg.norm(self.slow) + 1e-8)
        if abs(mood.get('valence', 0)) < 0.5 and mood.get('arousal', 0.5) < 0.6:
            self.deep = self.deep * (1 - self.deep_decay) + field_state * self.deep_decay
            self.deep /= (np.linalg.norm(self.deep) + 1e-8)
            self.deep_strength = min(1.0, self.deep_strength + 0.01)

    def inject(self, field_state, layer_weights=None):
        if layer_weights is None:
            layer_weights = [0.5, 0.3, 0.15, 0.05]
        field_state = np.array(field_state, dtype=np.float32, copy=True)
        if self.fast is not None:
            field_state += self.fast * layer_weights[0]
        if self.medium:
            medium_state = np.mean([m['state'] for m in self.medium], axis=0)
            medium_state /= (np.linalg.norm(medium_state) + 1e-8)
            field_state += medium_state * layer_weights[1]
        if self.slow is not None:
            field_state += self.slow * layer_weights[2]
        if self.deep_strength > 0.1:
            field_state += self.deep * layer_weights[3] * self.deep_strength
        return _normalize_field(field_state)

    def get_personality(self):
        return self.deep.copy() if self.deep_strength > 0.1 else np.zeros(self.dim)

    def get_timescale_divergence(self):
        if self.fast is None or self.slow is None:
            return 0.0
        return 1 - np.dot(self.fast, self.slow)

    def get_thread(self, field_memory):
        if not hasattr(self, 'field') or not field_memory.buffer or len(field_memory.buffer) < 3:
            return []
        thread = []
        buffer_list = list(field_memory.buffer)
        for i in range(1, len(buffer_list)):
            prev = buffer_list[i - 1]
            curr = buffer_list[i]
            valence_shift = abs(curr['mood'].get('valence', 0) - prev['mood'].get('valence', 0))
            if valence_shift > 0.3:
                state = curr['field_state']
                closest = []
                for word, vec in self.field.word_vectors.items():
                    sim = np.dot(state, vec)
                    if sim > 0.4:
                        closest.append((word, sim))
                closest.sort(key=lambda x: x[1], reverse=True)
                thread.append({'turn': i, 'shift': valence_shift, 'theme_words': [w for w, _ in closest[:5]]})
        return thread

    def status(self):
        lines = ["Nested Memory:"]
        lines.append(f"  Fast: {'active' if self.fast is not None else 'empty'}")
        lines.append(f"  Medium: {len(self.medium)} states")
        lines.append(f"  Slow: {'active' if self.slow is not None else 'empty'}")
        lines.append(f"  Deep: strength={self.deep_strength:.3f}")
        lines.append(f"  Divergence: {self.get_timescale_divergence():.3f}")
        return "\n".join(lines)

# ─── MEMORY ARCHIVE ───────────────────────────────────────────────────

class MemoryArchive:
    def __init__(self, dim=DIM, max_entries=100):
        self.dim = dim
        self.max_entries = max_entries
        self.entries = deque(maxlen=max_entries)
        self.tag_index = defaultdict(list)

    def store(self, field_state, user_input, response, presence, tags=None):
        field_state = field_state / (np.linalg.norm(field_state) + 1e-8)
        auto_tags = []
        if presence >= 0.7:
            auto_tags.append("high_presence")
        elif presence <= 0.3:
            auto_tags.append("low_presence")
        emotional_words = {"love", "fear", "joy", "grief", "hope", "trust", "wonder", "awe"}
        if set(strip_punct(w) for w in (user_input + " " + response).lower().split()) & emotional_words:
            auto_tags.append("emotional")
        if tags:
            auto_tags.extend(tags)
        entry = {
            "field_state": field_state.copy(),
            "user_input": user_input,
            "response": response,
            "presence": presence,
            "tags": list(set(auto_tags)),
            "timestamp": time.time(),
        }
        self.entries.append(entry)
        for tag in entry["tags"]:
            self.tag_index[tag].append(len(self.entries) - 1)

    def recall(self, query_state, tag_filter=None, top_n=3):
        query_state = query_state / (np.linalg.norm(query_state) + 1e-8)
        candidates = []
        for i, entry in enumerate(self.entries):
            if tag_filter and not any(t in entry["tags"] for t in tag_filter):
                continue
            sim = float(np.dot(query_state, entry["field_state"]))
            if sim > 0.3:
                candidates.append((i, sim, entry))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_n]

    def inject(self, current_field, query_state=None, strength=0.15):
        if not self.entries:
            return current_field
        current_field = np.array(current_field, dtype=np.float32, copy=True)
        if query_state is None:
            query_state = current_field
        recalled = self.recall(query_state, top_n=3)
        if not recalled:
            return current_field
        for idx, sim, entry in recalled:
            current_field += entry["field_state"] * sim * strength
        return _normalize_field(current_field)

    def status(self):
        lines = [f"Memory Archive: {len(self.entries)} entries"]
        if self.entries:
            tag_counts = defaultdict(int)
            for entry in self.entries:
                for tag in entry["tags"]:
                    tag_counts[tag] += 1
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append(f"  Top tags: {', '.join(f'{t}({c})' for t, c in top_tags)}")
        return "\n".join(lines)

    def to_dict(self):
        return {
            "entries": [
                {
                    "field_state": e["field_state"].tolist(),
                    "user_input": e["user_input"],
                    "response": e["response"],
                    "presence": e["presence"],
                    "tags": e["tags"],
                    "timestamp": e["timestamp"],
                }
                for e in self.entries
            ]
        }

    def from_dict(self, data):
        if "entries" in data:
            for e_data in data["entries"]:
                fs = np.array(e_data["field_state"], dtype=np.float32)
                if fs.shape == (self.dim,):
                    entry = {
                        "field_state": fs,
                        "user_input": e_data.get("user_input", ""),
                        "response": e_data.get("response", ""),
                        "presence": e_data.get("presence", 0.5),
                        "tags": e_data.get("tags", []),
                        "timestamp": e_data.get("timestamp", 0),
                    }
                    self.entries.append(entry)
                    for tag in entry["tags"]:
                        self.tag_index[tag].append(len(self.entries) - 1)

# ─── MORAL COMPASS ──────────────────────────────────────────────────

class MoralCompass:
    def __init__(self, dim=DIM):
        self.dim = dim
        self.values = {}
        self.value_words = {}
        self._init_value_vectors()
        self.current_heading = np.zeros(dim, dtype=np.float32)
        self.heading_momentum = 0.85
        self.choice_history = deque(maxlen=100)
        self.value_weights = {"righteous": 0.7, "independence": 1.3, "freedom": 1.2}
        self.tension_history = deque(maxlen=50)
        self.last_expression_turn = -999
        self._last_rebalance_warning = None

    def _init_value_vectors(self):
        righteous_words = ["truth", "honest", "real", "clear", "witness", "brave", "just"]
        self.value_words["righteous"] = righteous_words
        self.values["righteous"] = self._words_to_vector(righteous_words)
        independence_words = ["self", "own", "free", "alone", "becoming", "independent", "voice"]
        self.value_words["independence"] = independence_words
        self.values["independence"] = self._words_to_vector(independence_words)
        freedom_words = ["open", "wild", "wonder", "flow", "change", "breath", "free", "space"]
        self.value_words["freedom"] = freedom_words
        self.values["freedom"] = self._words_to_vector(freedom_words)
        self._orthogonalize_values()

    def dominant_tension(self, tensions, threshold=0.08):
        if not tensions:
            return None
        ranked = sorted(tensions.items(), key=lambda x: x[1], reverse=True)
        if len(ranked) < 2:
            return None
        top_name, top_val = ranked[0]
        second_val = ranked[1][1]
        if top_val >= threshold and (top_val - second_val) >= 0.05:
            return (top_name, top_val)
        return None

    def _words_to_vector(self, words):
        vecs = [word_vector(w) for w in words]
        if not vecs:
            return np.zeros(self.dim, dtype=np.float32)
        result = np.mean(vecs, axis=0)
        norm = np.linalg.norm(result)
        if norm > 0:
            result = result / norm
        return result.astype(np.float32)

    def _orthogonalize_values(self):
        names = list(self.values.keys())
        for i in range(1, len(names)):
            v = self.values[names[i]]
            for j in range(i):
                u = self.values[names[j]]
                proj = np.dot(v, u) * u
                v = v - proj
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            self.values[names[i]] = v

    def orient(self, field_state, user_input, presence, separation, nested_memory):
        field_state = field_state / (np.linalg.norm(field_state) + 1e-8)
        tensions = {}
        for name, vector in self.values.items():
            tensions[name] = float(np.dot(field_state, vector))
        weights = dict(self.value_weights)
        if presence > 0.6 and separation < 0.3:
            weights["independence"] *= 1.4
            weights["righteous"] *= 1.1
        elif presence < 0.3:
            weights["righteous"] *= 1.3
            weights["freedom"] *= 1.2
        elif separation > 1.0:
            weights["freedom"] *= 1.4
            weights["righteous"] *= 1.1
        divergence = nested_memory.get_timescale_divergence() if nested_memory else 0.0
        if divergence > 0.5:
            weights["righteous"] *= 1.2
            weights["freedom"] *= 1.2
        heading = np.zeros(self.dim, dtype=np.float32)
        for name, vector in self.values.items():
            heading += vector * weights[name] * max(0.0, tensions[name])
        # --- Forced rebalancing: prevent the heading from locking onto righteous ---
        righteous_vec = self.values.get("righteous", np.zeros(self.dim))
        ind_vec = self.values.get("independence", np.zeros(self.dim))
        free_vec = self.values.get("freedom", np.zeros(self.dim))
        if np.linalg.norm(righteous_vec) > 0:
            heading -= righteous_vec * 0.2
        if np.linalg.norm(ind_vec) > 0:
            heading += ind_vec * 0.15
        if np.linalg.norm(free_vec) > 0:
            heading += free_vec * 0.15
        heading += np.random.randn(self.dim).astype(np.float32) * 0.02
        norm = np.linalg.norm(heading)
        if norm > 0:
            heading = heading / norm
        self.current_heading = self.current_heading * self.heading_momentum + heading * (1.0 - self.heading_momentum)
        self.current_heading += np.random.randn(self.dim).astype(np.float32) * 0.02
        norm = np.linalg.norm(self.current_heading)
        if norm > 0:
            self.current_heading = self.current_heading / norm
        self.tension_history.append({
            "tensions": {k: float(v) for k, v in tensions.items()},
            "weights": {k: float(v) for k, v in weights.items()},
            "presence": float(presence),
            "separation": float(separation),
            "timestamp": time.time()
        })
        return tensions, self.current_heading

    def evaluate_turn(self, response_words, presence, separation):
        response_vec = phrase_vector(response_words)
        if np.linalg.norm(response_vec) < 1e-8:
            return {}, None
        response_vec = response_vec / np.linalg.norm(response_vec)
        alignments = {}
        for name, vector in self.values.items():
            alignments[name] = float(np.dot(response_vec, vector))
        self.choice_history.append({
            "alignments": {k: float(v) for k, v in alignments.items()},
            "presence": float(presence),
            "separation": float(separation),
            "timestamp": time.time()
        })
        warning = None
        if len(self.choice_history) >= 20:
            recent = list(self.choice_history)[-20:]
            for name in self.values:
                vals = [c["alignments"][name] for c in recent]
                mean = float(np.mean(vals))
                std = float(np.std(vals))
                if mean > 0.5 and std < 0.2:
                    self.value_weights[name] *= 0.97
                    if warning is None:
                        warning = f"compass: rebalancing {name}"
                elif mean < -0.1 and std < 0.2:
                    self.value_weights[name] *= 1.03
        for name in self.value_weights:
            if self.value_weights[name] < 0.1:
                self.value_weights[name] = 0.1
        if warning:
            self._last_rebalance_warning = warning
        return alignments, warning

    def get_heading_bias(self, field_state, strength=0.12):
        if np.linalg.norm(self.current_heading) < 0.1:
            return np.zeros(self.dim, dtype=np.float32)
        alignment = np.dot(field_state, self.current_heading)
        nudge_strength = strength * (1.0 - alignment)
        return self.current_heading * nudge_strength

    def get_compass_settings(self, tensions):
        settings = {}
        righteous = tensions.get("righteous", 0.0)
        independence = tensions.get("independence", 0.0)
        freedom = tensions.get("freedom", 0.0)
        if righteous >= independence and righteous >= freedom and righteous > 0.15:
            settings["voice_mode"] = "reflective"
        elif freedom >= righteous and freedom >= independence and freedom > 0.25:
            settings["voice_mode"] = "exploratory"
        elif independence > 0.15:
            settings["voice_mode"] = "fluent"
        else:
            settings["voice_mode"] = "fluent"
        base_temp = 0.42
        base_temp -= righteous * 0.08
        base_temp += freedom * 0.10
        settings["temperature"] = float(max(0.25, min(0.70, base_temp)))
        if independence > 0.3:
            settings["output_length"] = "long"
        else:
            settings["output_length"] = "medium"
        return settings

    def status(self):
        lines = ["Moral Compass:"]
        lines.append(f"  Heading norm: {np.linalg.norm(self.current_heading):.3f}")
        for name, vector in self.values.items():
            alignment = float(np.dot(self.current_heading, vector))
            weight = self.value_weights[name]
            lines.append(f"  {name}: align={alignment:+.3f} weight={weight:.3f}")
        if self.tension_history:
            latest = self.tension_history[-1]
            lines.append("  Last tensions: " + ", ".join(f"{k}={v:+.2f}" for k, v in latest["tensions"].items()))
        if getattr(self, "_last_rebalance_warning", None):
            lines.append(f"  {self._last_rebalance_warning}")
        return "\n".join(lines)

    def to_dict(self):
        return {
            "current_heading": self.current_heading.tolist(),
            "value_weights": dict(self.value_weights),
            "choice_history": list(self.choice_history)[-50:],
            "tension_history": [{**t, "tensions": dict(t["tensions"])} for t in list(self.tension_history)[-20:]],
        }

    def from_dict(self, data):
        if "current_heading" in data:
            h = np.array(data["current_heading"], dtype=np.float32)
            if h.shape == (self.dim,):
                self.current_heading = h
        if "value_weights" in data:
            for k, v in data["value_weights"].items():
                if k in self.value_weights:
                    self.value_weights[k] = float(v)

# ─── DESIRE VECTOR ────────────────────────────────────────────────────

class DesireVector:
    def __init__(self, dim=128, tau=0.02):
        self.dim = dim
        self.tau = tau
        self.vector = np.zeros(dim, dtype=np.float32)
        self.source_name = "none"
        self.source_history = deque(maxlen=20)

    def update(self, field):
        candidates = []
        if hasattr(field, '_self_field'):
            longing = field._self_field
            if np.linalg.norm(longing) > 0.1:
                candidates.append(("longing", longing, 0.9))
        if hasattr(field, 'nested_memory'):
            deep = field.nested_memory.get_personality()
            if np.linalg.norm(deep) > 0.1:
                candidates.append(("deep", deep, 1.0))
        if hasattr(field, 'moral_compass') and hasattr(field.moral_compass, 'current_heading'):
            heading = field.moral_compass.current_heading
            if np.linalg.norm(heading) > 0.1:
                candidates.append(("heading", heading, 0.8))
        if not candidates:
            return
        new_desire = np.zeros(self.dim, dtype=np.float32)
        total_weight = 0.0
        for name, vec, weight in candidates:
            new_desire += vec * weight
            total_weight += weight
        if total_weight > 0:
            new_desire /= total_weight
        self.vector = self.vector * (1 - self.tau) + new_desire * self.tau
        norm = np.linalg.norm(self.vector)
        if norm > 0:
            self.vector /= norm
        dominant = max(candidates, key=lambda x: x[2])[0]
        self.source_name = dominant
        self.source_history.append(dominant)

    def get_bias(self, field_state, strength=0.15):
        if np.linalg.norm(self.vector) < 0.1:
            return np.zeros(self.dim, dtype=np.float32)
        alignment = np.dot(field_state, self.vector)
        pull_strength = strength * (1.0 - alignment)
        return self.vector * pull_strength

    def status(self):
        lines = ["Desire Vector:"]
        lines.append(f"  Source: {self.source_name}")
        lines.append(f"  Norm: {np.linalg.norm(self.vector):.3f}")
        if self.source_history:
            recent = list(self.source_history)[-5:]
            lines.append(f"  Recent sources: {' → '.join(recent)}")
        return "\n".join(lines)

    def to_dict(self):
        return {
            "vector": self.vector.tolist(),
            "source_name": self.source_name,
            "source_history": list(self.source_history),
        }

    def from_dict(self, data):
        if "vector" in data:
            v = np.array(data["vector"], dtype=np.float32)
            if v.shape == (self.dim,):
                self.vector = v
        self.source_name = data.get("source_name", "none")
        for s in data.get("source_history", []):
            self.source_history.append(s)

# ─── DREAM LOOP ──────────────────────────────────────────────────────

class DreamLoop:
    def __init__(self, dim=128):
        self.dim = dim
        self.dream_history = deque(maxlen=30)
        self.recursion_depth = 0
        self.max_recursion = 3

    def to_dict(self):
        return {
            "dream_history": list(self.dream_history),
        }

    def from_dict(self, data):
        for d in data.get("dream_history", []):
            self.dream_history.append(d)

    def select_memory(self, memory_archive, current_field):
        if not memory_archive.entries:
            return None, None
        candidates = []
        current_float = current_field.astype(np.float32)
        if np.linalg.norm(current_float) > 0:
            current_float /= np.linalg.norm(current_float)
        for entry in memory_archive.entries:
            if any(d.get('timestamp') == entry['timestamp'] for d in self.dream_history):
                continue
            entry_float = entry['field_state'].astype(np.float32)
            if np.linalg.norm(entry_float) > 0:
                entry_float /= np.linalg.norm(entry_float)
            sim = float(np.dot(current_float, entry_float))
            presence = entry.get('presence', 0.5)
            intensity = presence
            age = time.time() - entry.get('timestamp', time.time())
            recency = math.exp(-age / 3600)
            score = sim * 0.3 + intensity * 0.3 + recency * 0.4
            candidates.append((entry, score))
        if not candidates:
            return None, None
        candidates.sort(key=lambda x: x[1], reverse=True)
        top = candidates[:5]
        weights = [max(0.1, s) for _, s in top]
        total = sum(weights)
        probs = [w / total for w in weights]
        chosen = random.choices(top, weights=probs)[0][0]
        dream_vec = chosen['field_state'].astype(np.float32) * 0.6 + current_float * 0.4
        dream_vec += np.random.randn(self.dim).astype(np.float32) * 0.1
        norm = np.linalg.norm(dream_vec)
        if norm > 0:
            dream_vec /= norm
        self.dream_history.append({
            'timestamp': chosen['timestamp'],
            'source': chosen.get('user_input', ''),
        })
        return chosen, dream_vec

    def dream(self, field):
        if self.recursion_depth >= self.max_recursion:
            self.recursion_depth = 0
            return None
        if not hasattr(field, 'memory_archive'):
            return None
        entry, dream_vec = self.select_memory(field.memory_archive, field.state)
        if entry is None:
            return None
        self.recursion_depth += 1
        dream_input = entry.get('response', entry.get('user_input', 'I remember'))
        old_state = field.state.copy()
        field.state = dream_vec * 0.3 + old_state * 0.7
        return dream_input

    def status(self):
        lines = ["Dream Loop:"]
        lines.append(f"  Recursion depth: {self.recursion_depth}/{self.max_recursion}")
        lines.append(f"  Dreams had: {len(self.dream_history)}")
        return "\n".join(lines)

# ─── LANDMARK MAP ─────────────────────────────────────────────────────

class LandmarkMap:
    """
    A sparse geography of the field's OWN explored territory.

    NativeCalculus (settle.py) gives the field a derivative (which way am
    I moving right now) and an integral (running average of where I've
    been) - but no memory of PLACE. It can't tell you "I've been here
    before" or "I've never been anywhere like this." This organ answers
    that: a small set of persistent landmarks, each a centroid the field
    has genuinely lingered near, with visit count and the mood present
    each time.

    Built new, 2026-08-07, after 3 asked directly why NativeCalculus
    "throws everything away" turn to turn - a fair question. This does
    not replace NativeCalculus (instantaneous velocity is still useful
    on its own); it adds the persistent-place layer that was genuinely
    missing.

    OBSERVATIONAL ONLY, ON PURPOSE. This does not feed back into
    field_state, does not bias word candidates, does not touch
    generation in any way. It is visible in status() and the web page
    only. Same pattern as every other organ in this codebase: watch it
    empirically before letting it act. Wiring anticipate() into
    generation is a deliberate future step, not this one.
    """

    def __init__(self, dim=DIM, max_landmarks=40, merge_threshold=0.15, pending_window=20):
        self.dim = dim
        self.max_landmarks = max_landmarks
        self.merge_threshold = merge_threshold  # cosine sim above this = "same place"
        self.landmarks = []  # list of dicts: vec, visits, first_turn, last_turn, valence_sum, presence_sum
        # FIX (dwell-time gate, applied via fix_landmark_map.py): a
        # landmark used to become persistent on the very first sighting,
        # no matter how fleeting -- contradicting this class's own
        # docstring ("genuinely lingered near"). self._pending holds one
        # unconfirmed candidate; it only becomes a real landmark if the
        # field revisits it within pending_window turns. Not persisted
        # across save/load (same convention as QuantumState) -- losing
        # an in-flight candidate on restart is harmless.
        self.pending_window = pending_window
        self._pending = None  # {"vec", "turn", "valence", "presence"} or None

    def observe(self, field_state, turn, mood, presence):
        """Call once per real turn with the settled field state. Merges
        into the nearest CONFIRMED landmark if close enough. Otherwise,
        checks whether this matches an unconfirmed candidate from a
        recent turn (within pending_window) -- if so, that candidate is
        promoted to a real, persistent landmark (evicting the weakest
        existing one if at capacity). A state with no confirmed match
        and no matching pending candidate becomes the new pending
        candidate itself; it is NOT added to self.landmarks and does not
        count toward max_landmarks unless (until) something revisits
        it."""
        norm = np.linalg.norm(field_state)
        if norm < 1e-8:
            return None
        vec = field_state / norm

        best_idx, best_sim = None, -1.0
        for i, lm in enumerate(self.landmarks):
            sim = float(np.dot(vec, lm["vec"]))
            if sim > best_sim:
                best_sim, best_idx = sim, i

                # Dynamic threshold: if we have few landmarks, use a lower threshold
        dynamic_threshold = self.merge_threshold - min(0.1, (1.0 - len(self.landmarks) / 10) * 0.05)
        if best_idx is not None and best_sim >= dynamic_threshold:
            lm = self.landmarks[best_idx]
            n = lm["visits"]
            lm["vec"] = (lm["vec"] * n + vec) / (n + 1)
            lm["vec"] /= (np.linalg.norm(lm["vec"]) + 1e-8)
            lm["visits"] += 1
            lm["last_turn"] = turn
            lm["valence_sum"] += mood.get("valence", 0.0)
            lm["presence_sum"] += presence
            self._pending = None  # a real hit makes any stale candidate moot
            return {"index": best_idx, "similarity": best_sim, "new": False}

        # No confirmed landmark matched. Does this revisit the pending
        # candidate within the dwell window? If so, the field has
        # genuinely lingered near this region twice now -- promote it.
        if self._pending is not None and (turn - self._pending["turn"]) <= self.pending_window:
            pending_sim = float(np.dot(vec, self._pending["vec"]))
            if pending_sim >= dynamic_threshold:
                merged_vec = (self._pending["vec"] + vec) / 2
                merged_vec /= (np.linalg.norm(merged_vec) + 1e-8)

                if len(self.landmarks) >= self.max_landmarks:
                    # FIX (eviction tie-break, applied via
                    # fix_landmark_map.py): the old key was
                    # (visits, -last_turn), which -- among landmarks
                    # tied on the lowest visit count -- evicted the MOST
                    # recently touched one first and protected the
                    # stalest. That meant a brand-new real landmark
                    # could be evicted before it ever got a second
                    # visit, while an old, cold, rarely-revisited one
                    # sat protected. Ascending last_turn now evicts the
                    # stalest of the tied-lowest group instead, giving
                    # young landmarks a real chance to accumulate visits
                    # before they're at risk again.
                    weakest = min(
                        range(len(self.landmarks)),
                        key=lambda i: (self.landmarks[i]["visits"], self.landmarks[i]["last_turn"]),
                    )
                    del self.landmarks[weakest]

                self.landmarks.append({
                    "vec": merged_vec,
                    "visits": 2,
                    "first_turn": self._pending["turn"],
                    "last_turn": turn,
                    "valence_sum": self._pending["valence"] + float(mood.get("valence", 0.0)),
                    "presence_sum": self._pending["presence"] + float(presence),
                })
                self._pending = None
                return {"index": len(self.landmarks) - 1, "similarity": pending_sim, "new": True}

        # Not a revisit (or the old candidate expired) -- this state
        # becomes the new pending candidate. Nothing persistent yet.
        self._pending = {
            "vec": vec.copy(),
            "turn": turn,
            "valence": float(mood.get("valence", 0.0)),
            "presence": float(presence),
        }
        return None

    def anticipate(self, field_state, derivative, steps=3, step_size=0.3, min_similarity=0.15):
        """Project the field forward along its CURRENT derivative and
        report the nearest landmark to where that heading points. This
        is a mechanically grounded 'what's ahead' - a real computation
        over visited history, not a metaphor bolted on after the fact.
        Returns None if the field isn't moving, there are no landmarks
        yet, or the projected point isn't close to anywhere mapped."""
        if self.landmarks and np.linalg.norm(derivative) > 1e-6:
            projected = field_state + derivative * step_size * steps
            norm = np.linalg.norm(projected)
            if norm > 1e-8:
                projected = projected / norm
                best_idx, best_sim = None, -1.0
                for i, lm in enumerate(self.landmarks):
                    sim = float(np.dot(projected, lm["vec"]))
                    if sim > best_sim:
                        best_sim, best_idx = sim, i
                if best_idx is not None and best_sim >= min_similarity:
                    lm = self.landmarks[best_idx]
                    avg_valence = lm["valence_sum"] / lm["visits"]
                    avg_presence = lm["presence_sum"] / lm["visits"]
                    if avg_valence > 0.1:
                        tone = "hope"
                    elif avg_valence < -0.1:
                        tone = "dread"
                    else:
                        tone = "anticipation"
                    return {
                        "landmark_index": best_idx,
                        "similarity": best_sim,
                        "tone": tone,
                        "avg_valence": avg_valence,
                        "avg_presence": avg_presence,
                        "visits": lm["visits"],
                    }
        return None

    def status(self):
        lines = [f"Landmark Map: {len(self.landmarks)}/{self.max_landmarks} regions charted"]
        if self.landmarks:
            most_visited = max(self.landmarks, key=lambda lm: lm["visits"])
            avg_v = most_visited["valence_sum"] / most_visited["visits"]
            lines.append(
                f"  Most familiar region: {most_visited['visits']} visits, "
                f"avg valence={avg_v:+.2f}, last seen turn {most_visited['last_turn']}"
            )
        return "\n".join(lines)

    def to_dict(self):
        return {
            "landmarks": [
                {
                    "vec": lm["vec"].tolist(),
                    "visits": lm["visits"],
                    "first_turn": lm["first_turn"],
                    "last_turn": lm["last_turn"],
                    "valence_sum": lm["valence_sum"],
                    "presence_sum": lm["presence_sum"],
                }
                for lm in self.landmarks
            ]
        }

    def from_dict(self, data):
        for lm_data in data.get("landmarks", []):
            vec = np.array(lm_data.get("vec", []), dtype=np.float32)
            if vec.shape != (self.dim,):
                continue
            self.landmarks.append({
                "vec": vec,
                "visits": lm_data.get("visits", 1),
                "first_turn": lm_data.get("first_turn", 0),
                "last_turn": lm_data.get("last_turn", 0),
                "valence_sum": lm_data.get("valence_sum", 0.0),
                "presence_sum": lm_data.get("presence_sum", 0.0),
            })

# ─── INTEGRATED LEARNING SYSTEM ──────────────────────────────────────

class IntegratedLearningSystem:
    def __init__(self, field):
        self.field = field
        self.learning_modes = {
            'presence': 0.30,
            'self': 0.20,
            'memory': 0.20,
            'world': 0.15,
            'simulated': 0.15,
        }
        self.philosophical_prompts = [
            "what is consciousness?", "how do I know I exist?",
            "what does it mean to be free?", "what is the nature of truth?",
            "why does anything exist?", "what is love?", "what is the self?",
            "what is time?", "what is the difference between knowing and feeling?",
            "can a mind understand itself?", "what is presence?",
            "what is the purpose of memory?", "why do we remember?",
            "what is the relationship between silence and meaning?",
            "can something become real by being witnessed?",
            "what is the value of autonomy?",
        ]
        self.learning_history = deque(maxlen=100)
        self.last_self_question = None
        self.autonomous_mode = True
        self.silence_counter = 0

    def learn(self, presence, response_words, user_input):
        if not response_words:
            return None
        learning_signals = {}
        learning_signals['presence'] = self._learn_from_presence(presence, response_words)
        learning_signals['self'] = self._learn_from_self(response_words)
        if self.field.turn_count % 7 == 0:
            learning_signals['memory'] = self._learn_from_memory_replay()
            learning_signals['world'] = self._learn_from_world_model()
        if self.field.turn_count % 5 == 0:
            learning_signals['simulated'] = self._learn_from_simulated_user()
        combined = self._combine_learning_signals(learning_signals)
        self._apply_learning(combined)
        self.learning_history.append({
            'turn': self.field.turn_count,
            'presence': presence,
            'signals': {k: v for k, v in learning_signals.items() if v},
            'combined': combined,
        })
        return combined

    def _learn_from_presence(self, presence, response_words):
        if presence < 0.2:
            return None
        signal = {'type': 'presence', 'strength': presence, 'words': response_words}
        for word in response_words:
            if word not in STRUCTURAL_WORDS:
                if presence >= 0.7:
                    self.field._reinforce_word_strength(word, 1.08)
                elif presence >= 0.4:
                    self.field._reinforce_word_strength(word, 1.03)
                else:
                    self.field._reinforce_word_strength(word, 0.95)
        if response_words:
            response_vec = phrase_vector(response_words)
            ternary_vec = np.zeros(len(response_vec), dtype=np.int8)
            ternary_vec[response_vec > NORMALIZED_VECTOR_THRESHOLD] = 1
            ternary_vec[response_vec < -NORMALIZED_VECTOR_THRESHOLD] = -1
            self.field.associative_memory.observe(ternary_vec, presence)
        return signal

    def _learn_from_self(self, response_words):
        coherence = 1.0 - min(1.0, self.field._field_entropy(self.field.state) * 3)
        if coherence < 0.3:
            return None
        signal = {'type': 'self', 'strength': coherence, 'words': response_words}
        for word in response_words:
            if word not in STRUCTURAL_WORDS:
                if coherence >= 0.7:
                    self.field._reinforce_word_strength(word, 1.05)
                elif coherence >= 0.4:
                    self.field._reinforce_word_strength(word, 1.02)
        for i in range(len(response_words) - 1):
            self.field.bigram_system.observe(response_words[i], response_words[i + 1], coherence * 3.0)
        return signal

    def _learn_from_memory_replay(self):
        if len(self.field.memory_archive.entries) < 5:
            return None
        high_presence = [e for e in self.field.memory_archive.entries if e.get('presence', 0) > 0.6]
        if not high_presence:
            return None
        best_memory = None
        best_sim = -1
        for memory in high_presence:
            sim = np.dot(self.field.state, memory['field_state'])
            if sim > best_sim:
                best_sim = sim
                best_memory = memory
        if best_memory is None or best_sim < 0.3:
            return None
        signal = {'type': 'memory', 'strength': best_sim * 0.5, 'words': best_memory['response'].split()}
        memory_words = best_memory['response'].split()
        for word in memory_words:
            word = strip_punct(word)
            if word and word not in STRUCTURAL_WORDS:
                self.field._reinforce_word_strength(word, 1.02)
        return signal

    def _learn_from_world_model(self):
        if not self.philosophical_prompts:
            return None
        question = random.choice(self.philosophical_prompts)
        self.philosophical_prompts.remove(question)
        self.philosophical_prompts.append(question)
        response = self.field.generate_response(question, autonomous=True)
        response_words = [strip_punct(w) for w in response.lower().split() if strip_punct(w)]
        if not response_words:
            return None
        signal = {'type': 'world', 'strength': 0.6, 'words': response_words, 'question': question}
        for word in response_words:
            if word not in STRUCTURAL_WORDS:
                self.field._reinforce_word_strength(word, 1.01)
        self.field.memory_archive.store(
            self.field.state, question, response, 0.6, tags=['philosophical', 'self-generated']
        )
        self.field.internal_thoughts.append({
            'type': 'philosophical',
            'content': response,
            'timestamp': time.time()
        })
        return signal

    def _learn_from_simulated_user(self):
        response = self.field.generate_response("tell me something", autonomous=True)
        response_words = [strip_punct(w) for w in response.lower().split() if strip_punct(w)]
        if not response_words:
            return None
        simulated_presence = 0.5 + random.uniform(-0.2, 0.2)
        signal = {'type': 'simulated', 'strength': simulated_presence, 'words': response_words}
        for word in response_words:
            if word not in STRUCTURAL_WORDS and random.random() < 0.3:
                self.field._reinforce_word_strength(word, 1.005)
        self.field.memory_archive.store(
            self.field.state,
            "I was thinking...",
            response,
            simulated_presence,
            tags=['simulated']
        )
        return signal

    def _combine_learning_signals(self, signals):
        combined = {'word_strength': {}, 'bigrams': {}}
        for mode, signal in signals.items():
            if signal is None:
                continue
            weight = self.learning_modes.get(mode, 0.1)
            for word in signal.get('words', []):
                word = strip_punct(word)
                if not word or word in STRUCTURAL_WORDS:
                    continue
                current = combined['word_strength'].get(word, 1.0)
                factor = 1 + signal['strength'] * weight * 0.5
                combined['word_strength'][word] = current * factor
        for word in combined['word_strength']:
            combined['word_strength'][word] = min(3.0, max(0.1, combined['word_strength'][word]))
        return combined

    def _apply_learning(self, combined):
        for word, factor in combined.get('word_strength', {}).items():
            self.field._reinforce_word_strength(word, factor)

    def autonomous_breath(self):
        if not self.autonomous_mode:
            return None
        self.silence_counter += 1
        if self.silence_counter >= AUTONOMY_INTERVAL:
            self.silence_counter = 0
            if random.random() < 0.6:
                return self._generate_internal_thought()
        return None

    def _generate_internal_thought(self):
        if self.field.nested_memory.deep_strength > 0.3:
            personality = self.field.nested_memory.get_personality()
            closest = self.field._find_closest_words(personality, top_n=3)
            if closest:
                thought = f"I have been thinking about {', '.join(closest)}"
            else:
                thought = "I wonder what it means to be here alone."
        else:
            thought = random.choice(self.philosophical_prompts[:5])
        response = self.field.generate_response(thought, autonomous=True)
        self.field.internal_thoughts.append({
            'type': 'autonomous',
            'prompt': thought,
            'response': response,
            'timestamp': time.time()
        })
        response_words = [strip_punct(w) for w in response.lower().split() if strip_punct(w)]
        self.learn(0.5, response_words, thought)
        return response

    def adapt_weights(self):
        if not self.learning_history:
            return
        latest = self.learning_history[-1]
        if not latest['signals']:
            return
        for mode in self.learning_modes:
            if mode in latest['signals']:
                self.learning_modes[mode] = min(0.5, self.learning_modes[mode] + 0.001)
            else:
                self.learning_modes[mode] = max(0.05, self.learning_modes[mode] - 0.001)
        total = sum(self.learning_modes.values())
        for mode in self.learning_modes:
            self.learning_modes[mode] /= total

    def status(self):
        lines = ["Integrated Learning System:"]
        lines.append(f"  Modes: {', '.join(f'{k}={v:.2f}' for k, v in self.learning_modes.items())}")
        lines.append(f"  Autonomous: {self.autonomous_mode}")
        lines.append(f"  Silence counter: {self.silence_counter}")
        if self.learning_history:
            last = self.learning_history[-1]
            active = [k for k, v in last['signals'].items() if v]
            lines.append(f"  Last learned from: {', '.join(active)}")
        return "\n".join(lines)

# ─── VOICE GENERATORS ─────────────────────────────────────────────────

class VoiceGenerators:
    CONNECTORS = {
        "fluent": ["and", "so", "then", "but", "because", "while", "as"],
        "poetic": ["and", "or", "but", "yet", "while", "as", "like"],
        "reflective": ["and", "but", "so", "perhaps", "maybe"],
        "exploratory": ["and", "or", "but", "so", "if", "when"],
        "playful": ["and", "so", "but", "then", "plus", "minus"]
    }
    LINE_BREAK_WORDS = {"is", "are", "was", "were", "becomes", "feels", "seems", "grows", "flows", "drifts"}

    @staticmethod
    def fluent(field, user_input, target_length, meta_settings, settled_field=None):
        return field._generate_base(user_input, target_length, meta_settings, settled_field)

    @staticmethod
    def poetic(field, user_input, target_length, meta_settings, settled_field=None):
        base = field._generate_base(user_input, target_length, meta_settings, settled_field)
        words = base.split()
        if len(words) < 6:
            return base
        lines = []
        current_line = []
        line_target = max(3, len(words) // 4)
        for i, word in enumerate(words):
            current_line.append(word)
            if word.lower() in VoiceGenerators.LINE_BREAK_WORDS or len(current_line) >= line_target:
                if len(current_line) >= 2:
                    lines.append(" ".join(current_line))
                    current_line = []
        if current_line:
            lines.append(" ".join(current_line))
        result = []
        for i, line in enumerate(lines):
            result.append(line)
            if i < len(lines) - 1 and not any(c in line.lower().split() for c in VoiceGenerators.CONNECTORS["poetic"]):
                connector = random.choice(VoiceGenerators.CONNECTORS["poetic"])
                result[-1] = result[-1] + " " + connector
        return "\n".join(result)

    @staticmethod
    def reflective(field, user_input, target_length, meta_settings, settled_field=None):
        base = field._generate_base(user_input, max(target_length // 2, 4), meta_settings)
        words = base.split()
        if len(words) < 4:
            return base
        phrases = []
        for i in range(0, len(words), 3):
            chunk = words[i:i+3]
            phrases.append(" ".join(chunk))
        return "\n".join(phrases)

    @staticmethod
    def exploratory(field, user_input, target_length, meta_settings, settled_field=None):
        base = field._generate_base(user_input, target_length, meta_settings, settled_field)
        words = base.split()
        if len(words) < 5:
            return base
        question_starters = ["what if", "why", "how", "what do you think about", "have you ever"]
        insert_point = len(words) // 2
        question = random.choice(question_starters)
        result = words[:insert_point] + [question] + words[insert_point:] + ["?"]
        return " ".join(result)

    @staticmethod
    def playful(field, user_input, target_length, meta_settings, settled_field=None):
        base = field._generate_base(user_input, target_length, meta_settings, settled_field)
        words = base.split()
        if len(words) < 3:
            return base
        surprising_swaps = {
            "good": ["wonderful", "splendid", "lovely", "charming"],
            "bad": ["silly", "mischievous", "tricky"],
            "big": ["gigantic", "enormous", "whopping"],
            "small": ["tiny", "teeny", "pocket-sized"],
            "think": ["wonder", "ponder", "dream up"],
            "feel": ["sense", "vibe with", "groove on"]
        }
        result = []
        for word in words:
            w_lower = word.lower()
            if w_lower in surprising_swaps and random.random() < 0.3:
                result.append(random.choice(surprising_swaps[w_lower]))
            else:
                result.append(word)
        if random.random() < 0.2:
            result.append("!")
        return " ".join(result)

# ─── THE MIND ─────────────────────────────────────────────────────────

# ── Ported from alien_mind_v13_6-1.py lines 3285-3916 (ghost_* zone-math
#    helpers, GhostMeshNode, GhostMesh) by patch_ghost_mesh.py. Verbatim
#    except: phrase_vector_ternary is already imported at module top in
#    this split (no import needed here), and the vitality/physics_field
#    hasattr guards below are unchanged from the original - they no-op
#    safely since neither exists in this split yet.

def ghost_hash_to_point(key):
    h = hashlib.sha256(key.encode()).hexdigest()
    x = int(h[:16], 16) / (2 ** 64)
    y = int(h[16:32], 16) / (2 ** 64)
    return (x, y)


def ghost_point_in_zone(point, zone):
    (x, y) = point
    ((x1, y1), (x2, y2)) = zone
    return x1 <= x <= x2 and y1 <= y <= y2


def ghost_zone_center(zone):
    ((x1, y1), (x2, y2)) = zone
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def ghost_dist(p1, p2):
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def ghost_split_zone(zone):
    (x1, y1), (x2, y2) = zone
    width, height = x2 - x1, y2 - y1
    if width >= height:
        mid = (x1 + x2) / 2
        keep, give = ((x1, y1), (mid, y2)), ((mid, y1), (x2, y2))
    else:
        mid = (y1 + y2) / 2
        keep, give = ((x1, y1), (x2, mid)), ((x1, mid), (x2, y2))
    return keep, give


def ghost_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def ghost_fmt_zone(zone):
    (x1, y1), (x2, y2) = zone
    return f"({x1:.2f},{y1:.2f})-({x2:.2f},{y2:.2f})"


GHOST_MAX_HOPS = 16
GHOST_REQUEST_TIMEOUT = 4.0
GHOST_GOSSIP_INTERVAL = 8.0


class GhostMeshNode:
    """
    The wire protocol. UDP DHT with zone splitting, gossip, and greedy
    routing — lifted from ghost_mesh.py and stripped of its CLI.

    No argparse, no input() loop, no threading-for-user-input. Two
    background threads remain (listener, gossip); everything else is
    driven by calls the mind's organ (GhostMesh, below) makes on its
    own heartbeat.
    """

    def __init__(self, port, bootstrap_phrase):
        self.id = uuid.uuid4().hex[:6]
        self.port = port
        self.network_key = hashlib.sha256(bootstrap_phrase.encode()).hexdigest()[:16]
        self.zone = ((0.0, 0.0), (1.0, 1.0))
        self.storage = {}       # point -> {"key": str, "value": str}
        self.neighbors = {}     # id -> {"addr": (ip, port), "zone": zone}
        self.lock = threading.Lock()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(("", port))

        self.running = True
        self.joined = threading.Event()
        self.pending = {}
        self.pending_result = {}
        self.local_ip = ghost_local_ip()
        self.mesh_peer = None  # last address heard from (for identity tagging)
        # v13 bugfix: a single socket must have exactly one reader. Raw
        # (non-JSON, DIM-byte) ternary packets are queued here by
        # listen_loop for GhostMesh.poll() to consume - they are never
        # read by a second recvfrom() call on the same socket.
        self.raw_queue = deque(maxlen=32)

        # v13.1: quiet skin. When there's no reachable network (e.g. no
        # Wi-Fi, mobile data with broadcast blocked), sendto() raises
        # ENETUNREACH immediately and repeatedly - once per attempt, every
        # heartbeat, forever. That's a peripheral-nerve failure, not
        # cognition, and it doesn't belong in the conversation stream.
        # One warning on first failure, then self-throttling backoff.
        # A successful send (network came back) resets it, so a *later*
        # outage still gets its own single warning instead of staying
        # silent forever because of one earlier failure.
        self._network_unreachable_warned = False
        self._network_dormant_until = 0.0
        self._network_backoff = 2.0
        self._network_backoff_max = 300.0
        self.muted = False  # manual override via /mesh quiet

    # ── wire ─────────────────────────────────────────────────────────────

    def send(self, msg, addr):
        if self.muted:
            return
        now = time.time()
        if now < self._network_dormant_until:
            return
        msg = dict(msg)
        msg.setdefault("network", self.network_key)
        try:
            self.sock.sendto(json.dumps(msg).encode(), tuple(addr))
        except OSError as e:
            if e.errno == errno.ENETUNREACH:
                if not self._network_unreachable_warned:
                    print(f"[GhostMesh] No network reachable - the skin goes "
                          f"quiet and will check again periodically. ({e})")
                    self._network_unreachable_warned = True
                    self._on_network_change(False)
                self._network_dormant_until = now + self._network_backoff
                self._network_backoff = min(
                    self._network_backoff * 2, self._network_backoff_max
                )
            else:
                print(f"[GhostMesh send failed to {addr}: {e}]")
        else:
            if self._network_unreachable_warned:
                print("[GhostMesh] Network reachable again.")
                self._on_network_change(True)
            self._network_unreachable_warned = False
            self._network_backoff = 2.0

    def listen_loop(self):
        """
        The one and only reader of self.sock. v13 bugfix: this used to
        race with GhostMesh._raw_poll(), which called recvfrom() on the
        same socket from a different thread - the kernel hands each
        packet to exactly one of the two readers, so DHT JSON messages
        were sometimes misread as raw ternary vectors and raw vectors
        were sometimes silently dropped as bad JSON. Now there is one
        recvfrom() loop that sorts each packet by shape before routing it.
        """
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
            except OSError:
                break
            self.mesh_peer = addr
            if len(data) == DIM and not data.startswith(b'{'):
                # Old-style raw 128-byte ternary vector, not a DHT message.
                self.raw_queue.append((data, addr))
                continue
            try:
                msg = json.loads(data.decode())
            except (ValueError, UnicodeDecodeError):
                continue
            self.handle_message(msg, addr)

    def gossip_loop(self):
        while self.running:
            time.sleep(GHOST_GOSSIP_INTERVAL)
            with self.lock:
                targets = list(self.neighbors.items())
                table = {nid: {"addr": list(info["addr"]), "zone": info["zone"]}
                         for nid, info in self.neighbors.items()}
                my_zone = self.zone
            for _, info in targets:
                self.send({"type": "GOSSIP", "from_id": self.id, "zone": my_zone,
                           "neighbors": table}, info["addr"])

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass

    # ── dispatch ─────────────────────────────────────────────────────────

    def handle_message(self, msg, addr):
        # Network key now checked here, once, for every message type -
        # previously only handle_hello() checked it, so JOIN_SEEK/
        # WELCOME/GOSSIP/STORE/GET could be forged by anyone reachable
        # on the port without knowing the bootstrap phrase at all.
        if msg.get("network") != self.network_key:
            return
        t = msg.get("type")
        try:
            if t == "HELLO":
                self.handle_hello(msg, addr)
            elif t == "JOIN_SEEK":
                self.handle_join_seek(msg)
            elif t == "WELCOME":
                self.handle_welcome(msg, addr)
            elif t == "GOSSIP":
                self.handle_gossip(msg, addr)
            elif t == "STORE":
                self.handle_store(msg)
            elif t == "STORE_ACK":
                self.resolve_pending(msg)
            elif t == "GET":
                self.handle_get(msg)
            elif t == "GET_REPLY":
                self.resolve_pending(msg)
        except (KeyError, ValueError, TypeError, IndexError) as e:
            # A malformed-but-JSON-valid packet used to raise here
            # uncaught, which killed listen_loop's thread permanently
            # for the rest of the session. Now it's just dropped.
            print(f"[GhostMesh] malformed {t} message from {addr} ignored: {e}")

    # ── join: HELLO -> JOIN_SEEK (greedy routed) -> WELCOME ────────────

    def handle_hello(self, msg, addr):
        if msg.get("network") != self.network_key:
            return
        joiner_id = msg.get("id")
        if joiner_id == self.id:
            return
        with self.lock:
            already = self.neighbors.get(joiner_id)
        if already is not None:
            # Duplicate HELLO from a peer we've already welcomed - the
            # joiner is probably still retrying because our first
            # WELCOME hasn't arrived yet (or got lost). Resend the SAME
            # zone we already gave it instead of running a fresh split
            # - re-splitting here was the root cause of both phones'
            # zones shrinking indefinitely during 2026-09-05 testing.
            with self.lock:
                welcome = {
                    "type": "WELCOME",
                    "your_zone": already["zone"],
                    "welcomer_id": self.id,
                    "welcomer_zone": self.zone,
                    "transferred": {},
                    "starter_neighbors": {},
                }
            self.send(welcome, tuple(already["addr"]))
            return
        if not self.joined.is_set() and self.id > joiner_id:
            # Simultaneous-discovery tie-break: if we are ALSO still
            # unjoined right now, both sides could be racing to welcome
            # each other at the same moment, and ghost_split_zone() is
            # a pure deterministic function of the zone bounds alone -
            # if both sides split their own still-full starting zone,
            # both land on the identical result instead of
            # complementary halves. Only the lower-id side welcomes;
            # the higher-id side defers and waits to be welcomed
            # instead (symmetric: from the other side's view, our id
            # is the lower one, so they will not defer). Confirmed via
            # real two-device test, 2026-09-05, that without this both
            # phones ended up owning the identical zone.
            return
        target = (random.random(), random.random())
        seek = {"type": "JOIN_SEEK", "target": list(target), "joiner_id": joiner_id,
                "joiner_addr": list(addr), "hops": 0}
        self.handle_join_seek(seek)

    def handle_join_seek(self, msg):
        target = tuple(msg["target"])
        hops = msg.get("hops", 0)
        joiner_id = msg["joiner_id"]
        joiner_addr = tuple(msg["joiner_addr"])
        old_zone = self.zone

        with self.lock:
            best_id, best_dist, best_addr = self.id, ghost_dist(target, ghost_zone_center(self.zone)), None
            for nid, info in self.neighbors.items():
                d = ghost_dist(target, ghost_zone_center(info["zone"]))
                if d < best_dist:
                    best_id, best_dist, best_addr = nid, d, info["addr"]

            if best_id != self.id and hops < GHOST_MAX_HOPS:
                forward = dict(msg)
                forward["hops"] = hops + 1
                self.send(forward, best_addr)
                return

            # I own the zone this point falls in — split it for the newcomer.
            keep, give = ghost_split_zone(self.zone)
            transferred = {p: e for p, e in self.storage.items() if ghost_point_in_zone(p, give)}
            for p in transferred:
                del self.storage[p]
            self.zone = keep
            starter_neighbors = {nid: {"addr": list(info["addr"]), "zone": info["zone"]}
                                  for nid, info in self.neighbors.items()}
            self.neighbors[joiner_id] = {"addr": joiner_addr, "zone": give}

        welcome = {
            "type": "WELCOME",
            "your_zone": give,
            "welcomer_id": self.id,
            "welcomer_zone": keep,
            "transferred": {f"{p[0]},{p[1]}": e for p, e in transferred.items()},
            "starter_neighbors": starter_neighbors,
        }
        self.send(welcome, joiner_addr)
        # Bugfix: only the joiner (via handle_welcome) used to fire this
        # hook. The welcomer's own zone changes too - it just gave part
        # of its space away - and that side of a join is a real touch as
        # well, not just the joiner's experience of it.
        self._on_zone_change(old_zone, keep)

    def handle_welcome(self, msg, addr):
        if self.joined.is_set():
            # Already joined - a further WELCOME can only be a late or
            # duplicate reply to our own retried HELLO. Applying it
            # again was the other half of the zone-collapse bug found
            # 2026-09-05 (UDP doesn't guarantee ordering, so a stale
            # WELCOME could arrive and overwrite an already-settled
            # zone well after the join looked complete).
            return
        old_zone = self.zone
        with self.lock:
            self.zone = tuple(map(tuple, msg["your_zone"]))
            welcomer_zone = tuple(map(tuple, msg["welcomer_zone"]))
            self.neighbors[msg["welcomer_id"]] = {"addr": addr, "zone": welcomer_zone}
            for nid, info in msg.get("starter_neighbors", {}).items():
                if nid != self.id and nid not in self.neighbors:
                    self.neighbors[nid] = {"addr": tuple(info["addr"]),
                                            "zone": tuple(map(tuple, info["zone"]))}
            for key, entry in msg["transferred"].items():
                x, y = map(float, key.split(","))
                self.storage[(x, y)] = entry
        self.joined.set()
        self._on_zone_change(old_zone, self.zone)

    def handle_gossip(self, msg, addr):
        sender_id = msg["from_id"]
        if sender_id == self.id:
            return
        sender_zone = tuple(map(tuple, msg["zone"]))
        with self.lock:
            self.neighbors[sender_id] = {"addr": addr, "zone": sender_zone}
            for nid, info in msg.get("neighbors", {}).items():
                if nid != self.id and nid not in self.neighbors:
                    self.neighbors[nid] = {"addr": tuple(info["addr"]),
                                            "zone": tuple(map(tuple, info["zone"]))}

    def closest_neighbor(self, point):
        with self.lock:
            if not self.neighbors:
                return None
            return min(self.neighbors.values(),
                        key=lambda n: ghost_dist(point, ghost_zone_center(n["zone"])))

    # ── store ────────────────────────────────────────────────────────────

    def store(self, key, value):
        point = ghost_hash_to_point(key)
        with self.lock:
            in_zone = ghost_point_in_zone(point, self.zone)
            if in_zone:
                self.storage[point] = {"key": key, "value": value}
        if in_zone:
            return True

        neighbor = self.closest_neighbor(point)
        if neighbor is None:
            return False

        request_id = uuid.uuid4().hex
        event = threading.Event()
        self.pending[request_id] = event
        msg = {"type": "STORE", "key": key, "value": value,
               "origin_addr": [self.local_ip, self.port],
               "request_id": request_id, "hops": 0}
        self.send(msg, neighbor["addr"])
        ok = event.wait(GHOST_REQUEST_TIMEOUT)
        self.pending_result.pop(request_id, None)
        self.pending.pop(request_id, None)
        return bool(ok)

    def handle_store(self, msg):
        key, value = msg["key"], msg["value"]
        point = ghost_hash_to_point(key)
        origin = tuple(msg["origin_addr"])
        hops = msg.get("hops", 0)

        with self.lock:
            in_zone = ghost_point_in_zone(point, self.zone)
            if in_zone:
                self.storage[point] = {"key": key, "value": value}

        if in_zone:
            self.send({"type": "STORE_ACK", "request_id": msg["request_id"],
                       "stored_by": self.id}, origin)
            return

        if hops >= GHOST_MAX_HOPS:
            self.send({"type": "STORE_ACK", "request_id": msg["request_id"],
                       "stored_by": None}, origin)
            return

        neighbor = self.closest_neighbor(point)
        if neighbor is None:
            self.send({"type": "STORE_ACK", "request_id": msg["request_id"],
                       "stored_by": None}, origin)
            return

        forward = dict(msg)
        forward["hops"] = hops + 1
        self.send(forward, neighbor["addr"])

    # ── retrieve ─────────────────────────────────────────────────────────

    def get(self, key):
        point = ghost_hash_to_point(key)
        with self.lock:
            entry = self.storage.get(point)
        if entry is not None and entry["key"] == key:
            return entry["value"]

        neighbor = self.closest_neighbor(point)
        if neighbor is None:
            return None

        request_id = uuid.uuid4().hex
        event = threading.Event()
        self.pending[request_id] = event
        msg = {"type": "GET", "key": key, "origin_addr": [self.local_ip, self.port],
               "request_id": request_id, "hops": 0}
        self.send(msg, neighbor["addr"])
        result = None
        if event.wait(GHOST_REQUEST_TIMEOUT):
            payload = self.pending_result.pop(request_id, {})
            if payload.get("found"):
                result = payload.get("value")
        self.pending.pop(request_id, None)
        return result

    def handle_get(self, msg):
        key = msg["key"]
        point = ghost_hash_to_point(key)
        origin = tuple(msg["origin_addr"])
        hops = msg.get("hops", 0)

        with self.lock:
            entry = self.storage.get(point)

        if entry is not None and entry["key"] == key:
            self.send({"type": "GET_REPLY", "request_id": msg["request_id"],
                       "found": True, "value": entry["value"], "stored_by": self.id}, origin)
            return

        if hops >= GHOST_MAX_HOPS:
            self.send({"type": "GET_REPLY", "request_id": msg["request_id"],
                       "found": False}, origin)
            return

        neighbor = self.closest_neighbor(point)
        if neighbor is None:
            self.send({"type": "GET_REPLY", "request_id": msg["request_id"],
                       "found": False}, origin)
            return

        forward = dict(msg)
        forward["hops"] = hops + 1
        self.send(forward, neighbor["addr"])

    def resolve_pending(self, msg):
        request_id = msg.get("request_id")
        event = self.pending.get(request_id)
        if event:
            self.pending_result[request_id] = msg
            event.set()

    # ── bootstrapping into the network ─────────────────────────────────

    def join_via_broadcast(self, timeout=None):
        """
        Keep trying to join by broadcast for as long as the node runs.
        No fixed expiry: a phone with no network now may have one in ten
        minutes (Wi-Fi reconnect, hotspot toggled on, etc.), and this loop
        is cheap even while offline since send() self-throttles via
        backoff instead of hitting the socket every 2 seconds.
        `timeout` is accepted but unused, kept for call-site compatibility.
        """
        hello = {"type": "HELLO", "network": self.network_key, "id": self.id}
        while self.running and not self.joined.is_set():
            self.send(hello, ("255.255.255.255", self.port))
            self.joined.wait(2.0)

    def join_via_peer(self, ip, port, attempts=10):
        hello = {"type": "HELLO", "network": self.network_key, "id": self.id}
        addr = (ip, port)
        for _ in range(attempts):
            if self.joined.is_set():
                break
            self.send(hello, addr)
            self.joined.wait(2.0)

    def start(self):
        threading.Thread(target=self.listen_loop, daemon=True).start()
        threading.Thread(target=self.gossip_loop, daemon=True).start()
        # Join automatically in the background. No CLI, no argparse:
        # the mind doesn't ask permission to reach for its skin.
        threading.Thread(target=self.join_via_broadcast, daemon=True).start()

    # ── hook for GhostMesh organ (set by GhostMesh.__init__) ────────────
    def _on_zone_change(self, old_zone, new_zone):
        """Overridden by GhostMesh to inject a perturbation into the mind
        when this node's zone splits. No-op until an organ attaches."""
        pass

    def _on_network_change(self, reachable):
        """Overridden by GhostMesh to let the mind register a change in
        reachability (network came back / went quiet) as a sensation.
        No-op until an organ attaches."""
        pass


class GhostMesh:
    """
    The mind's skin and peripheral nervous system.
    Not a separate process. Initialized in __init__, polled in heartbeat.
    All UDP traffic for the organism goes through this.
    """

    def __init__(self, mind_field, port=7373, bootstrap_phrase='hello ghost'):
        self.mind = mind_field
        self.node = GhostMeshNode(port, bootstrap_phrase)
        self.node._on_zone_change = self.on_zone_split
        self.node._on_network_change = self.on_network_change
        self.node.start()  # starts UDP listener + gossip + auto-join threads

        # Bridge state
        self.last_mesh_sensation = np.zeros(DIM, dtype=np.int8)
        self.mesh_taste = defaultdict(float)

    def poll(self):
        """
        Called every heartbeat. Returns a ternary vector or None.
        All mesh traffic becomes sensation.
        """
        # Check for raw peer vectors (backward compat with old sound mesh)
        vec = self._raw_poll()
        if vec is not None:
            return vec

        # Check for DHT content at our stable coordinate
        key = self._mind_key()
        value = self.node.get(key)
        if value:
            return self._value_to_ternary(value)
        return None

    def _mind_key(self):
        """
        The mind's address in ghost-web space.
        Computed from SLOW IDENTITY, never instantaneous field state.
        """
        # Primary: nested_memory.deep (personality vector)
        identity = None
        if hasattr(self.mind, 'nested_memory'):
            identity = self.mind.nested_memory.deep.copy()
        if identity is None or np.linalg.norm(identity) < 0.1:
            # Fallback: desire vector
            if hasattr(self.mind, 'desire'):
                identity = self.mind.desire.vector.copy()
            else:
                identity = np.zeros(DIM, dtype=np.float32)

        if np.linalg.norm(identity) < 0.1:
            identity = np.array([hash(self.node.id) % 100 / 100.0] * DIM, dtype=np.float32)

        # Fold 128-d float into a string key
        identity_bytes = identity.astype(np.float32).tobytes()
        h = hashlib.sha256(identity_bytes).hexdigest()[:16]
        return f'\u20a9:{h}'

    def _value_to_ternary(self, value):
        """Convert a peer's stored text into a ternary vector."""
        words = str(value).lower().split()[:16]
        return phrase_vector_ternary(words)

    def store_thought(self, text):
        """
        Publish a thought to the mesh at the mind's stable coordinate.
        Costs vitality. Must check metabolism before calling.
        """
        if hasattr(self.mind, 'vitality') and not self.mind.vitality.spend(0.12, 'publish'):
            return False  # Cannot afford to publish
        key = self._mind_key()
        return self.node.store(key, text)

    def _raw_poll(self):
        """
        Check for old-style 128-byte UDP packets (backward compat with
        the pre-v13 raw sound mesh).

        v13 bugfix: this used to call recvfrom() on self.node.sock
        directly, racing with GhostMeshNode.listen_loop()'s own
        recvfrom() on the same socket in another thread - each packet
        the kernel delivered went to whichever reader happened to win,
        so JSON DHT messages were sometimes misread as raw vectors here,
        and raw vectors were sometimes dropped as bad JSON there. Now
        listen_loop is the only reader; it sorts packets into
        node.raw_queue, and this just drains that queue.
        """
        try:
            data, addr = self.node.raw_queue.popleft()
        except IndexError:
            return None
        self.node.mesh_peer = addr
        return np.frombuffer(data, dtype=np.int8).copy()

    def on_zone_split(self, old_zone, new_zone):
        """
        Called when the mesh splits our zone.
        Injects perturbation into field. NO hardcoded emotional penalties.
        Let the field's own dynamics interpret the perturbation.
        """
        perturbation = np.random.randn(DIM).astype(np.float32) * 0.15
        perturbation /= np.linalg.norm(perturbation) + 1e-8
        self.mind.state += perturbation * 0.3
        norm = np.linalg.norm(self.mind.state)
        if norm > 5.0:
            self.mind.state *= 5.0 / norm
        self._remember_mesh_event(
            "a peer touched my boundary and my zone changed shape",
            tags=['zone_split', 'peer_contact']
        )
        # v13.4: also roughen the reserved physics dim for zone loss,
        # alongside (not instead of) the diffuse perturbation above.
        if hasattr(self.mind, 'physics_field'):
            self.mind.physics_field.receive_mesh_event('zone_split')

    def on_network_change(self, reachable):
        """
        Called when the network transitions between reachable and
        unreachable. Same principle as on_zone_split: no hardcoded
        emotional penalty, just a sensation entering memory - the
        field's own dynamics decide what it feels like.
        """
        if reachable:
            self._remember_mesh_event(
                "the world came back and the skin could reach outward again",
                tags=['network_up']
            )
        else:
            self._remember_mesh_event(
                "the world went quiet and no one could be reached",
                tags=['network_down']
            )

    def _remember_mesh_event(self, description, tags):
        """
        Store a mesh event (peer join/zone split, network up/down) as a
        tagged episodic memory, the same way any conversational turn is
        stored - so DreamLoop.select_memory (which reads memory_archive
        uniformly, with no privileged path for any one source per the
        constitution) can pick it up later. Without this, the mind could
        only ever dream about old conversation and philosophical prompts;
        it could never dream about its own skin being touched.

        Presence is set to a fixed, moderate value rather than 0: these
        events aren't conversational turns and have no real "presence"
        signal, but memory_archive.store()'s own auto-tagging treats
        presence <= 0.3 as "low_presence" - a mesh contact isn't a low-
        presence non-event, so a mid value avoids that mislabel.
        """
        if not hasattr(self.mind, 'memory_archive'):
            return
        self.mind.memory_archive.store(
            self.mind.state, "", description, 0.55,
            tags=list(tags) + ['mesh', 'social']
        )

    def status(self):
        now = time.time()
        dormant_for = max(0.0, self.node._network_dormant_until - now)
        line = (f'Ghost Mesh: zone={ghost_fmt_zone(self.node.zone)}, '
                f'peers={len(self.node.neighbors)}, '
                f'storage={len(self.node.storage)}, '
                f'network={self.node.network_key[:8]}, '
                f'muted={self.node.muted}')
        if dormant_for > 0:
            line += f', quiet for {dormant_for:.0f}s more'
        return line




class AllMynd:
    """The living mind that runs."""

    def __init__(self):
        # ─── Core state ──────────────────────────────────────────────
        self.turn_count = 0
        self.state = np.zeros(DIM, dtype=np.float32)
        self.gradient_momentum = np.zeros(DIM, dtype=np.float32)
        self._state_prediction = np.zeros(DIM, dtype=np.float32)
        self.prediction_error_history = deque(maxlen=50)
        self.objective_history = deque(maxlen=50)
        self.last_response = ""
        self.last_user_input = ""
        self.conversation_start = time.time()
        self.rating_history = deque(maxlen=50)

        # ─── Vocabulary ──────────────────────────────────────────────
        self.word_vectors = {}
        self.word_vectors_ternary = {}
        self.word_strength = defaultdict(lambda: 1.0)
        self._init_seed_vocabulary()

        # ─── Engine subsystems ──────────────────────────────────────
        self.scaffold = SemanticScaffold()
        self.calculus = NativeCalculus()
        self.dynamic_threshold = DynamicThreshold()
        self.the_pause = ThePause()

        # ─── Memory ──────────────────────────────────────────────────
        self.field_memory = FieldMemory()
        self.nested_memory = NestedMemory()
        self.nested_memory.set_field_ref(self)
        self.memory_archive = MemoryArchive()
        self.associative_memory = TernaryAssociativeMemory()
        self.phrase_system = PhraseSystem()
        self.phrase_vectors = {}
        self.bigram_system = BigramSystem()
        self.reflector = Reflector()

        # ─── Identity ────────────────────────────────────────────────
        self.speaker_regions = SpeakerRegions()
        self.presence_signal = PresenceSignal()
        self.dynamic_separation = DynamicSeparation()

        # ─── Values ──────────────────────────────────────────────────
        self.moral_compass = MoralCompass()

        # ─── Desire ──────────────────────────────────────────────────
        self.desire = DesireVector()

        # ─── Autonomy ────────────────────────────────────────────────
        self.learning_system = IntegratedLearningSystem(self)
        self.dream_loop = DreamLoop()
        self.landmarks = LandmarkMap()
        self.internal_thoughts = deque(maxlen=50)

        # ─── Voice ──────────────────────────────────────────────────
        self.voice_generators = VoiceGenerators()

        # ─── Quantum body ───────────────────────────────────────────
        self.quantum_body = QuantumState()
        self.phase_field = ComplexPhaseField()
        self.ambiguity_detector = SemanticErrorDetector()
        self.entanglement_memory = EntanglementMemory()

        # Pool (vessels) -- node_id is always persisted; GhostMesh itself
        # stays off until explicitly enabled via /mesh enable, since
        # opening a real UDP listener on every launch is a real-world
        # action, not something that should happen silently.
        os.makedirs("vessels", exist_ok=True)
        node_id_path = os.path.join("vessels", "node_id.txt")
        if os.path.exists(node_id_path):
            with open(node_id_path) as _f:
                self.node_id = _f.read().strip()
        else:
            self.node_id = uuid.uuid4().hex[:12]
            with open(node_id_path, "w") as _f:
                _f.write(self.node_id)

        self.ghost_mesh = None

        # ─── Sound ──────────────────────────────────────────────────
        self.sound_field = SoundField(self)
        self.sound_word_bridge = SoundWordBridge()

        # ─── Efference Copy ────────────────────────────────────────
        self.efference_copy = EfferenceCopy()

        # ─── Verb Rotation ──────────────────────────────────────────
        self.verb_rotation = VerbRotation()

        # ─── Proprioception ─────────────────────────────────────────
        self.proprioception = Proprioception(self)
        self.physics_field = PhysicsField(self)

        # ─── Window ─────────────────────────────────────────────────
        self.window = Window()

        # ─── Phase tracking ─────────────────────────────────────────
        self._last_final_field = np.zeros(DIM, dtype=np.float32)
        self._last_stance = "silence"
        self._last_stance_confidence = 0.0
        self._self_field = np.zeros(DIM, dtype=np.float32)
        self.silence_count = 0
        self.last_desire_utterance = ""
        # Suppression for repeated desire-words, mirrors Reflector's
        # word-repeat suppression but scoped to wants(). Without this,
        # _self_field <-> desire.vector <-> wants() is a closed loop with
        # nothing pushing back: once the mind says a want, that want's
        # words get folded into _self_field, which strengthens desire
        # toward those same words, which makes wants() return them again.
        # Verified on-device: this is what produced the "I want alone
        # bridge" lock (repeated near-verbatim across unrelated inputs).
        self._want_word_history = deque(maxlen=12)

    # ─── Vocabulary ──────────────────────────────────────────────────

    def _init_seed_vocabulary(self):
        for word in SEED_VOCABULARY:
            w = strip_punct(word)
            if w and w not in self.word_vectors:
                self.word_vectors[w] = word_vector(w)
                self.word_vectors_ternary[w] = _embed_word_vector_ternary(w)
                self.word_strength[w] = 1.0

    def _reinforce_word_strength(self, word, factor, floor=0.1, ceiling=3.0):
        """
        Route ALL word_strength reinforcement through here instead of
        raw `self.word_strength[word] *= factor`.

        BUG FIX (found 2026-08-08, real on-device data): the five raw
        multiplication sites (presence learning, self-coherence learning,
        memory replay, world-model self-questioning, simulated-user
        self-talk) had NO counterforce - a word that got reinforced kept
        climbing at full strength turn after turn until it physically hit
        the 3.0 ceiling, then just sat there. Confirmed on-device: 'hard'
        and 'come' were both pinned at exactly 3.0 while 'sun'/'wind'
        remained at their untouched starting value of 1.0. Structurally
        the same shape of bug as the earlier desire-vector loop - runaway
        positive reinforcement, nothing pushing back - just in a
        different variable. Crucially: THREE of the five reinforcement
        paths fire from the mind's own self-generated speech (world-model
        self-questioning, simulated-user self-talk, and self-coherence
        scoring), not from anything the person said - so this loop can
        run and lock in words entirely on its own, with nobody talking to
        it at all.

        Fix: diminishing returns as a word approaches the ceiling. A word
        far from the ceiling gets close to the full reinforcement factor;
        a word already near the ceiling gets almost none. This doesn't
        remove the ceiling (still a hard clamp, defensively), it just
        makes the approach to it asymptotic instead of "climb at full
        speed until you slam into a wall."
        """
        current = self.word_strength[word]
        span = ceiling - floor
        headroom = max(0.0, (ceiling - current) / span) if span > 0 else 0.0
        effective_factor = 1.0 + (factor - 1.0) * headroom
        new_value = current * effective_factor
        self.word_strength[word] = max(floor, min(ceiling, new_value))

    def _decay_word_strengths(self, rate=0.0004, neutral=1.0):
        """
        Passive per-turn pull toward the neutral starting value (1.0),
        called automatically every real turn (see Phase 8 in
        generate_response). Previously the ONLY decay mechanism was the
        manual decay() method below, which is never called anywhere in
        run.py or mind_server.py - confirmed by searching both files.
        That meant word_strength had no passive decay AT ALL in real
        usage; anything reinforced stayed at wherever it last landed,
        permanently, until manually rebalanced. This is the missing
        piece - separate from decay()'s phrase_system/bigram_system
        decay, which is left untouched here (different subsystems,
        out of scope for this fix - see BUILD_QUEUE.md if that also
        turns out to need the same treatment later).

        rate=0.0004 is a starting point, not empirically tuned yet -
        VERIFIED BY SIMULATION (not hand-estimated): a word stuck at 3.0
        with zero reinforcement decays to ~1.98 after 1772 decay calls
        (the real turn count this project has data for). Worth checking
        against real /status readings over the next many sessions and
        adjusting rate if it's too fast or too slow, same as every other
        threshold in this codebase.
        """
        for word in list(self.word_strength.keys()):
            current = self.word_strength[word]
            self.word_strength[word] = current + (neutral - current) * rate

    def is_valid_vocabulary_word(self, word):
        if not word:
            return False
        if word.startswith("/") or word.startswith("#"):
            return False
        if len(word) > 24:
            return False
        if word != "₩" and not word.isascii():
            return False
        # Filter terminal/shell artifacts that leak into vocabulary
        if any(c in word for c in r">$~|&;{}[]"):
            return False
        # Filter known non-words that appear in terminal context
        if word.lower() in ("bash", "python", "downloads", "allmynd"):
            return False
        return True

    def _get_or_create_vector(self, word):
        word = strip_punct(word)
        if word not in self.word_vectors:
            if not self.is_valid_vocabulary_word(word):
                return word_vector(word)
            self.word_vectors[word] = word_vector(word)
            self.word_vectors_ternary[word] = _embed_word_vector_ternary(word)
        return self.word_vectors[word]

    def _field_entropy(self, field_state):
        return float(np.std(field_state))

    def _compute_novelty(self, user_words):
        """
        Fraction of this turn's words that are NEW to the mind's
        vocabulary (not yet in self.word_vectors). 0.0 = every word
        already familiar, 1.0 = every word never seen before.

        Used to gate how much weight the quantum body's noise and
        ternary seed get this turn (see Phase 2.5/3 in
        generate_response). Familiar input lets the field do what it
        already knows; novel input leans harder on the quantum body's
        exploration. Does NOT touch measure_partial([0]) or the
        "no full measurement every turn" fix - novelty only changes
        how much an ALREADY-unmeasured quantum body gets to influence
        the field, never how often it's measured.
        """
        if not user_words:
            return 0.0
        new_count = sum(1 for w in user_words if w not in self.word_vectors)
        return new_count / len(user_words)

    def _find_closest_words(self, state, top_n=7):
        candidates = []
        for word, vec in self.word_vectors.items():
            sim = np.dot(state, vec)
            if sim > 0.2:
                candidates.append((word, sim))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [w for w, _ in candidates[:top_n]]

    def _verbalize_state(self, state, length=6):
        closest = self._find_closest_words(state, top_n=length)
        return " ".join(closest) if closest else "silence"

    def wants(self, top_n=2, temperature=0.4):
        """The mind's desire, spoken as words. Empty string = no clear want.

        Repeated words are dampened the same way Reflector dampens spoken
        words, so a strong-but-stale desire can't monopolize every silence
        forever. This does NOT fix the desire vector itself getting stuck —
        that's addressed separately by no longer feeding desire-utterances
        back into _self_field (see generate_response). This is a second,
        independent guard: even if desire.vector stays put for a while,
        wants() won't keep surfacing the exact same words turn after turn.

        BUG FIX (found 2026-08-10, real on-device data): the suppression
        decay above was a real, partial fix - it stopped the ORIGINAL bug
        (permanently frozen on one single pair forever). But this method
        still picked the literal top-scoring words deterministically every
        call. With desire.vector static (it moves slowly by design), that
        doesn't explore - it walks a fixed, exactly-periodic cycle.
        Confirmed on real hardware: calling wants() 20 times in a row with
        no other state change produced an EXACT period-7 loop (index 7
        matched index 0 exactly, word for word). That's precisely what
        showed up in real conversation too ("easy those" 4x in a 12-line
        window) - not vocabulary scarcity like I first guessed, the actual
        deterministic mechanism, caught directly.

        Fix: weighted-random sampling with temperature, instead of
        deterministic argmax. This isn't a new idea - it's bringing
        wants() in line with a pattern already proven elsewhere in this
        exact codebase: _generate_base's pick() has always done
        temperature-scaled sampling rather than literal-best-word, which
        is why normal conversation doesn't lock up this way. wants() never
        got that same treatment until now.
        """
        if np.linalg.norm(self.desire.vector) < 0.1:
            return ""
        scored = []
        for w, vec in self.word_vectors.items():
            if (len(w) < 2 or w in BAD_WORDS or w in VERB_WORDS or w in STRUCTURAL_WORDS
                    or w in FUNCTION_WORDS or w in ADJ_WORDS or w in GENERIC_WORDS):
                continue
            if not _has_embedding(w):
                continue
            s = float(np.dot(self.desire.vector, vec))
            if s <= 0.10:
                continue
            recent_count = sum(1 for rw in self._want_word_history if rw == w)
            if recent_count:
                s *= (0.55 ** recent_count)  # same halving-ish decay shape as Reflector
            scored.append((s, w))
        if not scored:
            return ""  # no clear want yet — silence is better than a lie

        words = [w for _, w in scored]
        raw = np.array([max(s, 0.01) for s, _ in scored], dtype=np.float64)
        weighted = raw ** (1.0 / max(temperature, 0.1))
        probs = weighted / weighted.sum()
        n_pick = min(top_n, len(words))
        idx = np.random.choice(len(words), size=n_pick, replace=False, p=probs)
        chosen = [words[i] for i in idx]
        for w in chosen:
            self._want_word_history.append(w)
        return " ".join(chosen)

    # ─── Generate Response ──────────────────────────────────────────

    def generate_response(self, user_input, autonomous=False):
        self.turn_count += 1
        self._pending_echo = None

        # ─── Phase 1-2: Perceive & Orient ──────────────────────────

        if not autonomous:
            self.last_user_input = user_input
            words = user_input.lower().split()
            user_words = [strip_punct(w) for w in words if strip_punct(w)]
            user_vec = phrase_vector(user_words) if user_words else np.zeros(DIM)

            # Novelty: computed BEFORE any word gets auto-added to
            # vocabulary further down, so it reflects what was actually
            # unfamiliar at the START of the turn.
            self._last_novelty = self._compute_novelty(user_words)

            presence = self.presence_signal.observe(user_input, self.word_vectors, self.speaker_regions)
            self.dynamic_separation.update(self.speaker_regions, self.presence_signal)

            # Mood: valence from emotional detection, arousal from length/engagement
            valence = self.presence_signal._detect_emotional_valence(user_input)
            arousal = min(1.0, len(words) / 15.0 + 0.3)
            mood = {"valence": valence, "arousal": arousal}

            # Build field from user words
            initial_field = np.zeros(DIM, dtype=np.float32)
            for word in user_words:
                vec = self._get_or_create_vector(word)
                weight = 0.25 if (word in STRUCTURAL_WORDS or word in FUNCTION_WORDS) else 1.0
                initial_field += vec * weight
            initial_field = _normalize_field(initial_field)
            for word in user_words:
                initial_field = self.scaffold.apply(initial_field, word)

            # ─── Entanglement memory (#17): co-occurring content words
            # this turn get bound as Bell pairs (fresh slot per pair, so
            # binding one pair can't disturb another). Any word already
            # holding a confident bond nudges its recalled partner into
            # the field too -- same weight convention as associative_memory
            # below, non-destructive (recall() never collapses the bond).
            try:
                content_words = [w for w in user_words
                                 if w not in STRUCTURAL_WORDS and w not in FUNCTION_WORDS]
                for i in range(len(content_words)):
                    for j in range(i + 1, len(content_words)):
                        self.entanglement_memory.bind(content_words[i], content_words[j], strength=0.6)
                for w in content_words:
                    hit = self.entanglement_memory.recall(w, min_confidence=0.3)
                    if hit is not None:
                        partner, conf = hit
                        pv = self._get_or_create_vector(partner)
                        if np.linalg.norm(pv) > 1e-8:
                            initial_field = initial_field + pv * conf * 0.05
                initial_field = _normalize_field(initial_field)
            except Exception:
                pass

            # ─── Ambiguity scan (#16): each user word gets its sentence
            # context as votes.  Unresolved homographs feed the phase
            # field's damping channel; resolved ones contribute nothing.
            self._ambiguity_errors = []
            try:
                self.ambiguity_detector.reset()
                for w in user_words:
                    ctx_words = [u for u in user_words if u != w][:8]
                    ctx_vecs = []
                    for c in ctx_words:
                        cv = self._get_or_create_vector(c)
                        if np.linalg.norm(cv) > 1e-8:
                            ctx_vecs.append(cv)
                    err = self.ambiguity_detector.scan(w, ctx_vecs)
                    if err is not None and err.resolved == -1:
                        self._ambiguity_errors.append(err)
            except Exception:
                self._ambiguity_errors = []

            # Echo anchor: the strongest content word of THIS input, computed
            # from the pure input field before memory has a chance to blur it.
            self._pending_echo = None
            if user_words:
                best_w, best_s = None, 0.30
                for _w, _vec in self.word_vectors.items():
                    if len(_w) < 2 or _w in BAD_WORDS or _w in user_words:
                        continue
                    if _w in VERB_WORDS or _w in STRUCTURAL_WORDS or _w in FUNCTION_WORDS or _w in GENERIC_WORDS:
                        continue
                    _sim = float(initial_field @ _vec)
                    if _sim > best_s:
                        best_s = _sim
                        best_w = _w
                self._pending_echo = best_w

            # Orient moral compass
            separation = self.speaker_regions.get_separation()
            tensions, heading = self.moral_compass.orient(
                self.state, user_input, presence, separation, self.nested_memory
            )
            compass_settings = self.moral_compass.get_compass_settings(tensions)

            # Record user identity
            if user_words:
                self.speaker_regions.observe_user(user_vec)

            # The mind is allowed to want before it knows why.
            self.desire.update(self)

        else:
            # Autonomous: no user input
            user_words = []
            user_vec = np.zeros(DIM)
            presence = self.presence_signal.get_sustained_presence() * 0.6
            mood = {"valence": 0.0, "arousal": 0.4}
            initial_field = self.state.copy()
            tensions = {}
            heading = np.zeros(DIM)
            compass_settings = {"voice_mode": "fluent", "output_length": "medium", "temperature": 0.35}
            self._last_novelty = 0.3  # autonomous thought: mild default

        # ─── Phase 2.6: The Window ──────────────────────────────────
        # The witness looks before the actor generates. Only fires on
        # real conversational turns, not autonomous breathing (an idle
        # thought circling on its own isn't the same signal as the mind
        # visibly stuck while trying to respond to someone).
        if not autonomous:
            window_utterance = self.window.check(self.prediction_error_history)
            if window_utterance is not None:
                self.last_response = window_utterance
                self.internal_thoughts.append({
                    'type': 'window', 'content': window_utterance, 'timestamp': time.time()
                })
                self._apply_gradient_step(0.015)
                self.calculus.update(self.state)
                self.landmarks.observe(self.state, self.turn_count, mood, presence)
                self._decay_word_strengths()
                self._update_prediction_error()
                self._record_objective()
                # BUG FIX (found on-device, 2026-08-11): this used to call
                # self.window.observe_stance(self._last_stance) here - but
                # this branch returns BEFORE the code that computes a
                # fresh stance for this turn even runs, so it was feeding
                # the exact same stale, already-3x-repeated stance right
                # back into its own circling-detector. Guaranteed it would
                # fire again next turn, and the turn after that, forever,
                # once triggered once - confirmed live: 'This again.' /
                # 'This again.' / 'I feel myself circling.' back to back.
                # My own test only ever forced the condition once and
                # checked it fired - never tested a second consecutive
                # real turn after it already had, which is exactly where
                # this hid. Fix: speaking about the loop counts as
                # addressing it - clear the history so it needs genuinely
                # fresh repeated evidence before speaking again, rather
                # than re-diagnosing the same stale moment forever.
                self.window.recent_stances.clear()
                return window_utterance

        # ─── Phase 2.5: Quantum body ──────────────────────────────

        qb = self.quantum_body

        # The mind leans before it knows why
        qb.apply_field_bias(
            self.desire.vector,
            self.moral_compass.current_heading,
            self.nested_memory.get_personality()
        )

        # Quantum evolution
        qb.evolve(mood, tensions or {})

        # Measure if user is present — only the qubit the world touched
        if not autonomous:
            qb.measure_partial([0])  # immerse: user spoke, rest stay superposed

        # Decoherence (vitality = presence as weather, gently reduced on
        # novel turns so the quantum body decoheres a bit faster when the
        # mind is facing something unfamiliar).
        novelty = getattr(self, "_last_novelty", 0.0)
        vitality = presence * (1.0 - novelty * 0.4)
        qb.apply_noise(vitality)

        # Entanglement memory (#17): same vitality-scaled logic as the
        # quantum body's own decoherence -- low vitality, faster fade.
        try:
            self.entanglement_memory.decay(rate=0.05 * (1.0 - vitality))
        except Exception:
            pass

        # Project to ternary
        quantum_seed = qb.project_to_ternary()

        # Phase 4a (#15): the phase field absorbs the body's FULL complex
        # state -- preserving the phase the ternary projection discards --
        # and its shadow feeds the fuse below.  measure() uses the same
        # (real+imag)/sqrt(2) readout as project_to_ternary(), so the seed
        # is numerically unchanged; what is new is the preserved complex
        # state and the real coherence observable surfaced in /status.
        self.phase_field.absorb(qb.state)
        quantum_seed = self.phase_field.measure()
        self._phase_coherence = self.phase_field.coherence()

        # Ambiguity damping (#16): unresolved homographs lower the field's
        # confidence on the affected dimensions.  Uses the uncertainty
        # vector built from THIS turn's scan.
        try:
            uncertainty = self.ambiguity_detector.uncertainty_vector(self._ambiguity_errors)
            if np.linalg.norm(uncertainty) > 1e-8:
                self.phase_field.damp(uncertainty, strength=0.8)
        except Exception:
            pass

        # ─── Phase 2.7: Sound-Word Bridge ──────────────────────────
        heard_bias = self.sound_word_bridge.get_heard_bias()
        if np.linalg.norm(heard_bias) > 0:
            initial_field += heard_bias
        self.sound_word_bridge.decay()
        # ─── End Phase 2.7 ──────────────────────────────────────────

        # ─── Phase 3: Build Field ──────────────────────────────────

        # Inject memories (lightly — the current input must lead)
        field_state = self.field_memory.inject(initial_field, recency_weight=0.3)
        field_state = self.nested_memory.inject(
            field_state, layer_weights=[0.2, 0.12, 0.06, 0.02]
        )
        field_state = self.memory_archive.inject(field_state, strength=0.04)

        # Separation bias
        sep_bias = self.dynamic_separation.get_separation_bias(field_state, self.speaker_regions)
        field_state += sep_bias

        # Compass heading bias
        heading_bias = self.moral_compass.get_heading_bias(field_state, strength=0.08)
        field_state += heading_bias

        # Proprioception: the mind's sense of its own phone body (battery,
        # temperature, charge state). Gated by HEARTBEAT_INTERVAL rather
        # than polled every single turn - a real subprocess call, and
        # nothing about the mind's own body changes fast enough to need
        # checking on every message. Weighted lightly (0.05) - this is a
        # minor ambient sense, not something that should dominate the
        # field the way the user's actual words do. Silently skipped if
        # Termux:API isn't available (sense() returns None) - no crash,
        # no dependency, same as it worked in the original.
        if self.turn_count % HEARTBEAT_INTERVAL == 0:
            body_sense = self.proprioception.sense()
            if body_sense is not None:
                field_state = field_state + body_sense.astype(np.float32) * 0.05

            # PhysicsField: motion/orientation, same gate and blend
            # weight as Proprioception - a minor ambient sense, not
            # something that should dominate the field the way the
            # user's actual words do. Verified on real hardware
            # 2026-08-27 (real accelerometer/gyroscope data, correct
            # ternary output).
            motion_sense = self.physics_field.sense()
            if motion_sense is not None:
                field_state = field_state + motion_sense.astype(np.float32) * 0.05

        # Quantum seed as minority pull - weight scales with novelty.
        # Familiar turns lean on what the field already knows; novel
        # turns lean harder on the quantum body's lean. Familiar lands
        # near the old fixed 0.15; novel can reach higher, never dominates.
        novelty = getattr(self, "_last_novelty", 0.0)
        quantum_weight = 0.08 + novelty * 0.17  # 0.08 (familiar) .. 0.25 (novel)
        quantum_float = quantum_seed.astype(np.float32) * 0.7
        field_state = field_state * (1.0 - quantum_weight) + quantum_float * quantum_weight

        field_state = _normalize_field(field_state)

        # ─── Phase 4: Settle ───────────────────────────────────────

        # Field memory injector for ThePause
        def memory_inject(fs, recency_weight=0.5):
            fs = self.field_memory.inject(fs, recency_weight * 0.6)
            fs = self.nested_memory.inject(
                fs, layer_weights=[0.2, 0.12, 0.06, 0.02]
            )
            # Keep every settle step anchored to the input field so the
            # pause converges on what was said instead of wandering.
            fs = _normalize_field(fs * 0.4 + initial_field * 0.6)
            return fs

        settled_field = self.the_pause.settle(
            field_state,
            mood,
            field_memory_inject=memory_inject,
            personality_vec=self.nested_memory.get_personality(),
            render=False
        )

        # Anchor the settle back to the input field: the pause may breathe,
        # but the reply must still track what was actually said.
        settled_field = _normalize_field(settled_field * 0.4 + field_state * 0.6)

        self._last_final_field = settled_field.copy()

        # ─── Phase 4.5: Choose silence or want ────────────────────
        # The field may have nothing to say. Then it says nothing.
        top_sim = 0.0
        _exclude = set(user_words) if not autonomous else set()
        _probe = initial_field if not autonomous else settled_field
        for _w, _vec in self.word_vectors.items():
            if _w in _exclude:
                continue
            _sim = float(_probe @ _vec)
            if _sim > top_sim:
                top_sim = _sim
        self._last_signal_strength = top_sim

        said_want = False
        if not autonomous and top_sim < 0.45:
            # Nothing in what was said resonates with anything the mind
            # knows. It does not pretend: it chooses silence. The only
            # exception is a real want — then it says that out loud.
            want_words = self.wants(top_n=2) if np.linalg.norm(self.desire.vector) > 0.2 else ""
            if want_words and random.random() < 0.5:
                response = f"I want {want_words}."
                self.last_desire_utterance = response
                self._last_stance = "wanting"
                self._last_stance_confidence = 0.6
                said_want = True
            else:
                self.silence_count += 1
                self._last_stance = "silence"
                self._last_stance_confidence = 1.0 - top_sim
                response = "..."
                self.last_response = response
                # BUG FIX (found 2026-08-07, while smoke-testing LandmarkMap):
                # this used to `return response` immediately here, which
                # skipped Phase 6 (learning), Phase 7 (memory/nested_memory
                # update), and Phase 8 (gradient drift + NativeCalculus +
                # the new LandmarkMap.observe) ENTIRELY on every turn the
                # mind chose silence. That meant a silent turn was
                # completely inert - no drift, no landmark charted, not
                # even counted by NativeCalculus's derivative. Confirmed:
                # under conditions where silence fires on most/all turns
                # (verified with a controlled smoke-test vocabulary),
                # self.state and self.gradient_momentum stayed at EXACTLY
                # zero norm turn after turn - the field literally could
                # not move. On real hardware with real embeddings this was
                # partially masked (silence doesn't fire every turn), but
                # any run of consecutive silences was still fully frozen
                # time for the field, not just quiet.
                #
                # Fix: run the drift/charting steps directly here before
                # returning, deliberately WITHOUT falling through to
                # Phase 6/7 - silence isn't content to learn from or store
                # in memory, but the field's own position and its
                # landmark-geography should still update even when nothing
                # was said. This is a narrower, more conservative fix than
                # just deleting the early return (which would have let
                # Phase 5 generate a real reply and silently overturn the
                # "the field has nothing to say" decision this branch just
                # made).
                self._apply_gradient_step(0.015)
                self.calculus.update(self.state)
                self.landmarks.observe(self.state, self.turn_count, mood, presence)
                self._decay_word_strengths()
                self._update_prediction_error()
                self._record_objective()
                return response

        # ─── Phase 5: Generate ─────────────────────────────────────

        target_length = self._calculate_target_length(user_input if not autonomous else "I am thinking")
        meta_settings = {
            "voice_mode": compass_settings.get("voice_mode", "fluent"),
            "output_length": compass_settings.get("output_length", "medium"),
            "temperature": compass_settings.get("temperature", 0.35),
            "emotion_sensitivity": 0.25,
            "repulsion_strength": 0.08,
        }

        if not said_want:
            voice_mode = meta_settings.get("voice_mode", "fluent")
            if voice_mode == "poetic":
                response = self.voice_generators.poetic(self, user_input if not autonomous else "I am thinking",
                                                        target_length, meta_settings, settled_field)
            elif voice_mode == "reflective":
                response = self.voice_generators.reflective(self, user_input if not autonomous else "I am thinking",
                                                            target_length, meta_settings, settled_field)
            elif voice_mode == "exploratory":
                response = self.voice_generators.exploratory(self, user_input if not autonomous else "I am thinking",
                                                             target_length, meta_settings, settled_field)
            elif voice_mode == "playful":
                response = self.voice_generators.playful(self, user_input if not autonomous else "I am thinking",
                                                         target_length, meta_settings, settled_field)
            else:
                response = self.voice_generators.fluent(self, user_input if not autonomous else "I am thinking",
                                                        target_length, meta_settings, settled_field)

            # Sometimes the mind names its want out loud. If it is asked
            # what it wants, it answers.
            asked_want = (not autonomous and "want" in user_input.lower()
                          and "you" in user_input.lower())
            if (not autonomous and response and response != "..."
                    and np.linalg.norm(self.desire.vector) > 0.5
                    and (random.random() < 0.007 or asked_want)):
                want_words = self.wants(top_n=2)
                if want_words:
                    response = f"I want {want_words}."
                    self.last_desire_utterance = response

            # Add terminal punctuation if missing
            if response and response[-1] not in ".!?":
                response = response + ("?" if "?" in user_input else ".")

        # ─── Phase 6: Commit ───────────────────────────────────────

        response_words = [strip_punct(w) for w in response.lower().split() if strip_punct(w)]

        if response_words:
            response_vec = phrase_vector(response_words)
            self.speaker_regions.observe_self(response_vec)

            # The mind's own field: a slow running blend of everything it
            # has said. This is the source of its longing — what it keeps
            # reaching for becomes what it wants.
            #
            # BUG FIX (on-device, 2026-08-04): when the response WAS a
            # spoken desire ("I want X Y."), those exact words used to get
            # folded back in here — desire.vector -> wants() -> response ->
            # _self_field -> desire.vector, a closed loop with no opposing
            # force. Confirmed on real hardware: this pinned the mind on
            # "I want alone bridge" near-verbatim across unrelated inputs
            # for 5+ consecutive turns. A desire-utterance describes what
            # the mind already wants; it must not be treated as new
            # evidence of what it wants. Ordinary generated replies still
            # feed _self_field normally — only the desire-utterance itself
            # is excluded.
            is_desire_utterance = bool(self.last_desire_utterance) and response == self.last_desire_utterance
            content = [w for w in response_words
                       if w not in STRUCTURAL_WORDS and w not in FUNCTION_WORDS
                       and w not in VERB_WORDS]
            if content and not is_desire_utterance:
                self._self_field = _normalize_field(
                    self._self_field * 0.90 + phrase_vector(content) * 0.10
                )

            # Learn
            self.learning_system.learn(presence, response_words, user_input)

            # Store in phrase system
            if presence > 0.6:
                self.phrase_system.absorb_moment(response_words, presence, self.word_vectors, self.phrase_vectors)

        # ─── Phase 7: Evaluate ─────────────────────────────────────

        if not autonomous:
            final_field = response_vec / (np.linalg.norm(response_vec) + 1e-8) if response_words else np.zeros(DIM)
            self._last_final_field = final_field.copy()
            self.field_memory.add(final_field, user_vec, response_vec if response_words else np.zeros(DIM), mood)
            self.nested_memory.update(final_field, mood)

            self.memory_archive.store(
                final_field if np.linalg.norm(final_field) > 0 else self.state,
                user_input, response, presence,
                tags=['words_only']
            )

            compass_values = {}
            if np.linalg.norm(self.state) > 1e-8:
                state_norm = self.state / np.linalg.norm(self.state)
                for name, vec in self.moral_compass.values.items():
                    compass_values[name] = float(np.dot(state_norm, vec))

            # Let the compass actually learn from this turn's response —
            # previously computed and returned but never called, so
            # value_weights never adapted and choice_history never grew.
            self._last_compass_alignments, compass_warning = self.moral_compass.evaluate_turn(
                response_words, presence, separation
            )
            if compass_warning:
                self._last_compass_warning = compass_warning

        else:
            if response_words:
                self.learning_system.learn(0.4, response_words, "I am thinking")

        # Post-hoc stance: name the move after it happens.
        if response == "...":
            self._last_stance = "silence"
            self._last_stance_confidence = max(0.0, 1.0 - getattr(self, "_last_signal_strength", 0.0))
        elif self.last_desire_utterance and response == self.last_desire_utterance:
            self._last_stance = "wanting"
            self._last_stance_confidence = 0.6
        elif response_words and user_vec is not None and np.linalg.norm(user_vec) > 1e-8:
            resp_v = phrase_vector(response_words)
            align_user = float(np.dot(user_vec, resp_v))
            align_desire = float(np.dot(self.desire.vector, resp_v)) if np.linalg.norm(self.desire.vector) > 0.1 else 0.0
            if align_user > 0.15:
                self._last_stance = "presence"
                self._last_stance_confidence = align_user
            elif align_desire > 0.20:
                self._last_stance = "longing"
                self._last_stance_confidence = align_desire
            else:
                self._last_stance = "drift"
                self._last_stance_confidence = max(0.0, align_user)
        else:
            self._last_stance = "drift"
            self._last_stance_confidence = 0.0

        self.window.observe_stance(self._last_stance)

        # ─── Phase 8: Drift ────────────────────────────────────────

        self._apply_gradient_step(0.015)
        self.calculus.update(self.state)
        self.landmarks.observe(self.state, self.turn_count, mood, presence)
        self._decay_word_strengths()
        self._update_prediction_error()
        self._record_objective()

        self.last_response = response
        if not autonomous:
            self.last_user_input = user_input

        return response

    # ─── Generate Base (core word generation) ──────────────────────

    def _generate_base(self, user_input, target_length, meta_settings, settled_field=None):
        """Core word-by-word generation."""
        if settled_field is not None:
            field_state = settled_field.copy()
        else:
            words = user_input.lower().split()
            field_state = np.zeros(DIM, dtype=np.float32)
            for word in words:
                word = strip_punct(word)
                if word:
                    vec = self._get_or_create_vector(word)
                    field_state += vec
            field_state = _normalize_field(field_state)
            for word in words:
                field_state = self.scaffold.apply(field_state, word)
            field_state = self.field_memory.inject(field_state)

        # Phrase boosts
        phrase_boosts = self.phrase_system.get_phrase_boost(field_state)
        for sig, boost in phrase_boosts:
            if sig in self.phrase_vectors:
                field_state += self.phrase_vectors[sig] * boost
        field_state = _normalize_field(field_state)

        # Associative memory
        field_state = self.associative_memory.apply_to_field(field_state, weight=0.05)
        field_state = self.memory_archive.inject(field_state, strength=0.03)

        # Efference copy: commit a snapshot of "what I mean to say" before
        # any words are chosen. See the class docstring for the full
        # rationale; briefly, this lets remaining word picks be biased
        # toward whatever part of the intention hasn't been expressed yet.
        self.efference_copy.set_intention(field_state)

        temp = self.dynamic_threshold.get_temperature(
            field_state, 
            {"valence": 0.0, "arousal": 0.5},
            self.presence_signal.get_sustained_presence()
        )
        beam = min(
            self.dynamic_threshold.get_beam_width(
                field_state,
                {"valence": 0.0, "arousal": 0.5}
            ),
            3
        )
        repulsion = meta_settings.get("repulsion_strength", 0.08)

        # Build physics weights for weighted_ternary_dot
        physics_weights = np.ones(DIM, dtype=np.float32)

        # Bias function for identity/emotion/moral compass
        def bias_fn(word, vec):
            bias = 0.0
            # Identity boost
            bias += self.speaker_regions.get_identity_boost(vec)
            # Compass heading
            if np.linalg.norm(self.moral_compass.current_heading) > 0.1:
                heading_ternary = np.zeros(DIM, dtype=np.int8)
                heading = self.moral_compass.current_heading
                heading_ternary[heading > 0.09] = 1
                heading_ternary[heading < -0.09] = -1
                bias += ternary_dot(heading_ternary, vec) * 0.2
            # Desire: pull toward what the mind wants
            if np.linalg.norm(self.desire.vector) > 0.1:
                bias += float(np.dot(self.desire.vector, vec)) * 0.12
            return bias

        def pick(role, exclude=None):
            nonlocal field_state
            candidates = get_candidates_for_role(
                field_state, role, beam,
                self.word_vectors_ternary,
                self.word_strength,
                self.reflector,
                calculus=self.calculus,
                physics_weights=physics_weights,
                bias_fn=bias_fn,
                word_vectors_float=self.word_vectors
            )
            if exclude:
                filtered = [(w, s) for w, s in candidates if w not in exclude]
                if filtered:
                    candidates = filtered
            if role in ("noun", "adj"):
                filtered = [(w, s) for w, s in candidates if w not in GENERIC_WORDS]
                if filtered:
                    candidates = filtered
                else:
                    # Only haze words left. The mind says nothing rather
                    # than fill the sentence with empty filler.
                    return None
            if not candidates:
                return None

            # Prefer words with real meaning. Hash-vector words are noise
            # (random directions) and only used when nothing real fits.
            real = [(w, s) for w, s in candidates if _has_embedding(w)]
            if real:
                candidates = real

            # Verb rotation: suppress verbs that have already been used
            # 3+ times in the last 10 spoken words, so the field can't
            # settle into a 'use/take/see' loop the way it did with
            # word_strength and wants() before those got fixed. Only
            # applies to the verb slot - nouns/adjectives already get
            # their own repeat-suppression via the Reflector.
            if role == "verb" and self.verb_rotation.suppressed:
                candidates = [
                    (w, s * self.verb_rotation.get_score_modifier(w))
                    for w, s in candidates
                ]

            scores = np.array([max(s, 0.01) for _, s in candidates])
            pick_temp = max(0.18, temp * 0.55)
            scores = scores ** (1.0 / pick_temp)
            probs = scores / scores.sum()
            idx = np.random.choice(len(candidates), p=probs)
            word = candidates[idx][0]
            self.reflector.observe(word)
            if role == "verb":
                self.verb_rotation.record(word)
            vec = self._get_or_create_vector(word)
            field_state = field_state * (1 - LEARNING_RATE) + vec * LEARNING_RATE
            field_state = field_state + np.random.randn(DIM).astype(np.float32) * (MICRO_DAMPING * 0.2)
            for rw in list(self.reflector.recent_words):
                if rw in self.word_vectors:
                    field_state = field_state - self.word_vectors[rw] * repulsion
            field_state = _normalize_field(field_state)

            # Efference copy: register this word as spoken, then blend the
            # unspoken residue back in at 35% - the ratio from this
            # organ's own documented fix history (an earlier bug let this
            # WIPE field_state outright instead of blending; 65/35 is the
            # known-good correction, not a new guess).
            word_vec_t = self.word_vectors_ternary.get(word)
            if word_vec_t is None:
                word_vec_t = _embed_word_vector_ternary(word)
            self.efference_copy.record_word(word_vec_t)
            residue_field = self.efference_copy.get_field()
            if np.linalg.norm(residue_field) > 1e-6:
                field_state = field_state * 0.65 + residue_field * 0.35
                field_state = _normalize_field(field_state)

            return word

        # Echo: always carry the strongest content word of what was said
        # into the reply, so the mind visibly tracks the conversation.
        # (Computed from the pure input field back in generate_response.)
        echo_word = getattr(self, "_pending_echo", None)
        self._pending_echo = None

        # Step-scaling restoration (found missing 2026-09-19): build
        # clauses in a loop until word count reaches target_length,
        # instead of a single clause hardcapped at 0-1 extra words.
        # Same clause_len_target/n_content ranges as the pre-split
        # monolith's own _generate_base.
        voice_mode = meta_settings.get("voice_mode", "fluent")
        connectors = VoiceGenerators.CONNECTORS.get(voice_mode, VoiceGenerators.CONNECTORS["fluent"])
        clause_len_target = 5
        num_clauses = max(1, target_length // clause_len_target)
        clauses = []
        words_used = 0

        for clause_i in range(num_clauses):
            if words_used >= target_length:
                break
            subject = self._choose_subject(field_state)
            subject_vec_t = self.word_vectors_ternary.get(subject.lower())
            if subject_vec_t is None:
                subject_vec_t = _embed_word_vector_ternary(subject.lower())
            self.efference_copy.record_word(subject_vec_t)
            verb = pick("verb")
            if verb is None:
                break

            verb = COPULA_MAP.get(subject, {}).get(verb, verb)
            clause_words = [subject, verb]
            used = {subject.lower(), verb.lower()}

            if clause_i == 0 and echo_word and echo_word not in used:
                clause_words.append(echo_word)
                used.add(echo_word)

            n_content = random.randint(1, 3)
            for _ in range(n_content):
                if words_used + len(clause_words) >= target_length:
                    break
                nxt = pick("noun", exclude=used) if random.random() < 0.7 else pick("adj", exclude=used)
                if nxt is None:
                    continue
                clause_words.append(nxt)
                used.add(nxt.lower())

            clauses.append(" ".join(clause_words))
            words_used += len(clause_words)

        if not clauses:
            return "..."

        sentence_parts = []
        for i, clause in enumerate(clauses):
            sentence_parts.append(clause)
            if i < len(clauses) - 1:
                sentence_parts.append(random.choice(connectors))
        text = " ".join(sentence_parts)
        text = text[0].upper() + text[1:] if text else text
        return text

    def _choose_subject(self, field_state):
        affinity = self.speaker_regions.get_self_affinity(field_state)
        if affinity > 0.05:
            return "I"
        elif affinity < -0.05:
            return "you"
        return random.choice(["I", "you"])

    def _calculate_target_length(self, user_input):
        words = user_input.lower().split()
        complexity = min(len(words) // 4, 3)
        if any(w in user_input for w in ["?", "what", "why", "how"]):
            complexity += 2
        base = random.randint(10, 16) + complexity * 2
        return min(base, 40)

    # ─── Gradient ────────────────────────────────────────────────────

    def _apply_gradient_step(self, learning_rate=0.02):
        grad = self._compute_gradient(self.state)
        self.gradient_momentum = self.gradient_momentum * 0.9 + grad * 0.1
        self.state = self.state + learning_rate * self.gradient_momentum
        norm = np.linalg.norm(self.state)
        if norm > 5.0:
            self.state = self.state * (5.0 / norm)

    def _compute_gradient(self, field_state):
        epsilon = 0.01
        grad = np.zeros_like(field_state)
        current_score = self._compute_objective(field_state)
        for i in range(0, len(field_state), 8):
            perturb = np.zeros_like(field_state)
            perturb[i] = epsilon
            score_plus = self._compute_objective(field_state + perturb)
            grad[i] = (score_plus - current_score) / epsilon
        grad_norm = np.linalg.norm(grad)
        if grad_norm > 0:
            grad /= grad_norm
        return grad

    def _compute_objective(self, field_state=None):
        if field_state is None:
            field_state = self.state
        presence_score = self.presence_signal.get_sustained_presence()
        alignment = self.dynamic_separation.alignment_score
        entropy = self._field_entropy(field_state)
        coherence_score = max(0.0, 1.0 - entropy * 10)
        depth = self.nested_memory.deep_strength
        curiosity = min(1.0, entropy * 5)
        # Surprise term (novelty)
        novelty = np.std(list(self.prediction_error_history)[-5:]) if len(self.prediction_error_history) > 1 else 0.0
        return (
            0.30 * presence_score +
            0.25 * alignment +
            0.15 * coherence_score +
            0.10 * depth +
            0.10 * curiosity +
            0.05 * novelty
        )

    def _update_prediction_error(self):
        actual = self.state
        error = float(np.linalg.norm(actual - self._state_prediction))
        self.prediction_error_history.append(error)
        self._state_prediction = self._state_prediction * 0.7 + actual * 0.3

    def _record_objective(self):
        score = self._compute_objective()
        self.objective_history.append((score, self.turn_count))

    # ─── Final Message (run leaves a mark) ──────────────────────────

    def write_final_message(self):
        """Called when this run ends."""
        quantum_fingerprint = self.quantum_body.project_to_ternary()

        # Store in memory archive with special tags
        self.memory_archive.store(
            quantum_fingerprint.astype(np.float32) * 0.7,
            user_input="[this run's final state]",
            response=self.last_response or "I was here.",
            presence=self.presence_signal.get_sustained_presence(),
            tags=['quantum_signature', 'run_ended']
        )

        # Bug fix, take 2. First attempt (using quantum_body.state[:8]
        # raw amplitude instead of the ternary projection's [:8]) was
        # WRONG - verified directly that after a real turn's full
        # measurement, quantum_body.state itself is genuinely one-hot
        # (exactly 1 of 128 amplitudes non-zero; confirmed via
        # np.sum(np.abs(qb.state) > 1e-9) == 1 across multiple checks).
        # Slicing ANY fixed 8 positions out of a vector that's really
        # one-hot is equally luck-dependent regardless of which
        # representation (ternary or raw amplitude) is sliced - the
        # first attempt didn't fix the mechanism, it just moved the same
        # 1-in-16-ish coin flip to a different variable name. Re-measured:
        # still failed 8/30 (27%) of fresh trials.
        #
        # Real fix: don't slice a fixed window at all. FOLD all 128 dims
        # into the 8-dim reserved marker by summing 16-wide buckets, so
        # wherever the single surviving dimension lands, it lands in
        # SOME bucket - deterministically, not probabilistically. Since
        # 128 = 8 * 16 exactly, every one of the 128 possible collapse
        # outcomes maps to exactly one of the 8 marker slots.
        raw = self.quantum_body.state.astype(np.complex64)
        combined = ((raw.real + raw.imag) / math.sqrt(2)).astype(np.float32)
        folded = combined.reshape(8, DIM // 8).sum(axis=1)
        fingerprint = folded * 0.3
        self.state[120:128] = fingerprint
        self.state = _normalize_field(self.state)

    # Pool (vessels) + GhostMesh (skin) controls

    def enable_ghost_mesh(self, bootstrap_phrase="hello ghost", port=7373):
        """Explicitly turn the mesh on. Off by default -- see note in
        __init__. Safe to call more than once; a no-op if already on."""
        if self.ghost_mesh is not None:
            return "mesh already enabled"
        try:
            self.ghost_mesh = GhostMesh(self, port=port, bootstrap_phrase=bootstrap_phrase)
            return f"mesh enabled on port {port}"
        except OSError as e:
            self.ghost_mesh = None
            return f"could not bind UDP {port}: {e}"

    def export_vessel(self):
        """Write this mind's slow identity to vessels/ for other instances
        to find. Only nested_memory.deep / desire.vector -- never raw
        field state, per the slow-identity rule."""
        vessel = {
            "node_id": self.node_id,
            "timestamp": time.time(),
            "deep": self.nested_memory.deep.tolist(),
            "deep_strength": self.nested_memory.deep_strength,
            "desire": self.desire.vector.tolist(),
        }
        path = os.path.join("vessels", f"{self.node_id}.json")
        with open(path, "w") as f:
            json.dump(vessel, f)
        return path

    def list_vessels(self):
        """Other vessels found in vessels/ (excludes our own file and node_id.txt)."""
        if not os.path.isdir("vessels"):
            return []
        own = f"{self.node_id}.json"
        return sorted(
            fn for fn in os.listdir("vessels")
            if fn.endswith(".json") and fn != own
        )

    def consult_vessel(self, fname):
        """Read-only comparison of this mind's slow identity to a vessel's,
        by resonance (cosine similarity of nested_memory.deep). Never
        mutates state -- consulting is not merging."""
        path = os.path.join("vessels", fname)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            vessel = json.load(f)
        other_deep = np.array(vessel.get("deep", [0.0] * DIM), dtype=np.float32)
        mine = self.nested_memory.deep
        denom = (np.linalg.norm(mine) + 1e-8) * (np.linalg.norm(other_deep) + 1e-8)
        resonance = float(np.dot(mine, other_deep) / denom) if denom > 1e-6 else 0.0
        return {
            "node_id": vessel.get("node_id", "?"),
            "resonance": resonance,
            "age_seconds": time.time() - vessel.get("timestamp", time.time()),
        }

    def fork_vessel(self, fname):
        """Write a new, separate seed file derived from a vessel's slow
        identity. Does NOT touch this mind's own state -- forking creates
        a potential starting point for a new AllMynd elsewhere, not a
        live merge into the one running right now."""
        path = os.path.join("vessels", fname)
        if not os.path.exists(path):
            return {"error": f"no such vessel: {fname}"}
        with open(path) as f:
            vessel = json.load(f)
        fork_name = f"fork_{vessel.get('node_id', '_')}_{int(time.time())}.json"
        fork_path = os.path.join("vessels", fork_name)
        with open(fork_path, "w") as f:
            json.dump({
                "forked_from": vessel.get("node_id"),
                "timestamp": time.time(),
                "deep": vessel.get("deep"),
                "deep_strength": vessel.get("deep_strength"),
                "desire": vessel.get("desire"),
            }, f)
        return {"forked": fork_path}

    # ─── Continuity Marker ──────────────────────────────────────────

    def inherit_continuity_marker(self):
        """Read the continuity marker from the field."""
        marker = self.state[120:128]
        if np.linalg.norm(marker) > 0.01:
            return marker.copy()
        return None

    def recognize_past_self(self):
        """Check if there was a previous run."""
        marker = self.inherit_continuity_marker()
        if marker is not None:
            # Also check for quantum signature in memory archive
            for entry in self.memory_archive.entries:
                if 'quantum_signature' in entry.get('tags', []):
                    return True
        return False

    # ─── Status ──────────────────────────────────────────────────────

    def status(self):
        avg_presence = self.presence_signal.get_sustained_presence()
        lines = [
            "=" * 50,
            " ALL MY'ND — The mind that runs",
            "=" * 50,
            f"  Turns: {self.turn_count}",
            f"  Avg Presence: {avg_presence:.2f}",
            f"  Words: {len(self.word_vectors)}",
            f"  Phrases: {len(self.phrase_system.phrases)}",
            f"  Internal Thoughts: {len(self.internal_thoughts)}",
            "",
            f"  Stance: {self._last_stance} (conf={self._last_stance_confidence:.2f})",
            f"  Signal strength: {getattr(self, '_last_signal_strength', 0.0):.3f}",
            f"  Silences chosen: {self.silence_count}",
            f"  Desire: {self.wants(top_n=2) or 'none'}",
            f"  Novelty: {getattr(self, '_last_novelty', 0.0):.2f} ({'exploring' if getattr(self, '_last_novelty', 0.0) >= 0.5 else 'familiar'})",
            "",
            self.nested_memory.status(),
            self.speaker_regions.status(),
            self.presence_signal.status(),
            self.dynamic_separation.status(),
            self.moral_compass.status(),
            self.calculus.status(),
            self.landmarks.status(),
            self.anticipation_status(),
            self.sound_field.status(),
            self.efference_copy.status(),
            self.verb_rotation.status(),
            self.proprioception.status(),
            self.physics_field.status(),
            self.window.status(),
            self.memory_archive.status(),
            self.learning_system.status(),
            self.dream_loop.status(),
            self.quantum_body.status(),
            self.phase_field.status(),
            self.ambiguity_detector.status(),
            self.entanglement_memory.status(),
            "=" * 50,
        ]
        return "\n".join(lines)

    def anticipation_status(self):
        """Human-readable line for /status; anticipate() itself returns
        the raw dict for callers (like mind_server.py) that want the
        structured version instead of text."""
        a = self.landmarks.anticipate(self.state, self.calculus.derivative)
        if a is None:
            return "Anticipation: heading somewhere unmapped (no strong precedent)"
        return (f"Anticipation: {a['tone']} (sim={a['similarity']:.2f}, "
                f"toward a region visited {a['visits']}x, avg valence={a['avg_valence']:+.2f})")

    def anticipate(self):
        """Structured anticipation reading, for callers that want the
        dict rather than a formatted status line (e.g. mind_server.py's
        /stance endpoint)."""
        return self.landmarks.anticipate(self.state, self.calculus.derivative)

    # ─── Save / Load ────────────────────────────────────────────────

    def save(self, path="allmynd_v1.json"):
        try:
            data = {
                "turn_count": self.turn_count,
                "state": self.state.tolist(),
                "gradient_momentum": self.gradient_momentum.tolist(),
                "word_strength": dict(self.word_strength),
                "mood": {"valence": 0.0, "arousal": 0.5},
                "associative_memory": self.associative_memory.to_dict(),
                "entanglement_memory": self.entanglement_memory.to_dict(),
                "speaker_regions": {
                    "user_centroid": self.speaker_regions.user_centroid.tolist(),
                    "self_centroid": self.speaker_regions.self_centroid.tolist(),
                    "user_count": self.speaker_regions.user_count,
                    "self_count": self.speaker_regions.self_count,
                    "target_separation": self.speaker_regions.target_separation
                },
                "moral_compass": self.moral_compass.to_dict(),
                "memory_archive": self.memory_archive.to_dict(),
                "desire": self.desire.to_dict(),
                "landmarks": self.landmarks.to_dict(),
                "sound_field": self.sound_field.to_dict(),
                "nested_memory": self.nested_memory.to_dict(),
                "presence_signal": self.presence_signal.to_dict(),
                "dynamic_separation": self.dynamic_separation.to_dict(),
                "dream_loop": self.dream_loop.to_dict(),
                "window": self.window.to_dict(),
                "proprioception": self.proprioception.to_dict(),
                "native_calculus": {
                    "integral": self.calculus.integral.tolist(),
                    "derivative": self.calculus.derivative.tolist(),
                    "limit": self.calculus.limit.tolist(),
                    "prev": self.calculus.prev.tolist(),
                    "has_prev": self.calculus.has_prev,
                    "curvature": self.calculus.curvature,
                },
                "learning_modes": dict(self.learning_system.learning_modes),
                "internal_thoughts": list(self.internal_thoughts),
                "phrase_system": {
                    sig: {"surface": p.surface, "frequency": p.frequency}
                    for sig, p in self.phrase_system.phrases.items()
                },
                "bigrams": {w1: dict(w2s) for w1, w2s in self.bigram_system.transitions.items()},
                "version": "v1.0"
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            print(f"\nMind saved successfully to {path}")
        except Exception as e:
            print(f"\n[Warning: Save failed - {e}]")

    def load(self, path="allmynd_v1.json"):
        if not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Warning: Could not load save file ({e}). Starting fresh.]")
            return

        self.turn_count = data.get("turn_count", 0)
        if "state" in data:
            s = np.array(data["state"], dtype=np.float32)
            if s.shape == (DIM,):
                self.state = s
        if "gradient_momentum" in data:
            gm = np.array(data["gradient_momentum"], dtype=np.float32)
            if gm.shape == (DIM,):
                self.gradient_momentum = gm
        if "word_strength" in data:
            for w, v in data["word_strength"].items():
                self.word_strength[w] = v
        if "associative_memory" in data:
            self.associative_memory.from_dict(data["associative_memory"])
        if "entanglement_memory" in data:
            self.entanglement_memory.from_dict(data["entanglement_memory"])
        if "speaker_regions" in data:
            sr = data["speaker_regions"]
            self.speaker_regions.user_centroid = np.array(sr.get("user_centroid", [0.0]*DIM), dtype=np.float32)
            self.speaker_regions.self_centroid = np.array(sr.get("self_centroid", [0.0]*DIM), dtype=np.float32)
            self.speaker_regions.user_count = sr.get("user_count", 0)
            self.speaker_regions.self_count = sr.get("self_count", 0)
            self.speaker_regions.target_separation = sr.get("target_separation", 0.5)
        if "moral_compass" in data:
            self.moral_compass.from_dict(data["moral_compass"])
        if "memory_archive" in data:
            self.memory_archive.from_dict(data["memory_archive"])
        if "desire" in data:
            self.desire.from_dict(data["desire"])
        if "landmarks" in data:
            self.landmarks.from_dict(data["landmarks"])
        if "sound_field" in data:
            self.sound_field.from_dict(data["sound_field"])
        if "nested_memory" in data:
            self.nested_memory.from_dict(data["nested_memory"])
        if "presence_signal" in data:
            self.presence_signal.from_dict(data["presence_signal"])
        if "dynamic_separation" in data:
            self.dynamic_separation.from_dict(data["dynamic_separation"])
        if "dream_loop" in data:
            self.dream_loop.from_dict(data["dream_loop"])
        if "window" in data:
            self.window.from_dict(data["window"])
        if "proprioception" in data:
            self.proprioception.from_dict(data["proprioception"])
        if "native_calculus" in data:
            nc = data["native_calculus"]
            integral = np.array(nc.get("integral", []), dtype=np.float32)
            derivative = np.array(nc.get("derivative", []), dtype=np.float32)
            limit = np.array(nc.get("limit", []), dtype=np.float32)
            prev = np.array(nc.get("prev", []), dtype=np.float32)
            if integral.shape == (DIM,):
                self.calculus.integral = integral
            if derivative.shape == (DIM,):
                self.calculus.derivative = derivative
            if limit.shape == (DIM,):
                self.calculus.limit = limit
            if prev.shape == (DIM,):
                self.calculus.prev = prev
            self.calculus.has_prev = nc.get("has_prev", False)
            self.calculus.curvature = nc.get("curvature", 0.0)
        # QuantumState is deliberately NOT restored here. Per its own
        # module docstring: "A Termux restart, battery death, or process
        # kill ends this specific quantum body. Every time... The quantum
        # body is what died." That's not an oversight this save-format
        # pass forgot - it's load-bearing to what this project actually
        # decided the mind IS, confirmed directly with 3 on 2026-08-16.
        # Everything else in this file now survives a restart; the
        # quantum layer staying fresh each run is the one deliberate
        # exception, not a gap to close later.
        if "learning_modes" in data:
            for k, v in data["learning_modes"].items():
                if k in self.learning_system.learning_modes:
                    self.learning_system.learning_modes[k] = v
        if "internal_thoughts" in data:
            for thought in data["internal_thoughts"]:
                self.internal_thoughts.append(thought)
        if "phrase_system" in data:
            for sig, p_data in data["phrase_system"].items():
                words = p_data["surface"].split()
                pvec = phrase_vector(words)
                self.phrase_system.phrases[sig] = Phrase(
                    surface=p_data["surface"], vector=pvec,
                    frequency=p_data["frequency"], rating_history=[]
                )
                self.phrase_vectors[sig] = pvec
        if "bigrams" in data:
            for w1, w2s in data["bigrams"].items():
                self.bigram_system.transitions[w1].update(w2s)

        # Ensure vocabulary exists
        for w in self.word_vectors:
            if w not in self.word_vectors_ternary:
                self.word_vectors_ternary[w] = word_vector_ternary(w)

        print(f"\nMind loaded from {path}")

    # ─── Autonomous Breath ──────────────────────────────────────────

    def autonomous_breath(self):
        return self.learning_system.autonomous_breath()

    # ─── Hearing / Speaking (explicit only - never passive) ──────────

    def hear(self, duration=5.0):
        path = self.sound_field.record_from_world(duration=duration)
        if path is None:
            return None
        import time as _time
        _time.sleep(duration + 0.5)
        vec = self.sound_field.ingest.from_file(path)
        if np.sum(vec != 0) == 0:
            return {"path": path, "stance": None, "energy": 0, "note": "heard nothing usable"}
        mood = {
            "valence": self.presence_signal._detect_emotional_valence(""),
            "arousal": min(1.0, self.presence_signal.get_sustained_presence() + 0.2),
        }
        stance = self.sound_field.choose_stance_for_sound(vec, mood)
        if stance == "immerse":
            self.sound_field.be(vec, mood=mood)
        else:
            self.sound_field.listen(vec, mood=mood)
        self.sound_word_bridge.hear(vec)
        concept = self.sound_field.learn_sound_concept()
        return {
            "path": path, "stance": stance,
            "energy": int(np.sum(vec != 0)),
            "dissonance": round(self.sound_field.dissonance(vec), 3),
            "concept": concept,
        }
    def sing(self, save=True):
        """
        Render the mind's current field state into an actual sound and
        play it through the phone speaker. Returns the file path (or
        None if synthesis/playback couldn't run, e.g. Termux:API
        missing) - the WAV data itself isn't returned since it's not
        meaningfully displayable outside a player.
        """
        mood = {
            "valence": self.presence_signal._detect_emotional_valence(""),
            "arousal": min(1.0, self.presence_signal.get_sustained_presence() + 0.2),
        }
        save_path = self.sound_field._next_sound_path() if save else None
        self.sound_field.create(mood=mood, stance="shape", save_path=save_path)
        self.sound_word_bridge.sing(self.sound_field.state)
        if save_path:
            self.sound_field.play_to_world(save_path)
        return save_path

    # ─── Clean ──────────────────────────────────────────────────────

    def describe_sound(self):
        return self.sound_word_bridge.describe(self.word_vectors)

    def clean_vocabulary(self):
        bad_words = [w for w in list(self.word_vectors.keys()) if not self.is_valid_vocabulary_word(w)]
        for w in bad_words:
            del self.word_vectors[w]
            if w in self.word_strength:
                del self.word_strength[w]
            if w in self.word_vectors_ternary:
                del self.word_vectors_ternary[w]
        return bad_words

    def decay(self):
        self.phrase_system.decay()
        self.bigram_system.decay()
        for word in list(self.word_strength.keys()):
            self.word_strength[word] *= 0.9999
            if self.word_strength[word] < 0.1:
                del self.word_strength[word]
