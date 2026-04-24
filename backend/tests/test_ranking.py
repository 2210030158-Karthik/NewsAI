from datetime import datetime, timedelta

from app.ranking import (
    FeedbackEvent,
    FeedbackTopicScore,
    clamp_weight,
    compute_feed_ranking_score,
    compute_feedback_preference_weights,
)


def test_clamp_weight_bounds_values() -> None:
    assert clamp_weight(9.2) == 5.0
    assert clamp_weight(-8.1) == -5.0
    assert clamp_weight(1.25) == 1.25


def test_feedback_preference_weights_accumulate_and_cancel() -> None:
    events = [
        FeedbackEvent(
            feedback_type="like",
            topic_scores=[
                FeedbackTopicScore(topic="Technology", score=0.9),
                FeedbackTopicScore(topic="AI", score=0.6),
            ],
            source_key="example.com",
        ),
        FeedbackEvent(
            feedback_type="dislike",
            topic_scores=[FeedbackTopicScore(topic="Technology", score=0.4)],
            source_key="example.com",
        ),
    ]

    topic_weights, source_weights = compute_feedback_preference_weights(events)

    assert topic_weights["Technology"] == 0.5
    assert topic_weights["AI"] == 0.6
    assert source_weights["example.com"] == 0.0


def test_feed_ranking_prefers_like_and_recent_articles() -> None:
    now = datetime.utcnow()

    like_recent = compute_feed_ranking_score(
        match_score=0.65,
        topic_weight=0.8,
        source_weight=0.2,
        feedback_type="like",
        published_at=now - timedelta(hours=2),
        now=now,
    )
    neutral_recent = compute_feed_ranking_score(
        match_score=0.65,
        topic_weight=0.8,
        source_weight=0.2,
        feedback_type=None,
        published_at=now - timedelta(hours=2),
        now=now,
    )
    dislike_recent = compute_feed_ranking_score(
        match_score=0.65,
        topic_weight=0.8,
        source_weight=0.2,
        feedback_type="dislike",
        published_at=now - timedelta(hours=2),
        now=now,
    )
    neutral_old = compute_feed_ranking_score(
        match_score=0.65,
        topic_weight=0.8,
        source_weight=0.2,
        feedback_type=None,
        published_at=now - timedelta(days=4),
        now=now,
    )

    assert like_recent > neutral_recent > dislike_recent
    assert neutral_recent > neutral_old
