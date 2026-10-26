# Fixture: nested packages

Exercises relative-import and dotted-package resolution.

```
main.py
src/
  __init__.py
  core/
    __init__.py
    models.py                 class Entity
    domain/
      __init__.py
      service.py              from ..models import Entity   (relative, level 2)
```

Import forms covered:

| File | Import | Form |
|---|---|---|
| `main.py` | `from src.core.domain.service import describe` | absolute dotted |
| `main.py` | `from src.core.models import Entity` | absolute dotted |
| `src/core/domain/service.py` | `from ..models import Entity` | relative, level 2 |
| `src/core/domain/__init__.py` | — | package marker |

The `__init__.py` files matter: `graph_builder` indexes `src.core.domain`
as a module path in its own right, so a missing package marker changes the
resolved node ids. That is exactly the kind of drift the golden test
exists to catch.
