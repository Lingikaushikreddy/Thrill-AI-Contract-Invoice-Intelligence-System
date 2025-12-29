# Deployment Guide

## Prerequisites

- **Docker & Docker Compose**: Ensure you have Docker installed and running.
- **Git**: To clone the repository.
- **API Keys**: OpenAI or Mistral API keys for LLM features.

## Environment Setup

1. Copy the example environment file (if available) or create `.env` in the root directory:

```bash
# Core
DATABASE_URL=postgresql://user:password@postgres:5432/ai_contract_db
REDIS_URL=redis://redis:6379/0

# Storage
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents
MINIO_SECURE=False  # Set to True if using HTTPS for MinIO

# Vector DB
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# AI / ML
OPENAI_API_KEY=your_key_here
# or
MISTRAL_API_KEY=your_key_here

# Security
SECRET_KEY=change_this_to_a_secure_random_string_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALLOWED_ORIGINS=http://localhost:3000,https://your-domain.com
```

## Running the System

1. **Build and Start Containers**:
   ```bash
   docker-compose up --build
   ```

2. **Access the Application**:
   - **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
   - **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **MinIO Console**: [http://localhost:9001](http://localhost:9001) (User: `minioadmin`, Pass: `minioadmin`)

## Production Considerations

- **Secrets**: Do not store API keys in `.env` committed to git. Use a secret manager (Vault, AWS Secrets Manager) or inject them at runtime.
- **HTTPS**: Run the application behind a reverse proxy (Nginx, Traefik) with SSL configured.
- **Persistence**: Ensure Docker volumes for Postgres, MinIO, and Qdrant are backed up.
- **Scaling**: The Celery worker can be scaled horizontally (`docker-compose up --scale worker=3`).
- **CORS**: Ensure `ALLOWED_ORIGINS` includes your frontend domain.

## Troubleshooting

- **Database Connection**: If the API fails to connect to DB on startup, ensure Postgres is healthy (`docker-compose ps`).
- **LLM Errors**: Verify API keys and quotas.
- **Frontend Build**: If the frontend fails to build, ensure `npm install` has been run and node modules are up to date.
