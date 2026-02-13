# Quickstart

## Install

```bash
pip install yagra
```

## Minimal Usage

```python
from yagra import Yagra


def passthrough(state: dict, params: dict) -> dict:
    _ = params
    return state


app = Yagra.from_workflow(
    workflow_path="workflows/support.yaml",
    registry={"passthrough": passthrough},
)

result = app.invoke({"message": "hello"})
print(result)
```
