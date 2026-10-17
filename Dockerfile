FROM node:22-bookworm-slim

ENV NODE_ENV=production

WORKDIR /app

# Install dependencies first so this layer is cached until the manifests change
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY app.js ./

USER node

EXPOSE 8080

CMD ["node", "app.js"]
