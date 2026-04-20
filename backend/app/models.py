from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Association table for the many-to-many relationship
# between users and their preferred topics.
user_topic_association = Table(
    "user_topic_association",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("topic_id", Integer, ForeignKey("topics.id"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    topics: Mapped[List["Topic"]] = relationship(
        secondary=user_topic_association, back_populates="users"
    )
    feedback_events: Mapped[List["UserFeedback"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preference_profile: Mapped[Optional["UserPreferenceProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    reports: Mapped[List["PersonalizedReport"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fetch_frequency_hours: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(20))

    users: Mapped[List["User"]] = relationship(
        secondary=user_topic_association, back_populates="topics"
    )
    article_scores: Mapped[List["ArticleTopicScore"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    robots_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    crawl_delay_seconds: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    articles: Mapped[List["Article"]] = relationship(back_populates="source_ref")

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(String(1000), index=True)
    source: Mapped[Optional[str]] = mapped_column(String(255))
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sources.id"), index=True)
    author: Mapped[Optional[str]] = mapped_column(String(255))
    image_url: Mapped[Optional[str]] = mapped_column(String(1000))
    raw_html: Mapped[Optional[str]] = mapped_column(Text)
    clean_text: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    content_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(50), default="discovered", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    source_ref: Mapped[Optional["Source"]] = relationship(back_populates="articles")
    topic_scores: Mapped[List["ArticleTopicScore"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    feedback_events: Mapped[List["UserFeedback"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class ArticleTopicScore(Base):
    __tablename__ = "article_topic_scores"
    __table_args__ = (UniqueConstraint("article_id", "topic_id", name="uq_article_topic_score"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)

    article: Mapped["Article"] = relationship(back_populates="topic_scores")
    topic: Mapped["Topic"] = relationship(back_populates="article_scores")


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_user_article_feedback"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    feedback_type: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="feedback_events")
    article: Mapped["Article"] = relationship(back_populates="feedback_events")


class UserPreferenceProfile(Base):
    __tablename__ = "user_preference_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    topic_weights_json: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    source_weights_json: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="preference_profile")


class PersonalizedReport(Base):
    __tablename__ = "personalized_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    report_date: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="reports")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    topics_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urls_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urls_scraped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    errors: Mapped[List["IngestionError"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class IngestionError(Base):
    __tablename__ = "ingestion_errors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.run_id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[Optional[int]] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), index=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000))
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    run: Mapped["IngestionRun"] = relationship(back_populates="errors")
    topic: Mapped[Optional["Topic"]] = relationship()

