# Odyssey RAG — Security

> **Version**: 1.1.0  
> **Date**: 2026-03-15  
> **Status**: Implemented  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §9, [DOCKER_SETUP.md](DOCKER_SETUP.md), [UI.md](UI.md) §2

---

## 1. Threat Model

| Threat | Impact | Mitigation |
|--------|--------|------------|
| Unauthorized API access | Data leakage, abuse | API key authentication |
| LLM API key exposure | Financial, security | Docker secrets, `.env` never committed |
| SQL injection | Data corruption | Parameterized queries (SQLAlchemy ORM) |
| Prompt injection via ingested docs | Misleading RAG results | Input sanitization, source validation |
| Container escape | Host compromise | Non-root containers, read-only FS |
| DB credential exposure | Full data access | Secrets management, limited user privileges |

---

## 2. Authentication

The system has **three authentication layers**:

| Layer | Mechanism | Scope |
|-------|-----------|-------|
| **Admin UI** | NextAuth.js (credentials + JWT) | Dashboard access |
| **RAG API** | `X-API-Key` header | Backend CRUD, search, ingest |
| **MCP Server** | `Authorization: Bearer <token>` | AI client access to MCP tools |

### 2.1 Admin UI Auth (NextAuth.js v5)

- Provider: Credentials (email + password verified against `admin_user` table)
- Session: JWT strategy, HttpOnly cookie, 7-day expiry
- Password: bcrypt hash (cost 12) stored in `admin_user.password_hash`
- Login: `POST /api/v1/auth/verify` validates credentials server-side
- Protected routes: middleware redirects unauthenticated users to `/login`
- Default user: `admin@odyssey.local` / `admin` (seeded via `003_seed_config.sql`)

### 2.2 API Key Auth

```python
# api/auth.py
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(
    api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """Verify API key for protected endpoints.
    
    In development mode (ENVIRONMENT=development), auth is optional.
    In production, a valid API key is required.
    """
    if settings.environment == "development" and not settings.api_keys:
        return "dev-anonymous"
    
    if not api_key or api_key not in settings.api_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    
    return api_key
```

### 2.2 Configuration

```python
# config/settings.py
class SecuritySettings(BaseModel):
    api_keys: list[str] = Field(default_factory=list)  # Comma-separated in env
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:*"]
```

```bash
# .env
API_KEYS=key-abc123,key-def456     # Comma-separated valid keys
```

### 2.3 Endpoint Protection

```python
# api/routes/search.py
@router.post("/search")
async def search(
    request: SearchRequest,
    _api_key: str = Depends(verify_api_key),  # Protected
):
    ...

# Health endpoint is always public
@app.get("/health")
async def health():
    ...
```

---

## 3. Secrets Management

### 3.1 Environment Variables

| Secret | Container | Source |
|--------|-----------|--------|
| `POSTGRES_PASSWORD` | postgres, rag-api | `.env` file |
| `OPENAI_API_KEY` | rag-api | `.env` file |
| `ANTHROPIC_API_KEY` | rag-api | `.env` file |
| `GOOGLE_API_KEY` | rag-api | `.env` file |
| `API_KEYS` | rag-api | `.env` file |

### 3.2 File Protections

```gitignore
# .gitignore — NEVER commit these
.env
*.pem
*.key
secrets/
```

### 3.3 Docker Secrets (Production)

For production, migrate from `.env` to Docker secrets:

```yaml
# docker-compose.prod.yml
services:
  rag-api:
    secrets:
      - postgres_password
      - openai_api_key
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  openai_api_key:
    file: ./secrets/openai_api_key.txt
```

```python
# config/settings.py — Support _FILE suffix pattern
def load_secret(env_name: str) -> str:
    """Load secret from env var or _FILE variant."""
    file_path = os.getenv(f"{env_name}_FILE")
    if file_path and Path(file_path).exists():
        return Path(file_path).read_text().strip()
    return os.getenv(env_name, "")
```

---

## 4. Database Security

### 4.1 User Privileges

```sql
-- db/init/001_extensions.sql
-- Main app user has restricted privileges
CREATE ROLE rag_app WITH LOGIN PASSWORD 'from_secret';
GRANT CONNECT ON DATABASE odyssey_rag TO rag_app;
GRANT USAGE ON SCHEMA public TO rag_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rag_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rag_app;

-- No DROP TABLE, CREATE TABLE, ALTER in production
-- Migrations run with a separate admin user
```

### 4.2 Connection Security

```python
# Always use parameterized queries via SQLAlchemy
# NEVER concatenate user input into SQL
# SQLAlchemy ORM handles parameterization automatically

# Example: SAFE
await session.execute(
    select(Chunk).where(Chunk.content_tsvector.match(user_query))
)

# Example: UNSAFE (never do this)
# await session.execute(text(f"SELECT * FROM chunk WHERE content LIKE '%{user_input}%'"))
```

---

## 5. Input Validation

### 5.1 API Input

```python
# All inputs validated via Pydantic schemas
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    message_type: str | None = Field(None, pattern=r"^(pacs|camt|pain|acmt)\.\d{3}$")
    top_k: int = Field(10, ge=1, le=20)
```

### 5.2 Ingestion Input

```python
# Source path must be within allowed directories
ALLOWED_SOURCE_DIRS = ["/app/sources"]

def validate_source_path(path: str) -> str:
    """Ensure source path is within allowed directories."""
    resolved = Path(path).resolve()
    if not any(str(resolved).startswith(d) for d in ALLOWED_SOURCE_DIRS):
        raise ValueError(f"Source path must be within: {ALLOWED_SOURCE_DIRS}")
    if not resolved.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    return str(resolved)
```

### 5.3 Content Sanitization

```python
# Strip potential prompt injection markers from ingested content
SANITIZE_PATTERNS = [
    r"<\|system\|>",
    r"<\|assistant\|>",
    r"<\|user\|>",
    r"\[INST\]",
    r"\[/INST\]",
]

def sanitize_content(text: str) -> str:
    """Remove potential prompt injection patterns from content."""
    for pattern in SANITIZE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text
```

---

## 6. Container Security

### 6.1 Non-Root User

```dockerfile
# Dockerfile — run as non-root
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

USER appuser
```

### 6.2 Read-Only Filesystem

```yaml
# docker-compose.yml
services:
  rag-api:
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - rag-models:/app/models:ro  # Models read-only after download
```

### 6.3 Resource Limits

```yaml
services:
  rag-api:
    deploy:
      resources:
        limits:
          memory: 3G
          cpus: "2.0"
  postgres:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
```

---

## 7. CORS Configuration

```python
# api/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Default: ["http://localhost:*"]
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)
```

---

## 8. Logging & Audit

### 8.1 Structured Logging

```python
# All API requests are logged with structlog
import structlog

logger = structlog.get_logger()

# Every search/ingest is logged
logger.info("search_request", query=query, api_key_hash=hash(api_key), results=len(evidence))
logger.info("ingest_request", source_path=path, api_key_hash=hash(api_key), status=status)
```

### 8.2 Sensitive Data Exclusion

```python
# NEVER log:
# - Full API keys (log hash only)
# - Database passwords
# - LLM API keys
# - Full file contents (log path + size only)
```

---

## 9. Security Checklist

- [ ] `.env` in `.gitignore`
- [ ] No secrets in Docker image layers
- [ ] API key auth enabled in production
- [ ] Database user has minimal privileges
- [ ] All inputs validated via Pydantic
- [ ] Source paths restricted to allowed directories
- [ ] Containers run as non-root
- [ ] CORS configured for allowed origins only
- [ ] Structured logging excludes sensitive data
- [ ] Dependencies pinned and scanned (`pip-audit`)
