"""Timing utilities for pymcpevals."""

import time
from collections.abc import Generator
from contextlib import contextmanager


class Timer:
    """Simple timer for measuring execution time."""

    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def start(self) -> None:
        """Start the timer."""
        self.start_time = time.perf_counter()

    def stop(self) -> None:
        """Stop the timer."""
        self.end_time = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (self.end_time - self.start_time) * 1000.0

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return self.end_time - self.start_time


@contextmanager
def measure_time() -> Generator[Timer, None, None]:
    """
    Context manager for measuring execution time.

    Usage:
        with measure_time() as timer:
            # do work
            pass
        print(f"Took {timer.elapsed_ms:.2f}ms")

    Returns:
        Timer object with elapsed_ms and elapsed_seconds properties
    """
    timer = Timer()
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()
