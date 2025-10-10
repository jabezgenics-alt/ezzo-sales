from pydantic_settings import BaseSettings
from typing import List, ClassVar, Dict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    
    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "ezzo_knowledge_base"
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application
    APP_NAME: str = "Ezzo Sales AI Quotation System"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10485760  # 10MB
    
    # Product Drawings (ClassVar so Pydantic doesn't treat as field)
    PRODUCT_DRAWINGS: ClassVar[Dict[str, str]] = {
        "cat_ladder": "CATLADDER WCAGE.pdf",
        # Future: add more products
    }
    
    # Admin
    ADMIN_EMAIL: str = "admin@ezzo.com"
    ADMIN_PASSWORD: str
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
