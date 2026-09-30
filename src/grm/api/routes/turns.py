"""Versioned turn endpoint. REST JSON today, streaming later behind this seam."""

from __future__ import annotations

import time

from fastapi import APIRouter

from grm.channels.router import route_turn
from grm.channels.schemas import TurnRequest, TurnResponse
from grm.observability.logging import get_logger

router = APIRouter(prefix="/v1", tags=["turns"])


@router.post("/turns", response_model=TurnResponse)
async def post_turn(payload: TurnRequest) -> TurnResponse:
    """Accept one beneficiary turn and return the response plus routing state.

    The session id is truncated in the log on purpose: it is enough to correlate
    a turn, and a full identifier in a log is one more copy of it in the world.
    """
    log = get_logger()
    started = time.perf_counter()
    log.info("request arrived", stage="http", session=payload.session_id[:8])

    try:
        result = await route_turn(payload)
    except Exception as exc:
        log.error(
            "request raised",
            stage="http",
            session=payload.session_id[:8],
            duration_s=round(time.perf_counter() - started, 2),
            error=type(exc).__name__,
            detail=str(exc)[:200],
        )
        raise

    log.info(
        "response leaving",
        stage="http",
        session=payload.session_id[:8],
        owner=result.owner,
        authenticated=result.authenticated,
        duration_s=round(time.perf_counter() - started, 2),
    )
    return result
