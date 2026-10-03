"""Synthetic visual QA only; run from project root with PYTHONPATH=tests:. ."""
import json
from pathlib import Path
from news.helpers import article
from src.news.research_v2 import build_research_output_v2
specs=[
 ('unknown','Community exhibition opens in Mexico','The local exhibition opened in Mexico today.'),
 ('medium','Saudi oil export disruption interrupts shipments','Oil shipments were interrupted in Saudi Arabia.'),
 ('nvda','Nvidia CEO discusses AI safety at a conference in Taiwan','Nvidia CEO spoke at a conference in Taiwan about AI safety.'),
 ('aapl','Apple cuts jobs at its operations in Japan','Apple confirmed workforce reduction at its operations in Japan.'),
 ('mention','Market roundup: Apple mentioned at investor forum in India','Apple was mentioned among market topics at an investor forum in India.'),
 ('multi','Apple and Nvidia discuss AI strategy in Australia','Apple and Nvidia discussed their AI strategy at a conference in Australia.')]
items=[article(body,headline=h,article_id='visual_qa_'+key,source='Synthetic Visual QA') for key,h,body in specs]
Path('docs/visual_hierarchy/synthetic_qa_snapshot.json').write_text(json.dumps(build_research_output_v2(items,[]),indent=2))
