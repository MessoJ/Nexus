FROM node:20-alpine AS dev
WORKDIR /app

# Install deps for dev
COPY package*.json ./
RUN npm ci || npm install
# Copy app for dev
COPY . .
EXPOSE 5173
# Dev server
CMD ["npm", "run", "dev", "--", "--host"]

FROM node:20-alpine AS builder
WORKDIR /app

# Install dependencies first for caching
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM node:20-alpine
WORKDIR /app

# Copy built files from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./

# For development, we'll override with docker-compose volumes
EXPOSE 5173

# Default to production server
CMD ["npm", "run", "serve"]

# For development (override in compose):
# CMD ["npm", "run", "dev", "--", "--host"]
