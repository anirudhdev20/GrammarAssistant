from fastapi import APIRouter, Request

from ..nlp.pipeline import Analyzer
from ..version import __version__

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(request: Request) -> dict:
    analyzer: Analyzer = request.app.state.analyzer
    return {
        "status": "ok",
        "version": __version__,
        "model": analyzer.nlp.meta.get("name", "en_core_web_sm"),
        "language_tool": analyzer.lt is not None,
        "user_words": len(analyzer.spell.user_words),
    }
