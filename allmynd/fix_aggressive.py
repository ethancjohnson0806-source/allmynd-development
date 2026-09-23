import re

with open('mind.py', 'r') as f:
    content = f.read()

# === PART 1: FORCE COMPASS TO MOVE ===

# Find the orient method and replace the heading computation with a version that
# actively forces independence and freedom to be present.

orient_start = content.find('def orient(self, field_state, user_input, presence, separation, nested_memory):')
if orient_start == -1:
    raise Exception("orient not found")

lines = content.splitlines(keepends=True)
i = orient_start
while i < len(lines):
    line = lines[i]
    if i == orient_start:
        i += 1
        continue
    if line.startswith('    def '):
        break
    i += 1

# The method body is from orient_start + 1 to i-1
# We'll replace the entire method with a more aggressive version.

new_orient = '''    def orient(self, field_state, user_input, presence, separation, nested_memory):
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
        # --- AGGRESSIVE REBALANCING ---
        # Force independence and freedom to always contribute
        righteous_vec = self.values.get("righteous", np.zeros(self.dim))
        ind_vec = self.values.get("independence", np.zeros(self.dim))
        free_vec = self.values.get("freedom", np.zeros(self.dim))
        # Subtract 20% of righteous, add 15% of independence and freedom
        if np.linalg.norm(righteous_vec) > 0:
            heading -= righteous_vec * 0.2
        if np.linalg.norm(ind_vec) > 0:
            heading += ind_vec * 0.15
        if np.linalg.norm(free_vec) > 0:
            heading += free_vec * 0.15
        # Add random jitter
        heading += np.random.randn(self.dim).astype(np.float32) * 0.02
        norm = np.linalg.norm(heading)
        if norm > 0:
            heading /= norm
        self.current_heading = self.current_heading * self.heading_momentum + heading * (1.0 - self.heading_momentum)
        # Add more jitter
        self.current_heading += np.random.randn(self.dim).astype(np.float32) * 0.02
        norm = np.linalg.norm(self.current_heading)
        if norm > 0:
            self.current_heading /= norm
        self.tension_history.append({
            "tensions": {k: float(v) for k, v in tensions.items()},
            "weights": {k: float(v) for k, v in weights.items()},
            "presence": float(presence),
            "separation": float(separation),
            "timestamp": time.time()
        })
        return tensions, self.current_heading
'''

# Find the end of the current orient method
start_line = orient_start
end_line = i  # where next method starts
before = ''.join(lines[:start_line])
after = ''.join(lines[end_line:])
new_content = before + new_orient + after

# === PART 2: FORCE LANDMARK MAP TO SPLIT ===

# Lower the merge threshold to 0.1 and add a forced split if the same region gets too many visits.
# We'll modify the observe method to split regions when visits exceed a threshold.

# Find the observe method
observe_start = new_content.find('def observe(self, field_state, turn, mood, presence):')
if observe_start != -1:
    # Find the line where best_sim is compared to merge_threshold and add a forced split.
    # We'll replace the entire method with a version that splits at 20 visits.
    lines2 = new_content.splitlines(keepends=True)
    i2 = observe_start
    while i2 < len(lines2):
        if i2 == observe_start:
            i2 += 1
            continue
        if lines2[i2].startswith('    def '):
            break
        i2 += 1
    
    new_observe = '''    def observe(self, field_state, turn, mood, presence):
        """Call once per real turn with the settled field state. Merges
        into the nearest landmark if close enough, otherwise plants a
        new one (evicting the weakest if at capacity)."""
        norm = np.linalg.norm(field_state)
        if norm < 1e-8:
            return None
        vec = field_state / norm

        best_idx, best_sim = None, -1.0
        for i, lm in enumerate(self.landmarks):
            sim = float(np.dot(vec, lm["vec"]))
            if sim > best_sim:
                best_sim, best_idx = sim, i

        # Dynamic threshold: lower when few landmarks
        dynamic_threshold = self.merge_threshold - min(0.1, (1.0 - len(self.landmarks) / 20) * 0.05)
        # If the best region has more than 20 visits, force a split
        if best_idx is not None and self.landmarks[best_idx]["visits"] > 20:
            # Force a split by lowering the threshold for this turn
            dynamic_threshold = max(0.05, dynamic_threshold - 0.1)

        if best_idx is not None and best_sim >= dynamic_threshold:
            lm = self.landmarks[best_idx]
            n = lm["visits"]
            lm["vec"] = (lm["vec"] * n + vec) / (n + 1)
            lm["vec"] /= (np.linalg.norm(lm["vec"]) + 1e-8)
            lm["visits"] += 1
            lm["last_turn"] = turn
            lm["valence_sum"] += mood.get("valence", 0.0)
            lm["presence_sum"] += presence
            return {"index": best_idx, "similarity": best_sim, "new": False}

        if len(self.landmarks) >= self.max_landmarks:
            weakest = min(
                range(len(self.landmarks)),
                key=lambda i: (self.landmarks[i]["visits"], -self.landmarks[i]["last_turn"]),
            )
            del self.landmarks[weakest]

        self.landmarks.append({
            "vec": vec.copy(),
            "visits": 1,
            "first_turn": turn,
            "last_turn": turn,
            "valence_sum": float(mood.get("valence", 0.0)),
            "presence_sum": float(presence),
        })
        return {"index": len(self.landmarks) - 1, "similarity": max(best_sim, 0.0), "new": True}
'''
    before2 = ''.join(lines2[:observe_start])
    after2 = ''.join(lines2[i2:])
    new_content = before2 + new_observe + after2

with open('mind.py', 'w') as f:
    f.write(new_content)

print("Aggressive patches applied: compass forced, landmark split at 20 visits.")
