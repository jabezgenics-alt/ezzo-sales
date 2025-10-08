from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import json
from app.database import get_db
from app.models import User, Enquiry, EnquiryMessage, EnquiryStatus, Quote
from app.schemas import (
    EnquiryCreate, EnquiryResponse, EnquiryMessageCreate,
    EnquiryMessageResponse, EnquiryAnswerRequest, AIResponse,
    DraftQuotePreview, ConversationTitleRequest, QuoteResponse
)
from app.auth import get_current_user
from app.services.ai_assistant import ai_assistant
from app.services.quote_engine import quote_engine

router = APIRouter(prefix="/api/enquiries", tags=["Enquiries"])


@router.post("/", response_model=AIResponse)
def create_enquiry(
    enquiry_data: EnquiryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new enquiry"""
    
    enquiry = Enquiry(
        customer_id=current_user.id,
        initial_message=enquiry_data.initial_message,
        status=EnquiryStatus.COLLECTING_INFO,
        collected_data={}
    )
    
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)
    
    # Process the initial message with AI to detect service and start conversation
    ai_response = ai_assistant.process_enquiry(db, enquiry)
    
    # Save AI's first response
    if ai_response.message:
        assistant_message = EnquiryMessage(
            enquiry_id=enquiry.id,
            role="assistant",
            content=ai_response.message
        )
        db.add(assistant_message)
        db.commit()
    
    # Add enquiry ID to response for frontend
    ai_response.id = enquiry.id
    
    return ai_response


@router.get("/", response_model=List[EnquiryResponse])
def list_enquiries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's enquiries"""
    enquiries = db.query(Enquiry).filter(
        Enquiry.customer_id == current_user.id
    ).order_by(Enquiry.created_at.desc()).all()
    
    return enquiries


@router.get("/{enquiry_id}", response_model=EnquiryResponse)
def get_enquiry(
    enquiry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get enquiry details"""
    
    enquiry = db.query(Enquiry).filter(
        Enquiry.id == enquiry_id,
        Enquiry.customer_id == current_user.id
    ).first()
    
    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found"
        )
    
    return enquiry


@router.post("/{enquiry_id}/message", response_model=AIResponse)
def send_message(
    enquiry_id: int,
    message_data: EnquiryMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message in an enquiry (customer asks/answers)"""
    
    enquiry = db.query(Enquiry).filter(
        Enquiry.id == enquiry_id,
        Enquiry.customer_id == current_user.id
    ).first()
    
    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found"
        )
    
    if enquiry.status not in [EnquiryStatus.COLLECTING_INFO, EnquiryStatus.DRAFT_READY]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message in current enquiry status"
        )
    
    # Save customer message
    customer_message = EnquiryMessage(
        enquiry_id=enquiry.id,
        role="customer",
        content=message_data.content
    )
    db.add(customer_message)
    db.commit()
    
    # Get AI response
    ai_response = ai_assistant.process_enquiry(db, enquiry, message_data.content)
    
    # Save AI response
    assistant_message = EnquiryMessage(
        enquiry_id=enquiry.id,
        role="assistant",
        content=ai_response.message
    )
    db.add(assistant_message)
    
    # Update status and show draft if ready
    if ai_response.draft_available:
        enquiry.status = EnquiryStatus.DRAFT_READY
        
        # Only extract data if NOT using a decision tree
        # (tree data is already in collected_data)
        if not enquiry.service_tree_id:
            try:
                # Build conversation text
                conversation_text = f"Initial request: {enquiry.initial_message}\n\n"
                for msg in enquiry.messages:
                    conversation_text += f"{msg.role}: {msg.content}\n"
                
                # Use AI to extract structured requirements
                extracted_data = ai_assistant.extract_requirements(conversation_text)
                print(f"Extracted data from conversation: {extracted_data}")
                
                # Store in collected_data
                if extracted_data:
                    enquiry.collected_data = extracted_data
            except Exception as extract_err:
                print(f"Error extracting data: {str(extract_err)}")
        
        db.commit()
        
        # Generate and show draft quote to user
        try:
            draft = quote_engine.calculate_draft_quote(db, enquiry)
            
            # ALWAYS show the draft to the user
            ai_response.draft_quote = draft
            
            # Auto-submit to admin if all info is available
            if draft.can_submit and draft.base_price > 0:
                # Create quote (no KnowledgeChunk dependency)
                quote = quote_engine.create_quote_from_draft(
                    db, enquiry.id, draft, source_chunk_ids=[]
                )
                
                # Update enquiry status
                enquiry.status = EnquiryStatus.SENT_TO_ADMIN
                db.commit()
                
        except Exception as e:
            print(f"Error generating draft quote: {str(e)}")
            import traceback
            traceback.print_exc()
    
    db.commit()
    
    return ai_response


@router.post("/{enquiry_id}/message/stream")
def send_message_stream(
    enquiry_id: int,
    message_data: EnquiryMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message in an enquiry with streaming AI response"""
    
    enquiry = db.query(Enquiry).filter(
        Enquiry.id == enquiry_id,
        Enquiry.customer_id == current_user.id
    ).first()
    
    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found"
        )
    
    if enquiry.status not in [EnquiryStatus.COLLECTING_INFO, EnquiryStatus.DRAFT_READY]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message in current enquiry status"
        )
    
    # Save customer message
    customer_message = EnquiryMessage(
        enquiry_id=enquiry.id,
        role="customer",
        content=message_data.content
    )
    db.add(customer_message)
    db.commit()
    
    # Store enquiry_id for use in generator
    enquiry_id_stored = enquiry.id
    
    def generate_stream():
        try:
            # Re-fetch enquiry in the generator context to avoid session issues
            enquiry_fresh = db.query(Enquiry).filter(Enquiry.id == enquiry_id_stored).first()
            if not enquiry_fresh:
                yield f"data: {json.dumps({{'type': 'error', 'message': 'Enquiry not found'}})}\n\n"
                return
            
            # Get streaming AI response
            for chunk in ai_assistant.process_enquiry_stream(db, enquiry_fresh, message_data.content):
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            print(f"Error in streaming: {str(e)}")
            error_chunk = {
                'type': 'error',
                'message': 'Sorry, there was an error processing your request.'
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )


@router.post("/{enquiry_id}/answer", response_model=AIResponse)
def answer_question(
    enquiry_id: int,
    answer_data: EnquiryAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Answer a specific question from the AI"""
    
    enquiry = db.query(Enquiry).filter(
        Enquiry.id == enquiry_id,
        Enquiry.customer_id == current_user.id
    ).first()
    
    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found"
        )
    
    # Store answer in collected_data
    if not enquiry.collected_data:
        enquiry.collected_data = {}
    
    enquiry.collected_data[answer_data.question_key] = answer_data.answer
    
    # Save customer answer as message
    customer_message = EnquiryMessage(
        enquiry_id=enquiry.id,
        role="customer",
        content=f"{answer_data.question_key}: {answer_data.answer}"
    )
    db.add(customer_message)
    db.commit()
    
    # Get AI response
    ai_response = ai_assistant.process_enquiry(db, enquiry)
    
    # Save AI response
    assistant_message = EnquiryMessage(
        enquiry_id=enquiry.id,
        role="assistant",
        content=ai_response.message
    )
    db.add(assistant_message)
    
    # Update status and show draft if ready
    if ai_response.draft_available:
        enquiry.status = EnquiryStatus.DRAFT_READY
        db.commit()
        
        # Generate and show draft quote to user
        try:
            draft = quote_engine.calculate_draft_quote(db, enquiry)
            
            # ALWAYS show the draft to the user
            ai_response.draft_quote = draft
            
            # Auto-submit to admin if all info is available
            if draft.can_submit and draft.base_price > 0:
                # Create quote (no KnowledgeChunk dependency)
                quote = quote_engine.create_quote_from_draft(
                    db, enquiry.id, draft, source_chunk_ids=[]
                )
                
                # Update enquiry status
                enquiry.status = EnquiryStatus.SENT_TO_ADMIN
                db.commit()
                
        except Exception as e:
            print(f"Error generating draft quote: {str(e)}")
            import traceback
            traceback.print_exc()
    
    db.commit()
    
    return ai_response


@router.get("/{enquiry_id}/draft", response_model=DraftQuotePreview)
def get_draft_quote(
    enquiry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get draft quote preview"""
    
    enquiry = db.query(Enquiry).filter(
        Enquiry.id == enquiry_id,
        Enquiry.customer_id == current_user.id
    ).first()
    
    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found"
        )
    
    # Calculate draft quote
    draft = quote_engine.calculate_draft_quote(db, enquiry)
    
    return draft


@router.post("/{enquiry_id}/submit")
def submit_to_admin(
    enquiry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit draft quote to admin for review"""
    
    enquiry = db.query(Enquiry).filter(
        Enquiry.id == enquiry_id,
        Enquiry.customer_id == current_user.id
    ).first()
    
    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found"
        )
    
    if enquiry.status != EnquiryStatus.DRAFT_READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft not ready for submission"
        )
    
    # Calculate draft and create quote
    draft = quote_engine.calculate_draft_quote(db, enquiry)
    
    if not draft.can_submit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing information: {', '.join(draft.missing_info)}"
        )
    
    # Get source chunk IDs
    from app.models import KnowledgeChunk
    chunks = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.item_name.ilike(f"%{draft.item_name}%")
    ).all()
    source_chunk_ids = [chunk.id for chunk in chunks]
    
    # Create quote
    quote = quote_engine.create_quote_from_draft(
        db, enquiry.id, draft, source_chunk_ids
    )
    
    # Update enquiry status
    enquiry.status = EnquiryStatus.SENT_TO_ADMIN
    db.commit()
    
    return {
        "message": "Quote submitted to admin for review",
        "quote_id": quote.id
    }


@router.get("/quotes", response_model=List[QuoteResponse])
def get_my_quotes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all quotes for the current user"""

    # Get all enquiries for this user
    enquiry_ids = db.query(Enquiry.id).filter(
        Enquiry.customer_id == current_user.id
    ).all()
    enquiry_ids = [e[0] for e in enquiry_ids]

    # Get all quotes for these enquiries
    quotes = db.query(Quote).filter(
        Quote.enquiry_id.in_(enquiry_ids)
    ).order_by(Quote.created_at.desc()).all()

    return quotes


@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
def get_my_quote(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific quote for the current user"""

    # Get the quote
    quote = db.query(Quote).filter(Quote.id == quote_id).first()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )

    # Verify the quote belongs to this user's enquiry
    enquiry = db.query(Enquiry).filter(
        Enquiry.id == quote.enquiry_id,
        Enquiry.customer_id == current_user.id
    ).first()

    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this quote"
        )

    return quote


@router.post("/generate-title")
def generate_conversation_title(
    request: ConversationTitleRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a creative conversation title based on the first message"""
    from openai import OpenAI
    from app.config import settings

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """Generate a short, creative, and engaging conversation title based on the user's first message.
The title should be:
- 2-5 words maximum
- Descriptive and fun
- Professional but friendly
- Capture the essence of what the user is asking about

Examples:
- "hello" → "Greetings from customer"
- "I need flagpoles" → "Flagpole inquiry"
- "Can you help me?" → "Assistance request"
- "parquet flooring quote" → "Parquet flooring project"
- "urgent installation needed" → "Urgent installation request"

Return ONLY the title, no quotes or extra text."""
                },
                {
                    "role": "user",
                    "content": request.message
                }
            ],
            temperature=0.7,
            max_tokens=20
        )

        title = response.choices[0].message.content.strip()

        # Remove quotes if present
        title = title.replace('"', '').replace("'", '')

        # Ensure it's not too long
        if len(title) > 40:
            title = title[:37] + '...'

        return {"title": title}

    except Exception as e:
        print(f"Error generating title: {str(e)}")
        # Fallback to simple title
        return {"title": request.message[:30]}
