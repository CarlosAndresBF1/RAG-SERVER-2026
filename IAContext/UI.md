# Odyssey RAG — Phase 2: Admin UI & Security

> **Version**: 1.1.0
> **Date**: 2026-03-15
> **Status**: Phase 2A–2D COMPLETE (20/24 tasks done, 4 deferred)
> **Depends on**: Phase 1 (RAG backend — COMPLETE)
> **Stack**: Next.js 16 (App Router) · React 19 · TypeScript 5 (strict) · Tailwind CSS 4 · shadcn/ui (@base-ui/react) · NextAuth.js v5
> **Runtime**: Node.js 22 LTS (Alpine) · npm 10+
> **Quality**: Vitest 4 + Playwright · npm audit clean · TypeScript strict mode · 196 backend tests + 6 frontend tests passing
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md), [API_REFERENCE.md](API_REFERENCE.md), [SECURITY.md](SECURITY.md), [DATA_MODEL.md](DATA_MODEL.md)

---

## 0. Project Structure

```
RAG/
├── src/odyssey_rag/          ← Backend Python (Phase 1 — exists)
├── web/                      ← Frontend Next.js (Phase 2 — NEW)
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── layout.tsx
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx           ← Sidebar + topbar shell
│   │   │   │   ├── page.tsx             ← Dashboard overview
│   │   │   │   ├── sources/
│   │   │   │   │   ├── page.tsx         ← Source browser
│   │   │   │   │   └── [id]/page.tsx    ← Source detail + chunks
│   │   │   │   ├── ingest/page.tsx      ← Upload & ingest
│   │   │   │   ├── search/page.tsx      ← Search playground
│   │   │   │   ├── coverage/page.tsx    ← Coverage matrix
│   │   │   │   ├── jobs/page.tsx        ← Ingestion history
│   │   │   │   ├── feedback/page.tsx    ← Feedback dashboard
│   │   │   │   ├── tokens/page.tsx      ← MCP token management
│   │   │   │   └── settings/page.tsx    ← System settings
│   │   │   ├── api/
│   │   │   │   └── auth/[...nextauth]/route.ts
│   │   │   ├── layout.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/                      ← shadcn/ui primitives
│   │   │   ├── layout/
│   │   │   │   ├── sidebar.tsx
│   │   │   │   ├── topbar.tsx
│   │   │   │   └── breadcrumb.tsx
│   │   │   ├── dashboard/
│   │   │   ├── sources/
│   │   │   ├── search/
│   │   │   ├── coverage/
│   │   │   └── tokens/
│   │   ├── lib/
│   │   │   ├── api-client.ts            ← Typed RAG API client
│   │   │   ├── auth.ts                  ← NextAuth config
│   │   │   └── utils.ts
│   │   └── types/
│   │       └── api.ts                   ← API response types
│   ├── public/
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
├── db/                                  ← Shared (add admin_user table)
├── docker-compose.yml                   ← Add web service
└── Makefile                             ← Add web targets
```

---

## 1. Design Language — "The Clerk"

### 1.1 Concepto Visual

Inspirado en la estética de **oficinas de registro documental, bufetes legales y archivos históricos**. Transmite seriedad, orden y precisión — cualidades asociadas con la gestión de estándares ISO y documentación financiera.

### 1.2 Principios de diseño

| Principio | Aplicación |
|-----------|------------|
| **Tipografía serif para títulos** | `font-family: "Playfair Display", serif` para headings; `"Inter", sans-serif` para cuerpo |
| **Paleta restringida** | Fondo: warm paper `#FAFAF7` · Texto: ink `#1A1A1A` · Acento: seal red `#8B2500` · Secundario: archive gold `#B8860B` · Bordes: aged line `#D4C5A9` |
| **Iconografía documental** | Sellos, carpetas con pestañas, etiquetas tipo archivo, badges tipo sello notarial |
| **Contenedores como fichas** | Cards con borde superior de color (tipo pestaña de carpeta), sombra sutil, esquinas ligeramente redondeadas |
| **Números en monospace** | Contadores, IDs, hashes, timestamps en `font-family: "JetBrains Mono", monospace` |
| **Estado como sellos** | Status badges circulares tipo sello: completed = verde sello, failed = rojo lacre, pending = dorado |
| **Sidebar como índice** | Navegación lateral tipo tabla de contenidos de un expediente |
| **Empty states** | Ilustración line-art de un archivero vacío o un escritorio limpio |

### 1.3 Paleta de colores

```
Background (paper):     #FAFAF7 (light) / #1C1917 (dark — stone-950)
Surface (card):         #FFFFFF (light) / #292524 (dark — stone-800)
Border (aged):          #D4C5A9 (light) / #44403C (dark — stone-700)
Text primary (ink):     #1A1A1A (light) / #FAFAF9 (dark)
Text secondary:         #57534E (light) / #A8A29E (dark — stone-400)
Accent (seal):          #8B2500 (light) / #DC6843 (dark)
Accent secondary (gold):#B8860B (light) / #D4A843 (dark)
Success (approved):     #2E7D32
Warning (pending):      #B8860B
Danger (rejected):      #8B2500
Info (reference):       #1565C0
```

### 1.4 Componentes visuales distintivos

```
┌──────────────────────────────────────────────────────────────────────┐
│  ┌─── TOPBAR ──────────────────────────────────────────────────┐    │
│  │  ⚖ ODYSSEY RAG ADMIN          🔍 Quick search     👤 Admin │    │
│  └─────────────────────────────────────────────────────────────┘    │
│  ┌─────────┐ ┌────────────────────────────────────────────────┐    │
│  │ SIDEBAR  │ │                                                │    │
│  │          │ │  ┌──────────┐ ┌──────────┐ ┌──────────┐      │    │
│  │ § Resumen│ │  │ 📄 247   │ │ 🧩 1,832 │ │ 🔍 89%   │      │    │
│  │ § Fuentes│ │  │Documents │ │ Chunks   │ │ Coverage │      │    │
│  │ § Ingerir│ │  │ ●● +12   │ │ ●● +94   │ │ ▲ +3%    │      │    │
│  │ § Buscar │ │  └──────────┘ └──────────┘ └──────────┘      │    │
│  │ § Cobert.│ │                                                │    │
│  │ § Trabajos│ │  ┌─ Actividad reciente ─────────────────┐    │    │
│  │ § Feedback│ │  │ ● 14:23  Ingestado: Annex_B.md       │    │    │
│  │ ─────────│ │  │ ● 14:20  Búsqueda: "pacs.008 fields" │    │    │
│  │ § Tokens │ │  │ ○ 14:15  Eliminado: old_spec_v2.xml   │    │    │
│  │ § Config │ │  └───────────────────────────────────────┘    │    │
│  │          │ │                                                │    │
│  └─────────┘ └────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Seguridad & Autenticación

### 2.1 Modelo de seguridad completo

El sistema maneja **tres capas de autenticación** independientes:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SECURITY LAYERS                              │
│                                                                     │
│  ┌─ Layer 1: Admin UI ──────────────────────────────────────────┐  │
│  │  NextAuth.js (credentials provider)                          │  │
│  │  Session: JWT HttpOnly cookie (7d expiry)                    │  │
│  │  Scope: Acceso al dashboard de administración                │  │
│  │  Users: tabla admin_user en PostgreSQL                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              │ Server Component fetch               │
│                              ▼                                      │
│  ┌─ Layer 2: RAG API ───────────────────────────────────────────┐  │
│  │  X-API-Key header (ya existe)                                │  │
│  │  La UI usa un API key interno (server-side, nunca al browser)│  │
│  │  Scope: CRUD de sources, chunks, search, ingest              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ Layer 3: MCP Token Management ──────────────────────────────┐  │
│  │  Tokens generados desde la UI para consumidores MCP          │  │
│  │  Bearer token en header Authorization del SSE/HTTP transport │  │
│  │  Scope: Acceso a herramientas MCP desde VS Code / AI clients │  │
│  │  Features: crear, revocar, expiración, rate limit, auditoría │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer 1 — Autenticación Admin UI (NextAuth.js)

**Provider**: Credentials (email + password). Escalable a OAuth en el futuro.

**Tabla `admin_user`** (nueva migración):

```sql
-- db/migrations/004_admin_users.sql
CREATE TABLE IF NOT EXISTS admin_user (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,          -- bcrypt hash
    display_name    VARCHAR(100) NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'admin',  -- admin | viewer
    is_active       BOOLEAN      DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX idx_admin_user_email ON admin_user (email) WHERE is_active = TRUE;
```

**Flujo de auth**:

```
Browser                     Next.js Server              PostgreSQL
───────                     ──────────────              ──────────
   │  POST /api/auth/signin     │                          │
   │  {email, password}         │                          │
   │ ──────────────────────────▶│                          │
   │                            │  SELECT * FROM admin_user │
   │                            │  WHERE email = $1         │
   │                            │ ────────────────────────▶│
   │                            │         {user row}       │
   │                            │ ◀────────────────────────│
   │                            │                          │
   │                            │  bcrypt.compare(pwd, hash)
   │                            │                          │
   │   Set-Cookie: session-jwt  │                          │
   │ ◀─────────────────────────│                          │
   │                            │                          │
   │  GET /dashboard            │                          │
   │  Cookie: session-jwt       │                          │
   │ ──────────────────────────▶│                          │
   │                            │  verify JWT              │
   │    <Dashboard HTML>        │                          │
   │ ◀─────────────────────────│                          │
```

**Configuración NextAuth**:

```typescript
// web/src/lib/auth.ts
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        // Query admin_user table via RAG API or direct DB
        // Verify bcrypt hash
        // Return user object or null
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 }, // 7 days
  pages: { signIn: "/login" },
});
```

**Middleware de protección**:

```typescript
// web/src/middleware.ts
export { auth as middleware } from "@/lib/auth";

export const config = {
  matcher: ["/((?!login|api/auth|_next|favicon).*)"],
};
```

### 2.3 Layer 2 — RAG API Key (Server-Side)

La UI **nunca expone el API key al browser**. Todas las llamadas a la RAG API se hacen desde Server Components o Route Handlers:

```typescript
// web/src/lib/api-client.ts
const RAG_API_URL = process.env.RAG_API_URL!;       // http://rag-api:8080
const RAG_API_KEY = process.env.RAG_INTERNAL_KEY!;   // Server-only, never in NEXT_PUBLIC_

export async function ragFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${RAG_API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": RAG_API_KEY,
      ...options?.headers,
    },
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}
```

### 2.4 Layer 3 — MCP Token Management

Los tokens MCP permiten a developers y AI clients (VS Code Copilot, Claude Code) conectarse al MCP server. El admin los gestiona desde la UI.

**Tabla `mcp_token`** (nueva migración):

```sql
-- db/migrations/005_mcp_tokens.sql
CREATE TABLE IF NOT EXISTS mcp_token (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100)  NOT NULL,           -- Descriptive name ("Carlos - VS Code")
    token_hash      VARCHAR(255)  NOT NULL,           -- SHA-256 of the token (never store raw)
    token_prefix    VARCHAR(12)   NOT NULL,           -- First 8 chars for identification ("odr_a1b2...")
    issued_by       UUID          NOT NULL REFERENCES admin_user(id),
    scopes          VARCHAR[]     NOT NULL DEFAULT ARRAY['read'],  -- read, write, ingest
    is_active       BOOLEAN       DEFAULT TRUE,
    expires_at      TIMESTAMPTZ,                      -- NULL = no expiry
    last_used_at    TIMESTAMPTZ,
    usage_count     INTEGER       DEFAULT 0,
    rate_limit_rpm  INTEGER       DEFAULT 60,         -- Requests per minute
    created_at      TIMESTAMPTZ   DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ                       -- NULL = active
);

CREATE INDEX idx_mcp_token_hash   ON mcp_token (token_hash) WHERE is_active = TRUE;
CREATE INDEX idx_mcp_token_prefix ON mcp_token (token_prefix);

-- Audit log
CREATE TABLE IF NOT EXISTS mcp_token_audit (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_id    UUID         NOT NULL REFERENCES mcp_token(id),
    action      VARCHAR(20)  NOT NULL,  -- created, used, revoked, expired
    ip_address  INET,
    user_agent  VARCHAR(500),
    tool_name   VARCHAR(100),           -- Which MCP tool was called
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX idx_mcp_audit_token   ON mcp_token_audit (token_id);
CREATE INDEX idx_mcp_audit_created ON mcp_token_audit (created_at DESC);
```

**Formato del token**:

```
odr_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4

Prefijo: odr_         (identifica como Odyssey RAG token)
Body:    48 chars      (crypto random, base62)
Total:   52 chars

Solo se muestra completo UNA VEZ al crear.
Se almacena como SHA-256 hash en la DB.
```

**Flujo de creación desde la UI**:

```
Admin (Browser)            Next.js Server            RAG API (Backend)
───────────────            ──────────────            ─────────────────
   │  POST /api/tokens         │                         │
   │  {name, scopes, expiry}   │                         │
   │ ─────────────────────────▶│                         │
   │                           │  1. Generate random token
   │                           │  2. SHA-256(token) = hash
   │                           │                         │
   │                           │  POST /api/v1/tokens    │
   │                           │  {name, hash, scopes}   │
   │                           │ ───────────────────────▶│
   │                           │       {id, prefix}      │
   │                           │ ◀───────────────────────│
   │                           │                         │
   │  {token: "odr_a1b2..."}  │  ← Token raw, solo esta vez
   │ ◀─────────────────────────│                         │
   │                           │                         │
   │  ⚠ "Copia este token.    │                         │
   │   No se mostrará de nuevo"│                         │
```

**Flujo de validación en MCP server**:

```
VS Code / AI Client           MCP Server                 PostgreSQL
───────────────────           ──────────                 ──────────
   │  GET /sse                     │                         │
   │  Authorization: Bearer odr_…  │                         │
   │ ─────────────────────────────▶│                         │
   │                               │  SHA-256(token)         │
   │                               │  SELECT FROM mcp_token  │
   │                               │  WHERE token_hash = $1  │
   │                               │    AND is_active = TRUE  │
   │                               │    AND (expires_at IS NULL
   │                               │         OR expires_at > NOW())
   │                               │ ─────────────────────▶ │
   │                               │     {token row}        │
   │                               │ ◀───────────────────── │
   │                               │                        │
   │                               │  Check rate limit       │
   │                               │  Log to mcp_token_audit │
   │                               │  UPDATE usage_count +1  │
   │                               │  UPDATE last_used_at    │
   │                               │                        │
   │  SSE: endpoint=/messages/...  │                        │
   │ ◀─────────────────────────────│                        │
```

**Scopes**:

| Scope | Permite |
|-------|---------|
| `read` | `find_message_type`, `find_business_rule`, `find_module`, `find_error`, `search` |
| `write` | Todos los de `read` + `ingest` |
| `admin` | Todos + gestión de tokens (solo para uso interno de la UI) |

### 2.5 Nuevos endpoints requeridos en RAG API

```
POST   /api/v1/tokens              ← Crear token (hash + metadata)
GET    /api/v1/tokens              ← Listar tokens activos (sin hash)
DELETE /api/v1/tokens/{id}         ← Revocar token
GET    /api/v1/tokens/{id}/audit   ← Log de uso de un token
POST   /api/v1/auth/verify         ← Validar credenciales admin (para NextAuth)
GET    /api/v1/stats/overview      ← Contadores del dashboard
GET    /api/v1/stats/coverage      ← Matriz de cobertura
GET    /api/v1/stats/feedback      ← Resumen de feedback
GET    /api/v1/jobs                ← Historial de ingest_jobs
```

---

## 3. Requerimientos Funcionales

### 3.1 — Dashboard Overview (RF-01)

**Ruta**: `/`

| Elemento | Fuente | Detalle |
|----------|--------|---------|
| Card: Total Documents | `GET /api/v1/stats/overview` | Contador + delta últimos 7d |
| Card: Total Chunks | idem | Contador + delta |
| Card: Coverage % | idem | message_types cubiertos / total esperados |
| Card: Health Status | `GET /health` | Semáforo: database, embedding, reranker |
| Tabla: Actividad reciente | `GET /api/v1/jobs?limit=10` | Últimas ingestas con status badges |
| Gráfica: Ingestas por día | `GET /api/v1/stats/overview` | Bar chart, últimos 30 días |
| Alerta: Gaps detectados | `GET /api/v1/stats/coverage` | Cards rojas para message_types sin cobertura completa |

### 3.2 — Source Browser (RF-02)

**Ruta**: `/sources`

| Elemento | Detalle |
|----------|---------|
| Tabla paginada | Columns: nombre, source_type (badge), chunks, tokens, fecha, acciones |
| Filtros | source_type dropdown, integration dropdown, búsqueda por path |
| Sort | Por nombre, fecha, chunks count |
| Acciones por fila | Ver detalle, re-ingestar, eliminar (con confirmación modal) |
| Badge source_type | Color-coded: annex_b_spec=blue, php_code=purple, xml_example=green, tech_doc=amber |

**Ruta**: `/sources/[id]`

| Elemento | Detalle |
|----------|---------|
| Header | source_path, type badge, file_hash (mono), timestamps |
| Lista de chunks | Cards colapsables con content preview, section, subsection, token_count |
| Metadata panel | message_types detectados, PHP classes, XPaths — extraído de chunk_metadata |
| Acciones | Re-ingest, Delete, Download chunks as JSON |

### 3.3 — Source Ingestion (RF-03)

**Ruta**: `/ingest`

| Elemento | Detalle |
|----------|---------|
| Dropzone | Drag & drop area, acepta .md, .php, .xml, .json, .pdf |
| Preview | Tabla de archivos seleccionados con source_type auto-detectado (editable) |
| Opciones | Toggle: `replace_existing`, field: `metadata_overrides` (JSON editor) |
| Progreso | Progress bar por archivo, SSE/polling para status en tiempo real |
| Resultado | Summary card: completed / skipped / failed con detalles expandibles |

**Nota**: Los archivos se suben primero a un endpoint nuevo `POST /api/v1/upload` que los coloca en `/app/sources/`, luego se llama al ingest existente.

### 3.4 — Search Playground (RF-04)

**Ruta**: `/search`

| Elemento | Detalle |
|----------|---------|
| Input | Textarea con autosize, placeholder: "Search the knowledge base..." |
| Filtros | message_type dropdown, source_type dropdown, focus selector, top_k slider |
| Resultados | Cards de evidence con: snippet (syntax highlighted), relevance bar, citation links |
| Citations | Click en citation → navega a `/sources/[doc_id]` con chunk resaltado |
| Metadata | Panel lateral: search_time_ms, total_candidates, query analysis |
| Historial | Últimas 10 búsquedas de la sesión, re-ejecutables |

### 3.5 — Coverage Matrix (RF-05)

**Ruta**: `/coverage`

| Elemento | Detalle |
|----------|---------|
| Heatmap/tabla | Filas: message_types (pacs.008, camt.056, etc.) · Columnas: source_types (annex_b, php, xml, tech_doc) |
| Celdas | Número de chunks, color-coded: 0=rojo, 1-5=amber, 5+=green |
| Detalle on-click | Expandir celda → lista de chunks con preview |
| Totales | Row totals, column totals, overall coverage percentage |
| Gaps list | Lista priorizada de combinaciones con 0 chunks |

### 3.6 — Ingestion History (RF-06)

**Ruta**: `/jobs`

| Elemento | Detalle |
|----------|---------|
| Timeline | Vertical timeline de ingest_jobs, más recientes arriba |
| Cada job | source_path, status (sello), duration_ms, chunks_created, timestamp |
| Filtros | Por status (completed/failed/skipped), por fecha |
| Acciones | Re-run (reenvía ingest), ver error detail (modal) |

### 3.7 — Feedback Dashboard (RF-07)

**Ruta**: `/feedback`

| Elemento | Detalle |
|----------|---------|
| KPIs | Avg rating, total feedbacks, positivity rate |
| Tabla | query, rating (thumbs), tool_name, date, chunk count |
| Gráfica | Ratings distribution (bar chart), trend over time (line) |
| Worst performers | Queries con peor rating promedio, chunks más rechazados |

### 3.8 — MCP Token Manager (RF-08)

**Ruta**: `/tokens`

| Elemento | Detalle |
|----------|---------|
| Lista de tokens | name, prefix (`odr_a1b2...`), scopes (badges), status, last_used, usage_count |
| Crear token | Modal: name, scopes checkboxes, expiry date picker, rate limit input |
| Token reveal | Dialog con token completo + botón copy, warning "solo se muestra una vez" |
| Revocar | Botón con confirmación, marca `revoked_at` + `is_active = FALSE` |
| Audit log | Por token: tabla de últimos usos con IP, user_agent, tool_name, timestamp |
| Config snippet | Genera automáticamente el bloque de `.vscode/mcp.json` con el token |

**Ejemplo de config snippet generado**:

```json
{
  "servers": {
    "odyssey-rag": {
      "type": "sse",
      "url": "http://localhost:3010/sse",
      "headers": {
        "Authorization": "Bearer odr_a1b2c3d4..."
      }
    }
  }
}
```

### 3.9 — System Settings (RF-09)

**Ruta**: `/settings`

| Elemento | Detalle |
|----------|---------|
| Service status | Live health check con refresh |
| LLM config | Provider actual, modelo, status de conexión (Ollama ping) |
| Embedding config | Provider, modelo, dimensión |
| DB stats | Tamaño total, tablas, rows per table |

---

## 4. Requerimientos No Funcionales

| RNF | Requisito | Detalle |
|-----|-----------|---------|
| **RNF-01** | Performance | First Contentful Paint < 1.5s, API responses cached con `revalidate` |
| **RNF-02** | Responsive | Desktop-first, funcional en tablet (≥768px). No mobile requerido |
| **RNF-03** | Dark mode | Toggle manual, persiste en localStorage, respeta `prefers-color-scheme` |
| **RNF-04** | Accesibilidad | WCAG 2.1 Level AA: contrast ratios, keyboard navigation, aria labels |
| **RNF-05** | SEO | No requerido (admin interno). `robots.txt` deny all |
| **RNF-06** | Seguridad | JWT HttpOnly, CSRF protection, rate limiting en auth endpoints |
| **RNF-07** | Observabilidad | Logs estructurados, request tracing header (X-Request-Id) |
| **RNF-08** | Docker | Imagen multi-stage, < 200MB, health check. Todo corre dockerizado. Dev y prod usan containers |
| **RNF-09** | Zero-config deploy | `docker compose up` levanta todo (DB + API + MCP + Web) |
| **RNF-10** | Versiones LTS | Node.js **22 LTS** (Alpine), Next.js **16**, React **19.2**, npm **10+** |
| **RNF-11** | TypeScript strict | `strict: true` en tsconfig. No `any` sin justificación. Tipos explícitos en API boundaries |
| **RNF-12** | Testing | **Unit**: Vitest + React Testing Library (>70% coverage). **E2E**: Playwright. **CI gate**: `npm test` debe pasar antes de build |
| **RNF-13** | npm audit | `npm audit --audit-level=high` debe retornar 0 vulnerabilidades high/critical. Se ejecuta en CI y durante Docker build |
| **RNF-14** | Dependencias actualizadas | Dependencias pinneadas en `package-lock.json`. Revisión periódica con `npm outdated`. Sin dependencias deprecated |

---

## 5. Docker Integration

### 5.1 Dockerfile (web)

```dockerfile
# web/Dockerfile
# ── Node 22 LTS (Alpine) ──────────────────────────
FROM node:22-alpine AS base
WORKDIR /app

# ── Dependencies ──────────────────────────────────
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci --only=production

# ── Build ─────────────────────────────────────────
FROM base AS build
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Audit: fail build on high/critical vulnerabilities
RUN npm audit --audit-level=high
# Type check before build
RUN npx tsc --noEmit
RUN npm run build

# ── Runner ────────────────────────────────────────
FROM base AS runner
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost:3000/api/health || exit 1
CMD ["npm", "start"]
```

### 5.2 docker-compose.yml (servicio web adicional)

```yaml
  # ─── Admin Web UI ──────────────────────────────────────
  web:
    build:
      context: ./web
      dockerfile: Dockerfile
    container_name: odyssey-rag-web
    restart: unless-stopped
    depends_on:
      rag-api:
        condition: service_healthy
      postgres:
        condition: service_healthy
    environment:
      NEXTAUTH_URL: http://localhost:${WEB_PORT:-3001}
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      RAG_API_URL: http://rag-api:8080
      RAG_INTERNAL_KEY: ${RAG_INTERNAL_KEY}
      DATABASE_URL: postgresql://${POSTGRES_USER:-rag_user}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-odyssey_rag}
    ports:
      - "${WEB_PORT:-3001}:3000"
    networks:
      - rag-net
```

### 5.3 Variables de entorno adicionales en `.env`

```bash
# ── Admin Web UI ──────────────────────────
WEB_PORT=3001
NEXTAUTH_SECRET=                        # REQUIRED: openssl rand -base64 32
NEXTAUTH_URL=http://localhost:3001
RAG_INTERNAL_KEY=                        # Internal API key for web→api calls
ADMIN_EMAIL=admin@odyssey.local
ADMIN_PASSWORD=                          # REQUIRED: initial admin password
```

---

## 6. Execution Plan

### Phase 2A — Scaffolding & Auth (Foundation)

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2A.1** | Scaffold Next.js project | `npx create-next-app@latest web` con App Router, TypeScript, Tailwind, ESLint | `npm run dev` arranca en `web/` |
| **2A.2** | Install & configure shadcn/ui | Init shadcn, agregar componentes base (button, card, input, dialog, table, badge, dropdown-menu, sheet, tooltip) | `import { Button } from "@/components/ui/button"` funciona |
| **2A.3** | Design tokens & theme | Configurar Tailwind con paleta "The Clerk", fonts (Playfair Display, Inter, JetBrains Mono), dark mode class strategy | Theme visible en `/` placeholder |
| **2A.4** | DB migration: admin_user + mcp_token | Crear `004_admin_users.sql` y `005_mcp_tokens.sql` con tablas e índices | Tablas existen tras `docker compose up` |
| **2A.5** | Seed admin user | Script `seed_admin.py` que crea el usuario admin inicial (bcrypt hash) | Login con `ADMIN_EMAIL` / `ADMIN_PASSWORD` funciona |
| **2A.6** | NextAuth.js setup | Provider credentials contra tabla admin_user, JWT strategy, middleware de protección | Redirect a `/login` si no autenticado |
| **2A.7** | Login page | Formulario email + password, estilo "The Clerk", error handling, loading states | Login funcional, redirect a dashboard |
| **2A.8** | Dashboard layout | Sidebar + topbar + main area, breadcrumb, collapsible sidebar, user menu | Navegación entre todas las rutas funciona |
| **2A.9** | Typed API client | `lib/api-client.ts` con funciones tipadas para cada endpoint RAG | Tipos TypeScript matchean schemas Pydantic |
| **2A.10** | Testing setup | Configurar Vitest + RTL + Playwright. Scripts: `npm test`, `npm run test:e2e`, `npm run test:coverage`. Configurar `tsconfig.json` con `strict: true` | `npm test` pasa, coverage report genera |
| **2A.11** | npm audit & CI gates | `npm audit --audit-level=high` = 0 vulns. Agregar script `npm run audit:check`. Dockerfile ejecuta audit + tsc en build stage | Build falla si hay vulns high/critical o errores TS |
| **2A.12** | Dockerfile + docker-compose | Multi-stage build (Node 22 LTS), servicio web en compose, health check, non-root user | `docker compose up` levanta 4 servicios |

### Phase 2B — Core Features (CRUD & Visualization)

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2B.1** | Backend: stats endpoints | Implementar `GET /stats/overview`, `/stats/coverage`, `/stats/feedback` en FastAPI | Endpoints retornan datos agregados correctos |
| **2B.2** | Backend: jobs endpoint | Implementar `GET /api/v1/jobs` con paginación y filtros | Devuelve ingest_jobs históricos |
| **2B.3** | Backend: token CRUD | Implementar `POST/GET/DELETE /api/v1/tokens` y `/tokens/{id}/audit` | Tokens se crean, listan, revocan con audit |
| **2B.4** | Backend: auth verify | Implementar `POST /api/v1/auth/verify` para NextAuth credentials | Devuelve user data si credenciales válidas |
| **2B.5** | Backend: MCP token auth | Middleware en MCP server que valida `Authorization: Bearer` contra mcp_token | MCP rechaza requests sin token válido |
| **2B.6** | Backend: file upload | Implementar `POST /api/v1/upload` (multipart, guarda en /app/sources/) | Archivo disponible para ingest posterior |
| **2B.7** | Dashboard overview page | Cards de KPIs, actividad reciente, gráfica de ingestas, alertas de gaps | Datos reales del backend |
| **2B.8** | Source browser | Tabla paginada, filtros, sort, actions | Navegar, filtrar, paginar sources |
| **2B.9** | Source detail page | Header, chunk list expandible, metadata panel, acciones | Ver chunks y metadata de un documento |
| **2B.10** | Ingest page | Dropzone, preview, opciones, progress tracking | Ingestar archivo via UI exitosamente |
| **2B.11** | Search playground | Query input, filtros, results cards, citations | Búsqueda RAG funcional desde UI |
| **2B.12** | Coverage matrix | Heatmap tabla, gap detection, drill-down | Visualizar cobertura por message_type × source_type |
| **2B.13** | Ingestion history | Timeline de jobs, filtros, re-run | Ver historial completo de ingestas |
| **2B.14** | Feedback dashboard | KPIs, tabla, gráficas | Visualizar calidad de las respuestas |
| **2B.15** | MCP token manager | CRUD tokens, reveal dialog, audit log, config snippet | Crear/revocar tokens, ver uso |
| **2B.16** | Settings page | Health check live, config display, DB stats | Ver estado del sistema |

### Phase 2C — Polish & Integration

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2C.1** | Dark mode | Toggle en topbar, tokens CSS, persiste en localStorage | Todos los componentes se ven bien en dark |
| **2C.2** | Empty states | Ilustraciones line-art para estados vacíos (sin sources, sin feedback, etc.) | Cada página vacía muestra estado apropiado |
| **2C.3** | Loading & error states | Skeletons, error boundaries, retry buttons | UX fluida en estados intermedios |
| **2C.4** | Quick search (topbar) | Cmd+K dialog, busca en sources + chunks + jobs | Acceso rápido a cualquier recurso |
| **2C.5** | Update .vscode/mcp.json | Configuración MCP con token auth obligatorio | MCP en VS Code funciona con token de la UI |
| **2C.6** | E2E testing | Playwright tests: login, CRUD sources, search, token flow | Suite verde con datos seed |
| **2C.7** | Documentation | README en `web/`, actualizar docker-compose docs, actualizar SECURITY.md | Onboarding claro para nuevo developer |

### Phase 2D — Wiring & Enrichment

> **Status**: Planning
> **Goal**: Wire remaining UI-only views to real backend data, add missing interactive actions, and introduce new features that complement the admin panel.

#### 2D-A: Feedback Loop (wire the admin UI)

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2D.1** | Feedback capture on search | Thumbs up/down + optional comment on each search result card | POST /api/v1/feedback called on click, toast confirmation |
| **2D.2** | Feedback detail table | Paginated table of individual feedbacks: query, rating, tool_name, date, chunk count | Table loads from new backend endpoint |
| **2D.3** | Backend: expanded feedback stats | Extend `GET /stats/feedback` with `rows[]` (per-query), `trend[]` (daily), `worst_performers[]` | New fields returned alongside existing aggregates |
| **2D.4** | Web proxy: POST /api/feedback | Next.js route handler that proxies to `POST /api/v1/feedback` | Feedback from search page flows through to DB |

#### 2D-B: Search & Navigation Enrichment

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2D.5** | Citation deep links | Search result citations link to `/sources/[id]?chunk=<chunk_id>` with scroll + highlight | Clicking citation navigates to source with highlighted chunk |
| **2D.6** | Search metadata panel | Collapsible side panel showing search_time_ms, total_candidates, reranker_model, query analysis | Panel visible after every search |

#### 2D-C: Source Management Actions

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2D.7** | Re-ingest action | Button in source detail header that calls `POST /api/v1/ingest` with existing source path | Re-ingest succeeds, chunks refreshed, toast + job link |
| **2D.8** | Delete source | Button with confirmation modal, calls `DELETE /api/v1/sources/{id}` | Source + chunks removed, redirect to /sources |
| **2D.9** | Download chunks JSON | Button that fetches all chunks for a source and triggers browser download | .json file downloaded with full chunk data |
| **2D.10** | Metadata summary panel | Sidebar in source detail aggregating message_types, PHP classes, XPaths from chunk metadata | Panel visible with clickable filters |
| **2D.11** | Source list sort | Column header sort for name, date, chunk count (client + server) | Clicking column toggles asc/desc sort |
| **2D.12** | Bulk operations | Multi-select checkboxes on source list + bulk delete / re-ingest toolbar | Select N sources → action → confirmation → execute |

#### 2D-D: Coverage & Jobs Interactivity

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2D.13** | Coverage cell drill-down | Click cell in coverage matrix → dialog/panel with matching chunks | Expandable detail with chunk previews + links to source |
| **2D.14** | Jobs status filters | Dropdown filters for status (completed/failed/skipped) and date range picker | Filters update job list |
| **2D.15** | Jobs re-run action | "Re-ingest" button per job row that triggers a new ingest for same source | New job created, appears in list |

#### 2D-E: Settings & System

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2D.16** | Live backend health | Settings page fetches `GET /health` from backend, shows per-service status (DB, embedding, reranker, LLM) | Live semaphore for each service |
| **2D.17** | Real DB statistics | New backend endpoint `GET /api/v1/stats/db` returning table sizes, row counts, DB size | Settings page displays real DB stats |
| **2D.18** | Editable config | Allow changing LLM provider/model and embedding provider via settings UI (persists to `config` table or `.env`) | Changes saved and reflected on next request |

#### 2D-F: New Complementary Features

| # | Task | Descripción | Acceptance Criteria |
|---|------|-------------|---------------------|
| **2D.19** | Toast notifications | Global toast system for ingest complete, token revoked, errors, feedback submitted | Sonner toasts appear for all async actions |
| **2D.20** | User management | Admin page to list, invite (create), deactivate admin_user records | CRUD operations on admin_user table |
| **2D.21** | Global audit log | Page showing recent activity across all entities (logins, ingests, token usage, searches) | Filterable chronological event stream |
| **2D.22** | Source version diff | When re-ingesting, show diff between old and new chunks (added/removed/changed) | Side-by-side or unified diff view |
| **2D.23** | Export to CSV | Export buttons on search results, feedback table, coverage matrix, source list | Browser downloads .csv file |
| **2D.24** | Real-time ingest progress | WebSocket/SSE connection for live ingest progress on dashboard and ingest page | Progress bar updates without polling |

---

## 7. Execution TODO

```
PHASE 2A — Foundation
[x] 2A.1   Scaffold Next.js project (App Router + TS + Tailwind)
[x] 2A.2   Install & configure shadcn/ui components
[x] 2A.3   Design tokens & theme ("The Clerk" palette + fonts)
[x] 2A.4   DB migration: admin_user + mcp_token tables
[x] 2A.5   Seed script: initial admin user (bcrypt)
[x] 2A.6   NextAuth.js credentials provider setup
[x] 2A.7   Login page (styled, with error handling)
[x] 2A.8   Dashboard layout (sidebar + topbar + main)
[x] 2A.9   Typed RAG API client (lib/api-client.ts)
[x] 2A.10  Testing setup (Vitest + RTL + Playwright + coverage)
[x] 2A.11  npm audit clean + CI quality gates
[x] 2A.12  Dockerfile (Node 22 LTS) + docker-compose web service

PHASE 2B — Core Features
[x] 2B.1   Backend: GET /stats/overview, /stats/coverage, /stats/feedback
[x] 2B.2   Backend: GET /api/v1/jobs (paginated)
[x] 2B.3   Backend: POST/GET/DELETE /api/v1/tokens + audit
[x] 2B.4   Backend: POST /api/v1/auth/verify
[x] 2B.5   Backend: MCP server Bearer token validation middleware
[x] 2B.6   Backend: POST /api/v1/upload (multipart file upload)
[x] 2B.7   Dashboard overview page (KPIs, activity, chart, alerts)
[x] 2B.8   Source browser page (table, filters, actions)
[x] 2B.9   Source detail page (chunks, metadata, actions)
[x] 2B.10  Ingest page (dropzone, preview, progress)
[x] 2B.11  Search playground page (query, filters, results)
[x] 2B.12  Coverage matrix page (heatmap, gaps)
[x] 2B.13  Ingestion history page (timeline, re-run)
[x] 2B.14  Feedback dashboard page (KPIs, charts)
[x] 2B.15  MCP token manager page (CRUD, audit, snippet)
[x] 2B.16  Settings page (health, config, DB stats)

PHASE 2C — Polish
[x] 2C.1   Dark mode toggle + theme persistence
[x] 2C.2   Empty state illustrations
[x] 2C.3   Loading skeletons + error boundaries
[x] 2C.4   Quick search (Cmd+K) dialog
[x] 2C.5   Update .vscode/mcp.json with token auth
[x] 2C.6   E2E tests (Playwright)
[x] 2C.7   Documentation updates

PHASE 2D — Wiring & Enrichment
[x] 2D.1   Feedback: thumbs up/down on search results
[x] 2D.2   Feedback: per-query table + trend chart + worst performers
[x] 2D.3   Backend: expand GET /stats/feedback with detail rows + trend
[x] 2D.4   Backend: web proxy route POST /api/feedback
[x] 2D.5   Search: citation links navigate to /sources/[id] with chunk highlight
[x] 2D.6   Search: metadata side panel (search_time, candidates, query analysis)
[x] 2D.7   Sources detail: re-ingest action button
[x] 2D.8   Sources detail: delete action with confirmation modal
[x] 2D.9   Sources detail: download chunks as JSON
[x] 2D.10  Sources detail: metadata summary panel (message_types, classes, xpaths)
[x] 2D.11  Sources list: sort by name / date / chunk count
[x] 2D.12  Coverage: cell click drills down to chunk list
[x] 2D.13  Jobs: status & date filters
[x] 2D.14  Jobs: re-run (re-ingest) action per job
[x] 2D.15  Settings: live health from backend /health (service statuses)
[x] 2D.16  Settings: real DB stats (table sizes, row counts)
[ ] 2D.17  Settings: editable LLM / embedding config — DEFERRED (requires config persistence layer)
[x] 2D.18  Notifications: toast on ingest complete / token revoked / errors
[x] 2D.19  User management: CRUD admin users (list, invite, deactivate)
[x] 2D.20  Audit log viewer: global activity log (token usage, logins, ingest events)
[ ] 2D.21  Source comparison: diff view — DEFERRED (requires chunk versioning)
[x] 2D.22  Bulk operations: multi-select sources for delete / re-ingest
[x] 2D.23  Export: download search results / feedback / coverage as CSV
[ ] 2D.24  Dashboard: real-time WebSocket updates — DEFERRED (requires SSE/WS infrastructure)
[x] MCP transport: upgraded from legacy SSE to streamable HTTP (MCP 2025-03-26 spec)
[x] UPDATE test, readme, documentation, run audit fix
```

---

## 8. Dependencies & Packages

### Frontend (web/package.json)

| Package | Version | Purpose |
|---------|---------|----------|
| `next` | 16.1.6 | Framework (App Router) |
| `react` / `react-dom` | 19.2.3 | UI library |
| `typescript` | ^5 | Type safety (strict mode) |
| `tailwindcss` | ^4 | Styling (via `@tailwindcss/postcss`) |
| `@base-ui/react` | ^1.3.0 | Accessible primitives (shadcn/ui) |
| `@radix-ui/react-dropdown-menu` | ^2.1.16 | Dropdown menu (shadcn fallback) |
| `next-auth` | ^5.0.0-beta.30 | Authentication (Auth.js v5, credentials) |
| `bcryptjs` | ^3.0.3 | Password hashing |
| `recharts` | ^3.8.0 | Charts (dashboard, feedback) |
| `@tanstack/react-table` | ^8.21.3 | Data tables (sources, chunks, tokens) |
| `react-dropzone` | ^15.0.0 | File upload (ingest) |
| `cmdk` | ^1.1.1 | Command palette (Cmd+K search) |
| `sonner` | ^2.0.7 | Toast notifications |
| `date-fns` | ^4.1.0 | Date formatting |
| `zod` | ^4.3.6 | Form validation |
| `lucide-react` | ^0.577.0 | Icons |
| `class-variance-authority` | ^0.7.1 | Component variant utilities |
| `clsx` / `tailwind-merge` | latest | Class name utilities |

### Testing & Quality (web/package.json devDependencies)

| Package | Version | Purpose |
|---------|---------|----------|
| `vitest` | ^4.1.0 | Unit test runner (Vite-based, Jest-compatible API) |
| `@vitejs/plugin-react` | ^6.0.1 | React support for Vitest |
| `@testing-library/react` | ^16.3.2 | Component testing utilities |
| `@testing-library/jest-dom` | ^6.9.1 | Custom DOM matchers |
| `@testing-library/user-event` | ^14.6.1 | User interaction simulation |
| `@playwright/test` | ^1.58.2 | E2E browser testing |
| `@vitest/coverage-v8` | ^4.1.0 | Code coverage (target >70%) |
| `msw` | ^2.12.11 | API mocking for integration tests |
| `jsdom` | ^29.0.0 | DOM environment for unit tests |

### Backend additions (requirements.txt)

| Package | Purpose |
|---------|---------|
| `bcrypt` | Admin password hashing |
| `python-multipart` | File upload support (already in deps) |

---

## 9. Risk Matrix

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| MCP token leak en logs | Media | Alto | Never log token body, only prefix. Structured logging |
| Rate limit bypass | Baja | Medio | Server-side sliding window, no client-side enforcement |
| Admin password brute force | Media | Alto | bcrypt cost 12, account lockout after 5 attempts, rate limit login |
| CSRF en admin UI | Baja | Alto | NextAuth CSRF token, SameSite cookie, Origin header check |
| Stale coverage data | Media | Bajo | Revalidate con ISR (5 min), manual refresh button |
| Docker network exposure | Baja | Alto | Only web port exposed, internal services on rag-net only |
| Dependencias con CVEs | Media | Alto | `npm audit` en Dockerfile build stage + CI. Falla el build si high/critical |
| TypeScript drift (any) | Media | Medio | `strict: true`, ESLint `@typescript-eslint/no-explicit-any` rule, CI type-check |
| Tests sin mantenimiento | Media | Medio | Coverage gate >70%, tests deben pasar para merge. Vitest watch en dev |