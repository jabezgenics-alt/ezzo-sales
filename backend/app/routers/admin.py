from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app.models import User, Quote, Enquiry, AuditLog, QuoteStatus, EnquiryStatus
from app.schemas import (
    QuoteResponse, QuoteUpdate, QuoteApprovalRequest,
    QuoteRejectionRequest, AuditLogResponse
)
from app.auth import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/quotes/pending", response_model=List[QuoteResponse])
def get_pending_quotes(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all pending quotes for admin review"""
    
    quotes = db.query(Quote).filter(
        Quote.status == QuoteStatus.PENDING_ADMIN
    ).order_by(Quote.created_at.desc()).all()
    
    return quotes


@router.get("/quotes", response_model=List[QuoteResponse])
def get_all_quotes(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all quotes"""
    
    quotes = db.query(Quote).order_by(
        Quote.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return quotes


@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
def get_quote(
    quote_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get quote details"""
    
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    return quote


@router.put("/quotes/{quote_id}", response_model=QuoteResponse)
def update_quote(
    quote_id: int,
    quote_data: QuoteUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Edit a quote (admin only)"""
    
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    # Save previous state for audit
    previous_state = {
        "item_name": quote.item_name,
        "quantity": quote.quantity,
        "unit": quote.unit,
        "base_price": quote.base_price,
        "adjustments": quote.adjustments,
        "total_price": quote.total_price,
        "conditions": quote.conditions,
        "admin_notes": quote.admin_notes
    }
    
    # Update fields
    if quote_data.item_name is not None:
        quote.item_name = quote_data.item_name
    if quote_data.quantity is not None:
        quote.quantity = quote_data.quantity
    if quote_data.unit is not None:
        quote.unit = quote_data.unit
    if quote_data.base_price is not None:
        quote.base_price = quote_data.base_price
    if quote_data.adjustments is not None:
        quote.adjustments = [adj.dict() for adj in quote_data.adjustments]
    if quote_data.total_price is not None:
        quote.total_price = quote_data.total_price
    if quote_data.conditions is not None:
        quote.conditions = quote_data.conditions
    if quote_data.admin_notes is not None:
        quote.admin_notes = quote_data.admin_notes
    
    # Save new state
    new_state = {
        "item_name": quote.item_name,
        "quantity": quote.quantity,
        "unit": quote.unit,
        "base_price": quote.base_price,
        "adjustments": quote.adjustments,
        "total_price": quote.total_price,
        "conditions": quote.conditions,
        "admin_notes": quote.admin_notes
    }
    
    # Create audit log
    audit_log = AuditLog(
        quote_id=quote.id,
        user_id=current_user.id,
        action="edited",
        description="Admin edited quote",
        previous_state=previous_state,
        new_state=new_state
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(quote)
    
    return quote


@router.post("/quotes/{quote_id}/approve", response_model=QuoteResponse)
def approve_quote(
    quote_id: int,
    approval_data: QuoteApprovalRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Approve a quote"""
    
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    if quote.status == QuoteStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quote already approved"
        )
    
    # Update quote
    quote.status = QuoteStatus.APPROVED
    quote.reviewed_by = current_user.id
    quote.reviewed_at = datetime.utcnow()
    if approval_data.admin_notes:
        quote.admin_notes = approval_data.admin_notes
    
    # Update enquiry status
    enquiry = db.query(Enquiry).filter(Enquiry.id == quote.enquiry_id).first()
    if enquiry:
        enquiry.status = EnquiryStatus.APPROVED
    
    # Create audit log
    audit_log = AuditLog(
        quote_id=quote.id,
        user_id=current_user.id,
        action="approved",
        description=f"Quote approved by admin: {current_user.email}",
        new_state={"status": "approved", "admin_notes": quote.admin_notes}
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(quote)
    
    return quote


@router.post("/quotes/{quote_id}/reject", response_model=QuoteResponse)
def reject_quote(
    quote_id: int,
    rejection_data: QuoteRejectionRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Reject a quote"""
    
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    # Update quote
    quote.status = QuoteStatus.REJECTED
    quote.reviewed_by = current_user.id
    quote.reviewed_at = datetime.utcnow()
    quote.admin_notes = rejection_data.admin_notes
    
    # Update enquiry status
    enquiry = db.query(Enquiry).filter(Enquiry.id == quote.enquiry_id).first()
    if enquiry:
        enquiry.status = EnquiryStatus.REJECTED
    
    # Create audit log
    audit_log = AuditLog(
        quote_id=quote.id,
        user_id=current_user.id,
        action="rejected",
        description=f"Quote rejected by admin: {current_user.email}. Reason: {rejection_data.reason}",
        new_state={
            "status": "rejected",
            "reason": rejection_data.reason,
            "admin_notes": quote.admin_notes
        }
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(quote)
    
    return quote


@router.post("/quotes/{quote_id}/send-to-customer")
def send_quote_to_customer(
    quote_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Send approved quote to customer"""
    
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    if quote.status != QuoteStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quote must be approved before sending to customer"
        )
    
    # Update status
    quote.status = QuoteStatus.SENT_TO_CUSTOMER
    
    # Create audit log
    audit_log = AuditLog(
        quote_id=quote.id,
        user_id=current_user.id,
        action="sent_to_customer",
        description=f"Quote sent to customer by admin: {current_user.email}",
        new_state={"status": "sent_to_customer"}
    )
    
    db.add(audit_log)
    db.commit()
    
    # TODO: Send email/notification to customer
    
    return {"message": "Quote sent to customer successfully"}


@router.get("/quotes/{quote_id}/audit", response_model=List[AuditLogResponse])
def get_quote_audit_trail(
    quote_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get audit trail for a quote"""
    
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    audit_logs = db.query(AuditLog).filter(
        AuditLog.quote_id == quote_id
    ).order_by(AuditLog.created_at.asc()).all()
    
    return audit_logs
