from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from pathlib import Path
from app.database import get_db
from app.models import User, Document, DocumentStatus
from app.schemas import DocumentResponse, DocumentSummaryUpdate
from app.auth import get_current_admin
from app.config import settings
from app.services.document_parser import document_parser
from app.services.vector_store import vector_store

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Upload a document (admin only)"""
    
    # Validate file type
    allowed_types = ['pdf', 'csv', 'txt', 'text']
    file_ext = file.filename.split('.')[-1].lower()
    
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type .{file_ext} not allowed. Allowed types: {', '.join(allowed_types)}"
        )
    
    # Create upload directory if not exists
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = upload_dir / unique_filename
    
    # Save file
    try:
        contents = await file.read()
        
        # Check file size
        if len(contents) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {settings.MAX_FILE_SIZE} bytes"
            )
        
        with open(file_path, 'wb') as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving file: {str(e)}"
        )
    
    # Create document record
    document = Document(
        filename=unique_filename,
        original_filename=file.filename,
        file_path=str(file_path),
        file_type=file_ext,
        file_size=len(contents),
        uploaded_by=current_user.id,
        status=DocumentStatus.UPLOADED
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return document


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all documents (admin only)"""
    documents = db.query(Document).offset(skip).limit(limit).all()
    return documents


@router.get("/{document_id}", response_model=DocumentResponse)
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


@router.post("/{document_id}/process", response_model=DocumentResponse)
def process_document(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Process a document - parse, chunk, and add to knowledge base"""
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if document.status == DocumentStatus.PROCESSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document already processed"
        )
    
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
        for idx, chunk_text in enumerate(chunks):
            # Extract structured data (pricing, etc.) from chunk with retry logic
            import time
            max_retries = 3
            structured_data = None
            
            for retry in range(max_retries):
                try:
                    structured_data = document_parser.extract_structured_data(chunk_text)
                    break
                except Exception as e:
                    if 'rate_limit' in str(e).lower() and retry < max_retries - 1:
                        # Wait and retry for rate limits
                        wait_time = (retry + 1) * 2  # 2, 4, 6 seconds
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
            
            # Build metadata - ChromaDB only accepts str, int, float, bool
            metadata = {
                'document_id': document.id,
                'document_name': document.original_filename,
                'chunk_index': idx,
                'source': f"{document.original_filename} chunk {idx+1}"
            }
            
            # Add pricing data if available (filter out None and ensure correct types)
            def safe_add_metadata(key, value, convert_fn=str):
                """Safely add metadata only if value is not None and can be converted"""
                if value is not None:
                    try:
                        # Handle lists specially - convert to string
                        if isinstance(value, list):
                            if value:  # Only if list is not empty
                                metadata[key] = ' | '.join(str(item) for item in value if item is not None)
                        else:
                            converted = convert_fn(value)
                            # Ensure we don't add None after conversion
                            if converted is not None:
                                metadata[key] = converted
                    except (ValueError, TypeError):
                        # Skip if conversion fails
                        pass
            
            # Add structured data to metadata
            if structured_data:
                safe_add_metadata('base_price', structured_data.get('base_price'), float)
                safe_add_metadata('price_unit', structured_data.get('price_unit'), str)
                safe_add_metadata('item_name', structured_data.get('item_name'), str)
                safe_add_metadata('location', structured_data.get('location'), str)
                safe_add_metadata('conditions', structured_data.get('conditions'), str)
            
            # Add to vector store with pricing metadata
            vector_store.add_chunk(
                chunk_id=f"doc_{document.id}_chunk_{idx}",
                content=chunk_text,
                metadata=metadata
            )
        
        # Update document status
        document.status = DocumentStatus.PROCESSED
        from datetime import datetime
        document.processed_at = datetime.utcnow()
        db.commit()
        db.refresh(document)
        
        return document
        
    except Exception as e:
        # Update status to failed
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )


@router.patch("/{document_id}/summary", response_model=DocumentResponse)
def update_document_summary(
    document_id: int,
    summary_update: DocumentSummaryUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update document summary (admin only)"""
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Update summary
    document.summary = summary_update.summary
    db.commit()
    db.refresh(document)
    
    return document


@router.post("/generate-knowledge-summary")
def generate_knowledge_summary(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Generate a comprehensive structured summary of ALL documents in the knowledge base"""
    
    # Get all processed documents
    documents = db.query(Document).filter(
        Document.status == DocumentStatus.PROCESSED
    ).all()
    
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No processed documents found. Please upload and process documents first."
        )
    
    # Prepare document summaries
    doc_summaries = []
    for doc in documents:
        if doc.summary:
            doc_summaries.append({
                'filename': doc.original_filename,
                'summary': doc.summary
            })
    
    if not doc_summaries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document summaries available. Please ensure documents are processed."
        )
    
    # Generate master summary
    master_summary = document_parser.generate_structured_knowledge_summary(doc_summaries)
    
    return {
        "summary": master_summary,
        "document_count": len(doc_summaries)
    }


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a document and its chunks"""
    
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


@router.post("/reprocess-all")
def reprocess_all_documents(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Reprocess ALL documents to extract pricing data (admin only)"""
    
    processed_count = 0
    failed_docs = []
    
    # Get all processed documents (lowercase status from DB)
    documents = db.query(Document).filter(
        Document.status == "processed"
    ).all()
    
    if not documents:
        return {
            "message": "No documents to reprocess",
            "processed_count": 0
        }
    
    for document in documents:
        try:
            # Delete old chunks from vector store first
            try:
                vector_store.delete_document_chunks(document.id)
                print(f"Deleted old chunks for document {document.id}")
            except Exception as del_err:
                print(f"Warning: Could not delete old chunks for document {document.id}: {str(del_err)}")
            
            # Re-parse and process
            text = document_parser.parse_document(document.file_path, document.file_type)
            
            # Re-generate summary
            summary = document_parser.generate_summary(text)
            document.summary = summary
            
            # Chunk text
            chunks = document_parser.chunk_text(text)
            
            # Store chunks with pricing extraction
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
            
            processed_count += 1
            print(f"Reprocessed document {document.id}: {document.original_filename}")
            
            # Commit after each document to avoid timeout
            db.commit()
            
        except Exception as e:
            print(f"Error reprocessing document {document.id}: {str(e)}")
            failed_docs.append({
                'id': document.id,
                'filename': document.original_filename,
                'error': str(e)
            })
            # Rollback on error to ensure clean state for next document
            db.rollback()
    
    response = {
        "message": f"Reprocessed {processed_count} documents successfully",
        "processed_count": processed_count,
        "total_documents": len(documents)
    }
    
    if failed_docs:
        response["failed_count"] = len(failed_docs)
        response["failed_documents"] = failed_docs
    
    return response


@router.get("/{document_id}/content")
def get_document_content(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get document content for viewing/editing"""
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    try:
        # Parse document to get text content
        text = document_parser.parse_document(document.file_path, document.file_type)
        return {"content": text}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading document content: {str(e)}"
        )


@router.put("/{document_id}/content")
def update_document_content(
    document_id: int,
    content_data: dict,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update document content"""
    
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


@router.post("/{document_id}/reprocess")
def reprocess_document(
    document_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Reprocess a single document"""
    
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
        from datetime import datetime
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


@router.delete("/")
def cleanup_all_documents(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete ALL documents, files, and vector store data (admin only)"""
    
    deleted_count = 0
    failed_files = []
    
    # Get all documents
    documents = db.query(Document).all()
    
    # Delete each document's files and vector store entries
    for document in documents:
        try:
            # Delete from vector store (ChromaDB)
            vector_store.delete_document_chunks(document.id)
        except Exception as e:
            print(f"Error deleting vector chunks for document {document.id}: {str(e)}")
        
        # Delete file from filesystem
        try:
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
        except Exception as e:
            failed_files.append(document.original_filename)
            print(f"Error deleting file {document.file_path}: {str(e)}")
        
        # Delete from database
        db.delete(document)
        deleted_count += 1
    
    # Commit database changes
    db.commit()
    
    # Clear the entire ChromaDB collection to be safe
    try:
        vector_store.collection.delete(where={})
    except Exception as e:
        print(f"Error clearing ChromaDB collection: {str(e)}")
    
    response = {
        "message": "All documents cleaned up successfully",
        "deleted_count": deleted_count
    }
    
    if failed_files:
        response["warning"] = f"Failed to delete {len(failed_files)} files from filesystem"
        response["failed_files"] = failed_files
    
    return response
