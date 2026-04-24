import React, { useEffect, useState } from 'react';
import { AuthForm } from './components/AuthForm.jsx';
import { TopicSelection } from './components/TopicSelection.jsx';
import { LandingPage } from './components/LandingPage.jsx';
import { NewsFeed } from './components/NewsFeed.jsx';

const API_BASE_URL = 'http://127.0.0.1:8011';

function App() {
  const [token, setToken] = useState(localStorage.getItem('news_token'));
  const [user, setUser] = useState(null);
  const [isBooting, setIsBooting] = useState(true);
  const [view, setView] = useState('landing');

  useEffect(() => {
    const fetchUser = async () => {
      if (token) {
        try {
          const response = await fetch(`${API_BASE_URL}/users/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });

          if (response.ok) {
            const userData = await response.json();
            setUser(userData);
            if (userData.topics && userData.topics.length > 0) {
              setView('app');
            } else {
              setView('topics');
            }
          } else {
            handleLogout();
          }
        } catch {
          handleLogout();
        }
      } else {
        setView('landing');
      }
      setIsBooting(false);
    };

    fetchUser();
  }, [token]);

  const handleLogin = (newToken, newUser) => {
    localStorage.setItem('news_token', newToken);
    setToken(newToken);
    setUser(newUser);
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
    setView('landing');
  };

  const handleTopicsSaved = (updatedUser) => {
    setUser(updatedUser);
    setView('app');
  };

  const renderView = () => {
    if (isBooting) {
      return <div className="loading-screen">Loading your newsroom...</div>;
    }

    if (!token || !user) {
      if (view === 'auth') {
        return <AuthForm onLoginSuccess={handleLogin} onBackToLanding={() => setView('landing')} />;
      }

      return <LandingPage onGetStartedClick={() => setView('auth')} />;
    }

    if (view === 'topics') {
      return (
        <div className="workspace-shell">
          <header className="workspace-topbar">
            <div>
              <p className="eyebrow">Newsroom</p>
              <h1>NewsAI Intelligence Desk</h1>
            </div>
            <div className="workspace-user">
              <span>{user.email}</span>
              <button onClick={handleLogout} className="button-secondary">
                Log Out
              </button>
            </div>
          </header>
          <TopicSelection token={token} onTopicsSaved={handleTopicsSaved} />
        </div>
      );
    }

    if (view === 'app') {
      return (
        <div className="workspace-shell">
          <header className="workspace-topbar">
            <div>
              <p className="eyebrow">Newsroom</p>
              <h1>NewsAI Intelligence Desk</h1>
            </div>
            <div className="workspace-user">
              <span>{user.email}</span>
              <button onClick={handleLogout} className="button-secondary">
                Log Out
              </button>
            </div>
          </header>
          <NewsFeed token={token} user={user} onUserUpdate={setUser} />
        </div>
      );
    }

    return <LandingPage onGetStartedClick={() => setView('auth')} />;
  };

  return <>{renderView()}</>;
}

export default App;



