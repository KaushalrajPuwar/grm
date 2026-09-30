"""Liveness probe. No protected data in any response here."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "grm"}
