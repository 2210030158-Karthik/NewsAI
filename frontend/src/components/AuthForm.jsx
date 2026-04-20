import React, { useState } from 'react';

const API_BASE_URL = 'http://127.0.0.1:8000';

// 1. Add the new 'onBack' prop
export function AuthForm({ onLoginSuccess, onBack }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    if (isLogin) {
      // --- Handle Login ---
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);
      try {
        const response = await fetch(`${API_BASE_URL}/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData,
        });
        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || 'Failed to log in');
        }
        const data = await response.json();
        const userResponse = await fetch(`${API_BASE_URL}/users/me`, {
          headers: { 'Authorization': `Bearer ${data.access_token}` },
        });
        const userData = await userResponse.json();
        onLoginSuccess(data.access_token, userData);
      } catch (err) {
        setError(err.message);
      }
    } else {
      // --- Handle Sign Up ---
      try {
        const response = await fetch(`${API_BASE_URL}/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || 'Failed to sign up');
        }
        // Auto-login after signup
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);
        const loginResponse = await fetch(`${API_BASE_URL}/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData,
        });
        const loginData = await loginResponse.json();
        const userResponse = await fetch(`${API_BASE_URL}/users/me`, {
          headers: { 'Authorization': `Bearer ${loginData.access_token}` },
        });
        const userData = await userResponse.json();
        onLoginSuccess(loginData.access_token, userData);
      } catch (err) {
        setError(err.message);
      }
    }
    setIsLoading(false);
  };

  return (
    <div className="card">
      {/* 2. Add the "Back" button */}
      <button onClick={onBack} className="back-link">
        &larr; Back to Home
      </button>

      <h2 style={{ textAlign: 'center', marginBottom: '2rem' }}>
        {isLogin ? 'Log In' : 'Sign Up'}
      </h2>
      <form onSubmit={handleSubmit} className="form-container">
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            className="form-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            className="form-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            required
          />
        </div>

        {error && <p style={{ color: '#ef4444' }}>{error}</p>}

        <button type="submit" className="button-primary" disabled={isLoading}>
          {isLoading ? 'Loading...' : (isLogin ? 'Log In' : 'Sign Up')}
        </button>
      </form>
      <button
        onClick={() => {
          setIsLogin(!isLogin);
          setError('');
        }}
        style={{
          background: 'none',
          border: 'none',
          color: '#3b82f6',
          cursor: 'pointer',
          marginTop: '1.5rem',
          width: '100%',
          textAlign: 'center'
        }}
      >
        {isLogin
          ? "Don't have an account? Sign Up"
          : 'Already have an account? Log In'}
      </button>
    </div>
  );
}

