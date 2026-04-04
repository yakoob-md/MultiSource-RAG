# === main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.upload import router as upload_router
from backend.api.query import router as query_router
from backend.api.sources import router as sources_router
from backend.api.delete import router as delete_router


app = FastAPI(title="RAG System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(query_router)
app.include_router(sources_router)
app.include_router(delete_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

#===config.py

from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    documents_dir: Path = data_dir / "documents"
    vector_db_dir: Path = data_dir / "vector_db"

    # Embeddings / models
    embedding_model_name: str = "intfloat/multilingual-e5-small"

    # Vector store
    chroma_collection: str = "documents"

    # LLM (Ollama)
    ollama_model: str = "llama3"
    ollama_base_url: str = "http://localhost:11434"

    # Retrieval
    top_k: int = 8


settings = Settings()

# Ensure data directories exist at import time
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.documents_dir.mkdir(parents=True, exist_ok=True)
settings.vector_db_dir.mkdir(parents=True, exist_ok=True)

#==requirements.txt==
fastapi==0.115.6
uvicorn[standard]==0.32.1
sentence-transformers==3.2.1
chromadb==0.5.23
pypdf==5.1.0
beautifulsoup4==4.12.3
requests==2.32.3
youtube-transcript-api==0.6.2
python-multipart==0.0.20

error when i run the backend
(C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv) C:\Users\dabaa\OneDrive\Desktop\Rag_System\backend>python -m uvicorn main:app --reload --port 8000
INFO:     Will watch for changes in these directories: ['C:\\Users\\dabaa\\OneDrive\\Desktop\\Rag_System\\backend']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [7376] using WatchFiles
Process SpawnProcess-1:
Traceback (most recent call last):
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\multiprocessing\process.py", line 314, in _bootstrap
    self.run()
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\multiprocessing\process.py", line 108, in run
    self._target(*self._args, **self._kwargs)
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\_subprocess.py", line 80, in subprocess_started
    target(sockets=sockets)
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\server.py", line 65, in run
    return asyncio.run(self.serve(sockets=sockets))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\asyncio\runners.py", line 190, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\asyncio\runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\asyncio\base_events.py", line 650, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\server.py", line 69, in serve
    await self._serve(sockets)
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\server.py", line 76, in _serve
    config.load()
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\config.py", line 434, in load
    self.loaded_app = import_from_string(self.app)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\importer.py", line 22, in import_from_string
    raise exc from None
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\importer.py", line 19, in import_from_string
    module = importlib.import_module(module_str)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\importlib\__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1206, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1178, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1149, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 940, in exec_module
  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\backend\main.py", line 4, in <module>
    from backend.api.upload import router as upload_router
ModuleNotFoundError: No module named 'backend'
WARNING:  WatchFiles detected changes in 'main.py'. Reloading...
Process SpawnProcess-2:
Traceback (most recent call last):
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\multiprocessing\process.py", line 314, in _bootstrap
    self.run()
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\multiprocessing\process.py", line 108, in run
    self._target(*self._args, **self._kwargs)
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\_subprocess.py", line 80, in subprocess_started
    target(sockets=sockets)
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\server.py", line 65, in run
    return asyncio.run(self.serve(sockets=sockets))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\asyncio\runners.py", line 190, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\asyncio\runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\asyncio\base_events.py", line 650, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\server.py", line 69, in serve
    await self._serve(sockets)
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\server.py", line 76, in _serve
    config.load()
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\config.py", line 434, in load
    self.loaded_app = import_from_string(self.app)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\importer.py", line 22, in import_from_string
    raise exc from None
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\site-packages\uvicorn\importer.py", line 19, in import_from_string
    module = importlib.import_module(module_str)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv\Lib\importlib\__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1206, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1178, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1149, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 940, in exec_module
  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
  File "C:\Users\dabaa\OneDrive\Desktop\Rag_System\backend\main.py", line 4, in <module>
    from backend.api.upload import router as upload_router
ModuleNotFoundError: No module named 'backend'
INFO:     Stopping reloader process [7376]

(C:\Users\dabaa\OneDrive\Desktop\Rag_System\rag_venv) C:\Users\dabaa\OneDrive\Desktop\Rag_System\backend>ollama list
