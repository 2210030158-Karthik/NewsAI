import React from 'react';

// This is the simple, stable landing page (reverted version).
// It only takes one prop: a function to call when the "Get Started" button is clicked.
export function LandingPage({ onGetStartedClick }) {
  return (
    <div className="hero-container">
      <h1 className="hero-title">
        Tired of clickbait?
        <br />
        Get your news, <span className="hero-highlight">intelligently.</span>
      </h1>
      <p className="hero-subtitle">
        NewsAI cuts through the noise. We use AI to classify, summarize, and
        deliver a news feed that's 100% personalized to your interests.
        No clutter, just clarity.
      </p>
      <button className="button-primary hero-button" onClick={onGetStartedClick}>
        Get Started — It's Free
      </button>
    </div>
  );
}

