
# MultiSource-RAG

# UMKA RAG System

UMKA is an advanced Retrieval-Augmented Generation (RAG) system designed to let you chat conversationally with your unstructured data. By seamlessly ingesting PDFs, Websites, and YouTube video transcripts, the system stores semantic relationships in a locally-hosted FAISS index paired with a MySQL metadata store, and uses the Groq API (LLaMA 3.3) for lightning-fast answer generation.

## 🌟 Key Features

- **Multi-Modal Data Ingestion:**
  - **PDFs:** Support for complex layouts using `pypdf` and `pdfplumber`. 
  - **Websites:** Intelligent scraping and text extraction using BeautifulSoup.
  - **YouTube:** Automatic transcript fetching using `youtube-transcript-api`.
- **Intelligent Chunking & Embeddings:** Powered by HuggingFace's `intfloat/multilingual-e5-large` model generating robust 1024-dimensional vectors.
- **Hybrid Storage Architecture:** 
  - **FAISS:** Used for lightning-fast semantic similarity searches.
  - **MySQL:** Stores exact chunks, chat history, and source metadata, synced to FAISS via UUID mapping.
- **Sleek React Frontend:** Built with Vite and TailwindCSS for a modern, responsive, chat-like User Experience.

---

## 🏗️ Project Architecture

```text
Rag_System_2/
├── backend/                  # FastAPI Application
│   ├── api/                  # Route handlers (history, query, sources, upload)
│   ├── database/             # MySQL schema & connection
│   ├── ingestion/            # File parsing & text chunking logic
│   ├── rag/                  # Retrieval and Groq LLM Generation
│   ├── vectorstore/          # Local FAISS index map management
│   └── main.py               # Application entrypoint
├── frontend/                 # React Application (Vite)
│   ├── src/app/              # API connections and main UI Views
│   └── package.json          # Node dependencies
├── data/                     # Output directory for FAISS bin maps & temporal uploads
└── requirements.txt          # Python dependencies
```

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed on your machine:
1. **Python 3.10+**
2. **Node.js (v18+)**
3. **MySQL Server:** Make sure MySQL is running in the background.
4. **Groq API Key:** Obtain a free key from [console.groq.com](https://console.groq.com/).

---

## 🚀 Setup & Installation

### 1. Database Initialization
1. Log in to your MySQL terminal or GUI (like MySQL Workbench).
2. Execute the setup schema file to create the `rag_system` database and tables:
   ```bash
   mysql -u root -p < backend/database/schema.sql
   ```

### 2. Environment Variables configuration
The application requires `.env` files to keep strings and secrets secure. 

Create **`backend/.env`**:
```env
# Database Credentials
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=rag_system

# LLM APIs
GROQ_API_KEY=gsk_your_api_key_here
```

Create **`frontend/.env`**:
```env
VITE_API_URL=http://127.0.0.1:8000
```

### 3. Start the Backend
Open a terminal and navigate to the project root directory.

```bash
# Create and activate a Virtual Environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Mac/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI Server
uvicorn backend.main:app --reload
```
*The backend will be available at `http://localhost:8000`. On your first run, the local embedding model (`multilingual-e5-large`) will be downloaded automatically (~2.2GB).*

### 4. Start the Frontend
Open a **new** terminal window and navigate into the `frontend/` directory.

```bash
cd frontend

# Install node dependencies
npm install

# Start the Vite development server
npm run dev
```
*The React app will automatically open in your browser or be available at `http://localhost:5173`.*

---

## 📖 How to Use

1. **Ingest Data:** Navigate to the main dashboard or the sidebar. Use the upload modules to drag-and-drop a PDF, drop a website URL, or insert a YouTube video link. 
2. **Track Status:** The file will be passed back to the backend, chunked, embedded, and mapped out. Wait for the loading indicators to confirm success.
3. **Ask AI:** Go to the chat interface. You can apply source filters (e.g., asking questions *only* against a specific set of uploaded documents) or query your entire uploaded knowledge base.
4. **View Context:** The right sidebar will populate showing the exact chunks and "Sources Used" (similar to Perplexity.ai) revealing what the AI analyzed to formulate its response.

