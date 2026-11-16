from fastapi import APIRouter, HTTPException, Request

from ..nlp.pipeline import Analyzer
from ..schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DictionaryRequest,
    DictionaryResponse,
    RewriteRequest,
    RewriteResponse,
)

router = APIRouter(prefix="/api", tags=["assistant"])


def _analyzer(request: Request) -> Analyzer:
    return request.app.state.analyzer


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    try:
        return await _analyzer(request).analyze(payload)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.post("/rewrite", response_model=RewriteResponse)
async def rewrite(payload: RewriteRequest) -> RewriteResponse:
    corrected = payload.text[: payload.start] + payload.replacement + payload.text[payload.end :]
    return RewriteResponse(text=corrected)


@router.get("/dictionary", response_model=DictionaryResponse)
async def list_dictionary(request: Request) -> DictionaryResponse:
    return DictionaryResponse(words=sorted(_analyzer(request).spell.user_words))


@router.post("/dictionary", response_model=DictionaryResponse)
async def add_to_dictionary(payload: DictionaryRequest, request: Request) -> DictionaryResponse:
    analyzer = _analyzer(request)
    analyzer.spell.add_word(payload.word)
    return DictionaryResponse(words=sorted(analyzer.spell.user_words))


@router.delete("/dictionary/{word}", response_model=DictionaryResponse)
async def remove_from_dictionary(word: str, request: Request) -> DictionaryResponse:
    analyzer = _analyzer(request)
    analyzer.spell.remove_word(word)
    return DictionaryResponse(words=sorted(analyzer.spell.user_words))
