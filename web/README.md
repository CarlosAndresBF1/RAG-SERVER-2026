# Oddysey RAG — Admin Dashboard

The Clerk-themed admin UI for Oddysey RAG. Built with **Next.js 16**, **React 19**, **Tailwind CSS 4**, and **shadcn/ui**.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 16 (App Router) |
| UI | Tailwind CSS 4 + shadcn/ui (base-ui) |
| Auth | NextAuth.js v5 (credentials) |
| Charts | Recharts |
| Command palette | cmdk |
| Testing | Vitest (unit) · Playwright (E2E) |

## Getting Started

```bash
# Install dependencies
npm install

# Start dev server (connects to RAG API at localhost:8089)
npm run dev
```

Open http://localhost:3000 — you'll be redirected to the login page.

**Default credentials** (seeded via `003_seed_config.sql`):
- Email: `admin@odyssey.local`
- Password: `admin`

## Project Structure

```
src/
├── app/
│   ├── (auth)/login/       # Login page
│   ├── (dashboard)/        # Authenticated pages
│   │   ├── page.tsx        # Overview dashboard
│   │   ├── sources/        # Source browser + detail
│   │   ├── ingest/         # File upload & ingestion
│   │   ├── search/         # Search playground
│   │   ├── coverage/       # Coverage matrix
│   │   ├── jobs/           # Jobs history
│   │   ├── feedback/       # Feedback dashboard
│   │   ├── tokens/         # MCP token manager
│   │   └── settings/       # Health & config
│   └── api/                # API proxy routes
├── components/
│   ├── layout/             # Sidebar, Topbar
│   ├── command-palette.tsx  # Cmd+K navigation
│   ├── empty-state.tsx     # Empty state illustrations
│   ├── skeleton.tsx        # Loading skeletons
│   └── theme-provider.tsx  # Dark mode
├── lib/                    # Auth config, utils
└── types/                  # TypeScript API types
```

## Key Features

- **Dark mode** with system preference detection and localStorage persistence
- **Cmd+K** command palette for quick page navigation
- **Loading skeletons** via Next.js Suspense boundaries
- **Error boundaries** with retry for graceful error handling
- **MCP token management** with SHA-256 client-side hashing
- **Drag & drop file upload** with automatic source type detection

## Scripts

```bash
npm run dev          # Development server
npm run build        # Production build
npm run lint         # ESLint
npm run test         # Vitest unit tests
npx playwright test  # E2E tests
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXTAUTH_SECRET` | (required) | Session encryption key |
| `NEXTAUTH_URL` | `http://localhost:3000` | Auth callback base URL |
| `RAG_API_URL` | `http://localhost:8089` | Backend API base URL |
