"""
Domain-agnostic SigLIP image–text similarity. Model cache keyed by model_name.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, Optional

import numpy as np

try:
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor

    SIGLIP_AVAILABLE = True
except ImportError:
    SIGLIP_AVAILABLE = False

logger = logging.getLogger(__name__)

_model_bundle: dict[str, tuple[Any, Any, str | None]] = {}
_load_failed: set[str] = set()
_text_embedding_cache: dict[tuple[str, str], np.ndarray] = {}


def _extract_embedding_tensor(output: Any) -> Any:
    if hasattr(output, "pooler_output") and output.pooler_output is not None:
        return output.pooler_output
    if hasattr(output, "last_hidden_state") and output.last_hidden_state is not None:
        return output.last_hidden_state[:, 0, :]
    return output[0] if hasattr(output, "__getitem__") else output


def _get_siglip(model_name: str) -> tuple[Any, Any, str] | None:
    if model_name in _load_failed:
        return None
    if model_name in _model_bundle:
        return _model_bundle[model_name]
    if not SIGLIP_AVAILABLE:
        return None
    try:
        processor = AutoProcessor.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        model.eval()
    except Exception:
        logger.exception("modality.embedding: SigLIP load failed for %s", model_name)
        _load_failed.add(model_name)
        return None
    _model_bundle[model_name] = (model, processor, device)
    return _model_bundle[model_name]


def encode_regulation_texts(
    regulation_texts: list[tuple[str, str]],
    model_name: str = "google/siglip-base-patch16-224",
) -> Optional[list[np.ndarray]]:
    """Encode (name, text) pairs to normalized text embeddings; uses per-text cache."""
    if not SIGLIP_AVAILABLE or not regulation_texts:
        return None
    embeddings: list[tuple[int, np.ndarray]] = []
    texts_to_encode: list[str] = []
    text_indices: list[int] = []
    for i, (_name, text) in enumerate(regulation_texts):
        ck = (model_name, text)
        if ck in _text_embedding_cache:
            embeddings.append((i, _text_embedding_cache[ck]))
        else:
            texts_to_encode.append(text)
            text_indices.append(i)
    if texts_to_encode:
        bundle = _get_siglip(model_name)
        if bundle is None:
            return None
        model, processor, device = bundle
        inputs = processor(
            text=texts_to_encode, return_tensors="pt", padding="max_length", truncation=True
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            out = model.get_text_features(**inputs)
            t = _extract_embedding_tensor(out)
            text_embeds = t.detach().cpu().numpy()
        for idx, (text, embedding) in enumerate(zip(texts_to_encode, text_embeds)):
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            embedding = embedding.astype(np.float32)
            _text_embedding_cache[(model_name, text)] = embedding
            embeddings.append((text_indices[idx], embedding))
    embeddings.sort(key=lambda x: x[0])
    return [emb for _, emb in embeddings]


def encode_image_bytes(
    image_data: bytes,
    model_name: str = "google/siglip-base-patch16-224",
) -> np.ndarray:
    """Normalized image embedding vector."""
    bundle = _get_siglip(model_name)
    if bundle is None:
        raise RuntimeError("SigLIP model unavailable")
    model, processor, device = bundle
    image = Image.open(BytesIO(image_data))
    if image.mode != "RGB":
        image = image.convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        features = model.get_image_features(**inputs)
        t = _extract_embedding_tensor(features)
        if t.dim() > 1:
            t = t[0]
        embedding = t.detach().cpu().numpy()
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding.astype(np.float32)


def similarity_scores(
    image_data: bytes,
    regulation_texts: list[tuple[str, str]],
    model_name: str = "google/siglip-base-patch16-224",
) -> list[tuple[str, float]]:
    """
    Cosine similarity mapped to [0,1] per regulation name.
    Returns (regulation_name, score) for each pair (same order as regulation_texts).
    """
    text_embs = encode_regulation_texts(regulation_texts, model_name=model_name)
    if text_embs is None:
        return []
    image_emb = encode_image_bytes(image_data, model_name=model_name)
    names = [n for n, _ in regulation_texts]
    scores: list[tuple[str, float]] = []
    for name, text_emb in zip(names, text_embs):
        dot_result = np.dot(image_emb, text_emb)
        cos_sim = float(np.asarray(dot_result).ravel()[0])
        score = max(0.0, min(1.0, (cos_sim + 1.0) / 2.0))
        scores.append((name, score))
    return scores
