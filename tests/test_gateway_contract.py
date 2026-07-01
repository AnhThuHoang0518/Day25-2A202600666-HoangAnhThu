"""Gateway contract tests — verify the gateway interface works end-to-end.

These tests require CircuitBreaker and ResponseCache to be implemented first.
"""
from reliability_lab.cache import ResponseCache
from reliability_lab.circuit_breaker import CircuitBreaker
from reliability_lab.gateway import ReliabilityGateway
from reliability_lab.providers import FakeLLMProvider


def test_gateway_returns_response_with_route_reason() -> None:
    provider = FakeLLMProvider("primary", fail_rate=0.0, base_latency_ms=1, cost_per_1k_tokens=0.001)
    breaker = CircuitBreaker("primary", failure_threshold=2, reset_timeout_seconds=1)
    gateway = ReliabilityGateway([provider], {"primary": breaker}, ResponseCache(60, 0.5))
    result = gateway.complete("hello world")
    assert result.text
    assert result.route in {"primary", "fallback", "static_fallback", "cache_hit:1.00"}


def test_gateway_falls_back_when_primary_fails() -> None:
    primary = FakeLLMProvider("primary", fail_rate=1.0, base_latency_ms=1, cost_per_1k_tokens=0.01)
    backup = FakeLLMProvider("backup", fail_rate=0.0, base_latency_ms=1, cost_per_1k_tokens=0.005)
    breakers = {
        "primary": CircuitBreaker("primary", failure_threshold=1, reset_timeout_seconds=10),
        "backup": CircuitBreaker("backup", failure_threshold=3, reset_timeout_seconds=10),
    }
    gateway = ReliabilityGateway([primary, backup], breakers)
    result = gateway.complete("test query")
    assert result.provider == "backup"
    assert result.route == "fallback"


def test_gateway_returns_static_fallback_when_all_fail() -> None:
    primary = FakeLLMProvider("primary", fail_rate=1.0, base_latency_ms=1, cost_per_1k_tokens=0.01)
    backup = FakeLLMProvider("backup", fail_rate=1.0, base_latency_ms=1, cost_per_1k_tokens=0.005)
    breakers = {
        "primary": CircuitBreaker("primary", failure_threshold=1, reset_timeout_seconds=10),
        "backup": CircuitBreaker("backup", failure_threshold=1, reset_timeout_seconds=10),
    }
    gateway = ReliabilityGateway([primary, backup], breakers)
    result = gateway.complete("test query")
    assert result.route == "static_fallback"
    assert result.error is not None


def test_gateway_uses_cache() -> None:
    provider = FakeLLMProvider("primary", fail_rate=0.0, base_latency_ms=1, cost_per_1k_tokens=0.001)
    breaker = CircuitBreaker("primary", failure_threshold=3, reset_timeout_seconds=1)
    cache = ResponseCache(60, 0.5)
    gateway = ReliabilityGateway([provider], {"primary": breaker}, cache)
    gateway.complete("cached query")
    result = gateway.complete("cached query")
    assert result.cache_hit
