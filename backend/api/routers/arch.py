"""
api/routers/arch.py
Serves the architecture rule set.

Correction C6: the five-layer taxonomy used to live ONLY in
frontend/src/components/graph/layerClassifier.ts. That meant the web UI
and any backend consumer (the MCP server, the CI gate) could disagree
about what "client" or "storage" means.

This endpoint is the single contract. The frontend, the MCP server, and CI
all read the rules from here — so there is exactly one rule table, and the
parity test in backend/tests/test_arch_rules.py keeps it honest.
"""
from fastapi import APIRouter, HTTPException

from arch_rules import load_ruleset, to_api_payload
from repo_tracker import load_state

router = APIRouter(prefix="/api/arch", tags=["architecture"])


@router.get("/rules")
async def arch_rules():
    """
    The effective architecture rules for the loaded repository.

    Returns the five canonical layers, the layer-matching rules, the
    default dependency policy, and any team-declared domains and boundary
    rules found in the repo's .reposcope.yml.
    """
    state = load_state()
    repo_root = state.get("local_path")
    if not repo_root:
        # No repo loaded — serve the built-in defaults so the frontend can
        # still render layer colors before a repository is selected.
        return to_api_payload()

    try:
        ruleset = load_ruleset(repo_root)
    except Exception as exc:  # never fail the whole request on a bad config
        raise HTTPException(
            status_code=500,
            detail="Failed to load architecture rules.",
        ) from exc

    return to_api_payload(ruleset)
