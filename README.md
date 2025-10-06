# Ezzo Sales - AI Quotation System

A comprehensive AI-powered quotation system with document processing, RAG-based knowledge base, and intelligent customer interaction using GPT-5.

## 🏗️ Architecture

```
[Document Upload] → [GPT-5 Parser & Chunker] → [MySQL + ChromaDB]
                                                         ↓
[Customer Enquiry] → [GPT-5 AI Assistant] → [RAG Retrieval (Highest Price)]
                                                         ↓
[Guided Questions] → [Draft Quote] → [Admin Review] → [Final Quote]
                                                         ↓
                                              [Full Audit Trail]
```

## ✨ Features

### Core Components

**A. Document Processing**
- Upload PDFs, CSVs, chatlogs
- GPT-5 powered parsing and extraction
- OCR support for images
- Structured data extraction (items, prices, conditions)

**B. Knowledge Base**
- MySQL for structured data
- ChromaDB for fast vector search
- Always fetches all relevant entries
- **Always uses highest price** (rule enforced)

**C. AI Assistant**
- GPT-5 powered customer interaction
- Guided questions to collect requirements
- Context-aware responses
- Builds draft incrementally

**D. Quote Calculation Engine**
- Dynamic pricing (no hardcoded values)
- Automatic adjustments based on:
  - Furniture shifting
  - Varnish type (water/oil-based)
  - Day/night job timing
  - Location surcharge
  - Urgency premium
- Full traceability

**E. Admin Panel**
- Review pending quotes
- Edit prices and conditions
- Approve/reject quotes
- Send to customers
- View audit trails

**F. Audit System**
- Logs all quote changes
- Before/after snapshots
- Full traceability
- User actions tracked

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- MySQL database access
- OpenAI API key

### Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Create database
python create_db.py

# Run migrations
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the start script:
```bash
chmod +x start.sh
./start.sh
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## 📝 Configuration

### Backend (.env)

```env
# Database
DATABASE_URL=mysql+pymysql://ezzo_user:246411@217.160.19.34:3306/ezzo-sales

# OpenAI (GPT-5)
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4o

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION_NAME=ezzo_knowledge_base

# Admin
ADMIN_EMAIL=admin@ezzo.com
ADMIN_PASSWORD=admin123
```

## 🔑 Key Rules (Enforced)

1. ✅ **All prices from Knowledge Base** - No hardcoding
2. ✅ **Always pick highest price** if multiple matches
3. ✅ **Guided questions** before drafting
4. ✅ **Admin approval required** before sending to customer
5. ✅ **Full traceability** - All actions logged

## 📊 Tech Stack

**Backend:**
- FastAPI (Python)
- MySQL (structured data)
- ChromaDB (vector search)
- OpenAI GPT-5 (AI processing)
- SQLAlchemy (ORM)
- Alembic (migrations)

**Frontend:**
- React 18
- Vite
- TailwindCSS
- Radix UI
- React Router
- Zustand (state)
- Axios (HTTP)

## 🎯 User Flows

### Customer Flow

1. Register/Login
2. Create enquiry ("I need parquet flooring for 3 bedrooms")
3. AI asks guided questions:
   - Area size?
   - Location?
   - Furniture shifting needed?
   - Varnish type preference?
   - Day or night job?
4. View draft quote preview
5. Submit to admin
6. Receive approved quote

### Admin Flow

1. Login as admin
2. View pending quotes
3. Review customer requirements
4. Edit prices/conditions if needed
5. Approve or reject
6. Send to customer
7. View audit trail

## 📁 Project Structure

```
ezzo-sales/
├── backend/
│   ├── app/
│   │   ├── routers/          # API routes
│   │   ├── services/         # Business logic
│   │   ├── models.py         # Database models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── auth.py           # Authentication
│   │   ├── database.py       # DB connection
│   │   └── main.py           # FastAPI app
│   ├── alembic/              # Migrations
│   ├── uploads/              # Uploaded files
│   ├── chroma_db/            # Vector store
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── components/ui/    # UI components
    │   ├── pages/            # Route pages
    │   ├── hooks/            # React hooks
    │   └── lib/              # Utilities
    └── package.json
```

## 🔗 API Endpoints

### Authentication
- `POST /api/auth/register` - Register customer
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user

### Documents (Admin)
- `POST /api/documents/upload` - Upload document
- `POST /api/documents/{id}/process` - Process document
- `GET /api/documents/` - List documents
- `DELETE /api/documents/{id}` - Delete document

### Knowledge Base
- `POST /api/kb/search` - Search KB
- `GET /api/kb/chunks` - List chunks (admin)
- `GET /api/kb/stats` - KB statistics (admin)

### Enquiries (Customer)
- `POST /api/enquiries/` - Create enquiry
- `GET /api/enquiries/` - List enquiries
- `POST /api/enquiries/{id}/message` - Send message
- `POST /api/enquiries/{id}/answer` - Answer question
- `GET /api/enquiries/{id}/draft` - Get draft quote
- `POST /api/enquiries/{id}/submit` - Submit to admin

### Admin
- `GET /api/admin/quotes/pending` - Pending quotes
- `GET /api/admin/quotes` - All quotes
- `PUT /api/admin/quotes/{id}` - Edit quote
- `POST /api/admin/quotes/{id}/approve` - Approve
- `POST /api/admin/quotes/{id}/reject` - Reject
- `GET /api/admin/quotes/{id}/audit` - Audit trail

## 🔐 Default Credentials

**Admin:**
- Email: `admin@ezzo.com`
- Password: `admin123`

## 🧪 Testing

### Upload Test Document

1. Login as admin
2. Go to Documents page
3. Upload a PDF with pricing info like:
```
Parquet Flooring
Price: ₱1200 per m²
Conditions:
- Manila area only
- Oil-based varnish included
- Minimum 20m²
```

4. Process the document
5. Check Knowledge Base to verify chunks

### Create Test Enquiry

1. Login as customer
2. Create enquiry: "I need parquet flooring for 3 bedrooms"
3. Answer AI questions
4. View draft quote
5. Submit to admin

### Admin Review

1. Login as admin
2. View pending quotes
3. Review and approve
4. Check audit trail

## 📈 Future Enhancements

- [ ] Email notifications
- [ ] PDF quote generation
- [ ] Multi-language support
- [ ] Advanced analytics
- [ ] Mobile app
- [ ] Webhook integrations
- [ ] Custom pricing rules engine

## 🐛 Troubleshooting

**Database Connection Issues:**
```bash
# Test connection
python -c "from app.config import settings; print(settings.DATABASE_URL)"
```

**ChromaDB Issues:**
```bash
# Clear and rebuild
rm -rf chroma_db/
# Reprocess documents
```

**OpenAI API Issues:**
```bash
# Verify API key
python -c "from app.config import settings; print(settings.OPENAI_API_KEY[:10])"
```

## 📞 Support

For issues or questions, check the documentation or create an issue.

## 📄 License

Proprietary - Ezzo Sales © 2025
