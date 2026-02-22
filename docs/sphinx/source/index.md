# Yagra Documentation

**Declarative LangGraph Builder powered by YAML**

Yagra enables you to build [LangGraph](https://langchain-ai.github.io/langgraph/)'s `StateGraph` from YAML definitions, separating workflow logic from Python implementation.

## What is Yagra?

Yagra is a Python library that lets you define LLM agent workflows declaratively in YAML files. Instead of writing boilerplate LangGraph code for every workflow variation, you define nodes, edges, and branching logic in YAML—then swap configurations without touching code.

### Key Benefits

- **Faster iteration**: Adjust workflows by editing YAML, not Python
- **Collaborative**: Prompt engineers and domain experts can participate via WebUI
- **Validation by design**: Pydantic-based schema catches errors before runtime
- **Visual editing**: Studio WebUI for drag-and-drop workflow construction
- **AI-ready**: MCP server enables coding agents to build and optimize workflows directly

## Quick Links

```{toctree}
:maxdepth: 2
:caption: Getting Started

getting_started
```

```{toctree}
:maxdepth: 2
:caption: User Guide

user_guide/workflow_yaml
user_guide/prompt_model
user_guide/branching_loops
user_guide/templates
user_guide/optimization_cycle
```

```{toctree}
:maxdepth: 2
:caption: CLI & API

cli_reference
api
```

```{toctree}
:maxdepth: 1
:caption: Additional Resources

examples
contributing
changelog
```

## Architecture Overview

Yagra follows **Hexagonal Architecture** (Ports and Adapters):

- **Domain**: Core workflow entities (`GraphSpec`, `NodeSpec`, `EdgeSpec`)
- **Application**: Use cases (`build_state_graph`, `validate_workflow`)
- **Ports**: Interfaces for extensibility (`NodeRegistryPort`)
- **Adapters**: Implementations (file system, WebUI server)

Dependency rule: Outer layers depend on inner layers, never the reverse.

## Use Cases

- **Prototyping LLM agent flows**: Rapidly test different workflow variations
- **Collaborative workflow development**: Enable domain experts to participate in workflow tuning via WebUI
- **AI-assisted workflow generation**: Let coding agents generate and validate workflows
- **Reducing boilerplate**: Build complex LangGraph applications with less code

## Community

- **GitHub**: [https://github.com/shogo-hs/Yagra](https://github.com/shogo-hs/Yagra)
- **Issues**: [https://github.com/shogo-hs/Yagra/issues](https://github.com/shogo-hs/Yagra/issues)
- **PyPI**: [https://pypi.org/project/yagra/](https://pypi.org/project/yagra/)

## License

MIT License - see [LICENSE](https://github.com/shogo-hs/Yagra/blob/main/LICENSE) for details.
