from app import classifier


def test_resolve_model_name_uses_local_model_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(classifier.settings, "ENABLE_LOCAL_RANKER", True)
    monkeypatch.setattr(classifier.settings, "LOCAL_CLASSIFIER_MODEL_NAME", "tiny-local-model")
    assert classifier._resolve_model_name() == "tiny-local-model"


def test_resolve_model_name_uses_zero_shot_model_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(classifier.settings, "ENABLE_LOCAL_RANKER", False)
    monkeypatch.setattr(classifier.settings, "ZERO_SHOT_MODEL_NAME", "large-model")
    assert classifier._resolve_model_name() == "large-model"


def test_classify_article_falls_back_when_model_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_classifier", lambda: None)

    results = classifier.classify_article_content(
        content="Technology and AI hardware are changing the market rapidly.",
        topics=["Technology", "Sports"],
    )

    assert len(results) == 2
    assert results[0]["topic"] == "Technology"
    assert float(results[0]["score"]) >= float(results[1]["score"])
