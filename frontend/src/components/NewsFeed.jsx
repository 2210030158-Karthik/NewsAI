import React, { useState, useEffect, useCallback } from 'react';
import { TopicEditor } from './TopicEditor.jsx'; 

const API_BASE_URL = 'http://127.0.0.1:8000';
const COOLDOWN_HOURS = 2;
const COOLDOWN_MS = COOLDOWN_HOURS * 60 * 60 * 1000;

function formatCooldownTime(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `On Cooldown (${hours}h ${minutes}m ${seconds}s)`;
}

export function NewsFeed({ token, user, onUserUpdate }) {
  const [articles, setArticles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [cooldownTime, setCooldownTime] = useState(0); 
  const [justRefreshed, setJustRefreshed] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isEditingTopics, setIsEditingTopics] = useState(false);

  const [feedDisplayMode, setFeedDisplayMode] = useState('feed'); // 'feed' or 'search'
  const [searchTerm, setSearchTerm] = useState('');
  const [currentSearchTerm, setCurrentSearchTerm] = useState(''); 
  const [isSearching, setIsSearching] = useState(false);

  // --- NEW STATE FOR MUTING ---
  const [mutedKeywords, setMutedKeywords] = useState([]);
  const [muteInput, setMuteInput] = useState('');
  // --- END NEW STATE ---

  const userCooldownKey = user ? `lastRefreshTimestamp_${user.email}` : null;

  const fetchFeed = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/feed`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) {
        throw new Error('Failed to fetch your personalized feed.');
      }
      const data = await response.json();
      setArticles(data); 
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [token]); 

  useEffect(() => {
    if (!isEditingTopics && feedDisplayMode === 'feed') {
      fetchFeed();
    }
  }, [fetchFeed, isEditingTopics, feedDisplayMode]); 

  useEffect(() => {
    if (!userCooldownKey) return; 
    const updateCooldown = () => {
      const lastRefresh = localStorage.getItem(userCooldownKey);
      if (!lastRefresh) {
        setCooldownTime(0);
        return;
      }
      const timePassed = Date.now() - parseInt(lastRefresh);
      if (timePassed < COOLDOWN_MS) {
        const remainingMs = COOLDOWN_MS - timePassed;
        setCooldownTime(Math.ceil(remainingMs / 1000));
      } else {
        setCooldownTime(0);
      }
    };
    updateCooldown(); 
    const interval = setInterval(updateCooldown, 1000); 
    return () => clearInterval(interval);
  }, [userCooldownKey]);

  const handleRefreshClick = async () => {
    if (cooldownTime > 0 || isRefreshing || !userCooldownKey || !user) return; 
    setIsRefreshing(true);
    setError('');
    setJustRefreshed(false);
    try {
      const topicIds = user.topics.map(topic => topic.id);
      if (topicIds.length === 0) {
        throw new Error("You have no topics selected.");
      }
      const processResponse = await fetch(`${API_BASE_URL}/articles/fetch-and-process`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ topic_ids: topicIds })
      });
      if (!processResponse.ok) {
        throw new Error('Failed to start article processing.');
      }
      await fetchFeed(); 
      localStorage.setItem(userCooldownKey, Date.now().toString());
      setCooldownTime(COOLDOWN_HOURS * 60 * 60);
      setJustRefreshed(true);
      setTimeout(() => setJustRefreshed(false), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleTopicsUpdated = (updatedUser) => {
    onUserUpdate(updatedUser); 
    setIsEditingTopics(false); 
  };

  const handleSearchSubmit = async (e) => {
    e.preventDefault();
    const query = searchTerm.trim();
    if (!query) return;

    setIsSearching(true);
    setError('');
    try {
      const url = `${API_BASE_URL}/search?q=${encodeURIComponent(query)}`;
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        }
      });
      if (!response.ok) {
        throw new Error('Search failed. Please try again.');
      }
      const data = await response.json();
      
      setArticles(data); 
      setFeedDisplayMode('search');
      setCurrentSearchTerm(query); 
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearSearch = () => {
    setArticles([]); 
    setFeedDisplayMode('feed');
    setSearchTerm('');
    setCurrentSearchTerm('');
  };

  // --- NEW MUTE KEYWORD HANDLERS ---
  const handleMuteSubmit = (e) => {
    e.preventDefault();
    const keywordToAdd = muteInput.trim().toLowerCase();
    if (keywordToAdd && !mutedKeywords.includes(keywordToAdd)) {
      setMutedKeywords([...mutedKeywords, keywordToAdd]);
    }
    setMuteInput(''); // Clear the input
  };

  const removeMutedKeyword = (keywordToRemove) => {
    setMutedKeywords(mutedKeywords.filter(k => k !== keywordToRemove));
  };
  // --- END NEW HANDLERS ---


  const isButtonDisabled = cooldownTime > 0 || isRefreshing;
  
  const getButtonText = () => {
    if (isRefreshing) {
      return (
        <>
          <span className="button-spinner"></span>
          Processing...
        </>
      );
    }
    if (cooldownTime > 0) {
      return formatCooldownTime(cooldownTime);
    }
    return 'Refresh Feed';
  };
  
  if (isEditingTopics) {
    return (
      <div className="feed-container">
        <div className="feed-header" style={{ borderBottom: 'none' }}>
          <div>
            <h2 className="feed-title">Edit Your Topics</h2>
            <p className="feed-subtitle">Select the topics you're interested in.</p>
          </div>
        </div>
        <TopicEditor
          token={token}
          currentUser={user}
          onSave={handleTopicsUpdated}
          onCancel={() => setIsEditingTopics(false)}
        />
      </div>
    );
  }

  const showLoading = isLoading || isSearching;
  
  const topicCount = user ? user.topics.length : 0;

  // --- NEW FILTER LOGIC ---
  const filteredArticles = articles.filter(item => {
    if (mutedKeywords.length === 0) {
      return true; // No keywords to mute, show all
    }
    // Get the correct article object (works for feed and search)
    const article = feedDisplayMode === 'feed' ? item.article : item;
    const textToCheck = `${article.title} ${article.description}`.toLowerCase();
    
    // Return true (keep) if *none* of the muted keywords are found
    return !mutedKeywords.some(keyword => textToCheck.includes(keyword));
  });
  // --- END FILTER LOGIC ---


  return (
    <div className="feed-container">
      <div className="feed-header">
        <div>
          <h2 className="feed-title">
            {feedDisplayMode === 'feed' ? 'Your Personalized Feed' : 'Search Results'}
          </h2>
          <p className="feed-subtitle">
            {feedDisplayMode === 'feed'
              ? `Based on your ${topicCount} selected topic(s).`
              : `Showing results for "${currentSearchTerm}"`
            }
          </p>
        </div>
        {feedDisplayMode === 'feed' && (
          <div className="feed-actions">
            {justRefreshed && (
              <span className="refresh-success">Refreshed!</span>
            )}
            <button 
              className="button-secondary"
              onClick={() => setIsEditingTopics(true)}
            >
              Edit Topics
            </button>
            <button 
              className="button-secondary" 
              onClick={handleRefreshClick}
              disabled={isButtonDisabled}
              style={{ minWidth: '160px' }}
            >
              {getButtonText()}
            </button>
          </div>
        )}
      </div>

      <div className="search-bar-container">
        <form className="search-form" onSubmit={handleSearchSubmit}>
          <input
            type="text"
            className="search-input"
            placeholder="Search for any topic (e.g., 'Cyberpunk 2077')..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <button type="submit" className="button-primary" disabled={isSearching}>
            {isSearching ? <span className="button-spinner-light"></span> : 'Search'}
          </button>
        </form>
        {feedDisplayMode === 'search' && (
          <button className="back-link" onClick={handleClearSearch} style={{ marginBottom: 0 }}>
            &larr; Back to your personalized feed
          </button>
        )}
      </div>

      {/* --- NEW MUTE KEYWORD SECTION --- */}
      <div className="mute-container">
        <form className="mute-form" onSubmit={handleMuteSubmit}>
          <input
            type="text"
            className="mute-input"
            placeholder="Mute a keyword (e.g., 'Kardashian')..."
            value={muteInput}
            onChange={(e) => setMuteInput(e.target.value)}
          />
          <button type="submit" className="button-secondary">Mute</button>
        </form>
        
        {mutedKeywords.length > 0 && (
          <div className="muted-keyword-list">
            {mutedKeywords.map(keyword => (
              <span key={keyword} className="muted-keyword-item">
                {keyword}
                <button onClick={() => removeMutedKeyword(keyword)}>&times;</button>
              </span>
            ))}
          </div>
        )}
      </div>
      {/* --- END NEW MUTE SECTION --- */}
      
      {error && <p className="error-message">{error}</p>}

      <>
        {showLoading ? (
          <div className="loading-spinner" style={{margin: '3rem auto'}}></div>
        ) : filteredArticles.length === 0 ? ( // Use filtered list
          <div className="card" style={{maxWidth: '100%', textAlign: 'center'}}>
            <p>
              {articles.length === 0 && feedDisplayMode === 'search'
                ? 'No articles found for your search term.'
                : (articles.length === 0 && feedDisplayMode === 'feed'
                  ? "Your feed is empty. Try refreshing or adding more topics!"
                  : "All articles are hidden by your muted keywords."
                )
              }
            </p>
          </div>
        ) : (
          <div className="feed-list-container">
            {/* --- USE THE FILTERED LIST TO RENDER --- */}
            {filteredArticles.map((item, index) => {
              
              const article = feedDisplayMode === 'feed' ? item.article : item;
              const matched_topic = feedDisplayMode === 'feed' ? item.matched_topic : null;
              
              const hasValidDescription = article.description && 
                                          article.description.toLowerCase() !== 'no description available.';
              
              const key = article.url ? article.url : `article-${index}`;
              const imageUrl = article.image_url; 

              return (
                <a 
                  key={key} 
                  href={article.url} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="article-card-link"
                >
                  <div className="article-card">
                    {imageUrl && (
                      <img 
                        src={imageUrl} 
                        alt={article.title} 
                        className="article-image" 
                        onError={(e) => {
                          e.target.src = 'https://placehold.co/150x150/f1f5f9/64748b?text=No+Image';
                          e.target.onerror = null;
                        }}
                      />
                    )}
                    <div 
                      className="article-content" 
                      style={{ paddingLeft: imageUrl ? 0 : '1rem' }}
                    >
                      <span className="article-source">
                        {article.source || 'News Source'}
                      </span>
                      <h3 className="article-title">{article.title}</h3>
                      
                      {hasValidDescription ? (
                        <p className="article-summary">{article.description}</p>
                      ) : (
                        <p className="article-summary-fallback">
                          {feedDisplayMode === 'feed' && matched_topic
                            ? `Primary Topic: ${matched_topic.name}`
                            : (feedDisplayMode === 'search' ? 'Search Result' : 'No summary')
                          }
                        </p>
                      )}
                    </div>
                  </div>
                </a>
              );
            })}
          </div>
        )}
      </>
    </div>
  );
}

