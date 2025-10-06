# Ezzo Sales Frontend

Modern React frontend for the AI Quotation System with beautiful UI using Tailwind CSS and Radix UI.

## Features

- 🎨 Modern UI with TailwindCSS
- 🔐 Authentication (Login/Register)
- 📱 Responsive sidebar navigation
- 👤 Customer enquiries and quotes
- 👨‍💼 Admin dashboard for quote management
- 📄 Document upload and knowledge base management

## Tech Stack

- **React 18** - UI library
- **Vite** - Build tool
- **React Router** - Routing
- **TailwindCSS** - Styling
- **Radix UI** - Headless UI components
- **Lucide React** - Icons
- **Zustand** - State management
- **Axios** - HTTP client

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Run Development Server

```bash
npm run dev
```

The app will run on `http://localhost:3000`

### 3. Build for Production

```bash
npm run build
```

## Project Structure

```
src/
├── components/
│   └── ui/              # UI components (Sidebar, Button, etc.)
├── hooks/
│   └── useAuth.js       # Authentication hook
├── pages/
│   ├── Login.jsx
│   ├── Register.jsx
│   ├── Dashboard.jsx
│   ├── Enquiries.jsx
│   ├── Quotes.jsx
│   └── admin/           # Admin pages
├── lib/
│   └── utils.js         # Utility functions
├── App.jsx              # Main app component
├── main.jsx             # Entry point
└── index.css            # Global styles
```

## Features

### Customer Features
- Create enquiries
- Chat with AI assistant
- View draft quotes
- Submit quotes to admin
- View approved quotes

### Admin Features
- Review pending quotes
- Approve/reject quotes
- Edit quote details
- Upload documents
- Manage knowledge base
- View audit trails

## Default Credentials

**Admin:**
- Email: admin@ezzo.com
- Password: admin123

## API Integration

The frontend connects to the FastAPI backend at `http://localhost:8000/api`
