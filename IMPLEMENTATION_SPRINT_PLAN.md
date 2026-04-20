# Personalized News Platform - Execution Sprint Plan

Date: 2026-04-20
Scope: Full-article scraping, async ingestion at scale (>=250 topics / 5 hours), local-model topic sorting, feedback learning (like/dislike), personalized reports, DB-backed storage and APIs.

## Delivery Principles

- No long-running scraping/model inference in API request path.
- Fully idempotent ingestion and ranking updates.
- Database migrations first, features second.
- Every ticket includes acceptance criteria and concrete file targets.
- Feature flags used for safe rollout and rollback.

## Target Architecture (End State)

- API service: FastAPI for auth, feed, feedback, article, report endpoints.
- Worker service: Celery workers for scraping, extraction, classification, ranking updates.
- Scheduler: Celery Beat job every 5 hours.
- Queue broker: Redis.
- Database: PostgreSQL.
- Local inference:
  - Topic sorting model (small local transformer/sentence model).
  - Local summarizer/report model (small quantized model).
- Scraper pipeline:
  - Discovery -> Fetch -> Extract (full text) -> Normalize -> Classify -> Persist.

## Build Order Overview

1. Sprint A: Platform foundation and migrations.
2. Sprint B: Full scraping/extraction pipeline.
3. Sprint C: Async jobs + 250-topic scheduler.
4. Sprint D: Local topic sorting and ranking.
5. Sprint E: Like/dislike learning loop.
6. Sprint F: Personalized report generation.
7. Sprint G: Frontend integration and UX.
8. Sprint H: Hardening, testing, observability.

---

## Sprint A - Foundation and Schema (Week 1)

### A1 - Add migration framework

Priority: P0
Dependencies: none
Estimate: 0.5 day
Files:

- backend/alembic.ini
- backend/alembic/env.py
- backend/alembic/versions/\*
- backend/requirements.txt
  Acceptance:
- alembic upgrade head works locally.
- Existing app boots with migrated schema only.

### A2 - Expand data model for full pipeline

Priority: P0
Dependencies: A1
Estimate: 1.5 days
Files:

- backend/app/models.py
- backend/app/schemas.py
- backend/alembic/versions/\*
  New/updated tables:
- topics (add fields: active, fetch_frequency_hours, language, region)
- sources (domain, reliability_score, robots_allowed, crawl_delay_seconds)
- articles (canonical_url, raw_html, clean_text, author, image_url, word_count, content_hash, fetched_at, extraction_status)
- article_topic_scores (article_id, topic_id, score)
- user_feedback (user_id, article_id, feedback_type like/dislike, created_at)
- user_preference_profiles (user_id, topic_weights_json, source_weights_json, updated_at)
- personalized_reports (user_id, report_date, report_text, metadata_json)
- ingestion_runs (run_id, started_at, ended_at, status, topics_total, urls_discovered, urls_scraped, success_count, fail_count)
- ingestion_errors (run_id, topic_id, url, stage, error_type, message)
  Acceptance:
- Migration creates all tables and indexes.
- Unique constraints prevent duplicate article URLs.
- Foreign keys and cascade rules are valid.

### A3 - Fix current schema/controller mismatches

Priority: P0
Dependencies: A2
Estimate: 0.5 day
Files:

- backend/app/models.py
- backend/app/api.py
- backend/app/schemas.py
  Acceptance:
- article-topic score field names are consistent across model/schema/API.
- /feed endpoint returns valid payload without ORM field errors.

### A4 - Introduce feature flags

Priority: P1
Dependencies: A2
Estimate: 0.5 day
Files:

- backend/app/config.py
- backend/.env.example
  Flags:
- ENABLE_ASYNC_INGESTION
- ENABLE_LOCAL_RANKER
- ENABLE_FEEDBACK_RANKING
- ENABLE_PERSONALIZED_REPORTS
  Acceptance:
- Flags toggle behavior without code edits.

---

## Sprint B - Full Web Scraping Pipeline (Week 1-2)

### B1 - Build URL discovery layer

Priority: P0
Dependencies: A2
Estimate: 1 day
Files:

- backend/app/discovery.py (new)
- backend/app/news_fetcher.py (refactor)
  Behavior:
- For each topic, discover candidate URLs from multiple source strategies.
- Deduplicate by canonical URL.
  Acceptance:
- Returns URL set with source metadata per topic.
- Duplicate URLs for same run are eliminated.

### B2 - Build robust fetch and extraction engine

Priority: P0
Dependencies: B1
Estimate: 2 days
Files:

- backend/app/scraper.py (new)
- backend/app/content_extractor.py (new)
- backend/app/news_fetcher.py (wire-up)
  Stack:
- Async HTTP client for static pages.
- Extraction fallback chain:
  1. metadata/OpenGraph parse
  2. readability/trafilatura extraction
  3. headless browser fallback (Playwright) for JS-heavy pages
     Acceptance:
- Stores full cleaned article text for successful pages.
- Stores extraction_status per article.
- Fallback path executed for JS pages.

### B3 - Add domain politeness and resilience

Priority: P0
Dependencies: B2
Estimate: 1 day
Files:

- backend/app/scraper.py
- backend/app/sources.py (new)
  Features:
- Per-domain concurrency limits
- Retry with exponential backoff
- robots/crawl-delay checks where applicable
- Timeout and circuit-breaker logic
  Acceptance:
- Scraper does not overload domains.
- Failures are retried and logged with stage metadata.

### B4 - Persist complete article records

Priority: P0
Dependencies: B2
Estimate: 1 day
Files:

- backend/app/repositories/article_repo.py (new)
- backend/app/news_fetcher.py
  Acceptance:
- raw_html and clean_text stored when available.
- content_hash dedupe prevents duplicate content rows.
- published_at and fetched_at always set.

---

## Sprint C - Async Jobs and 5-Hour Scheduler (Week 2)

### C1 - Integrate Celery + Redis

Priority: P0
Dependencies: A4
Estimate: 1 day
Files:

- backend/app/celery_app.py (new)
- backend/app/tasks.py (new)
- backend/requirements.txt
- backend/docker-compose.yml (new or update)
  Acceptance:
- Worker starts and processes test task.
- Redis broker and result backend configured.

### C2 - Create ingestion orchestration tasks

Priority: P0
Dependencies: C1, B4
Estimate: 1.5 days
Files:

- backend/app/tasks_ingestion.py (new)
- backend/app/tasks.py
  Flow:
- parent task starts run record
- chunk topics into batches
- enqueue discovery/scrape/classify pipeline
- finalize run metrics
  Acceptance:
- One run processes chunked topics asynchronously.
- Run metrics and failures persisted.

### C3 - 250-topic seed and 5-hour beat schedule

Priority: P0
Dependencies: C2
Estimate: 1 day
Files:

- backend/app/topic_seed.py (new)
- backend/app/tasks_schedule.py (new)
- backend/app/celery_app.py
  Acceptance:
- At least 250 active topics present.
- Beat triggers ingestion every 5 hours.
- New run created automatically on schedule.

### C4 - Add admin run-control endpoints

Priority: P1
Dependencies: C2
Estimate: 0.5 day
Files:

- backend/app/api.py
  Endpoints:
- POST /admin/ingestion/run-now
- GET /admin/ingestion/runs
- GET /admin/ingestion/runs/{run_id}
  Acceptance:
- Manual trigger works.
- Run status visible through API.

---

## Sprint D - Local Topic Sorting and Ranking Core (Week 3)

### D1 - Local model service abstraction

Priority: P0
Dependencies: A4
Estimate: 1 day
Files:

- backend/app/ml/local_models.py (new)
- backend/app/classifier.py (refactor)
  Behavior:
- Remove dependency on remote inference APIs.
- Batch classify clean_text against topic labels.
  Acceptance:
- Classification runs locally and persists topic scores.
- Batch mode supports worker throughput.

### D2 - Topic score persistence and calibration

Priority: P0
Dependencies: D1
Estimate: 1 day
Files:

- backend/app/classifier.py
- backend/app/repositories/article_repo.py
  Acceptance:
- Top-N topic scores stored per article.
- Score normalization consistent across articles.

### D3 - Base ranking formula for personalized feed

Priority: P0
Dependencies: D2
Estimate: 1 day
Files:

- backend/app/ranking.py (new)
- backend/app/api.py
  Formula components:
- topic relevance
- freshness decay
- source quality prior
- diversity penalty
  Acceptance:
- Feed endpoint returns ranked results with stable sorting.
- Explain metadata returned for debugging.

---

## Sprint E - Like/Dislike Learning Loop (Week 3)

### E1 - Feedback APIs and persistence

Priority: P0
Dependencies: A2
Estimate: 0.5 day
Files:

- backend/app/api.py
- backend/app/schemas.py
  Endpoints:
- POST /articles/{article_id}/feedback (like/dislike)
- DELETE /articles/{article_id}/feedback
  Acceptance:
- Feedback events stored with user and timestamp.
- Duplicate conflicting feedback is resolved predictably.

### E2 - Online preference profile updates

Priority: P0
Dependencies: E1, D3
Estimate: 1 day
Files:

- backend/app/preferences.py (new)
- backend/app/tasks_preferences.py (new)
  Behavior:
- Update user topic/source weights after each feedback event.
- Persist profile snapshots.
  Acceptance:
- Re-ranking reflects new preference shortly after feedback.

### E3 - Feedback-aware ranking integration

Priority: P0
Dependencies: E2
Estimate: 1 day
Files:

- backend/app/ranking.py
- backend/app/api.py
  Acceptance:
- Liked-topic content increases ranking probability.
- Disliked-topic/source content demoted.

---

## Sprint F - Personalized Report Generation (Week 4)

### F1 - Report generation pipeline (local model)

Priority: P0
Dependencies: D1, E2
Estimate: 1.5 days
Files:

- backend/app/reports.py (new)
- backend/app/tasks_reports.py (new)
- backend/app/ml/local_models.py
  Behavior:
- Generate user-specific report from top-ranked fresh articles.
- Group by dominant interests and date.
  Acceptance:
- Report text persisted in personalized_reports.
- Report reproducible for same time window and inputs.

### F2 - Report APIs

Priority: P0
Dependencies: F1
Estimate: 0.5 day
Files:

- backend/app/api.py
- backend/app/schemas.py
  Endpoints:
- GET /reports/latest
- GET /reports/history
  Acceptance:
- Authenticated user can fetch latest and past reports.

---

## Sprint G - Frontend Integration (Week 4)

### G1 - Full article display page/component

Priority: P0
Dependencies: B4
Estimate: 1 day
Files:

- frontend/src/components/NewsFeed.jsx
- frontend/src/components/ArticleView.jsx (new)
- frontend/src/App.jsx
  Acceptance:
- User can open and read full extracted article text in app.
- Loading/error states handled.

### G2 - Like/dislike controls in feed and article view

Priority: P0
Dependencies: E1
Estimate: 1 day
Files:

- frontend/src/components/NewsFeed.jsx
- frontend/src/components/ArticleActions.jsx (new)
  Acceptance:
- Like/dislike persists and updates UI state.
- Undo supported.

### G3 - Personalized report UI

Priority: P0
Dependencies: F2
Estimate: 1 day
Files:

- frontend/src/components/ReportView.jsx (new)
- frontend/src/App.jsx
  Acceptance:
- User can view latest report and report history.

### G4 - Topic/source preference controls

Priority: P1
Dependencies: E2
Estimate: 1 day
Files:

- frontend/src/components/TopicEditor.jsx
- frontend/src/components/PreferencePanel.jsx (new)
  Acceptance:
- User can view and adjust preference controls.

---

## Sprint H - Hardening and Release (Week 5)

### H1 - Test suite and CI gates

Priority: P0
Dependencies: A-G
Estimate: 2 days
Files:

- backend/tests/\*
- frontend tests/\*
- .github/workflows/\*
  Coverage:
- scraper extraction tests
- ranking correctness tests
- feedback learning tests
- API contract tests
  Acceptance:
- CI passes with mandatory tests.

### H2 - Observability and alerting

Priority: P0
Dependencies: C2
Estimate: 1 day
Files:

- backend/app/observability.py (new)
- backend/app/tasks\*.py
  Metrics:
- per-run success/failure
- extraction success ratio
- model inference latency
- feed latency
  Acceptance:
- Dashboard-ready metrics emitted.

### H3 - Performance and load validation

Priority: P0
Dependencies: H1
Estimate: 1 day
Targets:

- 250 topics complete in 5-hour window with margin.
- feed endpoint p95 latency target defined and met.
  Acceptance:
- Load report documented and baseline saved.

### H4 - Production readiness checklist

Priority: P0
Dependencies: H2, H3
Estimate: 0.5 day
Checklist:

- secrets management
- backup policy
- data retention
- legal compliance for scraping and content display
- rollback procedures
  Acceptance:
- Signed off checklist before release.

---

## API Contract Additions (Planned)

- GET /articles/{id} -> full article content and metadata
- POST /articles/{id}/feedback -> like/dislike event
- DELETE /articles/{id}/feedback -> undo
- GET /feed -> personalized ranked feed with explain fields
- GET /reports/latest -> current personalized report
- GET /reports/history -> historical reports
- POST /admin/ingestion/run-now -> trigger run
- GET /admin/ingestion/runs -> run list

## Ranking v1 (Initial Formula)

Score(article, user) =

- w1 \* topic_match(article, user_profile)
- w2 \* freshness_decay(article.published_at)
- w3 \* source_quality(article.source)
- w4 \* feedback_affinity(article, user)
- w5 \* diversity_penalty(recently_seen, article)

Weights are tuned from offline logs and updated after feedback analysis.

## Milestone Exit Criteria

- M1 (after Sprint C): ingestion runs async every 5 hours on >=250 topics.
- M2 (after Sprint E): like/dislike changes ranking behavior measurably.
- M3 (after Sprint F): personalized reports generated and stored.
- M4 (after Sprint H): production-ready reliability and observability.

## Immediate Start Tasks (First 48 Hours)

1. A1 migration framework
2. A2 schema migration
3. A3 current mismatch fixes
4. C1 celery/redis wiring
5. B1 discovery layer scaffold

If these 5 tickets are finished, coding can continue directly into the ingestion pipeline without rework.
