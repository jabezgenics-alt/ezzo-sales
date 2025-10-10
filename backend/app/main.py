from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import warnings
from app.config import settings
from app.database import init_db, get_db
from app.models import User, UserRole
from app.auth import create_user
from app.routers import auth, documents, enquiries, admin, knowledge, decision_trees, business_rules

# Suppress ChromaDB telemetry warnings
warnings.filterwarnings('ignore', message='.*telemetry.*')
logging.getLogger('chromadb').setLevel(logging.ERROR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("Starting Ezzo Sales AI Quotation System...")
    
    # Initialize database
    init_db()
    print("Database initialized")
    
    # Skip admin user check - handled separately
    print("Admin setup skipped for faster startup")
    
    print(f"Server running on http://localhost:8000")
    print(f"API docs available at http://localhost:8000/docs")
    
    yield
    
    # Shutdown
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered quotation system with document processing, RAG, and intelligent customer interaction",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(enquiries.router)
app.include_router(admin.router)
app.include_router(knowledge.router)
app.include_router(decision_trees.router)
app.include_router(business_rules.router)

# Serve uploaded files under /api/uploads so the frontend can access them via the proxy
app.mount("/api/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Ezzo Sales AI Quotation System",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "online"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
