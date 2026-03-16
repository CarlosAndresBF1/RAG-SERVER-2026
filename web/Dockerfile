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
