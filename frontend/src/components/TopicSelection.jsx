import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://127.0.0.1:8000';

// The "export" keyword here is what fixes the error
export function TopicSelection({ token, onTopicsSaved }) {
  const [allTopics, setAllTopics] = useState([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState(new Set());
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
  const handleSaveTopics = async () => {
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
      onTopicsSaved(updatedUser); // This tells App.jsx we're done
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
    <div className="card">
      <h2 className="form-title">Welcome to NewsAI!</h2>
      <p className="form-subtitle">Please select a few topics to personalize your feed.</p>
      
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
      
      <button 
        className="button-primary" 
        style={{width: '100%', marginTop: '1.5rem'}}
        onClick={handleSaveTopics}
        disabled={isSaving || selectedTopicIds.size === 0}
      >
        {isSaving ? <span className="button-spinner-light"></span> : 'Save and Continue'}
      </button>
    </div>
  );
}
