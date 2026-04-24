import re
from typing import Dict, List, Optional, Union

try:
    from transformers import pipeline
except Exception:
    pipeline = None

from .config import settings


_classifier = None
_classifier_initialized = False


def _tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", value.lower()))


def _fallback_classify(content: str, topics: List[str]) -> List[Dict[str, Union[str, float]]]:
    """
    Lightweight lexical fallback to keep ingestion running when large model
    cannot be loaded on constrained environments.
    """
    content_tokens = _tokenize(content)
    if not content_tokens:
        return []

    scored_topics: List[Dict[str, Union[str, float]]] = []
    for topic in topics:
        topic_tokens = _tokenize(topic)
        overlap = len(content_tokens.intersection(topic_tokens))
        confidence = 0.05 + min(0.9, (overlap / max(1, len(topic_tokens))) * 0.9)
        scored_topics.append({
            "topic": topic,
            "score": float(confidence),
        })

    return sorted(scored_topics, key=lambda item: float(item["score"]), reverse=True)


def _resolve_model_name() -> str:
    if settings.ENABLE_LOCAL_RANKER:
        return settings.LOCAL_CLASSIFIER_MODEL_NAME
    return settings.ZERO_SHOT_MODEL_NAME


def _get_classifier() -> Optional[object]:
    global _classifier
    global _classifier_initialized

    if _classifier_initialized:
        return _classifier

    _classifier_initialized = True
    if pipeline is None:
        print("Warning: transformers pipeline unavailable; using fallback classifier.")
        return None

    model_name = _resolve_model_name()
    mode_label = "small-local" if settings.ENABLE_LOCAL_RANKER else "large-zero-shot"
    print(f"Loading classifier model '{model_name}' ({mode_label})...")
    try:
        try:
            import torch

            device = 0 if torch.cuda.is_available() else -1
            print("Device set to use CUDA (GPU)" if device == 0 else "Device set to use cpu")
        except Exception:
            device = -1
            print("Torch unavailable. Device set to use cpu")

        _classifier = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=device,
        )
        print("Model loaded successfully.")
    except Exception as exc:
        _classifier = None
        print(f"Warning: failed to load '{model_name}'. Falling back to lexical classifier. Error: {exc}")

    return _classifier


def classify_article_content(content: str, topics: List[str]) -> List[Dict[str, Union[str, float]]]:
    """
    Takes article content and candidate topics and returns scored topics.
    """
    if not content or not topics:
        return []

    content = " ".join(content.split())
    if not content:
        return []

    classifier = _get_classifier()
    if classifier is None:
        return _fallback_classify(content, topics)

    try:
        result = classifier(
            content,
            topics,
            multi_label=True,
            truncation=True,
            max_length=settings.CLASSIFIER_MAX_LABEL_TEXT_LENGTH,
        )
        if "labels" in result and "scores" in result:
            return [
                {"topic": label, "score": float(score)}
                for label, score in zip(result["labels"], result["scores"])
            ]
        return _fallback_classify(content, topics)
    except Exception as exc:
        print(f"Warning: model classification failed, using fallback classifier. Error: {exc}")
        return _fallback_classify(content, topics)

# --- Example of how to use this (for testing) ---
if __name__ == "__main__":
    test_topics = ["Gaming", "Politics", "Technology", "Crimes", "International Law"]
    test_content = (
        "A new bill was passed in parliament today that restricts "
        "international trade. Lawmakers are concerned about the "
        "impact on the tech sector. Some have called it a 'crime' "
        "against free trade."
    )

    scores = classify_article_content(test_content, test_topics)
    print("\n--- Classification Test ---")
    print(f"Content: {test_content}\n")
    print("Scores:")
    if scores:
        for item in scores:
            print(f"- {item['topic']}: {item['score']:.2f}")
    else:
        print("Classification failed or returned no scores.")

