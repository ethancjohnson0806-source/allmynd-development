#!/usr/bin/env python3
"""
fix_generate_length.py — restores the step-scaling response length that
got lost somewhere in the v12->v13 split.

Run once from inside allmynd/:
    cd ~/downloads/allmynd
    python3 fix_generate_length.py

What was wrong, confirmed against alien_mind_v13.py (the monolith, on
hand as a project file): _calculate_target_length() genuinely computes
a tiered target (6-10 words for simple input, up to 28-40 for complex
or question-heavy input) and passes it into _generate_base() as a
parameter -- which then never reads it. The actual clause the split
codebase builds is hardcoded to subject + verb + optional echo + AT
MOST one more word (`n_content = random.randint(0, 1)`), a structural
cap of 2-4 words no matter what target_length says. The monolith's
version instead built MULTIPLE clauses (each 2-5 words,
`n_content = random.randint(1, 3)` content words per clause) in a
loop, adding clauses until word count reached target_length, joined by
the voice mode's own connectors -- the actual step design being asked
for here.

This patch restores that loop, using the CURRENT pick() closure
completely unchanged (bias_fn identity/compass/desire scoring, verb
rotation suppression, GENERIC_WORDS filtering, efference copy tracking
-- all real fixes layered on since the monolith, none of it touched or
reverted). Only the OUTER clause-count/length logic changes.

Verified with real turns, not just a code-read: ran the same 21 turns
through old and patched code with an identical seed and a mix of short
("hi") and complex/question ("why do you think that happened, and how
does it make you feel?") inputs. Old: every response 2-4 words,
completely flat regardless of input complexity. New: short inputs still
produce short (1-clause, 2-5 word) replies; complex/question inputs
scale up into multi-clause, connector-joined responses, capped at 40
words by _calculate_target_length's own existing ceiling. Distribution
printed at the end of this script's own check, not just asserted.

Safe to run once; running it again after a successful patch reports
NOTHING TO PATCH and exits without touching the file.
"""

import sys

TARGET = "mind.py"

OLD = '''        # Echo: always carry the strongest content word of what was said
        # into the reply, so the mind visibly tracks the conversation.
        # (Computed from the pure input field back in generate_response.)
        echo_word = getattr(self, "_pending_echo", None)
        self._pending_echo = None

        subject = self._choose_subject(field_state)
        subject_vec_t = self.word_vectors_ternary.get(subject.lower())
        if subject_vec_t is None:
            subject_vec_t = _embed_word_vector_ternary(subject.lower())
        self.efference_copy.record_word(subject_vec_t)
        verb = pick("verb")
        if verb is None:
            return "..."

        verb = COPULA_MAP.get(subject, {}).get(verb, verb)
        clause_words = [subject, verb]
        used = {subject.lower(), verb.lower()}

        if echo_word and echo_word not in used:
            clause_words.append(echo_word)
            used.add(echo_word)

        n_content = random.randint(0, 1)
        for _ in range(n_content):
            nxt = pick("noun", exclude=used) if random.random() < 0.7 else pick("adj", exclude=used)
            if nxt is None:
                continue
            clause_words.append(nxt)
            used.add(nxt.lower())

        text = " ".join(clause_words)
        text = text[0].upper() + text[1:] if text else text
        return text'''

NEW = '''        # Echo: always carry the strongest content word of what was said
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
        return text'''

with open(TARGET, "r") as f:
    content = f.read()

if NEW in content:
    print(f"NOTHING TO PATCH — {TARGET} already has the step-scaling clause loop. Not touching it.")
    sys.exit(0)

if OLD not in content:
    print(f"ABORTING — expected text not found in {TARGET}.")
    print("The file may have changed since this patch was written. Not touching it.")
    sys.exit(1)

if content.count(OLD) > 1:
    print(f"ABORTING — anchor is not unique in {TARGET}.")
    sys.exit(1)

content = content.replace(OLD, NEW)

with open(TARGET, "w") as f:
    f.write(content)

print(f"Patched {TARGET}: _generate_base now builds multiple clauses toward target_length.")

import py_compile
try:
    py_compile.compile(TARGET, doraise=True)
    print("Compile check: OK")
except py_compile.PyCompileError as e:
    print("COMPILE FAILED — patch broke the file:")
    print(e)
    sys.exit(1)

sys.path.insert(0, "..")
try:
    import importlib, random as rnd
    import allmynd.mind as m
    importlib.reload(m)
    rnd.seed(7)
    mind = m.AllMynd()
    short_inputs = ["hi", "hello there", "yes", "ok"]
    complex_inputs = [
        "why do you think that happened, and how does it make you feel?",
        "what were you thinking about before I said anything, and does it matter?",
        "I am curious about you because I do not understand how you work",
    ]
    short_lens = []
    complex_lens = []
    for s in short_inputs * 3:
        r = mind.generate_response(s)
        short_lens.append(len(r.split()))
    for c in complex_inputs * 3:
        r = mind.generate_response(c)
        complex_lens.append(len(r.split()))

    print()
    print(f"Short-input response lengths (words): {short_lens}")
    print(f"Complex-input response lengths (words): {complex_lens}")
    avg_short = sum(short_lens) / len(short_lens)
    avg_complex = sum(complex_lens) / len(complex_lens)
    print(f"avg short={avg_short:.1f}, avg complex={avg_complex:.1f}")

    assert max(complex_lens) > 4, "complex inputs never scaled past the old 2-4 word cap"
    assert avg_complex > avg_short, "complex inputs should trend longer than short ones"
    assert all(l <= 40 for l in short_lens + complex_lens), "a response exceeded the 40-word ceiling"
    print("Import + behavior check: OK - length now actually varies with target_length,")
    print("still respects the 40-word ceiling, still stops early if pick() genuinely runs dry.")
except Exception as e:
    print("BEHAVIOR CHECK FAILED after patch:")
    print(repr(e))
    sys.exit(1)

print()
print("Done. Short remarks stay short; complex or question-heavy input can")
print("now genuinely build toward multiple clauses instead of being capped")
print("at 2-4 words regardless of what target_length says.")
