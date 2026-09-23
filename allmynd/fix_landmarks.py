import re

with open('mind.py', 'r') as f:
    content = f.read()

# 1. Change the default merge threshold from 0.35 to 0.15
content = content.replace(
    'merge_threshold=0.35',
    'merge_threshold=0.15'
)

# 2. Add a dynamic adjustment in the observe method: if the region count is low, lower the threshold further.
# We'll find the observe method and add a line that adjusts threshold based on number of landmarks.
# Find the line where best_sim is compared to merge_threshold and add adaptive logic.

# We'll replace the line:
# if best_idx is not None and best_sim >= self.merge_threshold:
# with a block that uses a dynamic threshold.

observe_start = content.find('def observe(self, field_state, turn, mood, presence):')
if observe_start != -1:
    lines = content.splitlines(keepends=True)
    i = observe_start
    # Find the line with "if best_idx is not None and best_sim >= self.merge_threshold:"
    for idx, line in enumerate(lines):
        if 'if best_idx is not None and best_sim >= self.merge_threshold:' in line:
            # Replace the entire if block with a dynamic version.
            # We'll capture the block until the else or next method.
            # But simpler: we can just replace the condition with a call to a dynamic threshold.
            # I'll replace the condition and add a helper function.
            # Instead of complex rewriting, I'll add a line before the if that adjusts threshold based on len(self.landmarks).
            # Insert after the line that computes best_sim.
            break
    # I'll do a simpler replace: add a line before the if condition.
    content = content.replace(
        'if best_idx is not None and best_sim >= self.merge_threshold:',
        '        # Dynamic threshold: if we have few landmarks, use a lower threshold\n        dynamic_threshold = self.merge_threshold - min(0.1, (1.0 - len(self.landmarks) / 10) * 0.05)\n        if best_idx is not None and best_sim >= dynamic_threshold:'
    )

# 3. Also reduce the max_landmarks from 40 to 20? No, keep 40, but lower threshold is enough.

with open('mind.py', 'w') as f:
    f.write(content)

print("LandmarkMap threshold lowered to 0.15 and dynamic adjustment added.")
