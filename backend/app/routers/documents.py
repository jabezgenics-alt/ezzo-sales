from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from pathlib import Path
from app.database import get_db
from app.models import User, Document, DocumentStatus, ProductDocument, ProductDocumentType
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
        
        # Auto-detect and link products if this is a catalog/drawing
        try:
            _auto_link_products(db, document, text)
        except Exception as e:
            print(f"Error auto-linking products: {str(e)}")
            # Don't fail the whole processing if auto-link fails
        
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


def _auto_link_products(db: Session, document: Document, document_text: str):
    """Automatically detect products in document and create links"""
    from openai import OpenAI
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Use AI to detect products and document type
    prompt = f"""Analyze this document and identify:
1. What products are mentioned (e.g., cat ladder, court marking, glass partition, flooring, railing, etc.)
2. What type of document this is (catalog, technical_drawing, brochure, or spec_sheet)

Document filename: {document.original_filename}
Document text excerpt (first 2000 chars): {document_text[:2000]}

Return JSON with:
{{
    "products": ["product1", "product2"],  // Use snake_case like "cat_ladder", "court_marking"
    "document_type": "catalog" // or "technical_drawing", "brochure", "spec_sheet"
}}

Common products to look for:
- cat_ladder, access_ladder
- court_marking, line_marking  
- glass_partition, glass_panel
- handrail, safety_rail
- flooring, vinyl_flooring, wood_flooring, cork_flooring, spc_flooring, lvt_flooring
- staircase, staircase_railing
- canopy, sunshade
- bike_rack
- led_lantern
- artificial_grass
- ezz_green (LED products)
- rolling_tower, aluminium_tower

If it's a general catalog covering multiple products, list all. If focused on one product, return just that one.
If filename contains clear product names, prioritize those."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a product categorization assistant."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=200
        )
        
        result = json.loads(response.choices[0].message.content)
        products = result.get('products', [])
        doc_type = result.get('document_type', 'catalog')
        
        print(f"Auto-detected products for {document.original_filename}: {products}, type: {doc_type}")
        
        # Create links for each detected product
        for product_name in products:
            # Check if link already exists
            existing = db.query(ProductDocument).filter(
                ProductDocument.product_name == product_name,
                ProductDocument.document_id == document.id,
                ProductDocument.document_type == doc_type
            ).first()
            
            if not existing:
                product_doc = ProductDocument(
                    product_name=product_name,
                    document_type=ProductDocumentType(doc_type),
                    document_id=document.id,
                    display_order=0,
                    is_active=True
                )
                db.add(product_doc)
                print(f"Auto-linked {product_name} to document {document.id}")
        
        db.commit()
        
    except Exception as e:
        print(f"Error in auto product detection: {str(e)}")
        # Don't raise - this is optional enhancement
        pass


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


@router.get("/drawings/{product_name}")
async def get_product_drawing(
    product_name: str,
    document_type: str = "technical_drawing",
    db: Session = Depends(get_db)
):
    """Serve product document (drawing, catalog, etc.)"""
    from fastapi.responses import FileResponse
    
    # Query database for the product document
    product_doc = db.query(ProductDocument).join(Document).filter(
        ProductDocument.product_name == product_name,
        ProductDocument.document_type == document_type,
        ProductDocument.is_active == True
    ).order_by(ProductDocument.display_order).first()
    
    if not product_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {document_type} available for product: {product_name}"
        )
    
    # Get the actual document file path
    file_path = Path(product_doc.document.file_path)
    
    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file not found: {product_doc.document.original_filename}"
        )
    
    # Return the PDF file with inline disposition so the browser can preview it
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=product_doc.document.original_filename,
        headers={
            "Content-Disposition": f"inline; filename={product_doc.document.original_filename}",
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.get("/products/list")
def list_product_documents(
    product_name: str = None,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all product-document mappings (admin only)"""
    query = db.query(ProductDocument).join(Document)
    
    if product_name:
        query = query.filter(ProductDocument.product_name == product_name)
    
    product_docs = query.order_by(
        ProductDocument.product_name,
        ProductDocument.display_order
    ).all()
    
    return [
        {
            "id": pd.id,
            "product_name": pd.product_name,
            "document_type": pd.document_type,
            "document_id": pd.document_id,
            "document_filename": pd.document.original_filename,
            "display_order": pd.display_order,
            "is_active": pd.is_active,
            "created_at": pd.created_at,
            "updated_at": pd.updated_at
        }
        for pd in product_docs
    ]


@router.get("/products/{product_name}")
def get_product_documents(
    product_name: str,
    db: Session = Depends(get_db)
):
    """List all documents for a specific product"""
    product_docs = db.query(ProductDocument).join(Document).filter(
        ProductDocument.product_name == product_name,
        ProductDocument.is_active == True
    ).order_by(ProductDocument.display_order).all()
    
    return [
        {
            "id": pd.id,
            "document_type": pd.document_type,
            "document_id": pd.document_id,
            "document_filename": pd.document.original_filename,
            "display_order": pd.display_order,
            "url": f"/api/documents/drawings/{product_name}?document_type={pd.document_type}"
        }
        for pd in product_docs
    ]


@router.post("/products")
def link_document_to_product(
    product_name: str,
    document_id: int,
    document_type: str,
    display_order: int = 0,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Link a document to a product (admin only)"""
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}"
        )
    
    # Verify document_type is valid
    try:
        doc_type_enum = ProductDocumentType(document_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type: {document_type}. Must be one of: {[t.value for t in ProductDocumentType]}"
        )
    
    # Check if link already exists
    existing = db.query(ProductDocument).filter(
        ProductDocument.product_name == product_name,
        ProductDocument.document_id == document_id,
        ProductDocument.document_type == doc_type_enum
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This document is already linked to this product with this type"
        )
    
    # Create the link
    product_doc = ProductDocument(
        product_name=product_name,
        document_type=doc_type_enum,
        document_id=document_id,
        display_order=display_order,
        is_active=True
    )
    
    db.add(product_doc)
    db.commit()
    db.refresh(product_doc)
    
    return {
        "id": product_doc.id,
        "product_name": product_doc.product_name,
        "document_type": product_doc.document_type,
        "document_id": product_doc.document_id,
        "document_filename": document.original_filename,
        "display_order": product_doc.display_order,
        "is_active": product_doc.is_active
    }


@router.delete("/products/{link_id}")
def unlink_document_from_product(
    link_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Unlink a document from a product (admin only)"""
    product_doc = db.query(ProductDocument).filter(ProductDocument.id == link_id).first()
    
    if not product_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product-document link not found: {link_id}"
        )
    
    db.delete(product_doc)
    db.commit()
    
    return {"message": "Product-document link deleted successfully"}
