"""Bounded request-local reuse; no provider data survives a request."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import time

_state = ContextVar("research_data_scope", default=None)


@contextmanager
def data_scope(persistent=False):
    if _state.get() is not None:
        yield _state.get()
        return
    state = {"values": {}, "persistent": persistent, "oldest": time.time()}
    token = _state.set(state)
    try:
        yield state
    finally:
        _state.reset(token)


def state():
    return _state.get()


def reuse(key, loader):
    current = state()
    if current is None:
        return loader()
    if key not in current["values"]:
        value = (
            loader()
        )  # Exceptions are not cached: preserve caller-specific handling.
        if value is None:
            return None
        current["values"][key] = deepcopy(value)
    return deepcopy(current["values"][key])


def scoped(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with data_scope():
            return function(*args, **kwargs)

    return wrapped


def memoized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        key = (
            function.__module__,
            function.__name__,
            args,
            tuple(sorted(kwargs.items())),
        )
        return reuse(key, lambda: function(*args, **kwargs))

    return wrapped
