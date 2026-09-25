"""HTTP routes for the shopping panel of the Preparedness page (mounted by app.main)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from . import catalog, offers

router = APIRouter()


@router.get("/api/shopping")
def shopping() -> dict:
    """Per preparedness item id: where to buy, observed prices, recommended spec."""
    return offers.offers()


@router.get("/api/shopping/budget")
def shopping_budget(
    adults: Annotated[int, Query(ge=1, le=20)] = 1,
    children: Annotated[int, Query(ge=0, le=20)] = 0,
    days: Annotated[int, Query(ge=1, le=120)] = 14,
    include: Annotated[list[Literal["conditional", "optional"]] | None, Query()] = None,
) -> dict:
    """Indicative totals per priority / category for a household (THB, min-max)."""
    return offers.budget(adults, children, days, tuple(include or ()))


@router.get("/api/shopping/{item_id}")
def shopping_item(item_id: str) -> dict:
    entry = catalog.ITEM_BY_ID.get(item_id)
    if entry is None:
        raise HTTPException(404, f"no shopping entry for {item_id!r}")
    prep = next((it for it in offers.prep_items() if it["id"] == item_id), None)
    return offers.offer(entry, prep)
