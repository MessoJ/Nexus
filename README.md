# Nexus Engine - Advanced Content Automation Platform

## Overview

Nexus Engine is a production-ready, enterprise-grade content automation platform that transforms raw content sources into engaging multimedia content and distributes it across multiple social media platforms. Built with modern microservices architecture, it features AI-powered content analysis, advanced media generation, and intelligent multi-platform distribution.

## 🚀 Latest Updates - Phase 2 & 3 Complete!

### ✅ Enhanced Media Generation (Phase 2)
- **Advanced Audio Generation**: ElevenLabs TTS integration with voice cloning
- **Professional Video Creation**: Pictory & RunwayML API integration with fallback generation
- **AI-Powered Visual Assets**: DALL-E & Midjourney integration for thumbnails and graphics
- **Multi-Format Export**: Landscape (16:9), Portrait (9:16), and Square (1:1) video formats
- **Robust Storage**: S3-compatible object storage with MinIO

### ✅ Multi-Platform Distribution (Phase 3)
- **YouTube Integration**: Full video upload with custom thumbnails and metadata
- **Instagram Publishing**: Posts, Stories, and Reels with optimal formatting
- **Twitter/X Distribution**: Text posts, threads, and media sharing
- **LinkedIn Publishing**: Professional content with article sharing
- **Smart Scheduling**: Optimal timing based on platform analytics
- **Real-Time Analytics**: Engagement tracking and performance metrics

## Architecture

### Core Services

1. **Harvester Service** - Content ingestion from RSS feeds and APIs
2. **AI Analyst Service** - Content analysis and optimization using OpenAI/Gemini
3. **Producer Service (Legacy)** - Basic media generation
4. **Producer-Nexus Service** - Advanced media generation with AI integration
5. **Dashboard Service** - Real-time monitoring and job management with enhanced UI
6. **Distributor Service (Legacy)** - Basic content distribution
7. **Distributor-Nexus Service** - Multi-platform social media distribution

### Infrastructure Components

- **PostgreSQL** - Primary database with connection pooling
- **RabbitMQ** - Message queue system for service communication
- **MinIO** - S3-compatible object storage for media assets
- **Docker Compose** - Local development orchestration
- **Redis** - Caching and session management (planned)

## Features

### 🎯 Content Processing Pipeline
- Automated RSS feed monitoring and content harvesting
- AI-powered content analysis and enhancement with multiple providers
- Multi-format content generation (articles, social posts, videos)
- Human-in-the-loop approval workflow with sophisticated dashboard
- Real-time job status tracking with WebSocket updates

### 📊 Enhanced Dashboard Capabilities
- **Modern Glassmorphism UI** with responsive design
- **Real-time Statistics** with auto-refresh functionality
- **Advanced Job Management** with modal dialogs and bulk operations
- **Smart Search & Filtering** by title, ID, and status
- **Export Capabilities** for analytics and reporting
- **Color-coded Status Indicators** for instant job status recognition

### 🎬 Advanced Media Generation
- **Professional Audio**: ElevenLabs TTS with voice selection and fallback generation
- **Dynamic Video Creation**: AI-powered video generation with multiple format support
- **Custom Thumbnails**: DALL-E and Midjourney integration for eye-catching visuals
- **Multi-format Assets**: Optimized content for each social platform
- **Robust Processing**: Error handling, retries, and graceful degradation

### 🌐 Multi-Platform Distribution
- **YouTube**: Full video uploads with custom thumbnails, descriptions, and tags
- **Instagram**: Posts, Stories, and Reels with platform-optimized formatting
- **Twitter/X**: Text posts, threads, and media with character optimization
- **LinkedIn**: Professional content sharing with article integration
- **Smart Scheduling**: Optimal posting times based on platform analytics
- **Engagement Tracking**: Real-time analytics and performance monitoring

## Quick Start

### Prerequisites
- Docker and Docker Compose
- 16GB+ RAM recommended for full media generation
- API keys for AI and social media services

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd nexus
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. Start the services:
```bash
docker-compose up -d
```

4. Access the services:
- **Main Dashboard**: http://localhost:8000
- **Distribution API**: http://localhost:8003
- **MinIO Console**: http://localhost:9001

## Configuration

### Environment Variables

Essential configuration in `.env`:

```env
# Database & Infrastructure
DATABASE_URL=postgresql://relayforge:relayforge_password@postgres:5432/relayforge
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET=relayforge-assets

# AI Services
OPENAI_API_KEY=your_openai_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
PICTORY_API_KEY=your_pictory_api_key_here
RUNWAY_API_KEY=your_runway_api_key_here

# Social Media APIs
YOUTUBE_CLIENT_ID=your_youtube_client_id_here
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret_here
TWITTER_API_KEY=your_twitter_api_key_here
INSTAGRAM_ACCESS_TOKEN=your_instagram_access_token_here
LINKEDIN_ACCESS_TOKEN=your_linkedin_access_token_here
```

### API Key Setup Guide

#### YouTube API Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials
5. Set up OAuth consent screen
6. Generate refresh token using OAuth flow

#### Twitter API Setup
1. Apply for Twitter Developer Account
2. Create a new App in Twitter Developer Portal
3. Generate API keys and access tokens
4. Enable OAuth 1.0a for media uploads

#### Instagram API Setup
1. Create Facebook Developer Account
2. Set up Instagram Basic Display API
3. Generate long-lived access tokens
4. Configure Instagram Business Account

#### LinkedIn API Setup
1. Create LinkedIn Developer Account
2. Create a new LinkedIn App
3. Request Marketing Developer Platform access
4. Generate access tokens with proper scopes

## API Documentation

### Enhanced Dashboard API
- `GET /` - Modern dashboard interface with real-time updates
- `GET /api/jobs` - List jobs with advanced filtering
- `POST /api/jobs/{id}/approve` - Approve job for distribution
- `DELETE /api/jobs/{id}` - Delete job with confirmation
- `GET /api/jobs/{id}` - Get detailed job information
- `POST /api/jobs/bulk-clear` - Clear multiple jobs

### Distribution API
- `GET /platforms` - List supported social media platforms
- `POST /distribute/{job_id}` - Manually trigger distribution
- `GET /analytics/{job_id}` - Get comprehensive analytics
- `GET /health` - Service health check

### Media Generation API
- Audio generation with ElevenLabs TTS
- Video creation with multiple AI providers
- Image generation with DALL-E/Midjourney
- Multi-format asset optimization

## Development

### Enhanced Project Structure
```
nexus/
├── services/
│   ├── harvester/              # Content ingestion
│   ├── analyst/                # AI analysis
│   ├── producer/               # Legacy media generation
│   ├── producer-nexus/         # Advanced media generation
│   │   ├── src/
│   │   │   ├── services/       # Audio, Video, Image services
│   │   │   └── index.js        # Main application
│   │   ├── package.json        # Node.js dependencies
│   │   └── Dockerfile          # Container configuration
│   ├── distributor/            # Legacy distribution
│   ├── distributor-nexus/      # Multi-platform distribution
│   │   ├── app/
│   │   │   ├── platforms/      # Social media publishers
│   │   │   ├── scheduler/      # Content scheduling
│   │   │   ├── analytics/      # Engagement tracking
│   │   │   └── main.py         # Main application
│   │   ├── requirements.txt    # Python dependencies
│   │   └── Dockerfile          # Container configuration
│   └── api/                    # Enhanced dashboard
├── docker-compose.yml          # Complete service orchestration
├── .env                        # Comprehensive configuration
└── README.md                   # This documentation
```

### Service Architecture

#### Producer-Nexus (Node.js)
- **AudioService**: ElevenLabs TTS with fallback generation
- **VideoService**: Pictory & RunwayML integration with FFmpeg fallback
- **ImageService**: DALL-E & Midjourney with Canvas fallback
- **StorageService**: S3-compatible object storage management

#### Distributor-Nexus (Python)
- **Platform Publishers**: YouTube, Instagram, Twitter, LinkedIn
- **Posting Scheduler**: Optimal timing and bulk scheduling
- **Engagement Tracker**: Real-time analytics and performance monitoring

## Deployment

### Production Deployment

#### Kubernetes Configuration (Recommended)
```yaml
# Example Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: producer-nexus
spec:
  replicas: 2
  selector:
    matchLabels:
      app: producer-nexus
  template:
    metadata:
      labels:
        app: producer-nexus
    spec:
      containers:
      - name: producer-nexus
        image: producer-nexus:latest
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

## 🔒 Security Notes

- Change default passwords in production
- Use proper secrets management
- Configure CORS settings appropriately
- Enable HTTPS in production

## 📝 License

MIT License - see LICENSE file for details.