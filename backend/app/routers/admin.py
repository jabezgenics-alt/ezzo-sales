from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app.models import User, Quote, Enquiry, AuditLog, QuoteStatus, EnquiryStatus, Document
from app.schemas import (
    QuoteResponse, QuoteUpdate, QuoteApprovalRequest,
    QuoteRejectionRequest, AuditLogResponse, DocumentResponse
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


@router.delete("/quotes/{quote_id}")
def delete_quote(
    quote_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a quote"""
    
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    # Delete associated audit logs first
    db.query(AuditLog).filter(AuditLog.quote_id == quote_id).delete()
    
    # Delete the quote
    db.delete(quote)
    db.commit()
    
    return {"message": "Quote deleted successfully"}


@router.get("/documents", response_model=List[DocumentResponse])
def get_all_documents(
    response: Response,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all documents for knowledge base management (paginated without total count for speed)"""
    # Get paginated documents without counting total (much faster)
    documents = db.query(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    return documents


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get document details"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return document


@router.get("/documents/{document_id}/content")
def get_document_content(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get document content for viewing/editing"""
    from app.services.document_parser import document_parser
    import os
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check if file exists
    if not os.path.exists(document.file_path):
        # Try to find the file in uploads directory if path is relative
        import glob
        possible_paths = glob.glob(f"uploads/*{document.original_filename}")
        if possible_paths:
            # Update the path in database
            document.file_path = possible_paths[0]
            db.commit()
            # Continue to parse
        else:
            return {
                "content": f"⚠️ File not found\n\nOriginal filename: {document.original_filename}\nExpected path: {document.file_path}\n\nThe document file may have been moved or deleted from the filesystem.\n\nPlease re-upload the document or delete this record."
            }
    
    try:
        # Parse document to get text content
        text = document_parser.parse_document(document.file_path, document.file_type)
        return {"content": text}
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error reading document {document_id}: {error_details}")
        
        # Provide helpful error message based on error type
        error_msg = str(e)
        if "EOF marker not found" in error_msg:
            return {
                "content": f"⚠️ Corrupted PDF File\n\nThe PDF file appears to be corrupted or incomplete.\n\nOriginal filename: {document.original_filename}\nFile path: {document.file_path}\n\nPossible causes:\n- File was not fully uploaded\n- File was corrupted during transfer\n- Original PDF was already damaged\n\nSolution: Please re-upload a valid PDF file or delete this record."
            }
        else:
            return {
                "content": f"⚠️ Error Reading Document\n\nCould not parse the document content.\n\nOriginal filename: {document.original_filename}\nFile path: {document.file_path}\nFile type: {document.file_type}\n\nError details:\n{error_msg}\n\nPlease check if the file is valid or try re-uploading it."
            }


@router.put("/documents/{document_id}/content")
def update_document_content(
    document_id: int,
    content_data: dict,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update document content"""
    from app.models import DocumentStatus
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    try:
        # Write updated content to file
        with open(document.file_path, 'w', encoding='utf-8') as f:
            f.write(content_data['content'])
        
        # Update file size
        document.file_size = len(content_data['content'].encode('utf-8'))
        
        # Mark as needing reprocessing
        document.status = DocumentStatus.UPLOADED
        document.processed_at = None
        document.error_message = None
        
        db.commit()
        db.refresh(document)
        
        return {"message": "Document content updated successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating document content: {str(e)}"
        )


@router.post("/documents/{document_id}/reprocess")
def reprocess_document(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Reprocess a single document"""
    from app.services.document_parser import document_parser
    from app.services.vector_store import vector_store
    from app.models import DocumentStatus
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Delete old chunks from vector store first
    try:
        vector_store.delete_document_chunks(document.id)
    except Exception as e:
        print(f"Warning: Could not delete old chunks for document {document.id}: {str(e)}")
    
    # Update status to processing
    document.status = DocumentStatus.PROCESSING
    db.commit()
    
    try:
        # Parse document
        text = document_parser.parse_document(document.file_path, document.file_type)
        
        # Generate summary
        summary = document_parser.generate_summary(text)
        document.summary = summary
        
        # Chunk text
        chunks = document_parser.chunk_text(text)
        
        # Store chunks in ChromaDB with extracted pricing data
        import time
        for idx, chunk_text in enumerate(chunks):
            # Extract structured data with retry logic
            max_retries = 3
            structured_data = None
            
            for retry in range(max_retries):
                try:
                    structured_data = document_parser.extract_structured_data(chunk_text)
                    break
                except Exception as e:
                    if 'rate_limit' in str(e).lower() and retry < max_retries - 1:
                        wait_time = (retry + 1) * 2
                        print(f"Rate limit hit, waiting {wait_time}s before retry {retry + 1}/{max_retries}")
                        time.sleep(wait_time)
                    else:
                        print(f"Error extracting structured data (attempt {retry + 1}): {str(e)}")
                        structured_data = {
                            'item_name': None,
                            'base_price': None,
                            'price_unit': None,
                            'conditions': [],
                            'location': None
                        }
                        break
            
            # Build metadata
            metadata = {
                'document_id': document.id,
                'document_name': document.original_filename,
                'chunk_index': idx,
                'source': f"{document.original_filename} chunk {idx+1}"
            }
            
            # Helper function to safely add metadata
            def safe_add_metadata(key, value, convert_fn=str):
                if value is not None:
                    try:
                        if isinstance(value, list):
                            if value:
                                metadata[key] = ' | '.join(str(item) for item in value if item is not None)
                        else:
                            converted = convert_fn(value)
                            if converted is not None:
                                metadata[key] = converted
                    except (ValueError, TypeError):
                        pass
            
            # Add structured data to metadata
            if structured_data:
                safe_add_metadata('base_price', structured_data.get('base_price'), float)
                safe_add_metadata('price_unit', structured_data.get('price_unit'), str)
                safe_add_metadata('item_name', structured_data.get('item_name'), str)
                safe_add_metadata('location', structured_data.get('location'), str)
                safe_add_metadata('conditions', structured_data.get('conditions'), str)
            
            # Add to vector store
            vector_store.add_chunk(
                chunk_id=f"doc_{document.id}_chunk_{idx}",
                content=chunk_text,
                metadata=metadata
            )
        
        # Update document status
        document.status = DocumentStatus.PROCESSED
        document.processed_at = datetime.utcnow()
        document.error_message = None
        db.commit()
        db.refresh(document)
        
        return {"message": "Document reprocessed successfully"}
        
    except Exception as e:
        # Update status to failed
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reprocessing document: {str(e)}"
        )


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a document and its chunks"""
    import os
    from app.services.vector_store import vector_store
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Delete from vector store (ChromaDB)
    vector_store.delete_document_chunks(document.id)
    
    # Delete file
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
    except Exception as e:
        print(f"Error deleting file: {str(e)}")
    
    # Delete document from database
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}
