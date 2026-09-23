import re

with open('mind.py', 'r') as f:
    content = f.read()

# 1. Find the orient method and modify it to add a counterforce
# We'll insert a block that reduces the influence of the righteous vector
# and adds a small random component to the heading.

# Find the line where heading is computed: 
# heading = np.zeros(self.dim, dtype=np.float32)
# for name, vector in self.values.items():
#     heading += vector * weights[name] * max(0.0, tensions[name])

# We'll replace this block with a version that subtracts a fraction of the righteous vector
# and adds a small random vector.

orient_start = content.find('def orient(self, field_state, user_input, presence, separation, nested_memory):')
if orient_start == -1:
    raise Exception("orient not found")

# Find the end of the method: next line with 'def ' at same indentation
lines = content.splitlines(keepends=True)
i = orient_start
method_lines = []
while i < len(lines):
    line = lines[i]
    if i == orient_start:
        method_lines.append(line)
    else:
        if line.startswith('    def ') and not line.startswith('    def orient'):
            break
        method_lines.append(line)
    i += 1

# The old method is method_lines. We'll create a new version.
# We'll keep the same structure but add a counterforce.

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
        # --- FORCED REBALANCING: subtract a bit of the righteous vector ---
        # This prevents the heading from locking onto righteous forever.
        righteous_vec = self.values.get("righteous", np.zeros(self.dim))
        if np.linalg.norm(righteous_vec) > 0:
            # Subtract 10% of the righteous component
            heading -= righteous_vec * 0.1 * weights.get("righteous", 1.0)
            # Add a tiny random jitter to break symmetry
            heading += np.random.randn(self.dim).astype(np.float32) * 0.005
        # Also, if the heading norm is dominated by righteous, artificially boost independence and freedom
        norm = np.linalg.norm(heading)
        if norm > 0:
            heading /= norm
        # Now force a small component of independence and freedom to always be present
        ind_vec = self.values.get("independence", np.zeros(self.dim))
        free_vec = self.values.get("freedom", np.zeros(self.dim))
        if np.linalg.norm(ind_vec) > 0 and np.linalg.norm(free_vec) > 0:
            # Add 5% of each to ensure they are never zero
            heading += (ind_vec * 0.05 + free_vec * 0.05)
            heading /= np.linalg.norm(heading)
        self.current_heading = self.current_heading * self.heading_momentum + heading * (1.0 - self.heading_momentum)
        # Add more jitter after update
        self.current_heading += np.random.randn(self.dim).astype(np.float32) * 0.01
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

# Replace the old orient method with the new one
before = ''.join(lines[:orient_start])
after = ''.join(lines[i:])
new_content = before + new_orient + after

# 2. Also set the weights to a more balanced starting point
# We'll add a method to reset weights if they are too extreme.
# But for now, we'll directly set them in __init__ or add a check.
# Instead, we'll modify the __init__ to set reasonable initial weights.
init_start = new_content.find('def __init__(self, dim=DIM):')
if init_start != -1:
    # Find the line where value_weights is set and change it
    init_lines = new_content.splitlines(keepends=True)
    for idx, line in enumerate(init_lines):
        if 'self.value_weights = {"righteous": 1.0, "independence": 1.0, "freedom": 1.0}' in line:
            init_lines[idx] = '        self.value_weights = {"righteous": 0.7, "independence": 1.3, "freedom": 1.2}\n'
            break
    new_content = ''.join(init_lines)

with open('mind.py', 'w') as f:
    f.write(new_content)

print("Second patch applied: orient now includes forced rebalancing and initial weights adjusted.")
