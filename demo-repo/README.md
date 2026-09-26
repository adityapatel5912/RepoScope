# Demo Repo

A tiny Python project for testing RepoScope without needing an
external GitHub URL. Three modules with cross-dependencies.

## Modules
- `auth.py`     — login, token generation, session validation
- `checkout.py` — cart management, order creation (imports auth + payment)
- `payment.py`  — charge, retry logic, refund

## Try it
Point RepoScope at any public GitHub URL, or index this folder locally:

```
# Ask questions like:
"How does checkout work?"
"What depends on auth.py?"
"Show me the architecture."
```
