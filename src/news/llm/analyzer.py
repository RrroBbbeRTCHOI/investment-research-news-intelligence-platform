"""Model-specific success cache and at most three transient-error attempts/article."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from .base import ProviderError, content, PROMPT, PROMPT_VERSION
from .schemas import VERSION, validate, SchemaError

TRANSIENT = {'http_429', 'http_500', 'http_502', 'http_503', 'http_504'}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.pending_')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Analyzer:
    def __init__(self, config, provider=None):
        self.config = config
        self.calls = 0  # Actual provider requests, including retries; never a sentinel.
        self.processed = 0
        self.blocked = False
        self.memo = {}
        self.provider = provider or self._provider(config)

    @staticmethod
    def _provider(config):
        if config.provider == 'gemini':
            from .gemini_provider import GeminiProvider
            return GeminiProvider(config)
        if config.provider == 'openai':
            from .openai_provider import OpenAIProvider
            return OpenAIProvider(config)
        return None

    def _digest(self, article, model):
        identity = [content(article), PROMPT, PROMPT_VERSION, VERSION, self.config.provider, model]
        return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()

    def _cached(self, article, model):
        digest = self._digest(article, model)
        if digest in self.memo:
            result = self.memo[digest]
            return {**result, 'cache_hit': result['status'] == 'available'}
        if self.config.reprocess:
            return None
        try:
            result = json.loads((self.config.cache_dir / (digest + '.json')).read_text())
            validate(result['semantic'])
            if (result.get('status') == 'available' and result.get('content_hash') == digest
                    and result.get('schema_version') == VERSION
                    and result.get('prompt_version') == PROMPT_VERSION
                    and result.get('provider') == self.config.provider and result.get('model') == model):
                self.memo[digest] = result
                return {**result, 'cache_hit': True}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def analyze_article(self, article):
        c = self.config
        attempts = []
        model = c.model
        digest = self._digest(article, model)
        fallback = c.fallback_model if c.provider == 'gemini' and c.fallback_model != c.model else ''

        def unavailable(reason):
            return dict(status='unavailable', reason=reason, provider=c.provider,
                        model=model, requested_model=c.model, schema_version=VERSION,
                        prompt_version=PROMPT_VERSION, semantic=None, cache_hit=False,
                        attempts=list(attempts), attempt_count=len(attempts),
                        retry_count=max(0, len(attempts)-1), fallback_used=model != c.model)

        def cached_result():
            primary = self._cached(article, c.model)
            if primary is not None:
                return primary
            alternate = self._cached(article, fallback) if fallback else None
            # Reuse a fallback only if it previously succeeded after this primary's
            # transient failure; unrelated model cache is not a silent fallback.
            if alternate and alternate.get('status') == 'available' and alternate.get('requested_model') == c.model and alternate.get('fallback_used'):
                return alternate
            return None

        if c.provider == 'none':
            return unavailable('provider_disabled')
        cached = cached_result()
        if cached is not None:
            return cached
        if not c.api_key:
            return unavailable('missing_api_key')
        if not c.model:
            return unavailable('missing_model')
        if self.blocked or self.processed >= c.max_articles:
            return unavailable('run_limit')
        path = c.cache_dir / (digest + '.json')
        locks = []
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            lock = path.with_suffix('.lock')
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            locks.append(lock)
        except FileExistsError:
            return unavailable('processing_lock_exists')
        except OSError:
            return unavailable('cache_not_writable')
        try:
            cached = cached_result()
            if cached is not None:
                return cached
            self.processed += 1
            provider = self.provider
            for index in range(3):
                if index:
                    time.sleep((2, 5)[index-1])
                if index == 2 and fallback:
                    model = fallback
                    provider = self._provider(replace(c, model=model))
                    digest = self._digest(article, model)
                    path = c.cache_dir / (digest + '.json')
                    # A separate fallback-model lock prevents overlapping callers.
                    lock = path.with_suffix('.lock')
                    try:
                        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        os.close(fd)
                        locks.append(lock)
                    except FileExistsError:
                        return unavailable('processing_lock_exists')
                    cached = self._cached(article, model)
                    if cached and cached.get('status') == 'available':
                        return {**cached, 'requested_model': c.model, 'fallback_used': True,
                                'attempts_this_access': attempts}
                self.calls += 1
                attempt = {'attempt': index+1, 'provider': c.provider, 'model': model}
                attempts.append(attempt)
                try:
                    semantic, usage = provider.generate(article)
                    validate(semantic)
                    attempt['status'] = 'success'
                    break
                except (ProviderError, SchemaError, ValueError, KeyError, TypeError) as exc:
                    reason = str(exc) if isinstance(exc, ProviderError) else 'invalid_schema'
                    attempt.update(status='failed', reason=reason)
                    if reason in TRANSIENT and index < 2:
                        continue
                    result = unavailable(reason)
                    self.memo[self._digest(article, c.model)] = result
                    if reason in ('http_429', 'http_401', 'http_403'):
                        self.blocked = True
                    return result
            usage = usage if isinstance(usage, dict) else {}
            accounting = {k: v if type(v) is int and v >= 0 else None
                          for k, v in ((k, usage.get(k)) for k in ('input_tokens', 'output_tokens', 'total_tokens'))}
            cost = None
            # Primary pricing cannot silently price another model's response.
            if model == c.model and c.input_price is not None and c.output_price is not None and all(accounting[k] is not None for k in ('input_tokens', 'output_tokens')):
                cost = (accounting['input_tokens']*c.input_price + accounting['output_tokens']*c.output_price)/1e6
            record = dict(status='available', schema_version=VERSION, prompt_version=PROMPT_VERSION,
                          provider=c.provider, model=model, requested_model=c.model,
                          content_hash=digest, article_content_hash=hashlib.sha256(content(article).encode()).hexdigest(),
                          generated_at=datetime.now(timezone.utc).isoformat(), semantic=semantic,
                          usage={**accounting, 'estimated_cost_usd':cost, 'scope':'successful response only; failed-attempt usage unavailable'},
                          cache_hit=False, attempts=attempts, attempt_audit_scope='original enrichment generation; cache reuse makes no new requests', attempt_count=len(attempts),
                          retry_count=len(attempts)-1, fallback_used=model != c.model)
            atomic_json(path, record)
            self.memo[digest] = record
            return record
        except OSError:
            return unavailable('cache_write_failed')
        finally:
            for lock in locks:
                lock.unlink(missing_ok=True)
