from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, KnowledgeChunk
from app.schemas import KnowledgeChunkResponse, KnowledgeSearchRequest, KnowledgeSearchResult
from app.auth import get_current_user, get_current_admin
from app.services.vector_store import vector_store

router = APIRouter(prefix="/api/kb", tags=["Knowledge Base"])


@router.post("/search", response_model=List[KnowledgeSearchResult])
def search_knowledge_base(
    search_data: KnowledgeSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search knowledge base"""
    
    # Search vector store
    results = vector_store.search(search_data.query, limit=search_data.limit)
    
    if not results:
        return []
    
    # Get chunk IDs
    chunk_ids = []
    for result in results:
        metadata = result.get('metadata', {})
        if metadata.get('chunk_id'):
            chunk_ids.append(metadata['chunk_id'])
    
    # Fetch chunks from database
    chunks = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.id.in_(chunk_ids)
    ).all()
    
    # Create chunk lookup
    chunk_lookup = {chunk.id: chunk for chunk in chunks}
    
    # Format results
    formatted_results = []
    for result in results:
        metadata = result.get('metadata', {})
        chunk_id = metadata.get('chunk_id')
        
        if chunk_id and chunk_id in chunk_lookup:
            chunk = chunk_lookup[chunk_id]
            
            # Calculate similarity (convert distance to similarity)
            distance = result.get('distance', 1.0)
            similarity = 1.0 - distance if distance is not None else 0.0
            
            formatted_results.append(KnowledgeSearchResult(
                chunk=KnowledgeChunkResponse.from_orm(chunk),
                similarity=similarity
            ))
    
    return formatted_results


@router.get("/chunks", response_model=List[KnowledgeChunkResponse])
def list_chunks(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all knowledge chunks (admin only)"""
    
    chunks = db.query(KnowledgeChunk).offset(skip).limit(limit).all()
    return chunks


@router.get("/chunks/{chunk_id}", response_model=KnowledgeChunkResponse)
def get_chunk(
    chunk_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chunk details"""
    
    chunk = db.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).first()
    
    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunk not found"
        )
    
    return chunk


@router.get("/stats")
def get_kb_stats(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get knowledge base statistics"""
    
    total_chunks = db.query(KnowledgeChunk).count()
    chunks_with_price = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.base_price.isnot(None)
    ).count()
    
    vector_stats = vector_store.get_collection_stats()
    
    return {
        "total_chunks": total_chunks,
        "chunks_with_price": chunks_with_price,
        "vector_store": vector_stats
    }
