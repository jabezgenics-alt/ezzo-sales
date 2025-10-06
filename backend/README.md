# Ezzo Sales AI Quotation System - Backend

A comprehensive AI-powered quotation system with document processing, RAG-based knowledge base, and intelligent customer interaction.

## Features

- **Document Processing**: Upload and parse PDFs, chatlogs, CSVs with GPT-5
- **Knowledge Base**: MySQL + ChromaDB for fast vector search
- **AI Assistant**: GPT-5-powered customer interaction with guided questions
- **Quote Calculation**: Dynamic pricing with adjustments (no hardcoding)
- **Admin Panel**: Review, edit, and approve quotes
- **Audit Trail**: Full traceability of all quotes

## Architecture

```
[Document Upload] → [Parser & Chunker (GPT-5)] → [Knowledge Base]
                                                         ↓
[Customer Enquiry] → [AI Assistant (GPT-5)] → [RAG Retrieval]
                                                         ↓
[Guided Questions] → [Draft Quote] → [Admin Review] → [Final Quote]
                                                         ↓
                                              [Audit Log]
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update values:

```bash
cp .env.example .env
```

### 3. Initialize Database

```bash
# Create MySQL database
mysql -h 217.160.19.34 -u ezzo_user -p246411 -e "CREATE DATABASE IF NOT EXISTS ezzo_sales;"

# Run migrations
alembic upgrade head
```

### 4. Run Application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login (customer/admin)
- `POST /api/auth/register` - Register customer

### Documents
- `POST /api/documents/upload` - Upload documents (admin)
- `GET /api/documents/` - List documents
- `POST /api/documents/process/{id}` - Process document

### Knowledge Base
- `GET /api/kb/search` - Search knowledge base
- `GET /api/kb/chunks` - List all chunks

### Customer Interaction
- `POST /api/enquiries/` - Create enquiry
- `GET /api/enquiries/{id}` - Get enquiry
- `POST /api/enquiries/{id}/answer` - Answer question
- `GET /api/enquiries/{id}/draft` - Get draft quote

### Admin
- `GET /api/admin/quotes/pending` - Get pending quotes
- `POST /api/admin/quotes/{id}/approve` - Approve quote
- `POST /api/admin/quotes/{id}/edit` - Edit quote
- `POST /api/admin/quotes/{id}/reject` - Reject quote

### Audit
- `GET /api/audit/quotes/{id}` - Get quote audit trail

## Key Rules

1. ✅ All prices from Knowledge Base (no hardcoding)
2. ✅ Always pick highest price if multiple matches
3. ✅ Guided questions before drafting
4. ✅ Admin approval required
5. ✅ Full traceability

## Tech Stack

- **Framework**: FastAPI
- **Database**: MySQL
- **Vector DB**: ChromaDB
- **AI**: OpenAI GPT-5
- **Auth**: JWT
- **Document Processing**: PyPDF, Tesseract
