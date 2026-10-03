import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone
from src.news.market_snapshot import refresh_markets,read_market_snapshot
from src.news.live_config import LiveConfig

class MarketTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.c=LiveConfig(state_dir=Path(self.tmp.name),market_enabled=True)
        self.calls=0
    def quote(self,s,c):
        self.calls+=1
        return {'symbol':s,'currency':c,'value':100,'change':2,'change_percent':2.04,'timestamp':'2026-09-27T00:00:00+00:00'}
    def test_read_does_not_refetch(self):
        refresh_markets(self.c,self.quote);calls=self.calls
        for _ in range(3):
            p=read_market_snapshot('.',self.c,datetime(2026,9,27,tzinfo=timezone.utc))
            self.assertEqual(p['quotes']['NVDA']['value'],100)
        self.assertEqual(self.calls,calls)
    def test_stale_and_failure_preserve_value(self):
        refresh_markets(self.c,self.quote)
        def fail(*args): raise RuntimeError()
        refresh_markets(self.c,fail)
        p=read_market_snapshot('.',self.c)
        self.assertEqual(p['quotes']['NVDA']['value'],100);self.assertEqual(p['quotes']['NVDA']['status'],'stale')
    def test_unavailable(self):
        p=read_market_snapshot('.',self.c);self.assertEqual(p['status'],'unavailable')
        self.assertTrue(all(m['value'] is None for m in p['markets']))
    def test_disabled_no_calls(self):
        self.c.market_enabled=False;refresh_markets(self.c,self.quote);self.assertEqual(self.calls,0)
