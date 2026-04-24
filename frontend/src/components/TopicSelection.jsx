import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://127.0.0.1:8011';

// The "export" keyword here is what fixes the error
export function TopicSelection({ token, onTopicsSaved }) {
  const [allTopics, setAllTopics] = useState([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const fetchAllTopics = async () => {
      setIsLoading(true);
      setError('');
      try {
        const response = await fetch(`${API_BASE_URL}/topics`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) {
          throw new Error('Failed to load topics.');
        }
        const data = await response.json();
        setAllTopics(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };
    fetchAllTopics();
  }, [token]);

  const toggleTopic = (topicId) => {
    setSelectedTopicIds((prevSelected) => {
      const newSelected = new Set(prevSelected);
      if (newSelected.has(topicId)) {
        newSelected.delete(topicId);
      } else {
        newSelected.add(topicId);
      }
      return newSelected;
    });
  };

  const handleSaveTopics = async () => {
    setIsSaving(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/users/me/topics`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(Array.from(selectedTopicIds)),
      });
      if (!response.ok) {
        throw new Error('Failed to save your topics.');
      }
      const updatedUser = await response.json();
      onTopicsSaved(updatedUser);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="loading-spinner"></div>;
  }

  return (
    <section className="topic-selection-wrap">
      <div className="topic-selection-head">
        <p className="eyebrow">Onboarding</p>
        <h2>Pick your coverage beats</h2>
        <p>
          Choose at least one topic. We will use these signals to build your first personalized brief.
        </p>
      </div>

      {error && <p className="error-message">{error}</p>}

      <div className="topic-grid enhanced">
        {allTopics.map((topic) => (
          <button
            key={topic.id}
            className="topic-chip"
            data-selected={selectedTopicIds.has(topic.id)}
            onClick={() => toggleTopic(topic.id)}
          >
            {topic.name}
          </button>
        ))}
      </div>

      <div className="selection-footer">
        <span>{selectedTopicIds.size} selected</span>
      </div>

      <button
        className="button-primary"
        style={{ width: '100%' }}
        onClick={handleSaveTopics}
        disabled={isSaving || selectedTopicIds.size === 0}
      >
        {isSaving ? 'Saving...' : 'Save and Continue'}
      </button>
    </section>
  );
}
