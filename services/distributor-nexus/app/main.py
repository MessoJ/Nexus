import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio

import pika
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from fastapi import FastAPI, HTTPException
import uvicorn

from platforms.youtube_publisher import YouTubePublisher
from platforms.instagram_publisher import InstagramPublisher
from platforms.twitter_publisher import TwitterPublisher
from platforms.linkedin_publisher import LinkedInPublisher
from scheduler.posting_scheduler import PostingScheduler
from analytics.engagement_tracker import EngagementTracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://nexus:nexuspass@rabbitmq:5672/")
DATABASE_URL = os.getenv("DATABASE_URL")
DISTRIBUTION_QUEUE = os.getenv("DISTRIBUTION_QUEUE", "distribution_queue")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Database connection with pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)

# FastAPI app for API endpoints
app = FastAPI(title="Nexus Distribution Service", version="1.0.0")

# Platform publishers
publishers = {
    'youtube': YouTubePublisher(),
    'instagram': InstagramPublisher(),
    'twitter': TwitterPublisher(),
    'linkedin': LinkedInPublisher()
}

# Services
scheduler = PostingScheduler()
analytics = EngagementTracker()

class DistributionService:
    def __init__(self):
        self.connection = None
        self.channel = None

    async def connect_rabbitmq(self):
        """Connect to RabbitMQ"""
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=DISTRIBUTION_QUEUE, durable=True)
            self.channel.basic_qos(prefetch_count=1)
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job details from database"""
        try:
            with engine.begin() as conn:
                row = conn.execute(text("""
                    SELECT id, title, status, media_url, media_assets, analysis_json, distribution_config
                    FROM content_jobs 
                    WHERE id = :id
                """), {"id": job_id}).fetchone()
                
                if not row:
                    return None
                
                return {
                    'id': str(row[0]),
                    'title': row[1],
                    'status': row[2],
                    'media_url': row[3],
                    'media_assets': json.loads(row[4]) if row[4] else {},
                    'analysis_json': json.loads(row[5]) if row[5] else {},
                    'distribution_config': json.loads(row[6]) if row[6] else {}
                }
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {str(e)}")
            return None

    def update_job_status(self, job_id: str, status: str, published_urls: Dict = None):
        """Update job status and published URLs"""
        try:
            with engine.begin() as conn:
                update_data = {
                    'id': job_id,
                    'status': status,
                    'updated_at': datetime.utcnow()
                }
                
                query = "UPDATE content_jobs SET status = :status, updated_at = NOW()"
                
                if published_urls:
                    query += ", published_urls = :published_urls"
                    update_data['published_urls'] = json.dumps(published_urls)
                
                if status == 'published':
                    query += ", published_at = NOW()"
                
                query += " WHERE id = :id"
                
                conn.execute(text(query), update_data)
                logger.info(f"Updated job {job_id} status to {status}")
                
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {str(e)}")

    async def distribute_content(self, job_data: Dict):
        """Distribute content to multiple platforms"""
        job_id = job_data.get('job_id')
        logger.info(f"Starting distribution for job: {job_id}")

        try:
            job = self.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            # Get distribution configuration
            distribution_config = job.get('distribution_config', {})
            target_platforms = distribution_config.get('platforms', ['youtube', 'twitter'])
            
            # Check if content should be scheduled or published immediately
            schedule_time = distribution_config.get('schedule_time')
            if schedule_time:
                await self.schedule_distribution(job, target_platforms, schedule_time)
                return

            # Immediate distribution
            published_urls = {}
            errors = []

            for platform in target_platforms:
                try:
                    if platform in publishers:
                        publisher = publishers[platform]
                        
                        # Prepare platform-specific content
                        content = await self.prepare_platform_content(job, platform)
                        
                        # Publish to platform
                        result = await publisher.publish(content)
                        published_urls[platform] = result
                        
                        logger.info(f"Successfully published to {platform}: {result}")
                        
                        # Track analytics
                        await analytics.track_publication(job_id, platform, result)
                        
                    else:
                        logger.warning(f"Publisher for {platform} not available")
                        
                except Exception as e:
                    error_msg = f"Failed to publish to {platform}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Update job status
            if published_urls:
                if errors:
                    self.update_job_status(job_id, 'partially_published', published_urls)
                else:
                    self.update_job_status(job_id, 'published', published_urls)
            else:
                self.update_job_status(job_id, 'distribution_failed')

            logger.info(f"Distribution completed for job {job_id}")

        except Exception as e:
            logger.error(f"Distribution failed for job {job_id}: {str(e)}")
            self.update_job_status(job_id, 'distribution_failed')

    async def prepare_platform_content(self, job: Dict, platform: str) -> Dict:
        """Prepare content optimized for specific platform"""
        base_content = {
            'title': job['title'],
            'media_url': job['media_url'],
            'media_assets': job['media_assets'],
            'analysis': job['analysis_json']
        }

        if platform == 'youtube':
            return {
                **base_content,
                'description': self.generate_youtube_description(job),
                'tags': job['analysis_json'].get('hashtags', [])[:10],  # YouTube max 10 tags
                'thumbnail_url': job['media_assets'].get('thumbnail', {}).get('url'),
                'video_url': job['media_assets'].get('video', {}).get('url')
            }
            
        elif platform == 'instagram':
            return {
                **base_content,
                'caption': self.generate_instagram_caption(job),
                'hashtags': job['analysis_json'].get('hashtags', [])[:30],  # Instagram max 30
                'media_format': 'square' if 'square' in job['media_assets'].get('video', {}).get('formats', {}) else 'portrait'
            }
            
        elif platform == 'twitter':
            return {
                **base_content,
                'text': self.generate_twitter_text(job),
                'media_url': job['media_assets'].get('thumbnail', {}).get('url')
            }
            
        elif platform == 'linkedin':
            return {
                **base_content,
                'text': self.generate_linkedin_text(job),
                'article_url': job.get('source_url')
            }

        return base_content

    def generate_youtube_description(self, job: Dict) -> str:
        """Generate YouTube-optimized description"""
        analysis = job['analysis_json']
        description = f"{job['title']}\n\n"
        
        if 'summary' in analysis:
            description += f"{analysis['summary']}\n\n"
        
        if 'key_points' in analysis:
            description += "Key Points:\n"
            for point in analysis['key_points'][:5]:
                description += f"• {point}\n"
            description += "\n"
        
        # Add hashtags
        if 'hashtags' in analysis:
            description += " ".join(analysis['hashtags'][:10])
        
        return description

    def generate_instagram_caption(self, job: Dict) -> str:
        """Generate Instagram-optimized caption"""
        analysis = job['analysis_json']
        caption = f"{job['title']}\n\n"
        
        if 'summary' in analysis:
            # Keep it concise for Instagram
            summary = analysis['summary'][:200] + "..." if len(analysis['summary']) > 200 else analysis['summary']
            caption += f"{summary}\n\n"
        
        return caption

    def generate_twitter_text(self, job: Dict) -> str:
        """Generate Twitter-optimized text"""
        title = job['title']
        # Twitter has 280 character limit
        if len(title) > 240:
            title = title[:237] + "..."
        
        hashtags = job['analysis_json'].get('hashtags', [])[:3]  # Max 3 hashtags for Twitter
        hashtag_text = " ".join(hashtags) if hashtags else ""
        
        return f"{title}\n\n{hashtag_text}"

    def generate_linkedin_text(self, job: Dict) -> str:
        """Generate LinkedIn-optimized text"""
        analysis = job['analysis_json']
        text = f"{job['title']}\n\n"
        
        if 'summary' in analysis:
            text += f"{analysis['summary']}\n\n"
        
        # LinkedIn is more professional, so add insights
        if 'key_points' in analysis:
            text += "Key insights:\n"
            for point in analysis['key_points'][:3]:
                text += f"✓ {point}\n"
        
        return text

    async def schedule_distribution(self, job: Dict, platforms: List[str], schedule_time: str):
        """Schedule content for future distribution"""
        try:
            schedule_dt = datetime.fromisoformat(schedule_time)
            await scheduler.schedule_job(job['id'], platforms, schedule_dt)
            self.update_job_status(job['id'], 'scheduled')
            logger.info(f"Scheduled job {job['id']} for {schedule_time}")
        except Exception as e:
            logger.error(f"Failed to schedule job {job['id']}: {str(e)}")
            self.update_job_status(job['id'], 'schedule_failed')

    def handle_message(self, ch, method, properties, body):
        """Handle RabbitMQ messages"""
        try:
            data = json.loads(body.decode("utf-8"))
            
            # Run async distribution in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.distribute_content(data))
            loop.close()
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error processing distribution message: {str(e)}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def start_consuming(self):
        """Start consuming messages from RabbitMQ"""
        try:
            self.channel.basic_consume(
                queue=DISTRIBUTION_QUEUE,
                on_message_callback=self.handle_message
            )
            logger.info(f"Started consuming from {DISTRIBUTION_QUEUE}")
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping distribution service...")
            self.channel.stop_consuming()
            if self.connection:
                self.connection.close()

# API Endpoints
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "distribution"}

@app.get("/platforms")
def get_supported_platforms():
    return {
        "platforms": list(publishers.keys()),
        "status": "active"
    }

@app.post("/distribute/{job_id}")
async def manual_distribute(job_id: str, platforms: List[str] = None):
    """Manually trigger distribution for a job"""
    try:
        service = DistributionService()
        job_data = {"job_id": job_id}
        
        if platforms:
            # Update job distribution config
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE content_jobs SET distribution_config = :config WHERE id = :id"
                ), {
                    "id": job_id,
                    "config": json.dumps({"platforms": platforms})
                })
        
        await service.distribute_content(job_data)
        return {"message": f"Distribution initiated for job {job_id}"}
        
    except Exception as e:
        logger.error(f"Manual distribution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/{job_id}")
async def get_job_analytics(job_id: str):
    """Get analytics for a published job"""
    try:
        analytics_data = await analytics.get_job_analytics(job_id)
        return analytics_data
    except Exception as e:
        logger.error(f"Failed to get analytics for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Main execution
def main():
    """Main function to start the distribution service"""
    service = DistributionService()
    
    # Start RabbitMQ consumer in a separate thread
    import threading
    
    def start_consumer():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(service.connect_rabbitmq())
        service.start_consuming()
    
    consumer_thread = threading.Thread(target=start_consumer)
    consumer_thread.daemon = True
    consumer_thread.start()
    
    # Start FastAPI server
    logger.info("Starting Distribution Service API...")
    uvicorn.run(app, host="0.0.0.0", port=8003)

if __name__ == "__main__":
    main()
