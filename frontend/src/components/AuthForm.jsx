import React, { useState } from 'react';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8011' : '/_/backend');

export function AuthForm({ onLoginSuccess, onBackToLanding }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const isLogin = mode === 'login';

  const loginAndHydrateUser = async (identityEmail, identityPassword) => {
    const formData = new URLSearchParams();
    formData.append('username', identityEmail);
    formData.append('password', identityPassword);

    const loginResponse = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    if (!loginResponse.ok) {
      const errData = await loginResponse.json();
      throw new Error(errData.detail || 'Login failed.');
    }

    const loginData = await loginResponse.json();
    const userResponse = await fetch(`${API_BASE_URL}/users/me`, {
      headers: { Authorization: `Bearer ${loginData.access_token}` },
    });

    if (!userResponse.ok) {
      throw new Error('Could not load user profile.');
    }

    const userData = await userResponse.json();
    onLoginSuccess(loginData.access_token, userData);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      if (!isLogin) {
        const signupResponse = await fetch(`${API_BASE_URL}/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });

        if (!signupResponse.ok) {
          const errData = await signupResponse.json();
          throw new Error(errData.detail || 'Signup failed.');
        }
      }

      await loginAndHydrateUser(email, password);
    } catch (submitError) {
      setError(submitError.message || 'Something went wrong.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="auth-layout">
      <div className="auth-panel">
        <button className="text-action" onClick={onBackToLanding} type="button">
          Back to landing
        </button>

        <div className="auth-heading-wrap">
          <p className="eyebrow">Personalized News OS</p>
          <h2 className="auth-title">{isLogin ? 'Welcome back' : 'Create your account'}</h2>
          <p className="auth-subtitle">
            {isLogin
              ? 'Sign in to refresh your ranked feed and reports.'
              : 'Start building your own real-time AI-ranked newsroom.'}
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="email-input">
            Email
          </label>
          <input
            id="email-input"
            className="field-input"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <label className="field-label" htmlFor="password-input">
            Password
          </label>
          <input
            id="password-input"
            className="field-input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={6}
            required
          />

          {error && <div className="inline-error">{error}</div>}

          <button className="button-primary" type="submit" disabled={isLoading}>
            {isLoading ? 'Please wait...' : isLogin ? 'Log In' : 'Create Account'}
          </button>
        </form>

        <button
          className="text-action subtle"
          type="button"
          onClick={() => {
            setMode(isLogin ? 'signup' : 'login');
            setError('');
          }}
        >
          {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Log in'}
        </button>
      </div>
    </section>
  );
}

