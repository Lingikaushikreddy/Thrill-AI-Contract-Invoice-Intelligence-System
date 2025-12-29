# Security Checklist

## Implemented Features

- [x] **JWT Authentication**: Stateless authentication using JSON Web Tokens.
- [x] **Password Hashing**: Bcrypt hashing for user passwords (via `passlib`).
- [x] **RBAC (Role-Based Access Control)**:
    - **Admin**: Full access.
    - **AP (Accounts Payable)**: Can upload invoices and view documents.
    - **Legal**: Can review risks and override findings.
- [x] **Input Validation**: Pydantic models validate all incoming API requests.
- [x] **Rate Limiting**: Redis-backed rate limiter on API endpoints (defualt 60 req/min).
- [x] **Request Logging**: Middleware logs all requests and processing times.

## Production Requirements (To Do)

- [ ] **HTTPS/TLS**: Enable SSL encryption for all traffic. E.g., use Let's Encrypt with Nginx.
- [ ] **Secure Headers**: Configure HTTP headers (HSTS, CSP, X-Frame-Options).
- [ ] **Secrets Management**: Move sensitive keys (OpenAI, DB passwords) out of `.env` files and into a secure vault.
- [ ] **Database Network Isolation**: Ensure Postgres/Redis/Qdrant ports are not exposed publicly (Docker Compose handles this by default, but check firewall rules).
- [ ] **Regular Audits**: Periodically review user access logs and permission grants.
- [ ] **Dependency Scans**: Run `pip-audit` or similar tools in CI to catch vulnerable packages.
