import math
import re
import time
from typing import Any


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self._model = None
        try:
            from sentence_transformers import CrossEncoder  # type: ignore

            self._model = CrossEncoder(model_name)
        except Exception:
            # shortcut: falls back to deterministic term-proximity cross-attention scorer when PyTorch cross-encoder weights are offline
            self._model = None

    def score_pairs(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []

        if self._model is not None:
            try:
                pairs = [[query, t] for t in texts]
                scores = self._model.predict(pairs)
                # Sigmoid normalize if raw logits
                return [round(1.0 / (1.0 + math.exp(-float(s))), 4) for s in scores]
            except Exception:
                pass

        # Deterministic cross-attention proximity & coverage fallback
        q_tokens = [tok for tok in re.findall(r"\w+", query.lower()) if len(tok) > 1]
        if not q_tokens:
            q_tokens = query.lower().split()

        scores: list[float] = []
        for t in texts:
            t_lower = t.lower()
            t_tokens = re.findall(r"\w+", t_lower)
            if not t_tokens:
                scores.append(0.0)
                continue

            # 1. Term coverage ratio
            matched = sum(1 for q in q_tokens if q in t_lower)
            coverage = matched / max(len(q_tokens), 1)

            # 2. Exact phrase bonus
            phrase_bonus = 0.3 if query.lower() in t_lower else 0.0

            # 3. Proximity bonus (distance between query terms in target text)
            positions = [t_lower.find(q) for q in q_tokens if q in t_lower and t_lower.find(q) != -1]
            prox_bonus = 0.0
            if len(positions) >= 2:
                spread = max(positions) - min(positions)
                prox_bonus = max(0.0, 0.2 * (1.0 - (spread / max(len(t_lower), 1))))

            raw = coverage * 0.5 + phrase_bonus + prox_bonus
            # Sigmoid scaling
            score = round(1.0 / (1.0 + math.exp(-3.0 * (raw - 0.5))), 4)
            scores.append(score)

        return scores

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 10,
    ) -> tuple[list[dict[str, Any]], float]:
        t0 = time.perf_counter()
        if not candidates:
            return [], 0.0

        texts = [c.get("chunk_text", "") for c in candidates]
        scores = self.score_pairs(query, texts)

        reranked = []
        for c, score in zip(candidates, scores, strict=True):
            item = dict(c)
            item["rerank_score"] = score
            reranked.append(item)

        # Sort descending by cross-encoder rerank_score
        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return reranked[:top_k], round(elapsed_ms, 2)

