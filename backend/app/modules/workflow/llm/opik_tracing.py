"""
Native Opik LLM tracing for workflow nodes.

Returns a LangChain callback (Opik's OpikTracer) that captures prompts, completions,
token usage and cost for every LLM/agent invocation. Attached once at the model
factory (build_chat_model) so it covers all nodes without touching each invoke site.

Connection config (URL, API key, workspace, project) is read from the OPIK_* env vars
/ .opik.config by the opik SDK itself; here we only decide whether tracing is on and
which project traces land in.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def get_opik_callbacks() -> Optional[List[Any]]:
    """Return [OpikTracer] when USE_OPIK is enabled, else None.

    Imported lazily: opik.integrations.langchain pulls langchain, which transitively
    loads torch/transformers — this must not happen in a Celery prefork master.
    """
    from app.core.config.settings import settings

    if not settings.USE_OPIK:
        return None

    try:
        from opik.integrations.langchain import OpikTracer
    except ModuleNotFoundError:
        logger.error(
            "USE_OPIK is true but the opik package is not installed "
            "(pip install -r requirements-app.txt)"
        )
        return None

    tracer = OpikTracer(project_name=settings.OPIK_PROJECT_NAME or "genassist")
    return [tracer]