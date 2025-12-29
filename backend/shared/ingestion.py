import pdfplumber
from typing import List, Dict, Any
from dataclasses import dataclass
import logging
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
import os
import uuid

logger = logging.getLogger(__name__)

@dataclass
class Page:
    page_number: int
    text: str

@dataclass
class Chunk:
    id: str
    doc_id: int
    text: str
    page_number: int
    metadata: Dict[str, Any]

class ParsingService:
    @staticmethod
    def parse_pdf(file_path: str) -> List[Page]:
        pages = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages.append(Page(page_number=i+1, text=text))
            return pages
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")
            raise

class ChunkingService:
    @staticmethod
    def chunk_document(doc_id: int, pages: List[Page], chunk_size: int = 500, overlap: int = 50) -> List[Chunk]:
        chunks = []
        for page in pages:
            text = page.text
            # Simple sliding window chunking per page for now
            # TODO: Improve with sentence boundary detection
            
            if not text.strip():
                continue
                
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunk_text = text[start:end]
                
                # Adjust end to nearest space to avoid cutting words
                if end < len(text):
                    last_space = chunk_text.rfind(' ')
                    if last_space != -1:
                        end = start + last_space
                        chunk_text = text[start:end]
                
                chunk_id = str(uuid.uuid4())
                chunks.append(Chunk(
                    id=chunk_id,
                    doc_id=doc_id,
                    text=chunk_text,
                    page_number=page.page_number,
                    metadata={"filename": "TODO", "type": "text"} 
                ))
                
                # Ensure we advance, preventing infinite loop if chunk is small
                stride = len(chunk_text) - overlap
                if stride <= 0:
                    stride = max(1, len(chunk_text)) # Advance by at least 1 or full chunk if small
                
                start += stride
                
                if start >= len(text):
                    break
        return chunks

class VectorService:
    def __init__(self, collection_name: str = "contract_chunks"):
        # Models are downloaded to /root/.cache/torch/sentence_transformers
        # Should be cached in docker volume ideally, but okay for MVP
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        qdrant_host = os.getenv("QDRANT_HOST", "qdrant")
        qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.collection_name = collection_name
        
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.qdrant.get_collection(self.collection_name)
            logger.info(f"Collection {self.collection_name} exists.")
        except Exception:
            # If get failed, try to create. 
            # Note: In a real prod setup we should check the error type specifically.
            try:
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(size=384, distance=qmodels.Distance.COSINE)
                )
                logger.info(f"Created collection {self.collection_name}.")
            except Exception as e:
                if "already exists" in str(e) or "Conflict" in str(e):
                    logger.info(f"Collection {self.collection_name} already exists (race condition handled).")
                else:
                    raise e

    def upsert_chunks(self, chunks: List[Chunk]):
        if not chunks:
            return
            
        logger.info(f"Upserting {len(chunks)} chunks...")
        batch_size = 4 # Small batch size to prevent OOM / debug progress
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            texts = [c.text for c in batch]
            
            logger.info(f"Encoding batch {i} to {i+len(batch)}...")
            try:
                embeddings = self.model.encode(texts)
                logger.info(f"Encoded batch {i}.")
            except Exception as e:
                logger.error(f"Encoding failed: {e}")
                raise e
            
            points = []
            for j, chunk in enumerate(batch):
                points.append(qmodels.PointStruct(
                    id=chunk.id,
                    vector=embeddings[j].tolist(),
                    payload={
                        "text": chunk.text,
                        "doc_id": chunk.doc_id,
                        "page_number": chunk.page_number,
                        **chunk.metadata
                    }
                ))
            
            logger.info(f"Pushing batch {i} to Qdrant...")
            try:
                self.qdrant.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
            except Exception as e:
                logger.error(f"Qdrant push failed: {e}")
                raise e

        logger.info(f"Upserted all {len(chunks)} chunks.")

    def search(self, query: str, limit: int = 5, doc_id: int = None):
        query_vector = self.model.encode(query).tolist()
        
        query_filter = None
        if doc_id:
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="doc_id",
                        match=qmodels.MatchValue(value=doc_id)
                    )
                ]
            )

        results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit
        )
        return results
