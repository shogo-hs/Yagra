"""Static pricing table for LLM cost estimation (G-15).

Prices are in USD per 1,000 tokens (input/output separately).
Updated: 2026-02.
Sources: official provider pricing pages.

Note: This table is intentionally separate from the trace model so it
can be updated independently without schema migration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Per-model pricing in USD per 1,000 tokens.

    Attributes:
        input_per_1k: Cost per 1,000 prompt (input) tokens in USD.
        output_per_1k: Cost per 1,000 completion (output) tokens in USD.
    """

    input_per_1k: float
    output_per_1k: float

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculates estimated cost for a single LLM call.

        Args:
            prompt_tokens: Number of input tokens.
            completion_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD, rounded to 8 decimal places.
        """
        cost = (
            self.input_per_1k * prompt_tokens / 1000.0
            + self.output_per_1k * completion_tokens / 1000.0
        )
        return round(cost, 8)


# Key format: "{litellm_provider}/{model_name}" — matches the LLM handler's
# litellm_model string construction: f"{provider}/{model_name}"
#
# Pricing as of 2026-02 (USD per 1K tokens).
# Cached/batch pricing is NOT included (standard on-demand only).
LLM_PRICING_TABLE: dict[str, ModelPricing] = {
    # --- OpenAI ---
    "openai/gpt-4o": ModelPricing(input_per_1k=0.0025, output_per_1k=0.0100),
    "openai/gpt-4o-mini": ModelPricing(input_per_1k=0.00015, output_per_1k=0.00060),
    "openai/gpt-4-turbo": ModelPricing(input_per_1k=0.0100, output_per_1k=0.0300),
    "openai/gpt-4": ModelPricing(input_per_1k=0.0300, output_per_1k=0.0600),
    "openai/gpt-3.5-turbo": ModelPricing(input_per_1k=0.00050, output_per_1k=0.00150),
    "openai/o1": ModelPricing(input_per_1k=0.0150, output_per_1k=0.0600),
    "openai/o1-mini": ModelPricing(input_per_1k=0.0030, output_per_1k=0.0120),
    "openai/o3-mini": ModelPricing(input_per_1k=0.0011, output_per_1k=0.0044),
    # --- Anthropic ---
    "anthropic/claude-3-5-sonnet-20241022": ModelPricing(input_per_1k=0.0030, output_per_1k=0.0150),
    "anthropic/claude-3-5-haiku-20241022": ModelPricing(
        input_per_1k=0.00080, output_per_1k=0.00400
    ),
    "anthropic/claude-3-opus-20240229": ModelPricing(input_per_1k=0.0150, output_per_1k=0.0750),
    "anthropic/claude-3-sonnet-20240229": ModelPricing(input_per_1k=0.0030, output_per_1k=0.0150),
    "anthropic/claude-3-haiku-20240307": ModelPricing(input_per_1k=0.00025, output_per_1k=0.00125),
    # --- Google Gemini ---
    "google/gemini-1.5-flash": ModelPricing(input_per_1k=0.000075, output_per_1k=0.000300),
    "google/gemini-1.5-flash-8b": ModelPricing(input_per_1k=0.0000375, output_per_1k=0.00015),
    "google/gemini-1.5-pro": ModelPricing(input_per_1k=0.00125, output_per_1k=0.00500),
    "google/gemini-2.0-flash": ModelPricing(input_per_1k=0.000100, output_per_1k=0.000400),
    "google/gemini-2.0-pro": ModelPricing(input_per_1k=0.00125, output_per_1k=0.00500),
    # --- Meta (via Groq) ---
    "groq/llama-3.3-70b-versatile": ModelPricing(input_per_1k=0.00059, output_per_1k=0.00079),
    "groq/llama-3.1-8b-instant": ModelPricing(input_per_1k=0.000059, output_per_1k=0.000079),
    # --- Mistral ---
    "mistral/mistral-large-latest": ModelPricing(input_per_1k=0.0020, output_per_1k=0.0060),
    "mistral/mistral-small-latest": ModelPricing(input_per_1k=0.00020, output_per_1k=0.00060),
    "mistral/open-mistral-7b": ModelPricing(input_per_1k=0.000025, output_per_1k=0.000025),
}


def estimate_cost(litellm_model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Estimates the cost of an LLM call from the static pricing table.

    Args:
        litellm_model: Full litellm model string, e.g. 'openai/gpt-4o-mini'.
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.

    Returns:
        Estimated cost in USD, or None if the model is not in the pricing table.
    """
    pricing = LLM_PRICING_TABLE.get(litellm_model)
    if pricing is None:
        return None
    return pricing.estimate_cost(prompt_tokens, completion_tokens)
