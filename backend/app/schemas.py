from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

# --- Topic Schemas ---
# Pydantic models (Schemas) define the *shape* of data in the API.

# This is the base shape, used for inheritance
class TopicBase(BaseModel):
    name: str

# This is the shape for *creating* a new topic
class TopicCreate(TopicBase):
    pass

# This is the shape for *returning* a topic from the API
class Topic(TopicBase):
    id: int
    active: bool = True
    fetch_frequency_hours: int = 5
    language: str = "en"
    region: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- User Schemas ---

class UserBase(BaseModel):
    email: EmailStr

# This is the shape for *creating* a new user (input)
class UserCreate(UserBase):
    password: str

# This is the shape for *returning* a user from the API (output)
# This is the 'UserOut' that was missing!
class UserOut(UserBase):
    id: int
    topics: List[Topic] = []

    model_config = ConfigDict(from_attributes=True)


# --- Token Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


class Source(BaseModel):
    id: int
    domain: str
    reliability_score: float
    robots_allowed: bool
    crawl_delay_seconds: int

    model_config = ConfigDict(from_attributes=True)


class ArticleTopicScoreSchema(BaseModel):
    score: float
    topic: Topic

    model_config = ConfigDict(from_attributes=True)


class ArticleSchema(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    url: str
    canonical_url: Optional[str] = None
    source: Optional[str] = None
    source_id: Optional[int] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    raw_html: Optional[str] = None
    clean_text: Optional[str] = None
    word_count: Optional[int] = None
    content_hash: Optional[str] = None
    published_at: datetime
    fetched_at: datetime
    extraction_status: str
    topic_scores: List[ArticleTopicScoreSchema] = []

    model_config = ConfigDict(from_attributes=True)

class Article(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    url: str
    source: Optional[str] = None
    published_at: datetime
    image_url: Optional[str] = None
    clean_text: Optional[str] = None
    extraction_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FeedArticle(BaseModel):
    article: Article
    matched_topic: Topic
    matched_score: Optional[float] = None
    ranking_score: Optional[float] = None
    source_weight: Optional[float] = None
    topic_weight: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class FullArticleContentOut(BaseModel):
    article_id: int
    title: str
    source: Optional[str] = None
    published_at: datetime
    url: str
    canonical_url: Optional[str] = None
    extraction_status: str
    word_count: Optional[int] = None
    clean_text: Optional[str] = None
    is_full_content_available: bool

    model_config = ConfigDict(from_attributes=True)

class ArticleFetchRequest(BaseModel):
    topic_ids: List[int]


class SearchArticleSchema(BaseModel):
    title: str
    description: Optional[str]
    url: Optional[str]
    source: Optional[str]
    published_at: datetime
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackRequest(BaseModel):
    feedback_type: Literal["like", "dislike"]


class UserFeedbackOut(BaseModel):
    id: int
    user_id: int
    article_id: int
    feedback_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPreferenceProfileOut(BaseModel):
    user_id: int
    topic_weights_json: Dict[str, float]
    source_weights_json: Dict[str, float]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IngestionRunOut(BaseModel):
    run_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    topics_total: int
    urls_discovered: int
    urls_scraped: int
    success_count: int
    fail_count: int

    model_config = ConfigDict(from_attributes=True)


class IngestionEnqueueResponse(BaseModel):
    message: str
    run_id: str
    task_id: str
    status: str
    topics_total: int


class PersonalizedReportOut(BaseModel):
    id: int
    user_id: int
    report_date: datetime
    report_text: str
    metadata_json: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
