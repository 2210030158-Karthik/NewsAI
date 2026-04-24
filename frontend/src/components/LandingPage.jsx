import React from 'react';

export function LandingPage({ onGetStartedClick }) {
  const highlights = [
    {
      title: 'Signal-first ranking',
      text: 'Each story is re-ranked using your likes, dislikes, and topic profile in real time.',
    },
    {
      title: 'Deep article extraction',
      text: 'Get full text and context, not just thin headlines and snippets.',
    },
    {
      title: 'Personal daily briefings',
      text: 'Generate concise intelligence reports from your own reading behavior.',
    },
  ];

  return (
    <main className="landing-shell">
      <section className="landing-hero reveal-1">
        <p className="eyebrow">Personalized News Intelligence</p>
        <h1 className="landing-title">
          A newsroom that learns what matters to <span>you</span>.
        </h1>
        <p className="landing-subtitle">
          Break away from generic feeds. Track stories that fit your interests, react with one click,
          and let the ranking engine adapt continuously.
        </p>
        <div className="landing-actions">
          <button className="button-primary" onClick={onGetStartedClick}>
            Enter Your Newsroom
          </button>
          <div className="micro-copy">No credit card. Just your signal, your feed.</div>
        </div>
      </section>

      <section className="landing-grid reveal-2">
        {highlights.map((item) => (
          <article className="landing-feature-card" key={item.title}>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

