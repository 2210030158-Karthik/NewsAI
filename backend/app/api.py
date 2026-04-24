from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import Dict, List
from . import models, schemas, auth, db, news_fetcher, ingestion_service # Import all services
from .config import settings
from .db import get_db # Import get_db
from .ranking import (
    FeedbackEvent,
    FeedbackTopicScore,
    compute_feedback_preference_weights,
    compute_feed_ranking_score,
    extract_source_key,
)

api_router = APIRouter()


def _source_key_for_article(article: models.Article) -> str:
    source_domain = article.source_ref.domain if article.source_ref else None
    return extract_source_key(
        source_domain=source_domain,
        source_name=article.source,
        article_url=article.url,
    )


def _rebuild_user_preference_profile(db_session: Session, user_id: int) -> models.UserPreferenceProfile:
    feedback_rows = (
        db_session.query(models.UserFeedback)
        .options(
            joinedload(models.UserFeedback.article)
            .joinedload(models.Article.topic_scores)
            .joinedload(models.ArticleTopicScore.topic),
            joinedload(models.UserFeedback.article).joinedload(models.Article.source_ref),
        )
        .filter(models.UserFeedback.user_id == user_id)
        .all()
    )

    feedback_events: List[FeedbackEvent] = []
    for row in feedback_rows:
        article = row.article
        topic_scores = [
            FeedbackTopicScore(
                topic=article_topic_score.topic.name,
                score=float(article_topic_score.score),
            )
            for article_topic_score in article.topic_scores
        ]
        feedback_events.append(
            FeedbackEvent(
                feedback_type=row.feedback_type,
                topic_scores=topic_scores,
                source_key=_source_key_for_article(article),
            )
        )

    topic_weights, source_weights = compute_feedback_preference_weights(feedback_events)

    profile = (
        db_session.query(models.UserPreferenceProfile)
        .filter(models.UserPreferenceProfile.user_id == user_id)
        .one_or_none()
    )
    if profile is None:
        profile = models.UserPreferenceProfile(
            user_id=user_id,
            topic_weights_json=topic_weights,
            source_weights_json=source_weights,
        )
        db_session.add(profile)
    else:
        profile.topic_weights_json = topic_weights
        profile.source_weights_json = source_weights
        profile.updated_at = datetime.utcnow()

    db_session.commit()
    db_session.refresh(profile)
    return profile


def _build_personalized_report_payload(
    db_session: Session,
    current_user: models.User,
) -> tuple[str, Dict[str, str]]:
    user_with_topics = (
        db_session.query(models.User)
        .options(joinedload(models.User.topics))
        .filter(models.User.id == current_user.id)
        .one()
    )
    user_topic_ids = [topic.id for topic in user_with_topics.topics]

    profile = (
        db_session.query(models.UserPreferenceProfile)
        .filter(models.UserPreferenceProfile.user_id == current_user.id)
        .one_or_none()
    )
    topic_weights = profile.topic_weights_json if profile else {}

    top_pref_topics = sorted(
        topic_weights.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:3]

    feedback_rows = (
        db_session.query(models.UserFeedback)
        .filter(models.UserFeedback.user_id == current_user.id)
        .order_by(models.UserFeedback.created_at.desc())
        .limit(100)
        .all()
    )
    likes_count = len([row for row in feedback_rows if row.feedback_type == "like"])
    dislikes_count = len(feedback_rows) - likes_count

    recent_articles = []
    if user_topic_ids:
        recent_articles = (
            db_session.query(models.Article)
            .join(models.ArticleTopicScore, models.Article.id == models.ArticleTopicScore.article_id)
            .filter(models.ArticleTopicScore.topic_id.in_(user_topic_ids))
            .order_by(models.Article.published_at.desc())
            .limit(5)
            .all()
        )

    topic_summary = ", ".join(topic.name for topic in user_with_topics.topics[:5]) or "No topics selected"
    top_topics_summary = ", ".join(
        f"{name} ({score:.2f})" for name, score in top_pref_topics
    ) or "No learned preferences yet"
    headline_summary = "\n".join(
        f"- {article.title}"
        for article in recent_articles
    ) or "- No recent personalized articles yet"

    report_text = (
        "Personalized News Report\n"
        f"Generated at: {datetime.utcnow().isoformat()}Z\n"
        f"Tracked topics: {topic_summary}\n"
        f"Top learned preferences: {top_topics_summary}\n"
        f"Recent feedback: {likes_count} likes, {dislikes_count} dislikes\n"
        "Top recent articles:\n"
        f"{headline_summary}\n"
        "Action: Continue reacting with like/dislike to sharpen ranking quality."
    )

    metadata_json = {
        "likes_count": str(likes_count),
        "dislikes_count": str(dislikes_count),
        "topics_selected": str(len(user_topic_ids)),
        "recent_articles": str(len(recent_articles)),
    }
    return report_text, metadata_json

# --- Authentication Endpoints ---

@api_router.post("/signup", response_model=schemas.UserOut, tags=["Authentication"])
def create_user(user_in: schemas.UserCreate, db_session: Session = Depends(get_db)):
    db_user = auth.get_user_by_email(db_session, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    hashed_password = auth.get_password_hash(user_in.password)
    new_user = models.User(
        email=user_in.email,
        hashed_password=hashed_password
    )
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    return new_user

@api_router.post("/login", response_model=schemas.Token, tags=["Authentication"])
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db_session: Session = Depends(get_db)
):
    user = auth.authenticate_user(db_session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(
        data={"sub": user.email}
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- User Endpoints ---

@api_router.get("/users/me", response_model=schemas.UserOut, tags=["Users"])
def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    # Make sure topics are loaded
    # Use options() with joinedload() to ensure topics are eagerly loaded
    db_session = Session.object_session(current_user)
    user_with_topics = db_session.query(models.User).options(joinedload(models.User.topics)).filter(models.User.id == current_user.id).one()
    return user_with_topics


@api_router.post("/users/me/topics", response_model=schemas.UserOut, tags=["Users"])
def update_user_topics(
    topic_ids: List[int],
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    topics = db_session.query(models.Topic).filter(models.Topic.id.in_(topic_ids)).all()
    if len(topics) != len(topic_ids):
        # Find which IDs were missing
        found_ids = {topic.id for topic in topics}
        missing_ids = set(topic_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic IDs not found: {missing_ids}"
        )

    # Use options() with joinedload() for refreshing
    current_user.topics = topics
    db_session.add(current_user)
    db_session.commit()
    # Refreshing requires the session and specifying what to load
    db_session.refresh(current_user)
    # Eagerly load topics after refresh for the response
    user_with_topics = db_session.query(models.User).options(joinedload(models.User.topics)).filter(models.User.id == current_user.id).one()
    return user_with_topics


# --- Topic Endpoints ---

@api_router.post("/topics", response_model=schemas.Topic, tags=["Topics"])
def create_topic(topic_in: schemas.TopicCreate, db_session: Session = Depends(get_db)):
    db_topic = db_session.query(models.Topic).filter(models.Topic.name == topic_in.name).first()
    if db_topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Topic already exists"
        )
    new_topic = models.Topic(name=topic_in.name)
    db_session.add(new_topic)
    db_session.commit()
    db_session.refresh(new_topic)
    return new_topic

@api_router.get("/topics", response_model=List[schemas.Topic], tags=["Topics"])
def get_all_topics(db_session: Session = Depends(get_db)):
    return db_session.query(models.Topic).all()

# --- Article & AI Endpoints ---

@api_router.post("/articles/fetch-and-process", tags=["Articles"])
def fetch_and_process_articles(
    request_body: schemas.ArticleFetchRequest,
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    topic_ids_to_process = list(dict.fromkeys(request_body.topic_ids))
    if not topic_ids_to_process:
        raise HTTPException(status_code=400, detail="No topic IDs provided.")

    print(f"User {current_user.email} requested fetch for {len(topic_ids_to_process)} topics.")

    topics_to_fetch = (
        db_session.query(models.Topic)
        .filter(models.Topic.id.in_(topic_ids_to_process))
        .all()
    )
    if len(topics_to_fetch) != len(topic_ids_to_process):
        found_ids = {topic.id for topic in topics_to_fetch}
        missing_ids = sorted(set(topic_ids_to_process) - found_ids)
        raise HTTPException(
            status_code=404,
            detail=f"Topic IDs not found: {missing_ids}",
        )

    if settings.ENABLE_ASYNC_INGESTION:
        from . import tasks

        run = ingestion_service.create_ingestion_run(
            db_session=db_session,
            topic_ids=topic_ids_to_process,
            status="queued",
        )
        try:
            async_result = tasks.process_ingestion_run.delay(
                run.run_id,
                topic_ids_to_process,
                settings.INGESTION_MAX_ARTICLES_PER_TOPIC,
            )
            return schemas.IngestionEnqueueResponse(
                message="Ingestion job queued.",
                run_id=run.run_id,
                task_id=async_result.id,
                status="queued",
                topics_total=len(topic_ids_to_process),
            )
        except Exception as exc:
            # If Redis/Celery is unavailable, keep the endpoint usable by falling back
            # to in-process execution and preserving ingestion run accounting.
            summary = ingestion_service.process_ingestion_topic_batch(
                db_session=db_session,
                topic_ids=topic_ids_to_process,
                run_id=run.run_id,
                max_articles_per_topic=settings.INGESTION_MAX_ARTICLES_PER_TOPIC,
            )
            return {
                "message": "Async queue unavailable. Ingestion completed synchronously.",
                "run_id": run.run_id,
                "queue_error": str(exc),
                "summary": summary,
            }

    summary = ingestion_service.process_ingestion_topic_batch(
        db_session=db_session,
        topic_ids=topic_ids_to_process,
        run_id=None,
        max_articles_per_topic=settings.INGESTION_MAX_ARTICLES_PER_TOPIC,
    )
    return {
        "message": "Ingestion completed synchronously.",
        "summary": summary,
    }


@api_router.get("/ingestion/runs", response_model=List[schemas.IngestionRunOut], tags=["Ingestion"])
def list_ingestion_runs(
    limit: int = Query(20, ge=1, le=100),
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    # Keep authenticated access enforced for operational endpoints.
    _ = current_user
    return (
        db_session.query(models.IngestionRun)
        .order_by(models.IngestionRun.started_at.desc())
        .limit(limit)
        .all()
    )


@api_router.get("/ingestion/runs/{run_id}", response_model=schemas.IngestionRunOut, tags=["Ingestion"])
def get_ingestion_run(
    run_id: str,
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    _ = current_user
    run = (
        db_session.query(models.IngestionRun)
        .filter(models.IngestionRun.run_id == run_id)
        .one_or_none()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found.")
    return run


@api_router.get("/articles/{article_id}/full-content", response_model=schemas.FullArticleContentOut, tags=["Articles"])
def get_full_article_content(
    article_id: int,
    refresh_if_missing: bool = Query(default=True),
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    _ = current_user
    article = (
        db_session.query(models.Article)
        .filter(models.Article.id == article_id)
        .one_or_none()
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")

    clean_text = (article.clean_text or "").strip()
    has_full_content = len(clean_text) >= settings.FULL_ARTICLE_MIN_CHARS

    if not has_full_content and refresh_if_missing:
        article = ingestion_service.hydrate_article_content(db_session, article)
        clean_text = (article.clean_text or "").strip()
        has_full_content = len(clean_text) >= settings.FULL_ARTICLE_MIN_CHARS

    return schemas.FullArticleContentOut(
        article_id=article.id,
        title=article.title,
        source=article.source,
        published_at=article.published_at,
        url=article.url,
        canonical_url=article.canonical_url,
        extraction_status=article.extraction_status,
        word_count=article.word_count,
        clean_text=article.clean_text,
        is_full_content_available=has_full_content,
    )


@api_router.post("/admin/ingestion/run-active", tags=["Admin"])
def run_active_topic_ingestion(
    batch_size: int = Query(default=settings.ASYNC_INGESTION_TOPIC_BATCH_SIZE, ge=1, le=500),
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    _ = current_user
    active_topics = (
        db_session.query(models.Topic)
        .filter(models.Topic.active.is_(True))
        .order_by(models.Topic.id.asc())
        .limit(batch_size)
        .all()
    )

    topic_ids = [topic.id for topic in active_topics]
    if not topic_ids:
        raise HTTPException(status_code=404, detail="No active topics found.")

    run = ingestion_service.create_ingestion_run(
        db_session=db_session,
        topic_ids=topic_ids,
        status="queued",
    )

    if settings.ENABLE_ASYNC_INGESTION:
        from . import tasks

        try:
            async_result = tasks.process_ingestion_run.delay(
                run.run_id,
                topic_ids,
                settings.INGESTION_MAX_ARTICLES_PER_TOPIC,
            )
            return {
                "message": "Active-topic ingestion queued.",
                "status": "queued",
                "run_id": run.run_id,
                "task_id": async_result.id,
                "topics_total": len(topic_ids),
            }
        except Exception as exc:
            summary = ingestion_service.process_ingestion_topic_batch(
                db_session=db_session,
                topic_ids=topic_ids,
                run_id=run.run_id,
                max_articles_per_topic=settings.INGESTION_MAX_ARTICLES_PER_TOPIC,
            )
            return {
                "message": "Async queue unavailable. Active-topic ingestion completed synchronously.",
                "status": "completed",
                "run_id": run.run_id,
                "queue_error": str(exc),
                "topics_total": len(topic_ids),
                "summary": summary,
            }

    summary = ingestion_service.process_ingestion_topic_batch(
        db_session=db_session,
        topic_ids=topic_ids,
        run_id=run.run_id,
        max_articles_per_topic=settings.INGESTION_MAX_ARTICLES_PER_TOPIC,
    )
    return {
        "message": "Active-topic ingestion completed synchronously.",
        "status": "completed",
        "run_id": run.run_id,
        "topics_total": len(topic_ids),
        "summary": summary,
    }


@api_router.post("/articles/{article_id}/feedback", response_model=schemas.UserFeedbackOut, tags=["Feedback"])
def submit_article_feedback(
    article_id: int,
    feedback_in: schemas.FeedbackRequest,
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    article = (
        db_session.query(models.Article)
        .filter(models.Article.id == article_id)
        .one_or_none()
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")

    feedback = (
        db_session.query(models.UserFeedback)
        .filter(
            models.UserFeedback.user_id == current_user.id,
            models.UserFeedback.article_id == article_id,
        )
        .one_or_none()
    )

    if feedback is None:
        feedback = models.UserFeedback(
            user_id=current_user.id,
            article_id=article_id,
            feedback_type=feedback_in.feedback_type,
        )
        db_session.add(feedback)
    else:
        feedback.feedback_type = feedback_in.feedback_type

    db_session.commit()
    db_session.refresh(feedback)

    _rebuild_user_preference_profile(db_session, current_user.id)
    return feedback


@api_router.get("/users/me/preferences", response_model=schemas.UserPreferenceProfileOut, tags=["Users"])
def get_user_preference_profile(
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    profile = (
        db_session.query(models.UserPreferenceProfile)
        .filter(models.UserPreferenceProfile.user_id == current_user.id)
        .one_or_none()
    )

    if profile is None:
        profile = models.UserPreferenceProfile(
            user_id=current_user.id,
            topic_weights_json={},
            source_weights_json={},
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)

    return profile


@api_router.post("/reports/generate", response_model=schemas.PersonalizedReportOut, tags=["Reports"])
def generate_personalized_report(
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    report_text, metadata_json = _build_personalized_report_payload(db_session, current_user)
    report = models.PersonalizedReport(
        user_id=current_user.id,
        report_date=datetime.utcnow(),
        report_text=report_text,
        metadata_json=metadata_json,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


@api_router.get("/reports/latest", response_model=schemas.PersonalizedReportOut, tags=["Reports"])
def get_latest_personalized_report(
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    report = (
        db_session.query(models.PersonalizedReport)
        .filter(models.PersonalizedReport.user_id == current_user.id)
        .order_by(models.PersonalizedReport.report_date.desc())
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No report found. Generate one first.")
    return report


@api_router.get("/feed", response_model=List[schemas.FeedArticle], tags=["Feed"])
def get_personalized_feed(
    db_session: Session = Depends(get_db), # Using db_session
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Gets the personalized article feed for the current user.
    
    This is the new, fixed version:
    1. Finds the user's selected topics.
    2. Finds all articles that are linked to *any* of those topics.
    3. Bundles each article with the *specific topic* that matched it.
    4. Returns this new bundled list to the frontend.
    """
    user_with_topics = db_session.query(models.User).options(
        joinedload(models.User.topics)
    ).filter(models.User.id == current_user.id).one_or_none()

    if not user_with_topics:
        return []

    user_topic_ids = [topic.id for topic in user_with_topics.topics]

    if not user_topic_ids:
        return []

    profile = (
        db_session.query(models.UserPreferenceProfile)
        .filter(models.UserPreferenceProfile.user_id == current_user.id)
        .one_or_none()
    )
    topic_weights = profile.topic_weights_json if profile else {}
    source_weights = profile.source_weights_json if profile else {}

    feed_links = db_session.query(models.ArticleTopicScore).join(
        models.Article, models.Article.id == models.ArticleTopicScore.article_id
    ).options(
        joinedload(models.ArticleTopicScore.article).joinedload(models.Article.source_ref),
        joinedload(models.ArticleTopicScore.topic)
    ).filter(
        models.ArticleTopicScore.topic_id.in_(user_topic_ids)
    ).order_by(
        models.Article.fetched_at.desc(),
        models.Article.published_at.desc()
    ).limit(400).all()

    if not feed_links:
        return []

    candidate_article_ids = list({link.article_id for link in feed_links})
    feedback_rows = (
        db_session.query(models.UserFeedback)
        .filter(
            models.UserFeedback.user_id == current_user.id,
            models.UserFeedback.article_id.in_(candidate_article_ids),
        )
        .all()
    )
    feedback_map = {row.article_id: row.feedback_type for row in feedback_rows}

    ranked_by_article: Dict[int, schemas.FeedArticle] = {}
    ranking_scores: Dict[int, float] = {}
    freshness_scores: Dict[int, datetime] = {}

    for link in feed_links:
        article = link.article
        source_key = _source_key_for_article(article)
        topic_weight = float(topic_weights.get(link.topic.name, 0.0))
        source_weight = float(source_weights.get(source_key, 0.0)) if source_key else 0.0

        feedback_type = feedback_map.get(link.article_id)
        ranking_score = compute_feed_ranking_score(
            match_score=link.score,
            topic_weight=topic_weight,
            source_weight=source_weight,
            feedback_type=feedback_type,
            published_at=article.published_at,
        )

        article_freshness = article.fetched_at or article.published_at
        current_freshness = freshness_scores.get(link.article_id)
        if current_freshness is None or article_freshness > current_freshness:
            freshness_scores[link.article_id] = article_freshness

        if link.article_id not in ranking_scores or ranking_score > ranking_scores[link.article_id]:
            ranking_scores[link.article_id] = ranking_score
            ranked_by_article[link.article_id] = schemas.FeedArticle(
                article=article,
                matched_topic=link.topic,
                matched_score=link.score,
                ranking_score=ranking_score,
                source_weight=source_weight,
                topic_weight=topic_weight,
            )

    return sorted(
        ranked_by_article.values(),
        key=lambda item: (
            freshness_scores.get(item.article.id) or item.article.published_at,
            item.ranking_score if item.ranking_score is not None else -999,
            item.article.published_at,
        ),
        reverse=True,
    )[:100]


@api_router.get("/search", response_model=List[schemas.SearchArticleSchema], tags=["Search"])
def search_articles(
    q: str = Query(..., min_length=3, description="The search term to look for."),
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Performs a live search for articles using the news_fetcher.
    This does NOT use our AI classifier or save to the database.
    It returns live results directly from SerpApi.
    """
    print(f"User {current_user.email} searched for: {q}")
    
    # We can re-use our news_fetcher function for this!
    fetched_articles = news_fetcher.fetch_articles_for_topic(
        topic_name=q, 
        max_articles=25
    )
    
    # --- *** NEW VALIDATION FIX *** ---
    # Filter out any articles that the fetcher returned without a URL
    # before sending them to the user.
    valid_articles = [article for article in fetched_articles if article.get("url")]
    
    return valid_articles

#