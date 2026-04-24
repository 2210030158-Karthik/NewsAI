from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Sequence
from urllib.parse import urlparse


@dataclass(frozen=True)
class FeedbackTopicScore:
    topic: str
    score: float


@dataclass(frozen=True)
class FeedbackEvent:
    feedback_type: str
    topic_scores: Sequence[FeedbackTopicScore]
    source_key: Optional[str] = None


def clamp_weight(value: float, minimum: float = -5.0, maximum: float = 5.0) -> float:
    return max(minimum, min(maximum, value))


def extract_source_key(
    source_domain: Optional[str],
    source_name: Optional[str],
    article_url: Optional[str],
) -> str:
    if source_domain:
        return source_domain.lower().strip()

    if source_name:
        return source_name.lower().strip()

    parsed = urlparse(article_url or "")
    return (parsed.netloc or "").lower().strip()


def compute_feedback_preference_weights(
    events: Iterable[FeedbackEvent],
    source_signal_weight: float = 0.5,
) -> tuple[dict[str, float], dict[str, float]]:
    topic_weights: dict[str, float] = {}
    source_weights: dict[str, float] = {}

    for event in events:
        signal = 1.0 if event.feedback_type == "like" else -1.0

        for topic_score in event.topic_scores:
            prior = topic_weights.get(topic_score.topic, 0.0)
            topic_weights[topic_score.topic] = clamp_weight(prior + signal * float(topic_score.score))

        if event.source_key:
            source_prior = source_weights.get(event.source_key, 0.0)
            source_weights[event.source_key] = clamp_weight(source_prior + signal * source_signal_weight)

    return topic_weights, source_weights


def compute_feed_ranking_score(
    match_score: float,
    topic_weight: float,
    source_weight: float,
    feedback_type: Optional[str],
    published_at: datetime,
    now: Optional[datetime] = None,
) -> float:
    feedback_boost = 0.35 if feedback_type == "like" else (-0.6 if feedback_type == "dislike" else 0.0)

    if published_at.tzinfo:
        now_ref = now or datetime.now(published_at.tzinfo)
    else:
        now_ref = now or datetime.utcnow()

    age_hours = max((now_ref - published_at).total_seconds() / 3600.0, 0.0)
    recency_boost = 0.25 / (1.0 + age_hours / 24.0)

    return (
        float(match_score)
        + (0.2 * float(topic_weight))
        + (0.15 * float(source_weight))
        + feedback_boost
        + recency_boost
    )
