import React, { useState, useEffect } from 'react';
import { AuthForm } from './components/AuthForm.jsx';
import { TopicSelection } from './components/TopicSelection.jsx';
import { LandingPage } from './components/LandingPage.jsx';
import { NewsFeed } from './components/NewsFeed.jsx'; 

const API_BASE_URL = 'http://127.0.0.1:8000';

// This is the main "brain" of your application
function App() {
  const [token, setToken] = useState(localStorage.getItem('news_token'));
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // This new state tracks what the user is looking at
  const [view, setView] = useState('landing'); // 'landing', 'auth', 'app', 'topics'

  // This effect runs once on page load to check auth
  useEffect(() => {
    const fetchUser = async () => {
      if (token) {
        try {
          const response = await fetch(`${API_BASE_URL}/users/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (response.ok) {
            const userData = await response.json();
            setUser(userData);
            // User is logged in. Decide where to send them.
            if (userData.topics && userData.topics.length > 0) {
              setView('app'); // User is set up, go to feed
            } else {
              setView('topics'); // New user, go to topic selection
            }
          } else {
            // Token is invalid
            handleLogout();
          }
        } catch (err) {
          handleLogout();
        }
      } else {
        // No token, user is logged out
        setIsLoading(false);
        setView('landing');
      }
      setIsLoading(false);
    };
    fetchUser();
  }, [token]);

  // --- Auth & State Handlers ---

  const handleLogin = (newToken, newUser) => {
    localStorage.setItem('news_token', newToken);
    setToken(newToken);
    setUser(newUser);
    // Send them to the right place after login
    if (newUser.topics && newUser.topics.length > 0) {
      setView('app');
    } else {
      setView('topics');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('news_token');
    setToken(null);
    setUser(null);
    setView('landing'); // Go back to landing page on logout
  };

  const handleTopicsSaved = (updatedUser) => {
    setUser(updatedUser); // Update the user object
    setView('app'); // Send to the app feed
  };

  // --- This is the main render logic ---
  const renderView = () => {
    // Show a loading spinner on initial page load
    if (isLoading) {
      return <div className="loading-spinner"></div>;
    }

    // --- Logged-Out Views ---
    if (!token || !user) {
      if (view === 'auth') {
        return <AuthForm onLoginSuccess={handleLogin} onShowLanding={() => setView('landing')} />;
      }
      // This is the default view for logged-out users
      return <LandingPage onGetStartedClick={() => setView('auth')} />;
    }

    // --- Logged-In Views ---
    
    // 1. New user needs to pick topics
    if (view === 'topics') {
      return (
        <div className="app-container">
          <header className="header-nav">
            <h1>NewsAI</h1>
            <div className="header-user-info">
              <span>Hello, {user.email}!</span>
              <button onClick={handleLogout} className="button-secondary">Log Out</button>
            </div>
          </header>
          <TopicSelection token={token} onTopicsSaved={handleTopicsSaved} />
        </div>
      );
    }
    
    // 2. Existing user sees their feed
    if (view === 'app') {
      return (
        <div className="app-container">
          <header className="header-nav">
            <h1>NewsAI</h1>
            <div className="header-user-info">
              <span>Hello, {user.email}!</span>
              <button onClick={handleLogout} className="button-secondary">Log Out</button>
            </div>
          </header>
          <NewsFeed 
            token={token} 
            user={user} 
            onUserUpdate={setUser} // This allows NewsFeed to update the user
          />
        </div>
      );
    }

    // Fallback (should never be reached)
    return <LandingPage onGetStartedClick={() => setView('auth')} />;
  };

  return <>{renderView()}</>;
}

export default App;



