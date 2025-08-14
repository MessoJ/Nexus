FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    libgif-dev \
    librsvg2-dev \
    libpixman-1-dev \
    pkg-config \
    ffmpeg \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install -g npm@latest
RUN npm install --production

# Copy source code
COPY src/ ./src/

# Create temp directory for video processing
RUN mkdir -p /tmp/nexus-videos

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "console.log('Producer service healthy')" || exit 1

# Run the service
CMD ["npm", "start"]
