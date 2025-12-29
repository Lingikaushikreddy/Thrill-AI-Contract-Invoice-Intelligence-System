# AI Contract & Invoice Intelligence System

An enterprise-grade AI agent that parses, understands, and audits financial documents. It automates the review of Invoices against Contracts and assesses legal risks in contracts using a RAG-based approach.

## 🚀 Key Features

*   **📄 Document Ingestion**: High-fidelity PDF parsing (OCR-ready) with chunking and vector embedding (Qdrant).
*   **🧠 Intelligent Extraction**: Uses LLMs (Mistral/OpenAI) + LangGraph to extract structured data (Entities, Dates, Terms) from unstructured files.
*   **⚖️ Mismatch Detection**: Automatically links Invoices to Contracts and flags discrepancies (e.g., Invoice amounts exceeding Contract rates, Payment Term violations).
*   **🛡️ Risk Assessment**: Scores contract clauses against a "Gold Standard" library using Semantic Search. detailed redlines for high-risk clauses (e.g., "Unlimited Liability").
*   **👁️ Review Dashboard**: A Next.js frontend for split-screen document review, finding approval/override, and audit webhooks.
*   **📊 Evaluation Framework**: Built-in "Gold Dataset" generator and evaluation runner to track F1 / Precision / Recall metrics.

## 🏗️ Architecture

```mermaid
graph TD
    User[User / Frontend] -->|Upload| API[FastAPI Gateway]
    API -->|Save| MinIO[MinIO Storage]
    API -->|Index| Qdrant[Qdrant Vector DB]
    API -->|Queue| Redis[Redis Broker]
    
    subgraph "Worker Nodes"
        Worker[Celery Worker]
        Worker -->|Pull Task| Redis
        Worker -->|Embed| Qdrant
        Worker -->|LLM Calls| ExternalLLM[Mistral / OpenAI]
        Worker -->|Store Result| DB[Postgres DB]
    end
```

## 🛠️ Tech Stack

-   **Frontend**: Next.js 14, Tailwind CSS, Shadcn UI
-   **Backend**: Python FastAPI, SQLAlchemy, Pydantic
-   **Async Processing**: Celery + Redis
-   **Database**: PostgreSQL (Metadata), Qdrant (Vectors), MinIO (Files)
-   **AI/LLM**: LangChain, LangGraph, Sentence Transformers (All-MiniLM-L6-v2)
-   **DevOps**: Docker Compose, GitHub Actions

## 🏁 Getting Started

### Prerequisites

-   Docker & Docker Compose
-   API Key for LLM (OpenAI or Mistral)

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/Lingikaushikreddy/FinChurnFlow-fintech-churn-full-MLflow-pipeline.git
    cd "AI Contract & Invoice Intelligence System"
    ```

2.  **Configure Environment**:
    Create a `.env` file in the root (see `.env.example` or use the defaults below for dev):
    ```env
    DATABASE_URL=postgresql://user:password@postgres:5432/ai_contract_db
    REDIS_URL=redis://redis:6379/0
    MINIO_ENDPOINT=minio:9000
    OPENAI_API_KEY=sk-...  # or MISTRAL_API_KEY
    SECRET_KEY=supersecret
    ```

3.  **Run with Docker Compose**:
    ```bash
    docker-compose up --build
    ```

4.  **Access the App**:
    -   **Frontend**: [http://localhost:3000](http://localhost:3000)
    -   **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
    -   **MinIO Console**: [http://localhost:9001](http://localhost:9001)

## 📖 Usage Guide

### 1. Upload Documents
Go to the Dashboard and click **"Upload Document"**. You can upload PDF Contracts or Invoices.

### 2. Automated Analysis
-   **Invoices**: The system attempts to match the Invoice to an existing Contract (by Vendor Name) and checks for discrepancies.
-   **Contracts**: You can trigger a **Risk Assessment** from the document details page to identify risky clauses.

### 3. Review & Audit
Open a document to see the **Split View**. The left panel shows the PDF, and the right panel lists Findings.
-   **Approve**: Confirm a finding is valid.
-   **Override**: Mark a finding as false positive / acceptable.

## 🧪 Evaluation

To measure system performance against the Gold Dataset:

1.  **Generate Synthetic Data**:
    ```bash
    docker-compose exec worker python3 evaluation/generate_gold.py
    ```
2.  **Run Evaluation**:
    ```bash
    # Requires local python env with requests installed
    python3 backend/evaluation/eval_runner.py
    ```
3.  **View Report**:
    Navigate to [http://localhost:3000/evaluations](http://localhost:3000/evaluations) to see F1 scores and trends.

## 🔒 Security

This project includes production-ready hardening features:
-   **RBAC**: Role-Based Access Control (Admin, AP, Legal).
-   **JWT Auth**: Secure API endpoints.
-   **Rate Limiting**: Protection against abuse.

See [SecurityChecklist.md](./SecurityChecklist.md) for details.

## 📚 Documentation

-   [Deployment Guide](./Deployment.md)
-   [Model Card](./ModelCard.md)
-   [API Schemas](./backend/shared/schemas.py)
