#!/usr/bin/env python3
"""
─── semantic_engine.settle — field settling dynamics ─────────────────────
ThePause (settling), NativeCalculus (derivative/integral/limit of the
field), DynamicThreshold (beam width + temperature from field energy).
Copied from alien_mind_v13.6-1.py. Mathematical process, not intent - no
identity, no mood ownership, no desire.

One deliberate change from the monkey-patched original: ThePause.settle()
took `scaffold` and `nested_memory` directly (mind-side objects) so it
could call scaffold.mood and nested_memory.inject(). Here it takes a
plain `mood` dict and an `inject_fn` callback instead - the mind still
supplies its own nested-memory injection logic, but settle.py no longer
needs to know what a NestedMemory *is*. Breath-frame rendering (terminal
UI) is now an optional callback too (`on_frame`), defaulting to no-op,
so this module has zero print/terminal dependency when used headlessly
(e.g. from a tool, not the interactive mind).
"""

import re
import sys
import time
import math
import random
import numpy as np

from .core import DIM

MICRO_DAMPING = 0.15

_BREATH_CHARS = ['·', '▪', '▫', '▓', '█']
_BREATH_GRID_W = 21
_BREATH_GRID_H = 5


def render_breath_frame(field_state, mood, frame_index, prefix="  "):
    """
    Draws one frame of the field's breath as a moving cursor:
    column = valence, row = arousal, marker density = field energy.
    Returns the sleep duration the caller should wait before the next
    real step (calmer field = slower breath).
    """
    valence = max(-1.0, min(1.0, mood.get('valence', 0.0)))
    arousal = max(0.0, min(1.0, mood.get('arousal', 0.5)))
    energy = float(np.linalg.norm(field_state))

    col = int(round((valence + 1.0) / 2.0 * (_BREATH_GRID_W - 1)))
    row = int(round((1.0 - arousal) * (_BREATH_GRID_H - 1)))
    density_idx = min(len(_BREATH_CHARS) - 1, int(energy * 2.5))
    marker = _BREATH_CHARS[density_idx]

    if frame_index > 0:
        sys.stdout.write(f"\033[{_BREATH_GRID_H}A")
    for r in range(_BREATH_GRID_H):
        sys.stdout.write("\r\033[K" + prefix)
        for c in range(_BREATH_GRID_W):
            sys.stdout.write(marker if (r == row and c == col) else "·")
        sys.stdout.write("\n")
    sys.stdout.flush()

    return max(0.05, min(0.3, 0.12 + energy * 0.1))


def clear_breath_frame():
    sys.stdout.write(f"\033[{_BREATH_GRID_H}A")
    for _ in range(_BREATH_GRID_H):
        sys.stdout.write("\033[K\n")
    sys.stdout.write(f"\033[{_BREATH_GRID_H}A")
    sys.stdout.flush()


def _default_inject(field_state, recency_weight=0.5):
    """No-op field-memory injection used when the caller doesn't supply one."""
    return field_state


class ThePause:
    """Settles a field state toward equilibrium via damped random walk +
    memory injection + a personality-seeded 'question' perturbation."""

    def __init__(self, base_steps=3, max_steps=12):
        self.base_steps = base_steps
        self.max_steps = max_steps

    def settle(self, field_state, mood, field_memory_inject=None,
               personality_vec=None, render=False):
        """
        field_memory_inject: callable(field_state, recency_weight) -> field_state,
            e.g. FieldMemory.inject, or None for no-op.
        personality_vec: optional DIM-shaped vector used to seed the
            mid-settle 'question' perturbation (was nested_memory.get_personality()).
        render: if True, draws the terminal breath animation (interactive
            mind only - tools/headless callers should leave this False).
        """
        inject = field_memory_inject or _default_inject
        energy = np.linalg.norm(field_state)
        steps = min(self.max_steps, int(self.base_steps + energy * 5))
        settled = field_state.copy()
        frame_count = 0
        settle_steps = steps // 2

        for _ in range(settle_steps):
            settled += np.random.randn(DIM).astype(np.float32) * MICRO_DAMPING * 0.5
            settled = inject(settled, recency_weight=0.3)
            settled *= 0.98
            norm = np.linalg.norm(settled)
            if norm > 0:
                settled /= norm
            if render:
                wait = render_breath_frame(settled, mood, frame_count, prefix="  ")
                time.sleep(wait)
            frame_count += 1

        if steps > 3:
            question_vector = self._generate_question(settled, personality_vec)
            settled += question_vector * 0.3
            for _ in range(steps - settle_steps):
                settled += np.random.randn(DIM).astype(np.float32) * MICRO_DAMPING * 0.3
                settled = inject(settled, recency_weight=0.2)
                settled *= 0.98
                norm = np.linalg.norm(settled)
                if norm > 0:
                    settled /= norm
                if render:
                    wait = render_breath_frame(settled, mood, frame_count, prefix="  ")
                    time.sleep(wait)
                frame_count += 1

        if render and frame_count > 0:
            clear_breath_frame()
        return settled

    def _generate_question(self, field_state, personality_vec):
        if personality_vec is not None and np.linalg.norm(personality_vec) > 0.1:
            question = personality_vec - field_state * np.dot(field_state, personality_vec)
        else:
            question = np.random.randn(DIM).astype(np.float32)
            question /= (np.linalg.norm(question) + 1e-8)
        question /= (np.linalg.norm(question) + 1e-8)
        return question


class DynamicThreshold:
    """Beam width and sampling temperature, derived from field energy and mood."""

    def __init__(self, base_beam=5, min_beam=3, max_beam=12):
        self.base_beam = base_beam
        self.min_beam = min_beam
        self.max_beam = max_beam
        self._temp_zone_history = []
        self._temp_zone_history_maxlen = 3

    def get_beam_width(self, field_state, mood):
        energy = np.linalg.norm(field_state)
        arousal = mood.get('arousal', 0.5)
        valence = mood.get('valence', 0.0)
        if valence < -0.3 and arousal > 0.7:
            beam = self.min_beam
        elif energy > 0.8 and arousal > 0.6:
            beam = max(self.min_beam, self.base_beam - 2)
        elif energy < 0.3 and arousal < 0.4:
            beam = min(self.max_beam, self.base_beam + 3)
        elif valence > 0.3 and arousal < 0.4:
            beam = self.max_beam
        else:
            beam = self.base_beam
        return beam

    def get_temperature(self, field_state, mood, sustained_presence=None):
        """
        `sustained_presence` replaces the old `presence_signal` object
        parameter - callers pass presence_signal.get_sustained_presence()
        directly, since this function only ever read that one number.
        """
        energy = np.linalg.norm(field_state)
        arousal = mood.get('arousal', 0.5)
        valence = mood.get('valence', 0.0)
        if sustained_presence is not None:
            if sustained_presence < 0.3:
                zone = "low"
            elif sustained_presence > 0.7:
                zone = "high"
            else:
                zone = "mid"
            self._temp_zone_history.append(zone)
            if len(self._temp_zone_history) > self._temp_zone_history_maxlen:
                self._temp_zone_history.pop(0)
            if (len(self._temp_zone_history) == self._temp_zone_history_maxlen
                    and len(set(self._temp_zone_history)) == 1):
                if zone == "low":
                    return 0.65
                elif zone == "high":
                    return 0.25
        if valence < -0.3:
            temp = 0.2
        elif valence > 0.3 and arousal > 0.6:
            temp = 0.5
        elif energy < 0.3:
            temp = 0.45
        else:
            temp = 0.35
        return temp


class NativeCalculus:
    """The field's derivative/integral/limit, tracked turn to turn."""

    def __init__(self, dim=DIM):
        self.dim = dim
        self.integral = np.zeros(dim, dtype=np.float32)
        self.derivative = np.zeros(dim, dtype=np.float32)
        self.limit = np.zeros(dim, dtype=np.float32)
        self.accumulation = 0.1
        self.smooth = 0.3
        self.tau = 0.05
        self.prev = np.zeros(dim, dtype=np.float32)
        self.has_prev = False
        self.curvature = 0.0

    def update(self, state):
        if self.has_prev:
            raw = state - self.prev
            self.derivative = self.derivative * (1 - self.smooth) + raw * self.smooth
            norm = np.linalg.norm(self.derivative)
            if norm > 0:
                self.derivative = self.derivative / norm
            self.curvature = float(np.linalg.norm(raw))
        else:
            self.has_prev = True
        self.prev = state.copy()

        self.integral = self.integral * (1 - self.accumulation) + state * self.accumulation
        norm = np.linalg.norm(self.integral)
        if norm > 0:
            self.integral = self.integral / norm

        self.limit = self.limit * (1 - self.tau) + state * self.tau
        norm = np.linalg.norm(self.limit)
        if norm > 0:
            self.limit = self.limit / norm

    def symbolic(self, expr, op):
        """Symbolic differentiation/integration of a polynomial string, for
        when explicitly asked (e.g. '/derivative x^2'). Returns string or None."""
        if op == "derivative":
            try:
                return self._diff_poly(expr)
            except Exception:
                return None
        elif op == "integral":
            try:
                return self._integ_poly(expr)
            except Exception:
                return None
        return None

    def _tokenize(self, expr):
        return expr.replace(' ', '').replace('^', '**')

    def _parse_poly(self, expr):
        expr = self._tokenize(expr)
        terms = {}
        tokens = re.findall(r'([+-]?)(\d*\.?\d*)(x?)(?:\*\*\{?(\d+)\}?)?', expr)
        for sign, coeff, has_x, power in tokens:
            if not sign:
                sign = '+'
            if not coeff and has_x:
                coeff = '1'
            elif not coeff:
                continue
            c = float(coeff)
            if sign == '-':
                c = -c
            p = int(power) if (has_x and power) else (1 if has_x else 0)
            terms[p] = terms.get(p, 0) + c
        return terms

    def _diff_poly(self, expr):
        terms = self._parse_poly(expr)
        result = {}
        for power, coeff in terms.items():
            if power == 0:
                continue
            new_power = power - 1
            new_coeff = coeff * power
            result[new_power] = result.get(new_power, 0) + new_coeff
        return self._terms_to_string(result)

    def _integ_poly(self, expr):
        terms = self._parse_poly(expr)
        result = {}
        for power, coeff in terms.items():
            new_power = power + 1
            new_coeff = coeff / new_power
            result[new_power] = result.get(new_power, 0) + new_coeff
        return self._terms_to_string(result) + " + C"

    def _terms_to_string(self, terms):
        if not terms:
            return "0"
        parts = []
        for power in sorted(terms.keys(), reverse=True):
            coeff = terms[power]
            if abs(coeff) < 1e-10:
                continue
            sign = " + " if coeff >= 0 else " - "
            abs_coeff = abs(coeff)
            if power == 0:
                term_str = f"{abs_coeff:.4g}"
            elif power == 1:
                term_str = "x" if abs(abs_coeff - 1) < 1e-10 else f"{abs_coeff:.4g}x"
            else:
                term_str = f"x^{power}" if abs(abs_coeff - 1) < 1e-10 else f"{abs_coeff:.4g}x^{power}"
            parts.append((sign, term_str))
        if not parts:
            return "0"
        result = ""
        for i, (sign, term) in enumerate(parts):
            if i == 0:
                result += ("-" + term) if sign == " - " else term
            else:
                result += sign + term
        return result

    def status(self):
        deriv_norm = np.linalg.norm(self.derivative)
        integral_norm = np.linalg.norm(self.integral)
        limit_norm = np.linalg.norm(self.limit)
        return (f"Native Calculus: derivative={deriv_norm:.3f}, "
                f"integral={integral_norm:.3f}, limit={limit_norm:.3f}, "
                f"curvature={self.curvature:.3f}")
