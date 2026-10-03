"""News-only UI contracts, local assets and byte-level Research preservation."""
import hashlib
import json
import re
import shutil
import subprocess
import unittest
from bs4 import BeautifulSoup
from support import Replay, ROOT


class NewsUITests(unittest.TestCase):
    def test_analytical_sources_unchanged(self):
        # The Meridian migration intentionally changes routing adapters and
        # presentation files. Analytical models, providers, assumptions and
        # frozen fixtures remain protected by their original hashes.
        integration_files = {
            'app.py',
            'templates/research.html',
            'templates/financial_interpretation.html',
            'templates/valuation_interpretation.html',
            'src/ui/research_context.py',
            'src/ui/adapters.py',
            'src/services/company_service.py',
            'src/services/sec_filing_service.py',
            'src/services/historical_trends_service.py',  # cache wrapper; loader body separately locked
            'src/services/earnings_quality_service.py',  # authorized Revenue Resilience V1.4 integration
        }
        for path, checksum in json.loads((ROOT/'tests/news_legacy_hashes.json').read_text()).items():
            # Provider caches are mutable runtime artifacts and the supplied
            # archive already contains newer AAPL snapshots than this legacy
            # manifest. Protect code and frozen fixtures, not live caches.
            if path in integration_files or path.startswith('data/cache/'):
                continue
            with self.subTest(path=path):
                content = (ROOT/path).read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(), checksum)

    def test_meridian_navigation_and_required_research_sections(self):
        source=(ROOT/'templates/research.html').read_text() + '\n'.join(p.read_text() for p in (ROOT/'templates/research').glob('*.html'))
        for tab in ('overview','financials','valuation','historical-trends',
                    'earnings-quality','financial-health','sec-filing','relevant-events'):
            self.assertIn(tab,source)
        news=BeautifulSoup((ROOT/'templates/news.html').read_text(),'html.parser')
        self.assertIsNotNone(news.select_one('#theme-toggle'))
        self.assertIsNotNone(news.select_one('.right-panel > .bloomberg-live'))
        js=(ROOT/'static/js/news_ui.js').read_text()
        for heading in ('WHAT HAPPENED','EVENT SEVERITY','COMPANY RELATIONSHIP / MATCH',
                        'WHY IT MATTERS','EXPOSURE PATH','EVIDENCE ASSESSMENT','DEEP RESEARCH'):
            self.assertIn(heading,js)

    def test_news_route_and_panel_containment(self):
        with Replay() as r:
            response=r.app_module.app.test_client().get('/news')
            self.assertEqual(response.status_code,200)
            soup=BeautifulSoup(response.data,'html.parser')
            workspace=soup.select_one('.workspace')
            self.assertEqual([e.get('class')[0] for e in workspace.find_all(recursive=False)],['news-panel','center-panel','right-panel'])
            self.assertIsNotNone(soup.select_one('.right-panel > .bloomberg-live'))
            self.assertIsNotNone(soup.select_one('.center-panel > .time-strip'))
            self.assertIsNotNone(soup.select_one('.center-panel > .market-strip'))
            self.assertIsNone(soup.select_one('.center-panel .bloomberg-live'))
            self.assertEqual(soup.select_one('[aria-current=page]').get('href'),'/news')
            self.assertEqual(r.calls,[])

    def test_all_local_assets_and_geojson_are_served(self):
        with Replay() as r:
            client=r.app_module.app.test_client()
            for path in ['css/news.css','js/news_model.js','js/news_ui.js','js/news_globe.js','vendor/three/three.module.js','vendor/three/three.core.js','vendor/three/OrbitControls.js','vendor/d3.min.js','data/countries.geojson']:
                with self.subTest(path=path):
                    self.assertEqual(client.get('/static/'+path).status_code,200)
            data=json.loads(client.get('/static/data/countries.geojson').data)
            self.assertEqual(data['type'],'FeatureCollection')
            self.assertEqual(len(data['features']),177)
            for feature in data['features']:
                self.assertIn(feature['geometry']['type'],['Polygon','MultiPolygon'])

    def test_vendored_assets_match_recorded_hashes(self):
        for path, meta in json.loads((ROOT/'static/vendor/manifest.json').read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),meta['sha256'])

    def test_geography_and_render_dependencies_are_local(self):
        template=(ROOT/'templates/news.html').read_text()
        soup=BeautifulSoup(template,'html.parser')
        self.assertFalse(any((script.get('src') or '').startswith('http') for script in soup.select('script[src]')))
        globe=(ROOT/'static/js/news_globe.js').read_text()
        self.assertIn("fetch('/static/data/countries.geojson')",globe)
        self.assertNotIn('raw.githubusercontent.com',globe)
        self.assertNotIn('https://',globe)
        self.assertIn("from 'three'",globe)
        self.assertIn('ResizeObserver',globe)

    def test_external_stream_is_explicit_and_has_persistent_fallback(self):
        soup=BeautifulSoup((ROOT/'templates/news.html').read_text(),'html.parser')
        self.assertIsNotNone(soup.select_one('.bloomberg-live #load-live'))
        self.assertIsNotNone(soup.select_one('.bloomberg-live #video-fallback'))
        self.assertEqual(soup.select_one('.bloomberg-live a')['href'],'https://www.youtube.com/watch?v=QB5BNdBFujE')
        js=(ROOT/'static/js/news_ui.js').read_text()
        self.assertIn('autoplay=0&mute=1',js)
        self.assertIn('https://www.youtube.com/embed/QB5BNdBFujE',js)

    def test_javascript_model_behaviors(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node.js required for standalone JS checks; browser checks still apply')
        result=subprocess.run([node,str(ROOT/'tests/news_model_test.mjs')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_three_timezones_and_accessible_controls(self):
        soup=BeautifulSoup((ROOT/'templates/news.html').read_text(),'html.parser')
        self.assertEqual({n['data-zone'] for n in soup.select('[data-zone]')},{'America/New_York','Europe/London','Asia/Hong_Kong'})
        self.assertIsNotNone(soup.select_one('#collapse-news[aria-controls]'))
        self.assertIsNotNone(soup.select_one('#globe[tabindex="0"]'))
        self.assertIsNotNone(soup.select_one('#analysis[aria-live=polite]'))
