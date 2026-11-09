"""Bounded local timing samples. Values are elapsed milliseconds, never content."""
from collections import defaultdict, deque
from contextlib import contextmanager
from math import ceil
from threading import Lock
from time import perf_counter

_samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=256))
_lock = Lock()


def record(stage: str, started: float) -> None:
    elapsed = (perf_counter() - started) * 1000
    with _lock:
        _samples[stage].append(elapsed)


@contextmanager
def measure(stage: str):
    started = perf_counter()
    try:
        yield
    finally:
        record(stage, started)


def snapshot() -> dict:
    with _lock:
        samples = {stage: sorted(values) for stage, values in _samples.items()}
    return {
        stage: {
            "samples": len(values),
            **{f"p{pct}_ms": round(values[ceil(pct * len(values) / 100) - 1], 3)
               for pct in (50, 95, 99)},
        }
        for stage, values in samples.items()
    }
