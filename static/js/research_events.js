const root = document.getElementById('relevant-events');

if (root) {
  const ticker = root.dataset.ticker;
  const node = (tag, value, className = '') => {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    return element;
  };
  const safeText = value => typeof value === 'string' && value.trim() ? value : 'Unavailable';
  const label = value => safeText(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
  const matchLabel = analysis => ({
    qualified_direct_company_subject: 'Direct Company Match',
    qualified_direct_event_subject: 'Direct Event Match',
    indirect_exposure_match: 'Indirect Exposure',
    direct_mention: 'Mention Only',
    candidate_requires_review: 'Review Candidate',
  })[analysis?.qualification] || label(analysis?.relationship_type);

  const render = articles => {
    root.replaceChildren();
    const matches = [];
    for (const article of articles) {
      for (const analysis of article.ticker_analysis || []) {
        if (analysis.ticker === ticker) matches.push({ article, analysis });
      }
    }
    if (!matches.length) {
      const empty = node('div', '', 'metric-card');
      empty.append(node('div', 'No backend-qualified events in the current snapshot', 'metric-label'));
      const link = node('a', 'Open the complete News Intelligence workspace →', 'meridian-action');
      link.href = `/news?ticker=${encodeURIComponent(ticker)}`;
      empty.append(link);
      root.append(empty);
      return;
    }
    const grid = node('div', '', 'meridian-event-grid');
    for (const { article, analysis } of matches) {
      const card = node('article', '', 'metric-card meridian-event-card');
      const event = article.event || {};
      const severity = article.severity?.level || 'N/A — Not confirmed event';
      const evidence = analysis.evidence_assessment?.level || analysis.evidence_strength?.relationship_level || 'Unknown';
      const top = node('div', '', 'meridian-event-meta');
      top.append(node('span', severity, 'meridian-severity'), node('span', matchLabel(analysis), 'meridian-match'));
      card.append(top, node('h3', safeText(article.headline)), node('p', `${safeText(article.source)} · ${safeText(event.location_name || event.primary_country)}`, 'meridian-event-source'));
      const timestamp = node('time', safeText(article.published_at), 'meridian-event-source');
      if (typeof article.published_at === 'string') timestamp.dateTime = article.published_at;
      card.append(timestamp, node('p', safeText(analysis.explanation || analysis.relevance?.reason), 'meridian-event-relevance'));
      const dimensions = node('dl', '', 'meridian-dimensions');
      for (const [term, detail] of [['Severity', severity], ['Match', matchLabel(analysis)], ['Evidence', evidence]]) {
        dimensions.append(node('dt', term), node('dd', detail));
      }
      const link = node('a', 'Open in News Intelligence →', 'meridian-action');
      link.href = `/news?ticker=${encodeURIComponent(ticker)}&event=${encodeURIComponent(article.article_id)}`;
      card.append(dimensions, link);
      grid.append(card);
    }
    root.append(grid);
  };

  fetch('/api/news/intelligence', { cache: 'no-store' })
    .then(response => response.ok ? response.json() : Promise.reject(new Error()))
    .then(payload => render(payload.articles || []))
    .catch(() => {
      root.replaceChildren(node('div', 'News Intelligence is temporarily unavailable. Research data is unchanged.', 'metric-card meridian-events-error'));
    });
}
