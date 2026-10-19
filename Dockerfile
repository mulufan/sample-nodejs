# Build stage: install production dependencies with npm
FROM node:22-trixie-slim AS build

ENV NODE_ENV=production

WORKDIR /app

# Install dependencies first so this layer is cached until the manifests change
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY app.js ./

# Runtime stage: distroless Node 22 (no shell, no package manager, no npm)
FROM gcr.io/distroless/nodejs22-debian13:nonroot

ENV NODE_ENV=production

WORKDIR /app

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/app.js ./

# Runs as the image's "nonroot" user (UID/GID 65532)
USER nonroot

EXPOSE 8080

CMD ["app.js"]
