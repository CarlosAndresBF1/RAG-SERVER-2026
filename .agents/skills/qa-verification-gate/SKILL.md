---
name: qa-verification-gate
description: "Post-implementation QA verification gate for the Odyssey RAG project. MUST be invoked after every implementation batch. Covers code review, static analysis, tests, Docker validation, MCP functional test, and commit."
---

# QA Verification Gate

Mandatory post-implementation quality gate. Every batch of changes MUST pass through this gate before being considered done.

## When to Use This Skill

- After implementing any batch of code changes (quick wins, sprint items, bug fixes)
- Before committing changes to the repository
- As a permanent team process — not a one-time check

## Verification Phases (All Required)

### Phase 1: Code Review
- Review all changed files for correctness
- Check for anti-patterns (dead fields, missing filters, sync in async)
- Verify backward compatibility with existing contracts

### Phase 2: Static Analysis
```bash
cd RAG
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format --check src/ tests/
```
Pre-existing lint issues are acceptable. New violations are NOT.

### Phase 3: Unit Tests
```bash
cd RAG
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -x --tb=short -q
```
- ALL existing tests must pass (204+ baseline)
- New tests should be added for new code
- Zero regressions allowed

### Phase 4: Docker Build & Run
```bash
cd RAG
docker compose build
docker compose up -d
# Wait for all 4 services to be healthy
docker compose ps
```
Services: postgres (5433), rag-api (8089), mcp-server (3010), web (3044)

### Phase 5: Health Endpoints
```bash
curl -s http://localhost:8089/api/v1/health | jq .
curl -s http://localhost:3010/health | jq .
```
Both must return 200 with status: "ok"

### Phase 6: MCP Functional Test
Verify at least one MCP tool call works end-to-end.

### Phase 7: Commit (only if all phases pass)
```bash
cd RAG
git add -A
git commit -m "description of changes

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Phase 8: Push (when everything is green)
Only push after user approval.

## Lockout Rules

If a reviewer finds bugs in Agent A's code:
- Agent A is LOCKED OUT of fixing their own bugs
- A different agent (Agent B) must implement the fix
- This prevents confirmation bias

## Reporting

Write verification results to `.squad/decisions/inbox/hockney-{slug}.md` with:
- Phase-by-phase pass/fail status
- Any findings (with severity)
- Commit hash (if applicable)
- Follow-up items (if any)

---

*Established: 2026-04-17 | Status: Permanent team directive*
