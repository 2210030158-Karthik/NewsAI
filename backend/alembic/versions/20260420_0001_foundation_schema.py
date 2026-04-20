"""Foundation schema for ingestion, scoring, feedback, and reports.

Revision ID: 20260420_0001
Revises:
Create Date: 2026-04-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260420_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("fetch_frequency_hours", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("region", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_topics_id"), "topics", ["id"], unique=False)
    op.create_index(op.f("ix_topics_name"), "topics", ["name"], unique=True)

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("reliability_score", sa.Float(), nullable=False),
        sa.Column("robots_allowed", sa.Boolean(), nullable=False),
        sa.Column("crawl_delay_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sources_domain"), "sources", ["domain"], unique=True)
    op.create_index(op.f("ix_sources_id"), "sources", ["id"], unique=False)

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("topics_total", sa.Integer(), nullable=False),
        sa.Column("urls_discovered", sa.Integer(), nullable=False),
        sa.Column("urls_scraped", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("fail_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_runs_id"), "ingestion_runs", ["id"], unique=False)
    op.create_index(op.f("ix_ingestion_runs_run_id"), "ingestion_runs", ["run_id"], unique=True)
    op.create_index(op.f("ix_ingestion_runs_status"), "ingestion_runs", ["status"], unique=False)

    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("canonical_url", sa.String(length=1000), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("extraction_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index(op.f("ix_articles_canonical_url"), "articles", ["canonical_url"], unique=False)
    op.create_index(op.f("ix_articles_content_hash"), "articles", ["content_hash"], unique=False)
    op.create_index(op.f("ix_articles_id"), "articles", ["id"], unique=False)
    op.create_index(op.f("ix_articles_published_at"), "articles", ["published_at"], unique=False)
    op.create_index(op.f("ix_articles_source_id"), "articles", ["source_id"], unique=False)

    op.create_table(
        "user_topic_association",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("user_id", "topic_id"),
    )

    op.create_table(
        "article_topic_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "topic_id", name="uq_article_topic_score"),
    )
    op.create_index(op.f("ix_article_topic_scores_article_id"), "article_topic_scores", ["article_id"], unique=False)
    op.create_index(op.f("ix_article_topic_scores_id"), "article_topic_scores", ["id"], unique=False)
    op.create_index(op.f("ix_article_topic_scores_topic_id"), "article_topic_scores", ["topic_id"], unique=False)

    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("feedback_type", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "article_id", name="uq_user_article_feedback"),
    )
    op.create_index(op.f("ix_user_feedback_article_id"), "user_feedback", ["article_id"], unique=False)
    op.create_index(op.f("ix_user_feedback_id"), "user_feedback", ["id"], unique=False)
    op.create_index(op.f("ix_user_feedback_user_id"), "user_feedback", ["user_id"], unique=False)

    op.create_table(
        "user_preference_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("topic_weights_json", sa.JSON(), nullable=False),
        sa.Column("source_weights_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_preference_profiles_id"), "user_preference_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_user_preference_profiles_user_id"), "user_preference_profiles", ["user_id"], unique=True)

    op.create_table(
        "personalized_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.DateTime(), nullable=False),
        sa.Column("report_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_personalized_reports_id"), "personalized_reports", ["id"], unique=False)
    op.create_index(op.f("ix_personalized_reports_report_date"), "personalized_reports", ["report_date"], unique=False)
    op.create_index(op.f("ix_personalized_reports_user_id"), "personalized_reports", ["user_id"], unique=False)

    op.create_table(
        "ingestion_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_errors_id"), "ingestion_errors", ["id"], unique=False)
    op.create_index(op.f("ix_ingestion_errors_run_id"), "ingestion_errors", ["run_id"], unique=False)
    op.create_index(op.f("ix_ingestion_errors_topic_id"), "ingestion_errors", ["topic_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_errors_topic_id"), table_name="ingestion_errors")
    op.drop_index(op.f("ix_ingestion_errors_run_id"), table_name="ingestion_errors")
    op.drop_index(op.f("ix_ingestion_errors_id"), table_name="ingestion_errors")
    op.drop_table("ingestion_errors")

    op.drop_index(op.f("ix_personalized_reports_user_id"), table_name="personalized_reports")
    op.drop_index(op.f("ix_personalized_reports_report_date"), table_name="personalized_reports")
    op.drop_index(op.f("ix_personalized_reports_id"), table_name="personalized_reports")
    op.drop_table("personalized_reports")

    op.drop_index(op.f("ix_user_preference_profiles_user_id"), table_name="user_preference_profiles")
    op.drop_index(op.f("ix_user_preference_profiles_id"), table_name="user_preference_profiles")
    op.drop_table("user_preference_profiles")

    op.drop_index(op.f("ix_user_feedback_user_id"), table_name="user_feedback")
    op.drop_index(op.f("ix_user_feedback_id"), table_name="user_feedback")
    op.drop_index(op.f("ix_user_feedback_article_id"), table_name="user_feedback")
    op.drop_table("user_feedback")

    op.drop_index(op.f("ix_article_topic_scores_topic_id"), table_name="article_topic_scores")
    op.drop_index(op.f("ix_article_topic_scores_id"), table_name="article_topic_scores")
    op.drop_index(op.f("ix_article_topic_scores_article_id"), table_name="article_topic_scores")
    op.drop_table("article_topic_scores")

    op.drop_table("user_topic_association")

    op.drop_index(op.f("ix_articles_source_id"), table_name="articles")
    op.drop_index(op.f("ix_articles_published_at"), table_name="articles")
    op.drop_index(op.f("ix_articles_id"), table_name="articles")
    op.drop_index(op.f("ix_articles_content_hash"), table_name="articles")
    op.drop_index(op.f("ix_articles_canonical_url"), table_name="articles")
    op.drop_table("articles")

    op.drop_index(op.f("ix_ingestion_runs_status"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_run_id"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_id"), table_name="ingestion_runs")
    op.drop_table("ingestion_runs")

    op.drop_index(op.f("ix_sources_id"), table_name="sources")
    op.drop_index(op.f("ix_sources_domain"), table_name="sources")
    op.drop_table("sources")

    op.drop_index(op.f("ix_topics_name"), table_name="topics")
    op.drop_index(op.f("ix_topics_id"), table_name="topics")
    op.drop_table("topics")

    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
