from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class EnquiryStatus(str, enum.Enum):
    COLLECTING_INFO = "collecting_info"
    DRAFT_READY = "draft_ready"
    SENT_TO_ADMIN = "sent_to_admin"
    APPROVED = "approved"
    REJECTED = "rejected"


class QuoteStatus(str, enum.Enum):
    PENDING_ADMIN = "pending_admin"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_TO_CUSTOMER = "sent_to_customer"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(SQLEnum(UserRole), default=UserRole.CUSTOMER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    enquiries = relationship("Enquiry", back_populates="customer")
    quotes_reviewed = relationship("Quote", foreign_keys="Quote.reviewed_by")


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.UPLOADED)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    error_message = Column(Text)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    chunk_index = Column(Integer)
    content = Column(Text)
    vector_id = Column(String(255), unique=True)
    
    # Pricing metadata
    item_name = Column(String(255))
    base_price = Column(Float)
    price_unit = Column(String(50))
    conditions = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class DecisionTree(Base):
    __tablename__ = "decision_trees"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    tree_config = Column(JSON, nullable=False)  # Stores questions, pricing rules, etc.
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Enquiry(Base):
    __tablename__ = "enquiries"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    initial_message = Column(Text)
    status = Column(SQLEnum(EnquiryStatus), default=EnquiryStatus.COLLECTING_INFO)
    collected_data = Column(JSON, default=dict)
    service_tree_id = Column(Integer, ForeignKey("decision_trees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("User", back_populates="enquiries")
    messages = relationship("EnquiryMessage", back_populates="enquiry", order_by="EnquiryMessage.created_at")
    quotes = relationship("Quote", back_populates="enquiry")


class EnquiryMessage(Base):
    __tablename__ = "enquiry_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    enquiry_id = Column(Integer, ForeignKey("enquiries.id"))
    role = Column(String(50))  # 'customer' or 'assistant'
    content = Column(Text)
    image_url = Column(String(500), nullable=True)  # Store uploaded image path/URL
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    enquiry = relationship("Enquiry", back_populates="messages")


class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(Integer, primary_key=True, index=True)
    enquiry_id = Column(Integer, ForeignKey("enquiries.id"))
    item_name = Column(String(255))
    quantity = Column(Float)
    unit = Column(String(50))
    base_price = Column(Float)
    adjustments = Column(JSON)  # List of adjustments
    total_price = Column(Float)
    conditions = Column(JSON)  # List of conditions
    source_chunks = Column(JSON)  # List of chunk IDs used
    status = Column(SQLEnum(QuoteStatus), default=QuoteStatus.PENDING_ADMIN)
    admin_notes = Column(Text)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    enquiry = relationship("Enquiry", back_populates="quotes")
    reviewer = relationship("User", foreign_keys=[reviewed_by], overlaps="quotes_reviewed")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100))  # e.g., 'created', 'edited', 'approved'
    description = Column(Text)
    previous_state = Column(JSON)
    new_state = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
