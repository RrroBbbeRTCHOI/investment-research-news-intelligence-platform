import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const moduleFrom = async (name) =>
  import(
    'data:text/javascript;base64,' +
      Buffer.from(
        await readFile(
          new URL('../static/js/' + name, import.meta.url),
          'utf8'
        )
      ).toString('base64')
  );

const {
  adaptIntelligence,
  visibleArticles,
  mapArticles,
  compareArticles,
} = await moduleFrom('news_model.js');

const {
  present,
  relationshipState,
} = await moduleFrom('news_presentation.js');

const raw = JSON.parse(
  await readFile(
    new URL(
      '../data/news/research/stress_test_v1_v316_final_replay.json',
      import.meta.url
    ),
    'utf8'
  )
);

const before = JSON.stringify(raw);

const articles = adaptIntelligence({
  ...raw,
  schema_version: 'news_ui_v3',
  queue: raw.research_queue,
});

const get = (caseId) =>
  articles.find(
    (a) => a.id.includes('_' + caseId + '_')
  );


// ============================================================
// FEED VISIBILITY
// ============================================================

assert.equal(
  visibleArticles(articles).length,
  11
);

assert.equal(
  visibleArticles(articles, 'all').length,
  12
);


// ============================================================
// V3.2.3.1 MAP CONTRACT
//
// Processing through the event-research lane does NOT mean
// the backend confirmed a discrete event.
//
// Only:
//   gate.is_event === true
//   display_type === 'event'
//   supported backend geography
//
// may produce an event globe marker.
// ============================================================

const markers = mapArticles(articles);

assert.ok(
  markers.length > 0,
  'Confirmed events with supported geography remain visible'
);

for (const marker of markers) {

  assert.equal(
    marker.gate.is_event,
    true
  );

  assert.equal(
    marker.display_type,
    'event'
  );

  const source = raw.articles.find(
    (a) => a.article_id === marker.id
  );

  assert.ok(
    source,
    'Every marker must come from the frozen backend record'
  );

  assert.equal(
    source.gate.is_event,
    true
  );

  assert.deepEqual(
    marker.geography,
    source.geography
  );

  assert.equal(
    marker.latitude,
    source.geography.latitude
  );

  assert.equal(
    marker.longitude,
    source.geography.longitude
  );

  assert.ok(
    Number.isFinite(marker.latitude)
      && Number.isFinite(marker.longitude),
    `${marker.id}: event marker must have finite backend coordinates`
  );
}


// ============================================================
// UNCONFIRMED RESEARCH MUST NOT CREATE EVENT MARKERS
// ============================================================

for (const article of articles) {

  if (
    article.gate.is_event === false
    || article.display_type === 'research'
  ) {

    assert.ok(
      !markers.includes(article),
      `${article.id}: unconfirmed research is not an event marker`
    );

    assert.deepEqual(
      mapArticles([article]),
      []
    );
  }

  if (
    article.geography.latitude == null
    || article.geography.longitude == null
  ) {

    assert.ok(
      !markers.includes(article),
      `${article.id}: unresolved geography must not be invented`
    );
  }
}


// ============================================================
// STABLE CONFIRMED MARKER IDENTITIES
//
// This verifies semantics rather than only replacing the old
// raw assertion:
//   mapArticles(articles).length === 6
//
// Under the approved V3.2.3.1 contract, ST01 and ST09 are the
// confirmed frozen records with supported geography that retain
// event markers.
// ============================================================

assert.deepEqual(
  markers
    .map((a) => a.id)
    .sort(),

  ['ST01', 'ST09']
    .map((caseId) => get(caseId).id)
    .sort()
);


// ============================================================
// NOISE CASE MUST NEVER MAP
// ============================================================

assert.ok(
  !mapArticles(articles).includes(
    get('ST12')
  )
);


// ============================================================
// ORDERING / SEVERITY CONTRACT
// ============================================================

assert.deepEqual(
  articles
    .slice(0, 2)
    .map(
      (a) => a.severity.level
    ),

  [
    'High',
    'High',
  ]
);


// ============================================================
// HORMUZ CASES
// ============================================================

for (const c of [
  'ST09',
  'ST10',
]) {

  assert.equal(
    get(c).region,
    'Strait of Hormuz'
  );

  assert.equal(
    get(c).geography.event_country,
    null
  );

  assert.deepEqual(
    get(c).analyses,
    []
  );
}


// ============================================================
// GEOGRAPHY / EVENT CONTRACT
// ============================================================

assert.equal(
  get('ST05').region,
  'Kaohsiung'
);


// ============================================================
// SEVERITY CONTRACT
// ============================================================

assert.equal(
  get('ST01').severity.level,
  'Unknown'
);

assert.equal(
  get('ST03').severity.level,
  'Medium'
);


// ============================================================
// TICKER RELATIONSHIP CONTRACT
// ============================================================

assert.equal(
  relationshipState(
    get('ST03').analyses[0]
  ),
  'qualified'
);

const aws = get('ST07');

const amzn = aws.analyses.find(
  (t) => t.ticker === 'AMZN'
);

const aapl = aws.analyses.find(
  (t) => t.ticker === 'AAPL'
);

assert.equal(
  relationshipState(amzn),
  'qualified'
);

assert.equal(
  relationshipState(aapl),
  'review'
);


// ============================================================
// PRESENTATION CONTRACT
// ============================================================

assert.equal(
  present(
    aws,
    amzn
  ).classification,
  'Outage'
);

assert.ok(
  !present(
    aws,
    amzn
  ).why.includes(
    'no qualified relationship established'
  )
);

assert.equal(
  relationshipState(
    get('ST08').analyses[0]
  ),
  'qualified'
);

assert.equal(
  get('ST11').severity.level,
  'Low'
);


// ============================================================
// MINIMAL / NULL-SAFE RECORD
// ============================================================

const minimal = {
  article_id:
    'minimal',

  headline:
    'Company announcement',

  ticker_analysis:
    [],

  gate: {
    is_event:
      false,
  },

  feed: {
    state:
      'surface',
  },

  event: {
    latitude:
      1,

    longitude:
      2,
  },

  geography: {
    latitude:
      null,

    longitude:
      null,
  },
};

const missing = adaptIntelligence({
  schema_version:
    'news_ui_v3',

  queue:
    [],

  articles: [
    minimal,
  ],
})[0];

assert.equal(
  missing.region,
  'Unknown'
);

assert.equal(
  missing.latitude,
  null
);

assert.deepEqual(
  mapArticles([
    missing,
  ]),
  []
);


// ============================================================
// PRESENTATION NULL HANDLING
// ============================================================

assert.equal(
  present(
    missing
  ).impact,
  'Unknown'
);

assert.deepEqual(
  present(
    missing
  ).gaps,
  []
);

assert.deepEqual(
  present(
    missing
  ).reasons,
  []
);

assert.deepEqual(
  present(
    missing,
    {
      next_questions: [
        'Backend question',
      ],

      economic_channels:
        null,
    }
  ).gaps,

  [
    'Backend question',
  ]
);


// ============================================================
// REVIEW STATE
// ============================================================

assert.equal(
  relationshipState({
    qualification:
      'candidate_requires_review',

    relationship_type:
      'direct_company_subject',
  }),
  'review'
);


// ============================================================
// STABLE ARTICLE ORDERING
// ============================================================

assert.ok(
  compareArticles(
    {
      ...missing,
      id:
        'a',
    },

    {
      ...missing,
      id:
        'b',
    }
  ) < 0
);


// ============================================================
// FROZEN INPUT IMMUTABILITY
// ============================================================

assert.equal(
  JSON.stringify(raw),
  before
);


console.log(
  'PASS V3.1.6 frozen UI contracts: surface, confirmed-event markers, ordering, final fields, review, nulls and immutability.'
);