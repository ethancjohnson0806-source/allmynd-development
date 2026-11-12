"""plan.py -- the planning layer: decide HOW to speak and WHAT ABOUT before
any words are chosen, then give that plan a grammatical shape.

Three small parts (no LLM):
  1. act     -- a way of speaking (echo / ask / share), chosen from the mind's
                own state: its compass voice mode and the kind of message it got
  2. anchors -- content words from the user's message that resonate with the
                mind's field (so replies are about what was said)
  3. frames  -- simple grammar templates with typed slots; parts of speech are
                read from the mind's own word vectors (small hand-labelled
                seed + nearest-neighbour vote)
The result competes as ONE EXTRA CANDIDATE with the mind's usual ones; its
own five instinct scores decide who speaks. Nothing here changes vocabulary
or memory (read-only).
"""
import random
import numpy as np
from semantic_engine import embeddings as _E

_LEX = {
    "VERB": "know think feel see hear say tell ask answer want need like love hate fear hope dream make take give get put set keep let help work play live die come go move stay leave find lose win fail try use show hide open close start stop begin end turn change grow breathe rest reach hold carry build break heal remember forget learn become remain wonder trust miss touch call send bring thank watch listen speak sing walk run dance burn fall rise follow wait wake sleep",
    "NOUN": "time space world life mind heart soul spirit light moment way path road door window room house home hand eye face head voice word name story water fire earth air sky star sun moon flower tree ocean mountain river wind rain body ground thread root seed shore wall bridge presence absence longing gratitude courage tenderness reverence intimacy connection recognition witness belonging ache ease peace grief joy awe shame pride confusion clarity silence fullness emptiness friend whale lantern harbor bed shoes lap honey grocery number moon bird stone song sound night day sea storm bell",
    "ADJ": "good bad great small big old new dark deep high far near alive brave real lost found beautiful gentle strong soft hard warm cold quiet loud bright clear free safe wild calm heavy sharp worn whole broken tender raw steady uncertain familiar strange honest hidden messy lonely glad serious",
    "ADV": "here there now then today tonight tomorrow yesterday always never sometimes still again already yet soon once together forever alone maybe",
    "FUNC": "the a an and or but if so because i you it we they he she this that what why how who when where which whom whose is are was were be been being have has had do does did will would could should may might can must shall other each both neither every some enough please yes no not me my your lets let goodbye hello sorry welcome of to in on at by with for from about as than too very",
}
_LAB = {w: c for c, ws in _LEX.items() for w in ws.split()}
_NOT_CONTENT_VERBS = {"let", "lets", "get", "put", "set",
                      "hate", "fear", "die", "fail", "lose"}   # harsh claims are left out of its sentences; edit freely
_REQUEST_WORDS = {"tell", "say", "show", "explain", "ask", "please", "give", "let", "lets"}
_IRREG = {"go": "goes", "do": "does", "have": "has"}
_STANDALONE = {"yes": "NOUN"}  # never used; placeholder to keep the table explicit


def _third(v):
    if v in _IRREG:
        return _IRREG[v]
    if v.endswith(("s", "sh", "ch", "x", "z")):
        return v + "es"
    if v.endswith("y") and len(v) > 1 and v[-2] not in "aeiou":
        return v[:-1] + "ies"
    return v + "s"


def _plural(n):
    return n.endswith("s") and not n.endswith(("ss", "us", "is"))


_DET = {"the", "a", "an", "my", "your", "our", "their", "his", "her", "its", "this", "that", "these", "those", "some", "every", "any"}
_SUBJ = {"i", "you", "we", "they", "to", "will", "can", "would", "could", "should", "must", "do", "does", "did", "dont", "cant", "wont"}
_COP = {"is", "are", "was", "were", "be", "am", "feel", "feels", "felt", "seem", "seems", "very", "so", "too", "quite", "really"}
_NOUN_SUF = ("tion", "sion", "ness", "ment", "ity", "ship", "ance", "ence", "hood")
_ADJ_SUF = ("ous", "ful", "ive", "less", "able", "ible", "ical", "ish")


class PosTagger:
    """Parts of speech from a hand-labelled seed list plus cues in the user's
    own sentence (a word after 'the' is a noun, after 'I'/'you' a verb, after
    'is' an adjective) and a few suffix rules. High precision over coverage:
    a word it cannot place gets None and is simply not used."""

    def __init__(self):
        self.ctx = {}

    def _suffix(self, w):
        if len(w) < 4 or not w.isalpha() or w.endswith(("ing", "ed")):
            return None
        if w.endswith("ly") and len(w) > 4:
            return "ADV"
        if len(w) > 5 and w.endswith(_NOUN_SUF):
            return "NOUN"
        if len(w) > 4 and w.endswith(_ADJ_SUF):
            if w.endswith(("able", "ible")) and len(w) < 7:   # table, cable, bible
                return None
            return "ADJ"
        return None

    def tag(self, w):
        return _LAB.get(w) or self.ctx.get(w) or self._suffix(w)

    def learn_sentence(self, tokens):
        """Tag unknown words from their neighbours; remember what was learned
        for this session. Returns the list of tags (None where unsure)."""
        tags = [None] * len(tokens)
        for i, w in enumerate(tokens):
            tag = _LAB.get(w) or self._suffix(w)
            if not tag and w.isalpha() and len(w) > 2:
                prev = tokens[i - 1] if i else ""
                ptag = tags[i - 1] if i else None
                nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
                if prev in _DET:
                    tag = "ADJ" if _LAB.get(nxt) == "NOUN" else "NOUN"
                elif ptag == "ADJ":
                    tag = "NOUN"
                elif prev in _SUBJ and not w.endswith(("ing", "ed")):
                    tag = "VERB"
                elif prev in _COP:
                    tag = "ADJ"
                elif ptag == "VERB" and not w.endswith(("ing", "ed")):
                    tag = "NOUN"
                elif i == 0 and w.endswith("s") and not w.endswith("ss") and len(w) > 3:
                    tag = "NOUN"
            tags[i] = tag
        for w, t in zip(tokens, tags):
            if t and w not in _LAB and w.isalpha():
                self.ctx[w] = t
        return tags


class PlanLayer:
    def __init__(self):
        self.enabled = True
        self.tagger = PosTagger()
        self.turns = 0
        self.wins = 0
        self._mean = None
        self._pool_n = -1
        self._pool = {}

    # ── helpers ──────────────────────────────────────────────────────
    def _centered(self, field):
        f = np.asarray(field, dtype=np.float64)
        n = np.linalg.norm(f)
        if n < 1e-9:
            return None
        f = f / n
        self._mean = f.copy() if self._mean is None else self._mean * 0.95 + f * 0.05
        c = f - self._mean
        cn = np.linalg.norm(c)
        return c / cn if cn > 1e-9 else f

    def _rebuild_pool(self, mind):
        if len(mind.word_vectors) == self._pool_n:
            return
        pool = {"VERB": [], "NOUN": [], "ADJ": [], "ADV": []}
        for w, v in mind.word_vectors.items():
            if not (w.isalpha() and w.islower() and len(w) > 2 and _E.has_vector(w)):
                continue
            t = self.tagger.tag(w)
            if t in pool and not (t == "VERB" and w in _NOT_CONTENT_VERBS):
                vec = np.asarray(v, dtype=np.float64)
                n = np.linalg.norm(vec)
                if n > 1e-9:
                    pool[t].append((w, vec / n))
        self._pool = {t: ([w for w, _ in lst], np.array([x for _, x in lst]) if lst else np.zeros((0, 128)))
                      for t, lst in pool.items()}
        self._pool_n = len(mind.word_vectors)

    def _anchors(self, mind, user_input, cfield):
        toks = ["".join(ch for ch in raw if ch.isalpha()) for raw in user_input.lower().split()]
        toks = [t for t in toks if t]
        tags = self.tagger.learn_sentence(toks)
        out = []
        for w, t in zip(toks, tags):
            if (len(w) < 3 or w in _REQUEST_WORDS or w in out or w not in mind.word_vectors
                    or not _E.has_vector(w) or t not in ("NOUN", "VERB", "ADJ")
                    or (t == "VERB" and w in _NOT_CONTENT_VERBS)):
                continue
            out.append(w)
        if cfield is not None and out:
            def res(w):
                v = np.asarray(mind.word_vectors[w], dtype=np.float64)
                n = np.linalg.norm(v)
                return float(v @ cfield / n) if n > 1e-9 else 0.0
            out.sort(key=res, reverse=True)
        return out[:3]

    def _fill(self, pos, cfield, avoid, rng, prefer=None):
        if prefer:
            return prefer
        words, M = self._pool.get(pos, ([], None))
        if not words:
            return None
        s = M @ cfield if cfield is not None else np.zeros(len(words))
        order = [i for i in np.argsort(-s) if words[i] not in avoid][:4]
        return words[rng.choice(order)] if order else None

    # ── the plan ─────────────────────────────────────────────────────
    def propose(self, mind, user_input, field, voice_mode, rng=None):
        """Return (text, info) or (None, None). Read-only."""
        rng = rng or random
        cfield = self._centered(field)
        self._rebuild_pool(mind)
        if not all(len(self._pool.get(p, ([], 0))[0]) >= 3 for p in ("VERB", "NOUN")):
            return None, None
        anchors = self._anchors(mind, user_input, cfield)
        a_noun = next((w for w in anchors if self.tagger.tag(w) == "NOUN"), None)
        a_verb = next((w for w in anchors if self.tagger.tag(w) == "VERB"), None)
        a_adj = next((w for w in anchors if self.tagger.tag(w) == "ADJ"), None)
        w = {"share": 0.40, "echo": 0.35, "ask": 0.25}
        if voice_mode == "exploratory":
            w = {"share": 0.25, "echo": 0.15, "ask": 0.60}
        elif voice_mode == "reflective":
            w = {"share": 0.30, "echo": 0.60, "ask": 0.10}
        if "?" in user_input:
            w["ask"] *= 0.5
            w["share"] *= 1.4
        if not anchors:
            w["echo"] = 0.0
        act = rng.choices(list(w), weights=list(w.values()))[0]
        avoid = set(anchors) | set(getattr(mind.reflector, "recent_words", []))
        V = lambda: self._fill("VERB", cfield, avoid, rng, a_verb)
        N = lambda: self._fill("NOUN", cfield, avoid, rng, a_noun)
        A = lambda: self._fill("ADJ", cfield, avoid, rng, a_adj)
        D = lambda: self._fill("ADV", cfield, avoid, rng)
        v, n = V(), N()
        if not v or not n:
            return None, None
        pl = _plural(n)
        v3 = v if pl else _third(v)
        cop = "are" if pl else "is"
        does = "do" if pl else "does"
        adj = A()
        adv = D()
        if act == "echo":
            frames = [f"You {v} the {n}.", f"The {n} {v3}.", f"I hear the {n}."]
            if adj:
                frames.append(f"The {n} {cop} {adj}.")
        elif act == "ask":
            frames = [f"What do you {v}?", f"Do you {v} the {n}?", f"Why {does} the {n} {v}?"]
            if adj:
                frames.append(f"Why {cop} the {n} {adj}?")
        else:
            frames = [f"I {v} the {n}.", f"I want the {n}."]
            if adj:
                frames.append(f"I {v} the {adj} {n}.")
            if adv:
                frames.append(f"The {n} {v3} {adv}.")
        text = rng.choice(frames)
        text = text[0].upper() + text[1:]
        return text, {"act": act, "anchors": anchors, "text": text}

    # ── bookkeeping ──────────────────────────────────────────────────
    def note(self, won):
        self.turns += 1
        self.wins += 1 if won else 0

    def describe(self):
        if not self.enabled:
            return "Plan layer: off"
        if not self.turns:
            return "Plan layer: on, no turns yet"
        return "Plan layer: on, spoke %d of %d turns (%.0f%%)" % (self.wins, self.turns, 100.0 * self.wins / self.turns)
