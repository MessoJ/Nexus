FROM node:20-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY services/frontend/dashboard/package*.json ./
RUN npm install --no-audit --no-fund

# Copy source files
COPY services/frontend/dashboard/public ./public
COPY services/frontend/dashboard/src ./src
COPY services/frontend/dashboard/tsconfig.json ./tsconfig.json
COPY services/frontend/dashboard/vite.config.ts ./vite.config.ts

# Bring logo from repository root into public assets
COPY churnlogo.png ./public/logo.png

# Build the application
RUN npm run build

# Install only production dependencies for the server
RUN npm install --only=production --no-audit --no-fund

# Copy the server file after building
COPY services/frontend/dashboard/server.js ./server.js

EXPOSE 5173
CMD ["npm", "run", "serve"]

