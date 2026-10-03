"""Optional archived OOS context. Never trains, ranks, or qualifies a ticker."""
import csv
import hashlib
import json
import math
from pathlib import Path
from .exposure_matcher import parse_time

DISCLOSURE = ('Experimental historical association only. Not directional or causal. '
              'Retrospective OOS results may use historical backfill; not a live prediction.')
MODELS = ('B0', 'B1', 'B2a', 'B2b', 'B2')
THRESHOLDS = (.02, .03, .04)


def unavailable(reason='No explicit historical case binding supplied.'):
    return dict(status='unavailable', probability=None, predictions=[], reason=reason,
                disclosure=DISCLOSURE, used_for_relevance=False, used_for_priority=False)


def load_archive(root, mapping_path=None, artifact_dir=None):
    """Read existing artifacts once. Bad optional context cannot block relevance."""
    if mapping_path is None:
        return dict(status='unavailable', reason='No explicit article-to-case mapping supplied.')
    try:
        root = Path(root)
        folder = Path(artifact_dir) if artifact_dir else root/'data/news/ml'
        mapping = json.loads(Path(mapping_path).read_text())['article_to_case']
        if not isinstance(mapping, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                or not k or not v for k, v in mapping.items()):
            raise ValueError('Invalid article_to_case mapping')
        manifest = json.loads((folder/'material_reaction_run_manifest_v1.json').read_text())
        name = manifest['input_name']
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError('Invalid historical input name')
        source = root/'data/news/market_reaction'/name
        if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['input_sha256']:
            raise ValueError('Historical source hash mismatch')
        if parse_time(manifest['run_at']) is None:
            raise ValueError('Missing historical run timestamp')
        with source.open(newline='') as f:
            source_rows = list(csv.DictReader(f))
        identities = [(r['case_id'], r['ticker']) for r in source_rows]
        if len(identities) != len(set(identities)):
            raise ValueError('Duplicate historical source identity')
        with (folder/'material_reaction_sensitivity_predictions_v1.csv').open(newline='') as f:
            predictions = list(csv.DictReader(f))
        keys = [(r['case_id'], r['ticker'], float(r['threshold'])) for r in predictions]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate archived prediction identity')
        return dict(status='loaded', mapping=mapping, source=dict(zip(identities, source_rows)),
                    predictions=predictions, manifest=manifest)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return dict(status='unavailable', reason=f'Archived context not usable: {exc}')


def context_for(archive, article, event, ticker):
    if not archive or archive.get('status') != 'loaded':
        return unavailable((archive or {}).get('reason', 'No archived context supplied.'))
    case = archive['mapping'].get(article['article_id'])
    if not case:
        return unavailable('Article has no explicit archived case binding.')
    try:
        source = archive['source'][(case, ticker)]
        if source['ml_eligible'].lower() not in ('true', '1'):
            raise ValueError('Historical row is not ML eligible')
        if source.get('event_engine_status', '').startswith('rejected'):
            raise ValueError('Historical event was rejected')
        for key in ('event_type', 'event_subtype'):
            if source[key] != event[key]:
                raise ValueError(f'Historical {key} does not match this event')
        published = parse_time(article.get('published_at'))
        if published is None or published.date().isoformat() != source['event_date_reported']:
            raise ValueError('Historical article date mismatch or unavailable')
        if source.get('event_time_utc') and parse_time(source['event_time_utc']) != published:
            raise ValueError('Historical article timestamp mismatch')
        rows = [r for r in archive['predictions'] if (r['case_id'], r['ticker']) == (case, ticker)]
        if {float(r['threshold']) for r in rows} != set(THRESHOLDS):
            raise ValueError('Complete existing threshold predictions unavailable')
        predictions = []
        for r in rows:
            for key in ('event_type', 'event_subtype', 'relationship_type', 'effective_event_date'):
                if r[key] != source[key]:
                    raise ValueError(f'Archived prediction {key} mismatch')
            threshold = float(r['threshold'])
            if int(r['target']) != int(abs(float(source['qqq_relative_3d'])) > threshold):
                raise ValueError('Archived target disagrees with source')
            if int(r['n_train']) < int(archive['manifest'].get('min_train', 1)):
                raise ValueError('Archived training sample below recorded minimum')
            t0 = parse_time(r['prediction_t0'])
            end = parse_time(r['train_label_end_max'], end_of_day=True)
            if not t0 or not end or end >= t0 or t0 > parse_time(source['t0_session']):
                raise ValueError('Archived label maturation invalid')
            train_cases = set(r['train_case_ids'].split('|'))
            if not train_cases or case in train_cases:
                raise ValueError('Invalid historical train membership')
            training = [s for (c, _), s in archive['source'].items()
                        if c in train_cases and s['ml_eligible'].lower() in ('true', '1')]
            if {s['case_id'] for s in training} != train_cases or len(training) != int(r['n_train']):
                raise ValueError('Historical train membership inconsistent')
            if any(parse_time(s['t3_session'], end_of_day=True) >= t0 for s in training):
                raise ValueError('Historical training label was not mature')
            for model in MODELS:
                probability = float(r[f'p_{model.lower()}'])
                if not math.isfinite(probability) or not 0 <= probability <= 1:
                    raise ValueError('Invalid archived probability')
                predictions.append(dict(model=model, threshold=threshold, horizon_trading_days=3,
                                        probability=probability, fold=int(r['fold']), n_train=int(r['n_train'])))
        result = unavailable()
        result.update(status='retrospective_oos_diagnostic', reason=None, predictions=predictions,
                      provenance=dict(case_id=case, ticker=ticker, input_sha256=archive['manifest']['input_sha256'],
                                      run_at=archive['manifest']['run_at'],
                                      available_at_event_time=parse_time(archive['manifest']['run_at']) <= published,
                                      prediction_artifact_independently_reproduced=False),
                      limitation='No stable incremental B2b predictive value has been established.')
        return result
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return unavailable(f'Historical binding rejected: {exc}')
