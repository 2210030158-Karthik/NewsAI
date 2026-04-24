import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { TopicEditor } from './TopicEditor.jsx';

const API_BASE_URL = 'http://127.0.0.1:8011';

const truncate = (value, maxChars = 180) => {
  if (!value) {
    return '';
  }
  if (value.length <= maxChars) {
    return value;
  }
  return `${value.slice(0, maxChars).trim()}...`;
};

const scoreLabel = (score) => {
  if (score === null || score === undefined) {
    return 'N/A';
  }
  return Number(score).toFixed(2);
};

const toReadableParagraphs = (value) => {
  if (!value) {
    return [];
  }

  const normalized = value.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return [];
  }

  const sentences = normalized.split(/(?<=[.!?])\s+/).filter(Boolean);
  if (sentences.length === 0) {
    return [normalized];
  }

  const paragraphs = [];
  for (let index = 0; index < sentences.length; index += 3) {
    paragraphs.push(sentences.slice(index, index + 3).join(' '));
  }
  return paragraphs;
};

export function NewsFeed({ token, user, onUserUpdate }) {
  const [articles, setArticles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const [isEditingTopics, setIsEditingTopics] = useState(false);
  const [feedMode, setFeedMode] = useState('feed');
  const [searchTerm, setSearchTerm] = useState('');
  const [currentSearchTerm, setCurrentSearchTerm] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  const [muteInput, setMuteInput] = useState('');
  const [mutedKeywords, setMutedKeywords] = useState([]);

  const [feedbackMap, setFeedbackMap] = useState({});
  const [pendingFeedbackId, setPendingFeedbackId] = useState(null);

  const [isRefreshingFeed, setIsRefreshingFeed] = useState(false);

  const [reportData, setReportData] = useState(null);
  const [isReportLoading, setIsReportLoading] = useState(true);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [reportError, setReportError] = useState('');

  const [readerArticle, setReaderArticle] = useState(null);
  const [readerContent, setReaderContent] = useState(null);
  const [isReaderLoading, setIsReaderLoading] = useState(false);
  const [readerError, setReaderError] = useState('');

  const apiFetch = useCallback(
    async (path, options = {}) => {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(options.headers || {}),
        },
      });

      if (!response.ok) {
        let errorPayload = null;
        try {
          errorPayload = await response.json();
        } catch {
          errorPayload = null;
        }
        throw new Error(errorPayload?.detail || `Request failed (${response.status}).`);
      }

      if (response.status === 204) {
        return null;
      }

      return response.json();
    },
    [token]
  );

  const fetchFeed = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await apiFetch('/feed');
      setArticles(Array.isArray(data) ? data : []);
    } catch (fetchError) {
      setError(fetchError.message || 'Unable to load your feed.');
    } finally {
      setIsLoading(false);
    }
  }, [apiFetch]);

  const loadLatestReport = useCallback(async () => {
    setIsReportLoading(true);
    setReportError('');
    try {
      const report = await apiFetch('/reports/latest');
      setReportData(report);
    } catch (reportLoadError) {
      if (reportLoadError.message.toLowerCase().includes('no report found')) {
        setReportData(null);
      } else {
        setReportError(reportLoadError.message || 'Could not load report.');
      }
    } finally {
      setIsReportLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    if (!isEditingTopics && feedMode === 'feed') {
      fetchFeed();
    }
  }, [feedMode, fetchFeed, isEditingTopics]);

  useEffect(() => {
    loadLatestReport();
  }, [loadLatestReport]);

  const handleRefreshFeed = async () => {
    const topicIds = (user?.topics || []).map((topic) => topic.id);
    if (topicIds.length === 0) {
      setError('Please select topics before refreshing your feed.');
      return;
    }

    setIsRefreshingFeed(true);
    setError('');
    setSuccessMessage('');
    try {
      const result = await apiFetch('/articles/fetch-and-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_ids: topicIds }),
      });

      if (result?.status === 'queued') {
        setSuccessMessage(`Fetch queued. Run ID: ${result.run_id}`);
      } else {
        setSuccessMessage(result?.message || 'Article fetch completed.');
      }

      await fetchFeed();
    } catch (refreshError) {
      setError(refreshError.message || 'Could not fetch articles.');
    } finally {
      setIsRefreshingFeed(false);
    }
  };

  const handleSearchSubmit = async (event) => {
    event.preventDefault();
    const query = searchTerm.trim();
    if (!query) {
      return;
    }

    setIsSearching(true);
    setError('');
    setSuccessMessage('');

    try {
      const data = await apiFetch(`/search?q=${encodeURIComponent(query)}`);
      setArticles(Array.isArray(data) ? data : []);
      setFeedMode('search');
      setCurrentSearchTerm(query);
    } catch (searchError) {
      setError(searchError.message || 'Search failed.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearSearch = () => {
    setFeedMode('feed');
    setSearchTerm('');
    setCurrentSearchTerm('');
  };

  const handleAddMutedKeyword = (event) => {
    event.preventDefault();
    const keyword = muteInput.trim().toLowerCase();
    if (!keyword) {
      return;
    }
    if (!mutedKeywords.includes(keyword)) {
      setMutedKeywords((previous) => [...previous, keyword]);
    }
    setMuteInput('');
  };

  const handleRemoveMutedKeyword = (keywordToRemove) => {
    setMutedKeywords((previous) => previous.filter((keyword) => keyword !== keywordToRemove));
  };

  const handleFeedback = async (articleId, feedbackType) => {
    setPendingFeedbackId(articleId);
    setError('');
    try {
      await apiFetch(`/articles/${articleId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback_type: feedbackType }),
      });

      setFeedbackMap((previous) => ({
        ...previous,
        [articleId]: feedbackType,
      }));
      setSuccessMessage(`Feedback saved: ${feedbackType}. Ranking model updated.`);

      if (feedMode === 'feed') {
        await fetchFeed();
      }
    } catch (feedbackError) {
      setError(feedbackError.message || 'Could not save feedback.');
    } finally {
      setPendingFeedbackId(null);
    }
  };

  const handleGenerateReport = async () => {
    setIsGeneratingReport(true);
    setReportError('');
    setSuccessMessage('');
    try {
      const report = await apiFetch('/reports/generate', {
        method: 'POST',
      });
      setReportData(report);
      setSuccessMessage('New personalized report generated.');
    } catch (generateError) {
      setReportError(generateError.message || 'Could not generate report.');
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const handleCloseReader = () => {
    setReaderArticle(null);
    setReaderContent(null);
    setReaderError('');
    setIsReaderLoading(false);
  };

  const handleReadInApp = async (article) => {
    if (!article?.id || feedMode !== 'feed') {
      window.open(article?.url, '_blank', 'noopener,noreferrer');
      return;
    }

    setReaderArticle(article);
    setReaderContent(null);
    setReaderError('');
    setIsReaderLoading(true);

    try {
      const payload = await apiFetch(`/articles/${article.id}/full-content?refresh_if_missing=true`);
      setReaderContent(payload);
    } catch (loadError) {
      setReaderError(loadError.message || 'Unable to load full article content.');
    } finally {
      setIsReaderLoading(false);
    }
  };

  const handleTopicsUpdated = (updatedUser) => {
    onUserUpdate(updatedUser);
    setIsEditingTopics(false);
    setSuccessMessage('Topics updated successfully.');
    setFeedMode('feed');
    fetchFeed();
  };

  const normalizedItems = useMemo(() => {
    if (feedMode === 'feed') {
      return articles.map((item) => ({
        article: item.article,
        matchedTopic: item.matched_topic,
        matchedScore: item.matched_score,
        rankingScore: item.ranking_score,
        sourceWeight: item.source_weight,
        topicWeight: item.topic_weight,
      }));
    }

    return articles.map((article) => ({
      article,
      matchedTopic: null,
      matchedScore: null,
      rankingScore: null,
      sourceWeight: null,
      topicWeight: null,
    }));
  }, [articles, feedMode]);

  const filteredItems = useMemo(() => {
    if (mutedKeywords.length === 0) {
      return normalizedItems;
    }

    return normalizedItems.filter((item) => {
      const searchableText = `${item.article.title || ''} ${item.article.description || ''}`.toLowerCase();
      return mutedKeywords.every((keyword) => !searchableText.includes(keyword));
    });
  }, [mutedKeywords, normalizedItems]);

  const readerParagraphs = useMemo(() => {
    return toReadableParagraphs(readerContent?.clean_text || '');
  }, [readerContent]);

  const readerExtractionStatus = readerContent?.extraction_status || '';
  const readerLikelyBlocked =
    readerExtractionStatus === 'blocked_source' || readerExtractionStatus === 'fetch_failed';
  const readerFallbackPreview =
    readerArticle?.description && readerArticle.description !== 'No description available.'
      ? truncate(readerArticle.description, 360)
      : '';

  if (isEditingTopics) {
    return (
      <div className="newsroom-shell single-column">
        <TopicEditor
          token={token}
          currentUser={user}
          onSave={handleTopicsUpdated}
          onCancel={() => setIsEditingTopics(false)}
        />
      </div>
    );
  }

  return (
    <div className="newsroom-shell">
      <section className="news-main-col">
        <header className="news-main-header reveal-1">
          <div>
            <p className="eyebrow">Your intelligence desk</p>
            <h2>{feedMode === 'feed' ? 'Personalized Feed' : `Search: ${currentSearchTerm}`}</h2>
            <p>
              {feedMode === 'feed'
                ? `Tracking ${(user?.topics || []).length} active topic(s) with real-time ranking updates.`
                : 'Live search results from SerpApi, independent from your saved feed.'}
            </p>
          </div>
          <div className="header-action-grid">
            <button className="button-secondary" onClick={() => setIsEditingTopics(true)}>
              Edit Topics
            </button>
            <button
              className={isRefreshingFeed ? 'button-secondary' : 'button-primary'}
              disabled={isRefreshingFeed}
              onClick={handleRefreshFeed}
            >
              {isRefreshingFeed ? 'Fetching...' : 'Fetch Articles'}
            </button>
          </div>
        </header>

        <section className="command-bar reveal-2">
          <form className="search-form" onSubmit={handleSearchSubmit}>
            <input
              className="field-input"
              type="text"
              placeholder="Search topics, markets, events, or entities"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
            <button className="button-primary" type="submit" disabled={isSearching}>
              {isSearching ? 'Searching...' : 'Search'}
            </button>
            {feedMode === 'search' && (
              <button className="button-secondary" type="button" onClick={handleClearSearch}>
                Back to Feed
              </button>
            )}
          </form>

          <form className="mute-form" onSubmit={handleAddMutedKeyword}>
            <input
              className="field-input"
              type="text"
              placeholder="Mute keyword (example: gossip)"
              value={muteInput}
              onChange={(event) => setMuteInput(event.target.value)}
            />
            <button className="button-secondary" type="submit">
              Mute
            </button>
          </form>

          {mutedKeywords.length > 0 && (
            <div className="keyword-pills">
              {mutedKeywords.map((keyword) => (
                <button
                  key={keyword}
                  className="keyword-pill"
                  type="button"
                  onClick={() => handleRemoveMutedKeyword(keyword)}
                >
                  {keyword} ×
                </button>
              ))}
            </div>
          )}
        </section>

        {error && <div className="error-message reveal-3">{error}</div>}
        {successMessage && <div className="success-message reveal-3">{successMessage}</div>}

        <section className="article-stream reveal-3">
          {isLoading || isSearching ? (
            <div className="loading-panel">Loading stories...</div>
          ) : filteredItems.length === 0 ? (
            <div className="empty-panel">
              {feedMode === 'search'
                ? 'No stories matched this search.'
                : 'No stories available yet. Trigger a refresh to fetch articles.'}
            </div>
          ) : (
            filteredItems.map((item, index) => {
              const article = item.article;
              const summary =
                article.clean_text && article.clean_text.trim().length > 0
                  ? article.clean_text
                  : article.description;

              return (
                <article
                  key={article.id || article.url || `story-${index}`}
                  className="story-card"
                  style={{ animationDelay: `${Math.min(index * 35, 320)}ms` }}
                >
                  <div className="story-media-wrap">
                    {article.image_url ? (
                      <img className="story-media" src={article.image_url} alt={article.title} />
                    ) : (
                      <div className="story-media placeholder">No image</div>
                    )}
                  </div>

                  <div className="story-body">
                    <div className="story-meta-row">
                      <span className="story-source">{article.source || 'Unknown source'}</span>
                      <span className="story-date">{new Date(article.published_at).toLocaleString()}</span>
                    </div>

                    <h3 className="story-title">{article.title}</h3>
                    <p className="story-summary">{truncate(summary || 'No summary available.', 220)}</p>

                    <div className="story-chip-row">
                      {item.matchedTopic && <span className="story-chip">Topic: {item.matchedTopic.name}</span>}
                      {item.rankingScore !== null && (
                        <span className="story-chip">Rank: {scoreLabel(item.rankingScore)}</span>
                      )}
                      {item.topicWeight !== null && (
                        <span className="story-chip muted">Topic Weight: {scoreLabel(item.topicWeight)}</span>
                      )}
                      {item.sourceWeight !== null && (
                        <span className="story-chip muted">Source Weight: {scoreLabel(item.sourceWeight)}</span>
                      )}
                    </div>

                    <div className="story-actions">
                      <button
                        type="button"
                        className="button-secondary"
                        onClick={() => handleReadInApp(article)}
                      >
                        {article.id && feedMode === 'feed' ? 'Read In App' : 'Read Full Article'}
                      </button>

                      <a className="button-secondary" href={article.url} target="_blank" rel="noreferrer">
                        Open Source
                      </a>

                      {article.id && feedMode === 'feed' && (
                        <>
                          <button
                            type="button"
                            className={`reaction-btn ${feedbackMap[article.id] === 'like' ? 'active-like' : ''}`}
                            disabled={pendingFeedbackId === article.id}
                            onClick={() => handleFeedback(article.id, 'like')}
                          >
                            👍 Like
                          </button>
                          <button
                            type="button"
                            className={`reaction-btn ${feedbackMap[article.id] === 'dislike' ? 'active-dislike' : ''}`}
                            disabled={pendingFeedbackId === article.id}
                            onClick={() => handleFeedback(article.id, 'dislike')}
                          >
                            👎 Dislike
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </article>
              );
            })
          )}
        </section>
      </section>

      <aside className="news-side-col reveal-2">
        <section className="side-card">
          <div className="side-card-header">
            <h3>Daily Briefing</h3>
            <button
              className="button-primary"
              type="button"
              onClick={handleGenerateReport}
              disabled={isGeneratingReport}
            >
              {isGeneratingReport ? 'Generating...' : 'Generate Report'}
            </button>
          </div>

          {isReportLoading ? (
            <p className="side-state">Loading latest report...</p>
          ) : reportError ? (
            <p className="side-state error">{reportError}</p>
          ) : reportData ? (
            <>
              <p className="side-time">
                {new Date(reportData.report_date).toLocaleString()}
              </p>
              <pre className="report-text">{reportData.report_text}</pre>
            </>
          ) : (
            <p className="side-state">No report yet. Generate your first personalized report.</p>
          )}
        </section>
      </aside>

      {readerArticle && (
        <div className="reader-overlay" onClick={handleCloseReader} role="dialog" aria-modal="true">
          <article className="reader-panel" onClick={(event) => event.stopPropagation()}>
            <header className="reader-head">
              <div>
                <p className="eyebrow">In-app article reader</p>
                <h3>{readerArticle.title}</h3>
                <p className="reader-meta">
                  {(readerContent?.source || readerArticle.source || 'Unknown source')} •{' '}
                  {new Date(readerArticle.published_at).toLocaleString()}
                  {readerContent?.word_count ? ` • ${readerContent.word_count} words` : ''}
                </p>
              </div>
              <button type="button" className="button-secondary" onClick={handleCloseReader}>
                Close
              </button>
            </header>

            {isReaderLoading ? (
              <div className="loading-panel">Loading full article content...</div>
            ) : readerError ? (
              <div className="error-message">{readerError}</div>
            ) : readerContent?.is_full_content_available ? (
              <div className="reader-body">
                {readerParagraphs.map((paragraph, index) => (
                  <p key={`reader-paragraph-${index}`}>{paragraph}</p>
                ))}
              </div>
            ) : (
              <div className="empty-panel reader-empty">
                <p>
                  {readerLikelyBlocked
                    ? 'This publisher is blocking automated extraction for now. Open the source article directly.'
                    : 'Could not extract enough body text for this story yet. Open the source article directly.'}
                </p>
                {readerFallbackPreview && (
                  <p className="reader-fallback-preview">Preview: {readerFallbackPreview}</p>
                )}
                {readerExtractionStatus && (
                  <p className="reader-status-hint">Status: {readerExtractionStatus}</p>
                )}
              </div>
            )}

            <footer className="reader-foot">
              <a
                className="button-primary"
                href={readerContent?.canonical_url || readerArticle.url}
                target="_blank"
                rel="noreferrer"
              >
                Open Original Source
              </a>
            </footer>
          </article>
        </div>
      )}
    </div>
  );
}

