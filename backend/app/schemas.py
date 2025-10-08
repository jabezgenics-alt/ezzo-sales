from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models import UserRole, DocumentStatus, EnquiryStatus, QuoteStatus


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


# Document Schemas
class DocumentUpload(BaseModel):
    pass  # File will be handled by UploadFile


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: Optional[str]
    file_size: Optional[int]
    status: DocumentStatus
    summary: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True


class DocumentSummaryUpdate(BaseModel):
    summary: str


# Knowledge Chunk Schemas
class KnowledgeChunkResponse(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    item_name: Optional[str]
    base_price: Optional[float]
    price_unit: Optional[str]
    conditions: Optional[Dict[str, Any]]
    location: Optional[str]
    source_reference: Optional[str]
    
    class Config:
        from_attributes = True


class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    chunk: KnowledgeChunkResponse
    similarity: float


# Enquiry Schemas
class EnquiryCreate(BaseModel):
    initial_message: str


class EnquiryMessageCreate(BaseModel):
    content: str
    image_url: Optional[str] = None


class EnquiryMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    image_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class EnquiryResponse(BaseModel):
    id: int
    customer_id: int
    initial_message: str
    status: EnquiryStatus
    collected_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    messages: List[EnquiryMessageResponse] = []
    
    class Config:
        from_attributes = True


class EnquiryAnswerRequest(BaseModel):
    question_key: str
    answer: str


# Quote Schemas
class QuoteAdjustment(BaseModel):
    description: str
    amount: float
    type: str  # 'fixed' or 'percentage'


class QuoteCreate(BaseModel):
    item_name: str
    quantity: float
    unit: str
    base_price: float
    adjustments: List[QuoteAdjustment] = []
    conditions: List[str] = []
    source_chunks: List[int] = []


class QuoteUpdate(BaseModel):
    item_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    base_price: Optional[float] = None
    adjustments: Optional[List[QuoteAdjustment]] = None
    total_price: Optional[float] = None
    conditions: Optional[List[str]] = None
    admin_notes: Optional[str] = None


class QuoteResponse(BaseModel):
    id: int
    enquiry_id: int
    item_name: str
    quantity: Optional[float]
    unit: Optional[str]
    base_price: float
    adjustments: List[Dict[str, Any]]
    total_price: float
    conditions: List[Any]
    source_chunks: List[int]
    status: QuoteStatus
    admin_notes: Optional[str]
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class QuoteApprovalRequest(BaseModel):
    admin_notes: Optional[str] = None


class QuoteRejectionRequest(BaseModel):
    admin_notes: str
    reason: str


# Draft Quote Preview
class ConversationTitleRequest(BaseModel):
    message: str

class DraftQuotePreview(BaseModel):
    item_name: str
    base_price: float
    unit: str
    quantity: Optional[float]
    adjustments: List[QuoteAdjustment]
    total_price: float
    conditions: List[str]
    source_references: List[str]
    missing_info: List[str] = []
    can_submit: bool


# Audit Schemas
class AuditLogResponse(BaseModel):
    id: int
    quote_id: int
    user_id: Optional[int]
    action: str
    description: Optional[str]
    previous_state: Optional[Dict[str, Any]]
    new_state: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Decision Tree Schemas
class TreeQuestion(BaseModel):
    id: str
    question: str
    type: str  # 'text', 'choice', 'boolean', 'number'
    choices: Optional[List[str]] = None
    required: bool = True
    next: Optional[Dict[str, str]] = None  # For branching: {"answer": "next_question_id"}

class PricingRules(BaseModel):
    search_query: str
    calculation_type: str  # 'per_meter', 'per_unit', 'per_sqft'
    components: List[str]  # e.g., ['base_rate', 'cage_rungs', 'access_door']

class TreeConfig(BaseModel):
    questions: List[TreeQuestion]
    pricing_rules: PricingRules
    start_question: Optional[str] = None  # ID of first question (for branching), if None uses first in list

class DecisionTreeCreate(BaseModel):
    service_name: str
    display_name: str
    description: Optional[str] = None
    tree_config: TreeConfig

class DecisionTreeUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    tree_config: Optional[TreeConfig] = None
    is_active: Optional[bool] = None

class DecisionTreeResponse(BaseModel):
    id: int
    service_name: str
    display_name: str
    description: Optional[str]
    tree_config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# AI Response Schemas
class AIQuestion(BaseModel):
    key: str
    question: str
    type: str  # 'text', 'choice', 'boolean', 'number'
    choices: Optional[List[str]] = None
    required: bool = True


class AIResponse(BaseModel):
    message: str
    questions: List[AIQuestion] = []
    draft_available: bool = False
    draft_quote: Optional['DraftQuotePreview'] = None
    id: Optional[int] = None  # Add enquiry ID for frontend
