"""Reverse e-auction bidding endpoint — places a bid and updates the leading position.

This is a specialized route (not from the generic CRUD factory) because placing
a bid requires business logic: validate the auction is active, check that the
bid is lower than the current leading amount by at least the decrement step,
and update the auction's leading position.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import models
from .audit import log_action
from .brd_schemas2 import (
    AuctionBidCreate,
    AuctionBidRead,
    ReverseAuctionRead,
)
from .database import get_db
from .models import User
from .security import get_current_active_user, require_roles

router = APIRouter(prefix="/reverse-auctions", tags=["reverse_auctions"])


@router.get("/{auction_id}/bids", response_model=List[AuctionBidRead],
            summary="List all bids for an auction")
def list_auction_bids(
    auction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    auction = db.get(models.ReverseAuction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")
    if user.tenant_id is not None and auction.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Auction not found")
    bids = (
        db.query(models.AuctionBid)
        .filter(models.AuctionBid.auction_id == auction_id)
        .order_by(models.AuctionBid.placed_at.desc())
        .all()
    )
    return bids


@router.post("/{auction_id}/bids", response_model=AuctionBidRead, status_code=201,
             summary="Place a bid in a reverse e-aution",
             dependencies=[Depends(require_roles("project_manager"))])
def place_auction_bid(
    auction_id: int,
    payload: AuctionBidCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    auction = db.get(models.ReverseAuction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")
    if user.tenant_id is not None and auction.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Auction not found")

    if auction.status != "active":
        raise HTTPException(status_code=400, detail=f"Auction is not active (status={auction.status})")

    # Validate bid: must be lower than current leading amount by at least decrement_step.
    if auction.leading_amount > 0:
        required_min = auction.leading_amount - auction.decrement_step
        if payload.bid_amount > required_min:
            raise HTTPException(
                status_code=400,
                detail=f"Bid must be at most {required_min:.2f} (current leading: {auction.leading_amount:.2f}, decrement: {auction.decrement_step:.2f})",
            )
    elif payload.bid_amount > auction.reserve_price:
        raise HTTPException(
            status_code=400,
            detail=f"First bid must not exceed reserve price of {auction.reserve_price:.2f}",
        )

    # Clear previous leading flag.
    db.query(models.AuctionBid).filter(
        models.AuctionBid.auction_id == auction_id,
        models.AuctionBid.is_leading == True,  # noqa: E712
    ).update({models.AuctionBid.is_leading: False})

    # Create the new bid.
    bid = models.AuctionBid(
        tenant_id=user.tenant_id,
        auction_id=auction_id,
        vendor_id=payload.vendor_id,
        bid_amount=payload.bid_amount,
        is_leading=True,
    )
    db.add(bid)
    db.flush()

    # Update auction leading position.
    auction.leading_vendor_id = payload.vendor_id
    auction.leading_amount = payload.bid_amount

    log_action(db, user=user, action="create", entity_type="auction_bids",
               entity_id=bid.id, summary=f"Bid placed: {payload.bid_amount:.2f} on auction {auction_id}")
    db.commit()
    db.refresh(bid)
    return bid


@router.get("/{auction_id}/leaderboard", response_model=List[AuctionBidRead],
            summary="Get current auction leaderboard (sorted by lowest bid)")
def auction_leaderboard(
    auction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    auction = db.get(models.ReverseAuction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")
    if user.tenant_id is not None and auction.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Auction not found")
    bids = (
        db.query(models.AuctionBid)
        .filter(models.AuctionBid.auction_id == auction_id)
        .order_by(models.AuctionBid.bid_amount.asc())
        .all()
    )
    return bids