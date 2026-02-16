# Examples

This page showcases practical examples of Yagra workflows for common use cases.

## Example 1: Customer Support Router

Route customer queries to specialized handlers based on intent.

### Workflow Structure

- **Classifier**: Determines if query is FAQ, support, or sales
- **Specialized handlers**: FAQ bot, support bot, sales bot
- **Finish**: Collects final answer

### Files

**`workflows/support_router.yaml`**:

```yaml
version: "1.0"
start_at: "classifier"
end_at:
  - "finish"

nodes:
  - id: "classifier"
    handler: "classify_query"
  - id: "faq_handler"
    handler: "handle_faq"
    params:
      prompt_ref: "../prompts/support_prompts.yaml#faq"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.3
  - id: "support_handler"
    handler: "handle_support"
    params:
      prompt_ref: "../prompts/support_prompts.yaml#support"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.5
  - id: "sales_handler"
    handler: "handle_sales"
    params:
      prompt_ref: "../prompts/support_prompts.yaml#sales"
      model:
        provider: "anthropic"
        name: "claude-3-haiku"
  - id: "finish"
    handler: "finalize_answer"

edges:
  - source: "classifier"
    target: "faq_handler"
    condition: "faq"
  - source: "classifier"
    target: "support_handler"
    condition: "support"
  - source: "classifier"
    target: "sales_handler"
    condition: "sales"
  - source: "faq_handler"
    target: "finish"
  - source: "support_handler"
    target: "finish"
  - source: "sales_handler"
    target: "finish"
```

**`prompts/support_prompts.yaml`**:

```yaml
faq:
  system: |
    You are a FAQ assistant. Answer common questions about pricing, features, and policies concisely.
  user: |
    Question: {query}

support:
  system: |
    You are a technical support specialist. Help users troubleshoot issues and provide detailed solutions.
  user: |
    Issue: {query}

sales:
  system: |
    You are a sales assistant. Help customers understand products, pricing, and purchasing options.
  user: |
    Inquiry: {query}
```

**`run_support_router.py`**:

```python
from typing import TypedDict
from yagra import Yagra


class AgentState(TypedDict, total=False):
    query: str
    intent: str
    answer: str
    __next__: str


def classify_query(state: AgentState, params: dict) -> dict:
    query = state.get("query", "").lower()
    if "price" in query or "cost" in query or "料金" in query:
        intent = "faq"
    elif "help" in query or "issue" in query or "問題" in query:
        intent = "support"
    elif "buy" in query or "purchase" in query or "見積" in query:
        intent = "sales"
    else:
        intent = "faq"
    return {"intent": intent, "__next__": intent}


def handle_faq(state: AgentState, params: dict) -> dict:
    prompt = params.get("prompt", {})
    # In real implementation, call LLM with prompt and query
    return {"answer": f"FAQ: {state['query']}"}


def handle_support(state: AgentState, params: dict) -> dict:
    prompt = params.get("prompt", {})
    return {"answer": f"SUPPORT: {state['query']}"}


def handle_sales(state: AgentState, params: dict) -> dict:
    prompt = params.get("prompt", {})
    return {"answer": f"SALES: {state['query']}"}


def finalize_answer(state: AgentState, params: dict) -> dict:
    return {"answer": state.get("answer", "No answer")}


registry = {
    "classify_query": classify_query,
    "handle_faq": handle_faq,
    "handle_support": handle_support,
    "handle_sales": handle_sales,
    "finalize_answer": finalize_answer,
}

app = Yagra.from_workflow(
    workflow_path="workflows/support_router.yaml",
    registry=registry,
    state_schema=AgentState,
)

# Test different queries
queries = [
    "What's the pricing for enterprise plans?",
    "I'm having trouble logging in",
    "I want to purchase a subscription",
]

for query in queries:
    result = app.invoke({"query": query})
    print(f"Query: {query}")
    print(f"Answer: {result['answer']}")
    print()
```

## Example 2: Iterative Content Generation

Generate content, evaluate quality, and refine until acceptable.

### Workflow Structure

- **Generator**: Produces content based on requirements
- **Evaluator**: Checks quality and provides feedback
- **Loop**: Refine until quality threshold is met

### Files

**`workflows/content_generation.yaml`**:

```yaml
version: "1.0"
start_at: "generator"
end_at:
  - "finalize"

nodes:
  - id: "generator"
    handler: "generate_content"
    params:
      prompt_ref: "../prompts/content_prompts.yaml#generator"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.8
  - id: "evaluator"
    handler: "evaluate_quality"
    params:
      prompt_ref: "../prompts/content_prompts.yaml#evaluator"
      model:
        provider: "openai"
        name: "gpt-4.1-mini"
        kwargs:
          temperature: 0.2
      max_iterations: 3
  - id: "finalize"
    handler: "finalize_content"

edges:
  - source: "generator"
    target: "evaluator"
  - source: "evaluator"
    target: "generator"
    condition: "retry"
  - source: "evaluator"
    target: "finalize"
    condition: "done"
```

**`prompts/content_prompts.yaml`**:

```yaml
generator:
  system: |
    You are a content writer. Generate high-quality content based on the requirements.
    If feedback is provided, improve the content accordingly.
  user: |
    Requirements: {requirements}
    Feedback: {feedback}

evaluator:
  system: |
    You are a content evaluator. Assess the quality of the content and provide feedback.
    Check for clarity, completeness, and engagement.
  user: |
    Content: {content}
```

**`run_content_generation.py`**:

```python
from typing import TypedDict
from yagra import Yagra


class AgentState(TypedDict, total=False):
    requirements: str
    content: str
    feedback: str
    iteration: int
    __next__: str


def generate_content(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    # In real implementation, call LLM with prompt
    content = f"Generated content v{iteration + 1}"
    return {
        "content": content,
        "iteration": iteration + 1,
    }


def evaluate_quality(state: AgentState, params: dict) -> dict:
    iteration = state.get("iteration", 0)
    max_iterations = params.get("max_iterations", 3)

    # Simple quality check (in real implementation, use LLM)
    is_good = iteration >= 2

    if is_good or iteration >= max_iterations:
        return {"__next__": "done"}
    else:
        feedback = "Content needs more detail and examples"
        return {
            "feedback": feedback,
            "__next__": "retry",
        }


def finalize_content(state: AgentState, params: dict) -> dict:
    return {"content": state.get("content", "")}


registry = {
    "generate_content": generate_content,
    "evaluate_quality": evaluate_quality,
    "finalize_content": finalize_content,
}

app = Yagra.from_workflow(
    workflow_path="workflows/content_generation.yaml",
    registry=registry,
    state_schema=AgentState,
)

result = app.invoke({"requirements": "Write a blog post about AI agents"})
print(f"Final content: {result['content']}")
print(f"Iterations: {result['iteration']}")
```

## Example 3: RAG Pipeline

Retrieve documents, rerank by relevance, and generate an answer.

### Workflow Structure

- **Retriever**: Fetch relevant documents from vector DB
- **Reranker**: Score and rerank documents
- **Generator**: Generate answer using top documents

### Files

**`workflows/rag.yaml`**:

```yaml
version: "1.0"
start_at: "retriever"
end_at:
  - "generator"

nodes:
  - id: "retriever"
    handler: "retrieve_documents"
    params:
      top_k: 10
  - id: "reranker"
    handler: "rerank_documents"
    params:
      prompt_ref: "../prompts/rag_prompts.yaml#reranker"
      top_k: 3
  - id: "generator"
    handler: "generate_answer"
    params:
      prompt_ref: "../prompts/rag_prompts.yaml#generator"
      model:
        provider: "anthropic"
        name: "claude-3-sonnet"
        kwargs:
          temperature: 0.4
          max_tokens: 1000

edges:
  - source: "retriever"
    target: "reranker"
  - source: "reranker"
    target: "generator"
```

**`prompts/rag_prompts.yaml`**:

```yaml
reranker:
  system: |
    Rerank the following documents by relevance to the query.
    Return the top documents in order.
  user: |
    Query: {query}
    Documents: {documents}

generator:
  system: |
    Generate a comprehensive answer to the query using the provided context.
    Cite sources when applicable.
  user: |
    Query: {query}
    Context: {context}
```

**`run_rag.py`**:

```python
from typing import TypedDict
from yagra import Yagra


class AgentState(TypedDict, total=False):
    query: str
    documents: list[dict]
    context: str
    answer: str


def retrieve_documents(state: AgentState, params: dict) -> dict:
    top_k = params.get("top_k", 10)
    # In real implementation, query vector DB
    documents = [{"id": i, "text": f"Doc {i}"} for i in range(top_k)]
    return {"documents": documents}


def rerank_documents(state: AgentState, params: dict) -> dict:
    top_k = params.get("top_k", 3)
    documents = state.get("documents", [])
    # In real implementation, use reranking model
    reranked = documents[:top_k]
    context = "\n".join([doc["text"] for doc in reranked])
    return {"context": context}


def generate_answer(state: AgentState, params: dict) -> dict:
    # In real implementation, call LLM with prompt and context
    answer = f"Answer based on context: {state.get('context', '')}"
    return {"answer": answer}


registry = {
    "retrieve_documents": retrieve_documents,
    "rerank_documents": rerank_documents,
    "generate_answer": generate_answer,
}

app = Yagra.from_workflow(
    workflow_path="workflows/rag.yaml",
    registry=registry,
    state_schema=AgentState,
)

result = app.invoke({"query": "What is LangGraph?"})
print(f"Answer: {result['answer']}")
```

## Running Examples

All examples are available in the `examples/` directory of the Yagra repository:

```bash
git clone https://github.com/shogo-hs/Yagra.git
cd Yagra/examples
```

Run an example:

```bash
python run_support_router.py
```

## Visualizing Examples

Generate HTML visualizations:

```bash
yagra visualize --workflow workflows/support_router.yaml --output support.html
yagra visualize --workflow workflows/content_generation.yaml --output content.html
yagra visualize --workflow workflows/rag.yaml --output rag.html
```

## Next Steps

- [User Guide](user_guide/workflow_yaml.md)
- [CLI Reference](cli_reference.md)
- [API Reference](api.md)
