import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any
from app.config import settings as app_settings
import uuid
from openai import OpenAI


class VectorStore:
    """ChromaDB vector store for fast semantic search using OpenAI embeddings"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=app_settings.OPENAI_API_KEY)
        self.embedding_model = "text-embedding-ada-002"
        
        self.client = chromadb.PersistentClient(
            path=app_settings.CHROMA_PERSIST_DIR,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self.collection = self.client.get_or_create_collection(
            name=app_settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    
    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI's text-embedding-ada-002"""
        import logging
        logger = logging.getLogger(__name__)
        
        text = text.replace("\n", " ")
        logger.info(f"🤖 Generating embedding using OpenAI model: {self.embedding_model}")
        
        response = self.openai_client.embeddings.create(
            input=[text],
            model=self.embedding_model
        )
        
        logger.info(f"✅ Successfully generated embedding with dimension: {len(response.data[0].embedding)}")
        return response.data[0].embedding
    
    def add_chunk(
        self,
        chunk_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Add a chunk to the vector store with OpenAI embedding"""
        # Generate embedding using OpenAI
        embedding = self._get_embedding(content)
        
        # Add to ChromaDB collection
        self.collection.add(
            ids=[chunk_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata]
        )
        
        return chunk_id
    
    def search(
        self,
        query: str,
        limit: int = 5,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks using OpenAI embeddings"""
        # Generate query embedding using OpenAI
        query_embedding = self._get_embedding(query)
        
        where = filters if filters else None
        
        # Query with embedding vector instead of text
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and len(results['ids']) > 0:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        return formatted_results
    
    def delete_chunk(self, vector_id: str):
        """Delete a chunk from the vector store"""
        self.collection.delete(ids=[vector_id])
    
    def delete_document_chunks(self, document_id: int):
        """Delete all chunks for a document"""
        self.collection.delete(
            where={"document_id": document_id}
        )
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        return {
            "count": self.collection.count(),
            "name": self.collection.name
        }


# Singleton instance
vector_store = VectorStore()
