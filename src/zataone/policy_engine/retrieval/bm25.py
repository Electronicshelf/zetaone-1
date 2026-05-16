# zataone BM25 lexical retrieval (pure Python, no external index DB)

from __future__ import annotations

import math
import re
from collections import Counter


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class BM25Index:
    """Okapi BM25 index over a small set of policy documents."""

    def __init__(self, documents: dict[str, str], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._doc_ids = list(documents.keys())
        self._doc_tokens = {doc_id: tokenize(text) for doc_id, text in documents.items()}
        self._doc_len = {doc_id: len(tokens) for doc_id, tokens in self._doc_tokens.items()}
        self._avgdl = (
            sum(self._doc_len.values()) / len(self._doc_len) if self._doc_len else 0.0
        )
        self._df: Counter[str] = Counter()
        self._tf: dict[str, Counter[str]] = {}
        for doc_id, tokens in self._doc_tokens.items():
            tf = Counter(tokens)
            self._tf[doc_id] = tf
            for term in tf.keys():
                self._df[term] += 1
        self._N = len(self._doc_ids)

    def score(self, query: str, doc_id: str) -> float:
        q_terms = tokenize(query)
        if not q_terms or doc_id not in self._tf:
            return 0.0
        dl = self._doc_len.get(doc_id, 0)
        tf_map = self._tf[doc_id]
        total = 0.0
        for term in q_terms:
            df = self._df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1.0 + (self._N - df + 0.5) / (df + 0.5))
            freq = tf_map.get(term, 0)
            denom = freq + self._k1 * (1.0 - self._b + self._b * dl / max(self._avgdl, 1e-9))
            total += idf * (freq * (self._k1 + 1.0)) / max(denom, 1e-9)
        return total

    def query(self, query: str, top_k: int = 8) -> list[tuple[str, float]]:
        scores = [(doc_id, self.score(query, doc_id)) for doc_id in self._doc_ids]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
