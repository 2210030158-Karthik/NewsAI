from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from urllib.parse import urlparse
import hashlib
from typing import List
from . import models, schemas, auth, db, classifier, news_fetcher, scraper, content_extractor # Import all services
from .db import get_db # Import get_db

api_router = APIRouter()


def _normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = (parsed.netloc or "").lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _safe_status(value: str, max_length: int = 50) -> str:
    if not value:
        return "unknown"
    return value[:max_length]

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
    # 1. This now correctly accepts the list of IDs from the frontend
    request_body: schemas.ArticleFetchRequest, 
    db_session: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_active_user)
):
    
    topic_ids_to_process = request_body.topic_ids
    if not topic_ids_to_process:
        raise HTTPException(status_code=400, detail="No topic IDs provided.")

    print(f"User {current_user.email} requested fetch for {len(topic_ids_to_process)} topics.")

    #  2. Query the database for *only* the topics the user requested.
    topics_to_fetch = db_session.query(models.Topic).filter(
        models.Topic.id.in_(topic_ids_to_process)
    ).all()

    if not topics_to_fetch:
        raise HTTPException(status_code=404, detail="None of the selected topics were found.")

    all_topics_in_db = db_session.query(models.Topic).all()
    all_topic_names = [topic.name for topic in all_topics_in_db]
    if not all_topic_names:
         raise HTTPException(status_code=500, detail="No topics found in database for classifier.")


    all_new_articles_saved = []

    # 3. Loop through the *small list* of topics (e.g., 3)
    #    instead of all 15 topics.
    for topic in topics_to_fetch:
        print(f"--- Fetching for topic: {topic.name} ---")
        
        # 4. Call your *existing* news_fetcher function for one topic
        #    (We'll fetch 10 articles to get good coverage)
        fetched_articles_data = news_fetcher.fetch_articles_for_topic(
            topic_name=topic.name, 
            max_articles=10 
        )

        # 5. --- This is logic to classify and save ---
        for article_data in fetched_articles_data:
            # Check if this article URL is already in our database
            existing_article = db_session.query(models.Article).filter(
                models.Article.url == article_data["url"]
            ).first()

            if existing_article:
                # Backfill full content for existing rows that were previously metadata-only.
                if existing_article.clean_text:
                    continue
                try:
                    scraped_payload = scraper.fetch_article_html(article_data["url"])
                    extracted = content_extractor.extract_article_content(
                        raw_html=scraped_payload.get("raw_html"),
                        url=scraped_payload.get("final_url") or article_data["url"],
                    )

                    clean_text = extracted.get("clean_text")
                    extraction_status = extracted.get("status") or "extraction_failed"
                    if scraped_payload.get("error") and not scraped_payload.get("raw_html"):
                        extraction_status = "fetch_failed"

                    existing_article.canonical_url = (
                        existing_article.canonical_url
                        or article_data.get("canonical_url")
                        or extracted.get("canonical_url")
                        or scraped_payload.get("final_url")
                    )
                    existing_article.raw_html = scraped_payload.get("raw_html") or existing_article.raw_html
                    existing_article.clean_text = clean_text or existing_article.clean_text
                    existing_article.word_count = extracted.get("word_count") or existing_article.word_count
                    existing_article.author = extracted.get("author") or existing_article.author
                    existing_article.image_url = (
                        existing_article.image_url
                        or article_data.get("image_url")
                        or extracted.get("image_url")
                    )
                    existing_article.extraction_status = _safe_status(extraction_status)
                    existing_article.fetched_at = scraped_payload.get("fetched_at") or datetime.utcnow()
                    if clean_text and not existing_article.content_hash:
                        existing_article.content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

                    db_session.add(existing_article)
                    db_session.commit()
                    print(f"Enriched existing article: {existing_article.title}")
                except Exception as enrich_error:
                    print(f"Error enriching article {article_data['title']}: {enrich_error}")
                    db_session.rollback()
                continue

            # If it's a new article, process it
            try:
                    scraped_payload = scraper.fetch_article_html(article_data["url"])
                    extracted = content_extractor.extract_article_content(
                        raw_html=scraped_payload.get("raw_html"),
                        url=scraped_payload.get("final_url") or article_data["url"],
                    )

                    extraction_status = extracted.get("status") or "extraction_failed"
                    if scraped_payload.get("error") and not scraped_payload.get("raw_html"):
                        extraction_status = "fetch_failed"
                    extraction_status = _safe_status(extraction_status)

                    clean_text = extracted.get("clean_text")
                    content_to_classify = (
                        clean_text[:3500]
                        if clean_text
                        else f"{article_data['title']}. {article_data['description']}"
                    )
                    
                    classification_list = classifier.classify_article_content(
                        content=content_to_classify,
                        topics=all_topic_names 
                    )
                    
                    classification_results = {
                        item['topic']: item['score'] for item in classification_list
                    }

                    source_domain = _normalize_domain(article_data["url"])
                    source_row = None
                    if source_domain:
                        source_row = db_session.query(models.Source).filter(
                            models.Source.domain == source_domain
                        ).one_or_none()
                        if not source_row:
                            source_row = models.Source(domain=source_domain)
                            db_session.add(source_row)
                            db_session.flush()

                    published_at = (
                        extracted.get("published_at")
                        or article_data.get("published_at")
                        or datetime.utcnow()
                    )

                    canonical_url = (
                        article_data.get("canonical_url")
                        or extracted.get("canonical_url")
                        or scraped_payload.get("final_url")
                        or article_data["url"]
                    )

                    content_hash = (
                        hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
                        if clean_text
                        else None
                    )
                    
                    # 7. Create the new Article database object
                    new_article = models.Article(
                        title=article_data["title"],
                        description=article_data["description"],
                        url=article_data["url"],
                        canonical_url=canonical_url,
                        source=article_data["source"],
                        source_id=source_row.id if source_row else None,
                        author=extracted.get("author"),
                        image_url=article_data.get("image_url") or extracted.get("image_url"),
                        raw_html=scraped_payload.get("raw_html"),
                        clean_text=clean_text,
                        word_count=extracted.get("word_count"),
                        content_hash=content_hash,
                        published_at=published_at,
                        fetched_at=scraped_payload.get("fetched_at") or datetime.utcnow(),
                        extraction_status=extraction_status,
                    )
                    db_session.add(new_article)
                    db_session.flush()

                    # 8. Link the article to its topics in the join table
                    for result_topic_name, percentage in classification_results.items():
                        # Find the topic object for this name
                        topic_in_db = db_session.query(models.Topic).filter(models.Topic.name == result_topic_name).first()
                        
                        # Only link if the topic exists and percentage is significant (e.g., > 10%)
                        if topic_in_db and percentage > 0.1:
                            link = models.ArticleTopicScore(
                                article_id=new_article.id,
                                topic_id=topic_in_db.id,
                                score=percentage
                            )
                            db_session.add(link)
                    
                    db_session.commit() # Commit article and topic links in one transaction
                    db_session.refresh(new_article)
                    all_new_articles_saved.append(new_article)
                    print(f"Saved new article: {new_article.title}")

            except Exception as e:
                print(f"Error classifying/saving article {article_data['title']}: {e}")
                db_session.rollback() # Roll back any partial saves for this article
    
    print(f"--- Fetch complete. Saved {len(all_new_articles_saved)} new articles. ---")
    return {
        "message": f"Successfully processed {len(topics_to_fetch)} topics and saved {len(all_new_articles_saved)} new articles."
    }
    


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
    # Eagerly load topics for the current user
    user_with_topics = db_session.query(models.User).options(
        joinedload(models.User.topics)
    ).filter(models.User.id == current_user.id).one_or_none()

    if not user_with_topics:
        return [] # Should not happen if user is authenticated

    user_topic_ids = [topic.id for topic in user_with_topics.topics]
    
    if not user_topic_ids:
        return [] # Return empty list if user has no topics

    # This query finds all ArticleTopicScore links
    # that match the user's topics.
    # It also pre-loads the 'article' and 'topic' data to avoid extra queries.
    # 'joinedload' is already imported at the top of the file.

    feed_links = db_session.query(models.ArticleTopicScore).join(
        models.Article, models.Article.id == models.ArticleTopicScore.article_id
    ).options(
        joinedload(models.ArticleTopicScore.article),
        joinedload(models.ArticleTopicScore.topic)
    ).filter(
        models.ArticleTopicScore.topic_id.in_(user_topic_ids)
    ).order_by(
        models.Article.published_at.desc()
    ).limit(100).all() # Limit to 50 most recent articles

    # The query above can return duplicates if an article matches
    # multiple topics (e.g., "Gaming" and "Technology").
    # We'll use a set to keep track of articles we've already added.
    feed_results = []
    seen_article_ids = set()

    for link in feed_links:
        if link.article_id not in seen_article_ids:
            # This is the new "package" we're sending to the frontend
            # This assumes your schemas.py has a 'FeedArticle' schema
            feed_item = schemas.FeedArticle(
                article=link.article,
                matched_topic=link.topic,
                matched_score=link.score
            )
            feed_results.append(feed_item)
            seen_article_ids.add(link.article_id)
            
    return feed_results


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