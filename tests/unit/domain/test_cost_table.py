"""Unit tests for LLM cost estimation table (G-15)."""

from __future__ import annotations

import pytest

from yagra.domain.entities.cost_table import (
    LLM_PRICING_TABLE,
    ModelPricing,
    estimate_cost,
)


class TestModelPricing:
    def test_basic_cost_calculation(self) -> None:
        pricing = ModelPricing(input_per_1k=0.001, output_per_1k=0.002)
        cost = pricing.estimate_cost(1000, 500)
        assert cost == pytest.approx(0.001 + 0.001)  # 1.0 + 0.5 * 0.002

    def test_zero_tokens(self) -> None:
        pricing = ModelPricing(input_per_1k=0.001, output_per_1k=0.002)
        assert pricing.estimate_cost(0, 0) == pytest.approx(0.0)

    def test_rounds_to_8_decimal_places(self) -> None:
        pricing = ModelPricing(input_per_1k=0.00015, output_per_1k=0.00060)
        cost = pricing.estimate_cost(45, 12)
        # 45 * 0.00015 / 1000 + 12 * 0.00060 / 1000 = 0.00000675 + 0.0000072 = 0.00001395
        assert cost == pytest.approx(0.00001395, abs=1e-10)


class TestEstimateCost:
    def test_known_model(self) -> None:
        cost = estimate_cost("openai/gpt-4o-mini", 1000, 500)
        assert cost is not None
        assert cost > 0

    def test_unknown_model_returns_none(self) -> None:
        cost = estimate_cost("unknown/model-xyz", 1000, 500)
        assert cost is None

    def test_all_table_entries_return_positive_cost(self) -> None:
        for model_key in LLM_PRICING_TABLE:
            cost = estimate_cost(model_key, 100, 50)
            assert cost is not None
            assert cost > 0, f"Expected positive cost for {model_key}"

    def test_openai_gpt4o_mini_pricing(self) -> None:
        # 1000 prompt @ $0.00015/1K + 500 completion @ $0.00060/1K
        cost = estimate_cost("openai/gpt-4o-mini", 1000, 500)
        assert cost == pytest.approx(0.00015 + 0.0003)

    def test_anthropic_claude_haiku_in_table(self) -> None:
        cost = estimate_cost("anthropic/claude-3-haiku-20240307", 1000, 500)
        assert cost is not None


class TestPricingTableCoverage:
    def test_all_major_providers_represented(self) -> None:
        providers = {k.split("/")[0] for k in LLM_PRICING_TABLE}
        assert "openai" in providers
        assert "anthropic" in providers
        assert "google" in providers

    def test_table_not_empty(self) -> None:
        assert len(LLM_PRICING_TABLE) >= 10
