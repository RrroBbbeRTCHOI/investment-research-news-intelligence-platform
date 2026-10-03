"""Synthetic evidence fixtures, never production exposure knowledge."""
import json
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile
from src.news.exposure_matcher import REQUIRED_COLUMNS, WORKBOOK_NAME

def article(body='A 6.8 earthquake struck Taiwan and rail services were suspended.', **changes):
    a = dict(article_id='test_article_1',provider='synthetic_test',provider_article_id='uuid_1',
             headline='Taiwan earthquake',summary='',body=body,published_at='2026-09-17T08:00:00Z',
             fetched_at='2026-09-17T09:00:00Z',has_full_text=True)
    a.update(changes)
    return a

def edge(**changes):
    e = dict.fromkeys(REQUIRED_COLUMNS)
    e.update(edge_id='synthetic_edge',ticker='NVDA',country='Taiwan',channel_family='supply_chain',
        channel_subtype='general',role='input_dependency',stage='operating',evidence_status='verified',
        source_url='https://example.invalid/test-only',source_locator='Synthetic test evidence, not real exposure',
        known_at_utc='2026-01-01T00:00:00Z',valid_from='2026-01-01',confidence=0.8)
    e.update(changes)
    return e

def normalized(root: Path, articles):
    p=root/'data/news/normalized/freenewsapi_articles_normalized.json'
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({'_metadata':{'schema':'normalized_article_v2'},'articles':articles}),encoding='utf-8')
    return p

def workbook(root: Path, edges):
    """Tiny valid XLSX fixture using stdlib; no spreadsheet-authoring dependency."""
    p=root/WORKBOOK_NAME
    rows=[list(REQUIRED_COLUMNS)]+[[e.get(k) for k in REQUIRED_COLUMNS] for e in edges]
    xml=[]
    for r,row in enumerate(rows,1):
        cells=[]
        for c,v in enumerate(row):
            letter=chr(65+c)
            if v is not None:
                cells.append(f'<c r="{letter}{r}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>')
        xml.append(f'<row r="{r}">'+''.join(cells)+'</row>')
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel='http://schemas.openxmlformats.org/package/2006/relationships'
    with ZipFile(p,'w') as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels',f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Exposure Edges" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels',f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData>'+''.join(xml)+'</sheetData></worksheet>')
    return p
