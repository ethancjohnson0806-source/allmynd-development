import re

with open('mind.py', 'r') as f:
    content = f.read()

# 1. Replace evaluate_turn method entirely
# We'll locate the method and replace it with a corrected version.
# The corrected version uses a gentle counterforce on all three values,
# no break, and enforces a floor of 0.1.

old_start = content.find('    def evaluate_turn')
if old_start == -1:
    raise Exception("evaluate_turn not found")

# Find the end of the method: next line that starts with '    def ' (not '    def evaluate_turn')
lines = content.splitlines(keepends=True)
i = old_start
method_lines = []
while i < len(lines):
    line = lines[i]
    if i == old_start:
        method_lines.append(line)
    else:
        # If this line is a new method definition at the same indentation, break
        if line.startswith('    def ') and not line.startswith('    def evaluate_turn'):
            break
        method_lines.append(line)
    i += 1

# The old method is method_lines. We'll replace it with the new one.
new_method = '''    def evaluate_turn(self, response_words, presence, separation):
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
                # If this value is consistently high and stable, reduce its weight
                if mean > 0.5 and std < 0.2:
                    self.value_weights[name] *= 0.97
                    if warning is None:
                        warning = f"compass: rebalancing {name}"
                # If this value is consistently low, increase it slightly
                elif mean < -0.1 and std < 0.2:
                    self.value_weights[name] *= 1.03
        # Enforce a floor so no value can be silenced
        for name in self.value_weights:
            if self.value_weights[name] < 0.1:
                self.value_weights[name] = 0.1
        return alignments, warning
'''

# Replace the old method block with the new one
before = ''.join(lines[:old_start])
after = ''.join(lines[i:])
new_content = before + new_method + after

# 2. Add jitter to orient heading to prevent perfect lock
# Find the line where heading is assigned and insert jitter after it.
heading_assign = 'self.current_heading = self.current_heading * self.heading_momentum + heading * (1.0 - self.heading_momentum)'
jitter = '''
        # Add tiny jitter to prevent perfect lock
        self.current_heading += np.random.randn(self.dim).astype(np.float32) * 0.005
        norm = np.linalg.norm(self.current_heading)
        if norm > 0:
            self.current_heading /= norm
'''
new_content = new_content.replace(heading_assign, heading_assign + jitter)

# 3. Reduce heading bias strength from 0.12 to 0.08
new_content = new_content.replace(
    'heading_bias = self.moral_compass.get_heading_bias(field_state, strength=0.12)',
    'heading_bias = self.moral_compass.get_heading_bias(field_state, strength=0.08)'
)

with open('mind.py', 'w') as f:
    f.write(new_content)

print("Patched mind.py successfully.")
