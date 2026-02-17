# Structured Output LLM Handler Example

This example demonstrates Yagra's structured output LLM handler, which uses Pydantic models to parse and validate LLM responses into type-safe Python objects.

## What This Example Does

1. Defines a `PersonInfo` Pydantic model (`name: str`, `age: int`)
2. Creates a `create_structured_llm_handler(schema=PersonInfo)` handler
3. Sends a text input to GPT-4o and extracts structured person information
4. Returns a `PersonInfo` instance with full type safety

## Prerequisites

- Python 3.12+
- `yagra[llm]` installed
- OpenAI API key

## Setup

```bash
# Install with LLM support
pip install 'yagra[llm]'

# Or with uv
uv add 'yagra[llm]'

# Set your API key
export OPENAI_API_KEY="your-api-key"
```

## Run

```bash
python run_example.py
```

Expected output:

```
Creating structured LLM handler with schema: PersonInfo
Loading workflow from: .../workflow.yaml

Executing workflow with input text: 'My name is Alice and I am 30 years old.'

============================================================
Structured Output Result:
============================================================
Type   : PersonInfo
Name   : Alice
Age    : 30
============================================================

[Type Safety]
  person.name is str : True
  person.age is int  : True
```

## File Structure

```
llm-structured/
├── README.md         # This file
├── workflow.yaml     # Workflow definition
├── prompts.yaml      # Prompt templates
└── run_example.py    # Execution script
```

## Key Differences from Basic LLM Handler

| Feature | `create_llm_handler` | `create_structured_llm_handler` |
|---------|---------------------|----------------------------------|
| Output type | `str` | `pydantic.BaseModel` instance |
| Type safety | ❌ Manual parsing needed | ✅ Automatic validation |
| JSON mode | ❌ Optional | ✅ Enabled by default |
| Schema enforcement | ❌ None | ✅ Pydantic validation |

## Customization

### Change the Schema

Define any Pydantic model to fit your extraction needs:

```python
from pydantic import BaseModel

class ArticleSummary(BaseModel):
    title: str
    key_points: list[str]
    sentiment: str

handler = create_structured_llm_handler(schema=ArticleSummary)
```

### Change the Model

Update `workflow.yaml` to use a different LLM provider:

```yaml
model:
  provider: "anthropic"
  name: "claude-3-5-sonnet-20241022"
```

### Disable JSON Mode (for models that don't support it)

Some models may not support `response_format=json_object`. You can override it via `model.kwargs`:

```yaml
model:
  provider: "anthropic"
  name: "claude-3-5-haiku-20241022"
  kwargs:
    response_format: null  # Disable automatic JSON mode
```

The system prompt will still instruct the LLM to return JSON.

## Troubleshooting

**`LLMHandlerCallError: Failed to parse LLM response`**
- The LLM returned invalid JSON or a response that doesn't match your schema
- Try adding more specific instructions in the system prompt
- Try a more capable model (e.g., `gpt-4o` instead of `gpt-3.5-turbo`)

**`ImportError: litellm is not installed`**
- Install with: `pip install 'yagra[llm]'`

## Next Steps

- **Basic Handler**: See [`../llm-basic/`](../llm-basic/) for simple text output
- **Streaming** (Coming Soon): `create_streaming_llm_handler()` for real-time output
