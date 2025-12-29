from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from minio import Minio
import os
import uuid
import logging

from shared.database import get_db, engine, Base
from shared.models import Document, DocumentStatus, User, UserRole
from shared.auth import create_access_token, verify_password, get_password_hash, RoleChecker
# from worker.celery_app import celery_app # Deferred import to avoid circular issues if any, but usually fine.
from celery import Celery
from qdrant_client.http import models as qmodels
from pydantic import BaseModel
from typing import Optional, List
from shared.middleware import RequestLoggerMiddleware, RateLimitMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from fastapi import status

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables (Simple init for now, will use Alembic later)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Contract Intelligence API")

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middleware
app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(RateLimitMiddleware, limit=60, window=60)

# MinIO Client
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "documents")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"

minio_client = Minio(
    MINIO_ENDPOINT.replace("http://", "").replace("https://", ""), # Minio client expects host:port
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

# Celery Client (Simple init for pushing tasks)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("worker", broker=REDIS_URL)

@app.get("/health")
def health_check():
    return {"status": "ok", "services": {"database": "connected", "minio": "connected"}}

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    user: User = Depends(RoleChecker(["ap", "admin"]))
):
    try:
        # 1. Generate unique filename
        file_ext = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        
        # 2. Upload to MinIO
        # Check bucket exists
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
        
        # Upload
        # To handle async reads from FastAPI upload file, we might need to read into memory or stream
        # For MVP, read small files into memory
        file_content = await file.read()
        import io
        file_stream = io.BytesIO(file_content)
        
        minio_client.put_object(
            MINIO_BUCKET,
            unique_filename,
            file_stream,
            length=len(file_content),
            content_type=file.content_type
        )
        logger.info(f"Uploaded {unique_filename} to MinIO")

        # 3. Create DB Record
        db_doc = Document(
            filename=file.filename,
            s3_key=unique_filename,
            status=DocumentStatus.PENDING
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)

        # 4. Trigger Worker
        celery_app.send_task("process_document", args=[db_doc.id])
        
        return {"id": db_doc.id, "filename": db_doc.filename, "status": db_doc.status, "message": "Upload successful"}

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from shared.ingestion import VectorService
vector_service = VectorService()

@app.get("/search")
def search_documents(q: str, doc_id: int = None, limit: int = 5):
    try:
        results = vector_service.search(q, limit, doc_id)
        return {"results": [
            {
                "score": hit.score,
                "text": hit.payload.get("text"),
                "page_number": hit.payload.get("page_number"),
                "doc_id": hit.payload.get("doc_id"),
                "metadata": hit.payload
            } for hit in results
        ]}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/chunks/{doc_id}")
def debug_chunks(doc_id: int):
    # This is a bit of a hack to peek at Qdrant
    # In a real app we might query by filter without vector
    try:
        # Dummy search to find chunks for this doc
        # Ideally Qdrant client has scroll() API
        results = vector_service.qdrant.scroll(
            collection_name=vector_service.collection_name,
            scroll_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="doc_id",
                        match=qmodels.MatchValue(value=doc_id)
                    )
                ]
            ),
            limit=100
        )
        points, _ = results
        return {"chunks": [p.payload for p in points]}
    except Exception as e:
        logger.error(f"Debug failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    # Normalize for frontend
    return {"documents": [
        {
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "created_at": d.created_at
        } for d in docs
    ]}

@app.get("/documents/{doc_id}/extraction")
def get_extraction_result(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "result": doc.extraction_result
    }

@app.post("/documents/{doc_id}/analyze")
def analyze_document(doc_id: int, db: Session = Depends(get_db)):
    from shared.comparison import ComparisonGraph
    from shared.models import Finding as DBFinding
    
    # Run Comparison
    try:
        graph = ComparisonGraph(db)
        findings = graph.run(doc_id)
        
        # Save Findings
        db_findings = []
        for f in findings:
            db_f = DBFinding(
                document_id=doc_id,
                finding_type=f.finding_type,
                severity=f.severity,
                description=f.description,
                evidence=f.evidence or {},
                status="open"
            )
            db.add(db_f)
            db_findings.append(db_f)
        
        db.commit()
        return {"status": "success", "findings_count": len(db_findings)}
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{doc_id}/findings")
def get_findings(doc_id: int, db: Session = Depends(get_db)):
    from shared.models import Finding as DBFinding
    findings = db.query(DBFinding).filter(DBFinding.document_id == doc_id).all()
    return {"findings": findings}

@app.post("/contracts/{doc_id}/risk_assessment")
def assess_risk(doc_id: int, db: Session = Depends(get_db)):
    from shared.risk import RiskAssessmentGraph
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Get text from chunks (better than storing huge text in DB, but for now we re-construct or use what we have)
    # Ideally extraction_result has full text? No.
    # We should fetch from Qdrant or store text in extraction?
    # For MVP, let's fetch chunks from Qdrant or just assume we have text access 
    # (Actually we don't store full text in DB).
    # Solution: We will fetch full text from Qdrant chunks for this doc.
    
    try:
        from shared.ingestion import VectorService
        vec = VectorService() # Default collection
        # Hacky: search with empty query to get all chunks? No limit is 100 usually.
        # Better: Re-download from MinIO and parse? Yes, cleaner.
        # But for speed, let's use the text from the Extraction result if available? No.
        
        # Re-download logic (duplicated from worker slightly)
        minio_client.fget_object("documents", doc.s3_key, f"/tmp/{doc.s3_key}")
        from shared.ingestion import ParsingService
        pages = ParsingService.parse_pdf(f"/tmp/{doc.s3_key}")
        full_text = "\n".join([p.text for p in pages])
        
        graph = RiskAssessmentGraph()
        findings = graph.run(doc.id, full_text)
        
        # Save Findings to DB
        from shared.models import Finding as DBFinding
        for f in findings:
            # Check if exists? For MVP just add.
            db_f = DBFinding(
                document_id=doc.id,
                finding_type=f.clause_type, # e.g. "Liability Cap"
                severity=f.risk_level, # "high"
                description=f"{f.explanation}\nOriginal: {f.original_text}\nRedline: {f.redline_text}",
                evidence={"original": f.original_text, "standard": f.standard_clause, "risk_score": f.risk_score},
                status="open"
            )
            db.add(db_f)
        db.commit()
        
        return {"status": "success", "risks": findings}
        
    except Exception as e:
        logger.error(f"Risk assessment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ReviewRequest(BaseModel):
    decision: str # APPROVE, OVERRIDE
    comment: Optional[str] = None
    user_id: str = "user_123"

@app.post("/findings/{finding_id}/review")
def review_finding(
    finding_id: int, 
    req: ReviewRequest, 
    db: Session = Depends(get_db),
    user: User = Depends(RoleChecker(["legal", "admin"]))
):
    from shared.models import ReviewDecision, Finding as DBFinding
    
    finding = db.query(DBFinding).filter(DBFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
        
    decision = ReviewDecision(
        finding_id=finding_id,
        decision=req.decision,
        comment=req.comment,
        user_id=req.user_id
    )
    db.add(decision)
    
    # Update finding status
    finding.status = "reviewed" if req.decision == "APPROVE" else "overridden"
    
    db.commit()
    return {"status": "success"}

@app.get("/documents/{doc_id}/audit")
def get_audit_log(doc_id: int, db: Session = Depends(get_db)):
    from shared.models import ReviewDecision, Finding as DBFinding
    
    # Join findings and decisions? Or just fetch all decisions for findings of this doc
    # MVP: Fetch all findings, then fetch decisions where finding_id in findings
    findings = db.query(DBFinding).filter(DBFinding.document_id == doc_id).all()
    finding_ids = [f.id for f in findings]
    
    decisions = db.query(ReviewDecision).filter(ReviewDecision.finding_id.in_(finding_ids)).all()
    
    return {"decisions": decisions}

@app.get("/documents/{doc_id}/report")
def export_report(doc_id: int, db: Session = Depends(get_db)):
    from shared.models import ReviewDecision, Finding as DBFinding
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    findings = db.query(DBFinding).filter(DBFinding.document_id == doc_id).all()
    finding_ids = [f.id for f in findings]
    decisions = db.query(ReviewDecision).filter(ReviewDecision.finding_id.in_(finding_ids)).all()
    
    # Map decisions to findings
    decision_map = {d.finding_id: d for d in decisions}
    
    report_data = {
        "document_id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "findings": []
    }
    
    for f in findings:
        decision = decision_map.get(f.id)
        report_data["findings"].append({
            "type": f.finding_type,
            "severity": f.severity,
            "description": f.description,
            "status": f.status,
            "review_decision": decision.decision if decision else None,
            "review_comment": decision.comment if decision else None,
            "reviewed_by": decision.user_id if decision else None,
            "reviewed_at": decision.created_at if decision else None
        })
        
    return report_data

@app.get("/evaluation/report")
def get_eval_report():
    try:
        report_path = "/app/evaluation/eval_report.json"
        import json
        with open(report_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load report: {e}")
        return {"metrics": {"extraction_f1": 0, "mismatch_accuracy": 0, "risk_recall": 0}, "details": [], "timestamp": "N/A"}

# --- Auth ---

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

class UserRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "ap"

@app.post("/users")
def create_user(
    new_user: UserRequest, 
    db: Session = Depends(get_db), 
    admin: User = Depends(RoleChecker(["admin"]))
):
    # For MVP, allow creation without auth if no admins exist?
    # Or just use a script to seed admin.
    db_user = User(
        username=new_user.username,
        email=new_user.email,
        hashed_password=get_password_hash(new_user.password),
        role=new_user.role
    )
    db.add(db_user)
    db.commit()
    return {"status": "success", "user": new_user.username}
