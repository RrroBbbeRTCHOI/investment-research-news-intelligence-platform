"""Offline live identity helpers; no enrichment/cache or research semantics."""
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

PRESENTATION = {'www', 'm', 'mobile', 'amp'}
# Cross-host inference is deliberately narrower than full eTLD+1 clustering.
DELIVERY = {'pass', 'news'}
# Only these known suffix boundaries are supported offline; unknowns fail closed.
SUFFIXES = {'com', 'net', 'org', 'edu', 'gov', 'co.uk', 'org.uk', 'com.au', 'co.jp'}
SHARED_HOSTS = {'blogspot.com', 'wordpress.com', 'tumblr.com', 'wixsite.com',
                'weebly.com', 'amazonaws.com', 'azurewebsites.net', 'cloudfront.net',
                'herokuapp.com', 'github.io', 'pages.dev', 'vercel.app', 'netlify.app'}


def canonicalize_live_url(value):
    try:
        u = urlsplit(value or '')
        if u.scheme.lower() not in ('http', 'https') or not u.hostname or u.username or u.password:
            return None
        host = u.hostname.lower().encode('idna').decode('ascii')
        prefix, dot, rest = host.partition('.')
        if prefix in PRESENTATION and dot and '.' in rest:
            host = rest
        port = u.port
        authority = '[' + host + ']' if ':' in host else host
        if port is not None and port != (443 if u.scheme.lower() == 'https' else 80):
            authority += ':' + str(port)
        path = u.path or '/'
        # Only trim an article-like path, not the homepage or arbitrary directories.
        if re.search(r'/(?:news|article|articles)/[^/].*/$', path):
            path = path[:-1]
        query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]
        return urlunsplit((u.scheme.lower(), authority, path, urlencode(query), ''))
    except (ValueError, UnicodeError, AttributeError, TypeError):
        return None


def publisher_anchor(host):
    """Bounded publisher-root anchor, NOT a general public-suffix resolver."""
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    label, dot, parent = host.partition('.')
    candidate = parent if label in DELIVERY and dot else host
    if any(candidate == h or candidate.endswith('.' + h) for h in SHARED_HOSTS):
        return None
    # Require exactly one registrant label before a supported suffix. This refuses
    # arbitrary subdomains, unknown suffixes and listed shared hosts rather than guessing.
    first, dot, suffix = candidate.partition('.')
    if not dot or not first or suffix not in SUFFIXES:
        return None
    return candidate


def cross_subdomain_key(article):
    url = canonicalize_live_url(article.get('article_url'))
    headline = ' '.join(str(article.get('headline') or '').casefold().split())
    if not url or not headline:
        return None
    u = urlsplit(url)
    anchor = publisher_anchor(u.hostname)
    # A root URL is not an article path. Exact path is required; numeric IDs alone
    # are intentionally insufficient in this minimal patch.
    if not anchor or u.path == '/':
        return None
    try:
        timestamp = datetime.fromisoformat(str(article.get('published_at') or '').replace('Z', '+00:00'))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return None
        timestamp = timestamp.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None
    parts = [u.scheme, anchor, u.port, u.path, u.query, headline, timestamp]
    return 'crossurl:' + hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def usable_text(article):
    headline = ' '.join(str(article.get('headline') or '').casefold().split())
    return any(text and text != headline for text in
               (' '.join(str(article.get(k) or '').casefold().split()) for k in ('body', 'summary')))


def rebuild_identity_index(state, identities):
    """Backfill aliases and retire duplicate pending work before any LLM attempt.

    Completed records win over pending. Never merge/delete completed research or
    alter quota usage. Old seen-only aliases remain in place.
    """
    # Old seen-only URL entries can gain presentation aliases without article text.
    for key, aid in list(state['seen'].items()):
        if key.startswith('url:'):
            url = canonicalize_live_url(key[4:])
            if url:
                state['seen'].setdefault('url:' + url, aid)
    index = {}
    for aid, record in state['records'].items():
        for key in identities(record):
            index.setdefault(key, aid)
    retired = 0
    for aid, item in list(state['pending'].items()):
        keys = identities(item['article'])
        existing = next((index[k] for k in keys if k in index), None)
        if existing and existing != aid:
            del state['pending'][aid]
            retired += 1
            # Preserve old provider/content aliases of the retired pending ID.
            for key, target in list(state['seen'].items()):
                if target == aid:
                    state['seen'][key] = existing
            for key in keys:
                index.setdefault(key, existing)
        else:
            for key in keys:
                index.setdefault(key, aid)
    state['seen'].update(index)
    return retired
