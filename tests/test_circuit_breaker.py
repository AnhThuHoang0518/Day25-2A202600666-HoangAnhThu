"""Circuit breaker tests — all must pass when your implementation is correct.

These tests verify the 3-state machine: CLOSED → OPEN → HALF_OPEN → CLOSED.
"""
import time

import pytest

from reliability_lab.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


def test_starts_closed() -> None:
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout_seconds=1)
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request()


def test_opens_after_failure_threshold() -> None:
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout_seconds=1)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert not cb.allow_request()


def test_does_not_open_below_threshold() -> None:
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout_seconds=1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED


def test_success_resets_failure_count() -> None:
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout_seconds=1)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.failure_count == 0
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED


def test_open_transitions_to_half_open_after_timeout() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=0.1)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(0.15)
    assert cb.allow_request()
    assert cb.state == CircuitState.HALF_OPEN


def test_half_open_closes_on_success() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=0.1)
    cb.record_failure()
    time.sleep(0.15)
    cb.allow_request()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_half_open_reopens_on_failure() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=0.1)
    cb.record_failure()
    time.sleep(0.15)
    cb.allow_request()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_call_raises_circuit_open_error() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=10)
    cb.record_failure()
    with pytest.raises(CircuitOpenError):
        cb.call(lambda: "hello")


def test_call_records_success_and_failure() -> None:
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout_seconds=1)
    result = cb.call(lambda: "ok")
    assert result == "ok"
    assert cb.success_count == 1

    def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        cb.call(fail)
    assert cb.failure_count == 1


def test_transition_log_records_state_changes() -> None:
    cb = CircuitBreaker("test", failure_threshold=2, reset_timeout_seconds=0.1)
    cb.record_failure()
    cb.record_failure()
    assert len(cb.transition_log) == 1
    assert cb.transition_log[0]["from"] == "closed"
    assert cb.transition_log[0]["to"] == "open"
    assert cb.transition_log[0]["reason"] == "failure_threshold_reached"


def test_no_duplicate_transitions() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=10)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    open_transitions = [t for t in cb.transition_log if t["to"] == "open"]
    assert len(open_transitions) == 1


def test_success_threshold_greater_than_one() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_seconds=0.05, success_threshold=2)
    cb.record_failure()
    time.sleep(0.1)
    cb.allow_request()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
