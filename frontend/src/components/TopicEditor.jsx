import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://127.0.0.1:8000';

// This is the new component to edit topics "inline"
export function TopicEditor({ token, currentUser, onSave, onCancel }) {
  const [allTopics, setAllTopics] = useState([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState(
    // Initialize with the user's current topics
    new Set(currentUser.topics.map(t => t.id))
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Fetch all available topics when the component loads
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

  // Handle topic click
  const toggleTopic = (topicId) => {
    setSelectedTopicIds(prevSelected => {
      const newSelected = new Set(prevSelected);
      if (newSelected.has(topicId)) {
        newSelected.delete(topicId);
      } else {
        newSelected.add(topicId);
      }
      return newSelected;
    });
  };

  // Handle saving the new topic selection
  const handleSaveChanges = async () => {
    setIsSaving(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/users/me/topics`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(Array.from(selectedTopicIds))
      });
      if (!response.ok) {
        throw new Error('Failed to save your topics.');
      }
      const updatedUser = await response.json();
      
      // This calls 'handleTopicsUpdated' in NewsFeed.jsx
      onSave(updatedUser); 

    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="loading-spinner" style={{margin: '3rem auto'}}></div>;
  }

  return (
    <div className="card" style={{ maxWidth: '100%', marginTop: 0 }}>
      <h3 className="form-title">Edit Your Topics</h3>
      <p className="form-subtitle">Select the topics you're interested in.</p>
      
      {error && <p className="error-message">{error}</p>}
      
      <div className="topic-grid">
        {allTopics.map(topic => (
          <button
            key={topic.id}
            className="topic-button"
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
          disabled={isSaving}
        >
          {isSaving ? <span className="button-spinner-light"></span> : 'Apply Changes'}
        </button>
      </div>
    </div>
  );
}
