import React, { useState, useEffect } from 'react';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8011' : '/_/backend');

export function TopicEditor({ token, currentUser, onSave, onCancel }) {
  const [allTopics, setAllTopics] = useState([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState(
    new Set(currentUser.topics.map((topic) => topic.id))
  );
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

  const handleSaveChanges = async () => {
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

      onSave(updatedUser);

    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="loading-spinner" style={{ margin: '3rem auto' }}></div>;
  }

  return (
    <section className="topic-editor-card">
      <div className="topic-selection-head compact">
        <p className="eyebrow">Preferences</p>
        <h3>Refine your topics</h3>
        <p>Select and deselect to tune your briefing priorities.</p>
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

      <div className="topic-editor-actions">
        <button
          className="button-secondary"
          onClick={onCancel}
          disabled={isSaving}
        >
          Cancel
        </button>
        <button
          className="button-primary"
          onClick={handleSaveChanges}
          disabled={isSaving || selectedTopicIds.size === 0}
        >
          {isSaving ? 'Saving...' : 'Apply Changes'}
        </button>
      </div>
    </section>
  );
}
