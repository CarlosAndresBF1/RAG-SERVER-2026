# Odyssey RAG — Descripcion Completa del Sistema

## Que es?

Odyssey RAG es un **sistema de conocimiento inteligente** que indexa toda la documentacion del proyecto Odyssey (especificaciones ISO 20022, mensajería IPS Annex B, codigo PHP de Bimpay, ejemplos XML) y permite que agentes de IA (como GitHub Copilot en VS Code) consulten esa informacion de forma precisa, con citas y sin inventar nada.

En terminos simples: es un "cerebro" que lee tus documentos, los entiende, los guarda, y despues responde preguntas sobre ellos.

---

## Las 4 Etapas del Sistema

```
 ╔═══════════════╗     ╔═══════════════╗     ╔═══════════════╗     ╔═══════════════╗
 ║  1. INGESTION ║ ──▶ ║ 2. ANALISIS   ║ ──▶ ║  3. GUARDADO  ║ ──▶ ║  4. CONSULTA  ║
 ║  (Entrada)    ║     ║ (Procesamiento)║     ║ (Almacenamiento)║     ║  (Busqueda)   ║
 ╚═══════════════╝     ╚═══════════════╝     ╚═══════════════╝     ╚═══════════════╝
```

---

## ETAPA 1: Ingestion (Entrada de Documentos)

**Que hace?** Recibe archivos fuente y los prepara para ser procesados.

### Como se activa?

| Metodo | Descripcion |
|--------|-------------|
| `POST /api/v1/ingest` | Llamada HTTP manual o desde la UI web |
| `odyssey_rag.ingest` | Tool MCP invocado desde VS Code |
| `seed_initial_sources.py` | Script para carga inicial masiva |

### Tipos de archivo soportados

- **Markdown** (.md) — Especificaciones Annex B, docs tecnicos, guias
- **Codigo PHP** (.php) — Clases del proyecto Bimpay (builders, parsers, validators)
- **XML** (.xml) — Ejemplos de mensajes ISO 20022 (pacs, camt, pain)
- **PDF** (.pdf) — Documentacion general
- **Postman** (.json) — Colecciones de API

### Deteccion automatica de tipo

El sistema detecta el tipo de archivo por su nombre usando reglas de patron:
- `IPS_Annex_B*.md` → `annex_b_spec`
- `*.php` → `php_code`
- `*.xml` → `xml_example`
- `*.md` → `generic_text` (fallback)

Tambien se puede forzar el tipo manualmente al ingestar.

### Deduplicacion

Calcula un hash **SHA-256** del archivo. Si ya fue ingestado y no cambio, lo salta automaticamente.

**Tecnologia clave:** Python + FastAPI para la API REST.
**Codigo:** `src/odyssey_rag/ingestion/pipeline.py`

---

## ETAPA 2: Analisis (Parsing + Chunking + Metadata)

**Que hace?** Descompone cada documento en fragmentos pequeños ("chunks") que el sistema puede buscar eficientemente, y extrae metadata estructurada.

### 2a. Parsing (Lectura Inteligente)

Cada tipo de archivo tiene su propio **parser** que entiende su estructura:

| Parser | Archivos | Que hace |
|--------|----------|----------|
| **MarkdownParser** | Annex B, docs tecnicos | Divide por encabezados (H1/H2/H3). Para Annex B, detecta tablas de campos ISO con XPath, multiplicidad, status |
| **PhpCodeParser** | Codigo PHP Bimpay | Extrae clases, metodos publicos, constantes como secciones independientes |
| **XmlExampleParser** | Mensajes XML ISO | Descompone mensajes XML por tipo y seccion |
| **GenericTextParser** | Cualquier otro texto | Fallback para archivos no especializados |

**Codigo:** `src/odyssey_rag/ingestion/parsers/`

### 2b. Chunking (Fragmentacion)

Cada seccion parseada se divide en **chunks** de tamaño manejable. La estrategia varia segun el tipo:

- **Markdown**: corta por jerarquia de encabezados (cada seccion H2/H3 es un chunk)
- **PHP**: cada metodo publico de una clase es un chunk independiente
- **XML**: cada tipo de mensaje + seccion es un chunk
- **Generico**: por tamaño de tokens con overlap

**Codigo:** `src/odyssey_rag/ingestion/chunkers/`

### 2c. Extraccion de Metadata

De cada chunk se extrae metadata estructurada que permite filtrar busquedas:

| Campo | Ejemplo | Uso |
|-------|---------|-----|
| `message_type` | pacs.008, camt.056 | Filtrar por tipo de mensaje ISO |
| `iso_version` | pacs.008.001.12 | Version exacta del mensaje |
| `module_path` | Bimpay/Messages/Pacs008CreditTransfer.php | Ubicar codigo fuente |
| `php_class` | Pacs008CreditTransfer | Clase PHP asociada |
| `php_symbol` | buildGroupHeader | Metodo especifico |
| `field_xpath` | GrpHdr/MsgId | Campo XML especifico |
| `rule_status` | M (Mandatorio), O (Opcional), C (Condicional) | Obligatoriedad del campo |
| `source_type` | annex_b_spec, php_code, xml_example | Tipo de fuente |

**Codigo:** `src/odyssey_rag/ingestion/metadata/`

---

## ETAPA 3: Guardado (Embeddings + Almacenamiento)

**Que hace?** Convierte cada chunk en un vector numerico y lo guarda junto con su texto y metadata en la base de datos.

### 3a. Generacion de Embeddings

Cada chunk de texto se convierte en un **vector de 768 dimensiones** usando el modelo **nomic-embed-text v1.5**.

**Que es un embedding?** Es una representacion matematica del significado del texto. Textos con significado similar tendran vectores cercanos en el espacio. Esto permite busqueda por **concepto**, no solo por palabras exactas.

**Ejemplo simplificado:**
```
"campos obligatorios del Group Header" → [0.23, -0.87, 0.45, ..., 0.12]  (768 numeros)
"mandatory fields in GrpHdr"          → [0.21, -0.85, 0.44, ..., 0.11]  (muy similar!)
```

| Aspecto | Detalle |
|---------|---------|
| **Modelo** | nomic-embed-text v1.5 |
| **Dimensiones** | 768 numeros por chunk |
| **Donde corre** | Localmente dentro del contenedor Docker (cero costo de API) |
| **Ventana de contexto** | 8,192 tokens por chunk |
| **Libreria** | sentence-transformers (Python) |

**Codigo:** `src/odyssey_rag/embeddings/`

### 3b. Almacenamiento en PostgreSQL + pgvector

Todo se guarda en una base de datos **PostgreSQL 16** con la extension **pgvector**:

| Tabla | Que guarda |
|-------|------------|
| `document` | Archivo fuente original (ruta, tipo, hash SHA-256, version) |
| `chunk` | Fragmento de texto + indice tsvector para busqueda por palabras |
| `chunk_embedding` | Vector de 768 dimensiones asociado a cada chunk |
| `chunk_metadata` | Metadata estructurada (message_type, php_class, field_xpath, etc.) |
| `ingest_job` | Registro de cada proceso de ingestion (status, errores, duracion) |
| `feedback` | Feedback de usuarios sobre la calidad de las respuestas |
| `mcp_token` | Tokens de acceso para el servidor MCP |
| `admin_user` | Usuarios administradores del panel web |

**Porque PostgreSQL y no una BD vectorial dedicada (Pinecone, Weaviate)?**
- Ya se usa PostgreSQL en el ecosistema Odyssey → familiaridad del equipo
- Una sola BD para vectores + metadata + full-text search + feedback
- Menos componentes = operacion mas simple
- pgvector tiene rendimiento excelente para <100K chunks

**Indices importantes:**
- **HNSW** (pgvector): indice para busqueda rapida por similitud de vectores
- **tsvector + GIN**: indice para busqueda full-text (similar a BM25)
- **pg_trgm**: para busqueda por similitud de trigramas

**Codigo:** `db/init/002_schema.sql`, `db/migrations/`

---

## ETAPA 4: Consulta (Busqueda Hibrida + Reranking)

**Que hace?** Cuando alguien hace una pregunta, el sistema combina dos tipos de busqueda, fusiona resultados, los reordena con IA y arma una respuesta con citas exactas.

### 4a. Pre-procesamiento de la Query

El `QueryProcessor` analiza la pregunta y la prepara:

1. **Detecta el tipo de mensaje** mencionado (ej. "pacs.008")
2. **Detecta la intencion** (buscar mensaje, regla de negocio, modulo, error, general)
3. **Expande abreviaciones** para enriquecer la busqueda:
   - "pacs" → "payment clearing and settlement"
   - "GrpHdr" → "Group Header"
   - "BIC" → "Business Identifier Code"
4. **Construye filtros de metadata** (ej. `message_type = 'pacs.008'`)

**Codigo:** `src/odyssey_rag/retrieval/query_processor.py`

### 4b. Busqueda Hibrida (dos busquedas en paralelo)

Se ejecutan **dos busquedas simultaneas** y complementarias:

| Busqueda | Como funciona | Buena para |
|----------|---------------|------------|
| **Vector (Semantica)** | Compara el embedding de la pregunta contra los embeddings de los chunks usando similitud coseno via pgvector | Preguntas conceptuales: "como construyo un mensaje de transferencia?" |
| **BM25 (Palabras clave)** | Busqueda full-text clasica usando PostgreSQL tsvector con ranking por densidad | Terminos exactos: "GrpHdr/MsgId", "RJCT", "FF01", "pacs.008" |

**Porque dos busquedas?** Cada una tiene fortalezas distintas. La semantica entiende conceptos; la BM25 encuentra terminos exactos. Combinandolas, se obtiene lo mejor de ambos mundos.

**Codigo:** `src/odyssey_rag/retrieval/vector_search.py` y `src/odyssey_rag/retrieval/bm25_search.py`

### 4c. Fusion con RRF (Reciprocal Rank Fusion)

Los resultados de ambas busquedas se combinan con el algoritmo **RRF**:

```
RRF_score(chunk) = 1/(60 + rank_vector) + 1/(60 + rank_bm25)
```

Si un chunk aparece bien rankeado en AMBAS busquedas, su score combinado es alto. Si solo aparece en una, su score es moderado. Esto produce una lista unificada y balanceada.

**Codigo:** `src/odyssey_rag/retrieval/fusion.py`

### 4d. Reranking con Cross-Encoder

Los top ~20 resultados fusionados pasan por un **cross-encoder** que evalua la relevancia con mayor precision:

| Aspecto | Detalle |
|---------|---------|
| **Modelo** | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| **Que hace** | Toma cada par (pregunta, chunk_candidato) y da un score de relevancia preciso |
| **Parametros** | 22M (modelo pequeño y rapido) |
| **Velocidad** | ~10ms por par en CPU |
| **Resultado** | Selecciona los top 5-8 chunks mas relevantes |

**Porque un reranker?** Los embeddings son rapidos pero aproximados. El cross-encoder es mas lento pero mucho mas preciso porque ve la pregunta y el chunk juntos, no por separado.

**Codigo:** `src/odyssey_rag/retrieval/reranker.py`

### 4e. Ensamblado de Respuesta

El `ResponseBuilder` arma la respuesta final con tres secciones:

```json
{
  "evidence": [
    {
      "text": "GrpHdr/MsgId es Mandatory [1..1], Max35Text...",
      "score": 0.87,
      "citations": [{ "source_path": "IPS_Annex_B.md", "section": "pacs.008 > GrpHdr" }]
    }
  ],
  "gaps": [
    "No se encontro documentacion sobre timeout en pacs.008"
  ],
  "followups": [
    { "tool": "odyssey_rag.find_error", "args": {"iso_status": "RJCT"} }
  ]
}
```

**Principio fundamental:** `strict_citations=true` — si no hay evidencia, se reporta como **gap** (vacio). **Nunca se inventa información.**

**Codigo:** `src/odyssey_rag/retrieval/response_builder.py`

---

## El Servidor MCP (Model Context Protocol)

### Que es MCP?

MCP es un protocolo estandar creado por Anthropic que permite a agentes de IA (como Copilot, Claude Code) comunicarse con herramientas externas de forma segura y estructurada. Es el "puente" entre VS Code y el RAG.

### Como funciona?

VS Code se conecta al servidor MCP via HTTP Streamable (`POST http://localhost:3010/mcp/`) y puede llamar cualquiera de las 6 herramientas como si fueran funciones nativas del agente.

**Tecnologia:** SDK oficial de Anthropic para MCP (`mcp` Python SDK v1.9.4), transporte Streamable HTTP (spec MCP 2025-03-26).

### Las 6 Herramientas MCP

| Herramienta | Proposito | Ejemplo de uso |
|-------------|-----------|----------------|
| `odyssey_rag.find_message_type` | Buscar especificacion completa de un tipo de mensaje ISO 20022 (campos Annex B, codigo PHP, ejemplos XML) | "Que campos tiene un pacs.008?" |
| `odyssey_rag.find_business_rule` | Buscar reglas de negocio y validaciones del sistema | "Cual es la regla para el monto maximo de transferencias?" |
| `odyssey_rag.find_module` | Buscar modulos y clases PHP del proyecto Bimpay | "Donde esta el parser de camt.056?" |
| `odyssey_rag.find_error` | Buscar codigos de error ISO y diagnostico de problemas | "Que significa el error FF01 en un RJCT de pacs.002?" |
| `odyssey_rag.search` | Busqueda libre de texto general | "Como funciona el poller de IPS?" |
| `odyssey_rag.ingest` | Ingestar nuevos documentos al sistema de conocimiento | "Indexa este nuevo archivo de spec" |

### Contrato de Salida (todas las herramientas)

Todas las herramientas devuelven el mismo formato:
- **evidence[]**: Chunks relevantes con citas exactas a la fuente original
- **gaps[]**: Lo que NO se encontro (transparencia total, sin inventar)
- **followups[]**: Sugerencias de consultas adicionales con otras herramientas

### Autenticacion MCP

Los clientes se autentican con tokens Bearer generados desde el panel web:
- Token generado client-side, hasheado con SHA-256
- Solo el hash se almacena en la BD (seguridad)
- Scopes: read, write, admin
- Rate limiting por token (RPM)
- Audit log de cada uso

**Codigo:** `src/odyssey_rag/mcp_server/`

---

## El Panel Web (Admin Dashboard)

Una interfaz web completa para administrar el sistema RAG.

### Paginas principales

| Pagina | Funcion |
|--------|---------|
| **Dashboard** | Vista general: documentos indexados, chunks, tendencias |
| **Sources** | Lista de documentos indexados, estado, chunks por documento |
| **Ingest** | Subir y procesar nuevos documentos |
| **Search** | Probar busquedas manualmente contra el RAG |
| **Coverage** | Matriz de cobertura: que message_types tienen documentacion |
| **Jobs** | Monitorear procesos de ingestion (pendientes, en progreso, completados, fallidos) |
| **Feedback** | Feedback de usuarios sobre calidad de respuestas |
| **Tokens** | Gestionar tokens MCP (crear, revocar, audit log) |
| **Users** | Administrar usuarios del panel |
| **Audit Log** | Registro de todas las acciones del sistema |
| **Settings** | Configuracion general |

### Stack del Frontend

| Tecnologia | Version | Funcion |
|------------|---------|---------|
| **Next.js** | 16 (App Router) | Framework React full-stack |
| **React** | 19 | Motor de UI |
| **TypeScript** | 5 (strict) | Tipado estatico |
| **Tailwind CSS** | 4 | Estilos utility-first |
| **shadcn/ui** | base-ui/react | Componentes UI accesibles |
| **NextAuth.js** | v5 | Autenticacion (credentials + JWT) |

**Puerto:** `http://localhost:3044` (desarrollo)
**Codigo:** `web/src/`

---

## LLM Providers (Generacion de Respuestas)

El sistema usa un **patron de proveedor abstracto** para generar respuestas en lenguaje natural basadas en los chunks recuperados. Es intercambiable con solo cambiar una variable de entorno:

| Proveedor | Modelo | Cuando usarlo |
|-----------|--------|---------------|
| **OpenAI** | GPT-4o | Principal, por defecto. Mejor calidad de respuesta |
| **Anthropic** | Claude Sonnet | Alternativa. Excelente para codigo y razonamiento |
| **Google** | Gemini 2.5 Pro | Alternativa. Buena ventana de contexto |
| **Ollama** | Llama 3.1 (local) | Sin costo, privacidad total. Corre localmente |

Cambiar de proveedor: solo modificar `LLM_PROVIDER=openai` en el `.env`.

Todos usan adaptadores de **LangChain**, lo que permite la intercambiabilidad.

**Codigo:** `src/odyssey_rag/llm/` (factory.py + un provider por LLM)

---

## Resumen de Tecnologias

```
┌──────────────────────────────────────────────────────────────────────┐
│                    STACK TECNOLOGICO COMPLETO                        │
├─────────────────────┬────────────────────────┬───────────────────────┤
│      CAPA           │     TECNOLOGIA         │     FUNCION           │
├─────────────────────┼────────────────────────┼───────────────────────┤
│ Backend API         │ Python 3.11 + FastAPI  │ API REST asincrona    │
│ Base de datos       │ PostgreSQL 16          │ Almacenamiento central│
│ Vectores            │ pgvector extension     │ Busqueda semantica    │
│ Full-text search    │ tsvector + pg_trgm     │ Busqueda por palabras │
│ Embeddings (local)  │ nomic-embed-text v1.5  │ Texto → vector 768d   │
│ Reranking (local)   │ ms-marco-MiniLM-L-6-v2│ Precision de busqueda │
│ LLM (respuestas)    │ GPT-4o / Claude / etc  │ Generacion de texto   │
│ MCP Server          │ mcp SDK (Anthropic)    │ Protocolo para IA     │
│ Frontend            │ Next.js 16 + React 19  │ Dashboard web admin   │
│ UI Components       │ shadcn/ui + Tailwind 4 │ Interfaz visual       │
│ Autenticacion       │ NextAuth v5 (JWT)      │ Login y sesiones      │
│ ORM                 │ SQLAlchemy async        │ Acceso a BD           │
│ Contenedores        │ Docker + Compose       │ Despliegue unificado  │
│ Orquestacion        │ LangChain              │ Cadenas de LLM        │
│ Testing Backend     │ pytest + pytest-asyncio│ Tests asincrono       │
│ Testing Frontend    │ Vitest + Playwright    │ Tests unitarios + E2E │
│ Linting             │ Ruff (Python)          │ Calidad de codigo     │
└─────────────────────┴────────────────────────┴───────────────────────┘
```

---

## Infraestructura Docker

Todo corre en un solo `docker compose up`:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Docker Compose                              │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  PostgreSQL   │  │   RAG API    │  │  MCP Server  │          │
│  │  + pgvector   │  │  (FastAPI)   │  │  (mcp SDK)   │          │
│  │  port: 5432   │  │  port: 8080  │  │  port: 3010  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ▲                  ▲                  ▲                  │
│         │                  │                  │                  │
│  ┌──────────────┐          │                  │                  │
│  │   Web UI      │─────────┘                  │                  │
│  │  (Next.js)    │                            │                  │
│  │  port: 3044   │                            │                  │
│  └──────────────┘                             │                  │
│                                               │                  │
│                                    VS Code / Copilot             │
│                                     (via MCP HTTP)               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flujo Completo (Ejemplo de Punta a Punta)

```
 1. INGESTION   → Se sube "01-pacs008-credit-transfer.md" via la UI web
         ↓
 2. PARSING     → MarkdownParser lo divide por encabezados H2/H3
         ↓
 3. CHUNKING    → Se generan ~25 chunks (GrpHdr, CdtTrfTxInf, SttlmInf...)
         ↓
 4. METADATA    → Se extrae: message_type=pacs.008, campos, status M/O/C
         ↓
 5. EMBEDDING   → nomic-embed convierte cada chunk en vector de 768 dims
         ↓
 6. STORAGE     → Se graban en PostgreSQL: document + chunks + embeddings + metadata
         ↓
         ↓  ... mas tarde, un desarrollador pregunta desde VS Code ...
         ↓
 7. MCP CALL    → Copilot llama odyssey_rag.find_message_type("pacs.008")
         ↓
 8. QUERY PREP  → Se pre-procesa la pregunta, se expanden abreviaciones
         ↓
 9. SEARCH      → Busqueda vector (semantica) + BM25 (keywords) en paralelo
         ↓
10. FUSION      → RRF combina ambos rankings en uno solo
         ↓
11. RERANK      → Cross-encoder reordena los top 20 → top 5-8
         ↓
12. RESPONSE    → Se arma { evidence[], gaps[], followups[] } con citas exactas
         ↓
13. RESULT      → Copilot recibe la respuesta y la muestra al desarrollador
```
