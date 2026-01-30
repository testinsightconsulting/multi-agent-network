"""RAG engine for querying device documentation"""
from typing import List, Optional, Dict, Tuple
import hashlib
import math
import re
from pathlib import Path

# ChromaDB: use PersistentClient (new API); see https://docs.trychroma.com/deployment/migration
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200
MAX_UPSERT_BATCH = 1000
MAX_CHUNKS_PER_DOC = 3000


class RAGEngine:
    """RAG engine for querying device documentation"""
    

    def __init__(self, knowledge_base_root: str = "knowledge_base"):
        self.knowledge_base_root = Path(knowledge_base_root)
        self.collections: Dict[str, object] = {}
        self._text_cache: Dict[Path, Tuple[float, str]] = {}
        
        if CHROMADB_AVAILABLE:
            try:
                persist_path = str(self.knowledge_base_root / ".chroma")
                self.client = chromadb.PersistentClient(path=persist_path)
                self._initialize_collections()
                # Auto-ingestion removed for performance. Use scripts/ingest_kb.py
            except Exception as e:
                print(f"Warning: Could not initialize ChromaDB: {e}")
                self.client = None
        else:
            self.client = None
            print("Warning: ChromaDB not available. RAG will use simple file search.")

        if not PDF_AVAILABLE:
            print("Warning: pypdf not available. PDF ingestion disabled.")
    
    def _initialize_collections(self):
        """Initialize vector collections for each device type."""
        if not self.client:
            return
        for device_type in self._discover_device_types():
            self._get_or_create_collection(device_type)

    def _discover_device_types(self) -> List[str]:
        """Discover device types from knowledge_base subdirectories."""
        if not self.knowledge_base_root.exists():
            return ["generic"]
        device_types = [
            p.name.strip().lower()
            for p in self.knowledge_base_root.iterdir()
            if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_")
        ]
        return sorted(set(device_types)) or ["generic"]

    def _get_or_create_collection(self, device_type: str):
        """Get or create a collection for the given device type."""
        if not self.client:
            return None
        key = (device_type or "generic").strip().lower()
        if key not in self.collections:
            try:
                self.collections[key] = self.client.get_or_create_collection(
                    name=f"{key}_docs",
                    metadata={"device_type": key}
                )
            except Exception as e:
                print(f"Warning: Could not create collection for {key}: {e}")
                return None
        return self.collections[key]
    
    def query(self, query: str, device_type: str = "generic", top_k: int = 3) -> str:
        """Query the knowledge base"""
        device_key = (device_type or "generic").strip().lower()
        collection = self._get_or_create_collection(device_key) if self.client else None
        if not self.client or not collection:
            # Fallback to simple file search
            return self._simple_file_search(query, device_key)
        
        try:
            results = collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            if results and results['documents']:
                return "\n\n".join(results['documents'][0])
            return ""
        except Exception as e:
            print(f"Error querying RAG: {e}")
            return self._simple_file_search(query, device_key)

    def ingest_all(self) -> Dict[str, int]:
        """Ingest all documents from the knowledge base into ChromaDB (manual trigger)."""
        stats = {}
        if not self.client:
            print("ChromaDB not available.")
            return stats
            
        for dtype in self._discover_device_types():
            print(f"Ingesting {dtype}...")
            count = 0
            collection = self._get_or_create_collection(dtype)
            if not collection:
                continue
            for file_path in self._iter_document_paths(dtype):
                try:
                    self._ingest_file(collection, dtype, file_path)
                    count += 1
                except Exception as e:
                    print(f"Failed to ingest {file_path}: {e}")
            stats[dtype] = count
        return stats

    def ingest_knowledge_base(self, device_type: Optional[str] = None) -> None:
        """Legacy method retained for compatibility, but now optional."""
        if not self.client:
            return
        device_types = [device_type] if device_type else self._discover_device_types()
        for dtype in device_types:
            collection = self._get_or_create_collection(dtype)
            if not collection:
                continue
            for file_path in self._iter_document_paths(dtype):
                self._ingest_file(collection, dtype, file_path)
    
    def _simple_file_search(self, query: str, device_type: str) -> str:
        """Simple fallback file search (txt, md, pdf)."""
        device_path = self.knowledge_base_root / device_type
        if not device_path.exists():
            return ""

        keywords = [k.lower() for k in (query or "").split() if k.strip()]
        if not keywords:
            return ""

        results: List[str] = []
        for file_path in self._iter_document_paths(device_type):
            try:
                # OPTIMIZATION: Check mtime before reading if we have a cache mechanism
                # For simple search, we just read.
                content = self._get_file_text(file_path)
                if not content:
                    continue
                lowered = content.lower()
                if any(keyword in lowered for keyword in keywords):
                    results.append(content[:500])  # First 500 chars
            except Exception:
                continue

        return "\n\n".join(results[:3]) if results else ""

    def _iter_document_paths(self, device_type: str) -> List[Path]:
        """Return supported document paths for a device type."""
        device_path = self.knowledge_base_root / device_type
        if not device_path.exists():
            return []
        return [
            p for p in device_path.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

    def _get_file_text(self, file_path: Path) -> str:
        """Return cached or extracted text for a file."""
        try:
            mtime = file_path.stat().st_mtime
        except Exception:
            return ""
        cached = self._text_cache.get(file_path)
        if cached and cached[0] == mtime:
            return cached[1]

        suffix = file_path.suffix.lower()
        text = ""
        if suffix in SUPPORTED_TEXT_EXTENSIONS:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
        elif suffix in SUPPORTED_PDF_EXTENSIONS:
            text = self._read_pdf_text(file_path)

        self._text_cache[file_path] = (mtime, text)
        return text

    def _read_pdf_text(self, file_path: Path) -> str:
        """Extract text from a PDF file."""
        if not PDF_AVAILABLE:
            return ""
        try:
            reader = PdfReader(str(file_path))
            pages = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    pages.append(page_text)
            return "\n".join(pages)
        except Exception:
            return ""

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
        max_chunks: int = MAX_CHUNKS_PER_DOC,
    ) -> List[str]:
        """Chunk text with overlap."""
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned:
            return []
        
        # Simple sliding window with overlap
        chunks = []
        if len(cleaned) <= chunk_size:
            return [cleaned]
        
        # Ensure we make progress
        step = max(1, chunk_size - overlap)
        
        for i in range(0, len(cleaned), step):
            chunk = cleaned[i:i + chunk_size]
            chunks.append(chunk)
            if i + chunk_size >= len(cleaned):
                break
                
        # Limit total chunks to prevent exploding on massive files
        if max_chunks and len(chunks) > max_chunks:
            return chunks[:max_chunks]
            
        return chunks

    def _ingest_file(self, collection, device_type: str, file_path: Path) -> None:
        """Ingest a single file into a collection."""
        print(f"  - Processing {file_path.name}...")
        text = self._get_file_text(file_path)
        if not text.strip():
            return

        chunks = self._chunk_text(text)
        if not chunks:
            return

        source = str(file_path)
        # Delete existing chunks for this file
        try:
            collection.delete(where={"source": source})
        except Exception:
            pass

        try:
            total_chunks = len(chunks)
            for start in range(0, total_chunks, MAX_UPSERT_BATCH):
                end = min(start + MAX_UPSERT_BATCH, total_chunks)
                batch = chunks[start:end]
                ids = [self._make_chunk_id(source, idx) for idx in range(start, end)]
                metadatas = [
                    {
                        "source": source,
                        "device_type": (device_type or "generic").strip().lower(),
                        "chunk": idx,
                        "total_chunks": total_chunks,
                        "file_name": file_path.name,
                        "file_type": file_path.suffix.lower().lstrip("."),
                    }
                    for idx in range(start, end)
                ]
                collection.upsert(documents=batch, ids=ids, metadatas=metadatas)
        except Exception as e:
            print(f"Warning: Could not ingest {file_path.name}: {e}")

    @staticmethod
    def _make_chunk_id(source: str, chunk_index: int) -> str:
        digest = hashlib.sha256(f"{source}:{chunk_index}".encode("utf-8")).hexdigest()
        return digest

