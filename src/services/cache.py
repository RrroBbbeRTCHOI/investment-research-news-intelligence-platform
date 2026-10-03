"""Process-local 300-second shared service results, with bounded storage."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
import time
from src.data.reuse import state

_results = OrderedDict()
_lock = RLock()
_loads = [RLock() for _ in range(32)]
TTL = 300
MAX_ENTRIES = 128


def clear():
    with _lock:
        _results.clear()


def cached(key, loader, acceptable=lambda value: True):
    current = state()
    if current is None or not current["persistent"]:
        return loader()
    # Same-key loads coalesce without holding the global store lock across I/O.
    with _loads[hash(key) % len(_loads)]:
        now = time.time()
        with _lock:
            item = _results.get(key)
            if item is not None and 0 <= now - item[0] < TTL:
                current["oldest"] = min(current["oldest"], item[0])
                _results.move_to_end(key)
                return deepcopy(item[1])
            _results.pop(key, None)
        value = loader()
        if acceptable(value):
            timestamp = current["oldest"]
            with _lock:
                _results[key] = (timestamp, deepcopy(value))
                while len(_results) > MAX_ENTRIES:
                    _results.popitem(last=False)
        return value
