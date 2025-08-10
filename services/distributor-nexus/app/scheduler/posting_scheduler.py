import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import schedule
import time
import threading
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import pika

logger = logging.getLogger(__name__)

class PostingScheduler:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://nexus:nexuspass@rabbitmq:5672/")
        self.distribution_queue = os.getenv("DISTRIBUTION_QUEUE", "distribution_queue")
        
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Database connection
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=3,
            max_overflow=5,
            pool_pre_ping=True
        )
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Posting scheduler initialized")

    async def schedule_job(self, job_id: str, platforms: List[str], schedule_time: datetime):
        """Schedule a job for future distribution"""
        try:
            with self.engine.begin() as conn:
                # Insert scheduled job
                conn.execute(text("""
                    INSERT INTO scheduled_posts (job_id, platforms, scheduled_time, status, created_at)
                    VALUES (:job_id, :platforms, :scheduled_time, 'scheduled', NOW())
                    ON CONFLICT (job_id) DO UPDATE SET
                        platforms = :platforms,
                        scheduled_time = :scheduled_time,
                        status = 'scheduled',
                        updated_at = NOW()
                """), {
                    "job_id": job_id,
                    "platforms": json.dumps(platforms),
                    "scheduled_time": schedule_time
                })
                
                logger.info(f"Scheduled job {job_id} for {schedule_time} on platforms: {platforms}")
                
        except Exception as e:
            logger.error(f"Failed to schedule job {job_id}: {str(e)}")
            raise

    def _run_scheduler(self):
        """Run the background scheduler"""
        schedule.every(1).minutes.do(self._check_scheduled_posts)
        
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds

    def _check_scheduled_posts(self):
        """Check for posts that need to be published"""
        try:
            current_time = datetime.utcnow()
            
            with self.engine.begin() as conn:
                # Get posts scheduled for now or earlier
                scheduled_posts = conn.execute(text("""
                    SELECT job_id, platforms, scheduled_time
                    FROM scheduled_posts 
                    WHERE status = 'scheduled' 
                    AND scheduled_time <= :current_time
                    ORDER BY scheduled_time ASC
                    LIMIT 10
                """), {"current_time": current_time}).fetchall()
                
                for post in scheduled_posts:
                    try:
                        job_id = str(post[0])
                        platforms = json.loads(post[1])
                        
                        # Send to distribution queue
                        self._send_to_distribution_queue({
                            "job_id": job_id,
                            "platforms": platforms,
                            "scheduled": True
                        })
                        
                        # Update status
                        conn.execute(text("""
                            UPDATE scheduled_posts 
                            SET status = 'sent_to_queue', updated_at = NOW()
                            WHERE job_id = :job_id
                        """), {"job_id": job_id})
                        
                        logger.info(f"Sent scheduled job {job_id} to distribution queue")
                        
                    except Exception as e:
                        logger.error(f"Failed to process scheduled post {post[0]}: {str(e)}")
                        
                        # Mark as failed
                        conn.execute(text("""
                            UPDATE scheduled_posts 
                            SET status = 'failed', error_message = :error, updated_at = NOW()
                            WHERE job_id = :job_id
                        """), {"job_id": str(post[0]), "error": str(e)})
                        
        except Exception as e:
            logger.error(f"Error checking scheduled posts: {str(e)}")

    def _send_to_distribution_queue(self, message: Dict):
        """Send message to RabbitMQ distribution queue"""
        try:
            params = pika.URLParameters(self.rabbitmq_url)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            
            channel.queue_declare(queue=self.distribution_queue, durable=True)
            
            channel.basic_publish(
                exchange='',
                routing_key=self.distribution_queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
            )
            
            connection.close()
            
        except Exception as e:
            logger.error(f"Failed to send message to distribution queue: {str(e)}")
            raise

    async def get_scheduled_posts(self, limit: int = 50) -> List[Dict]:
        """Get list of scheduled posts"""
        try:
            with self.engine.begin() as conn:
                posts = conn.execute(text("""
                    SELECT sp.job_id, sp.platforms, sp.scheduled_time, sp.status, 
                           sp.created_at, sp.updated_at, cj.title
                    FROM scheduled_posts sp
                    LEFT JOIN content_jobs cj ON sp.job_id = cj.id
                    ORDER BY sp.scheduled_time ASC
                    LIMIT :limit
                """), {"limit": limit}).fetchall()
                
                return [
                    {
                        "job_id": str(row[0]),
                        "platforms": json.loads(row[1]),
                        "scheduled_time": row[2].isoformat() if row[2] else None,
                        "status": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "title": row[6]
                    }
                    for row in posts
                ]
                
        except Exception as e:
            logger.error(f"Failed to get scheduled posts: {str(e)}")
            return []

    async def cancel_scheduled_post(self, job_id: str) -> bool:
        """Cancel a scheduled post"""
        try:
            with self.engine.begin() as conn:
                result = conn.execute(text("""
                    UPDATE scheduled_posts 
                    SET status = 'cancelled', updated_at = NOW()
                    WHERE job_id = :job_id AND status = 'scheduled'
                """), {"job_id": job_id})
                
                if result.rowcount > 0:
                    logger.info(f"Cancelled scheduled post for job {job_id}")
                    return True
                else:
                    logger.warning(f"No scheduled post found for job {job_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to cancel scheduled post {job_id}: {str(e)}")
            return False

    async def reschedule_post(self, job_id: str, new_time: datetime) -> bool:
        """Reschedule a post to a new time"""
        try:
            with self.engine.begin() as conn:
                result = conn.execute(text("""
                    UPDATE scheduled_posts 
                    SET scheduled_time = :new_time, status = 'scheduled', updated_at = NOW()
                    WHERE job_id = :job_id AND status IN ('scheduled', 'failed')
                """), {"job_id": job_id, "new_time": new_time})
                
                if result.rowcount > 0:
                    logger.info(f"Rescheduled job {job_id} to {new_time}")
                    return True
                else:
                    logger.warning(f"No schedulable post found for job {job_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to reschedule post {job_id}: {str(e)}")
            return False

    async def get_optimal_posting_times(self, platform: str) -> List[Dict]:
        """Get optimal posting times for a platform based on historical data"""
        try:
            # This would analyze historical engagement data to suggest optimal times
            # For now, return default optimal times
            
            optimal_times = {
                'youtube': [
                    {'hour': 14, 'minute': 0, 'day_of_week': 'Tuesday'},
                    {'hour': 15, 'minute': 0, 'day_of_week': 'Thursday'},
                    {'hour': 20, 'minute': 0, 'day_of_week': 'Saturday'}
                ],
                'instagram': [
                    {'hour': 11, 'minute': 0, 'day_of_week': 'Monday'},
                    {'hour': 13, 'minute': 0, 'day_of_week': 'Wednesday'},
                    {'hour': 17, 'minute': 0, 'day_of_week': 'Friday'}
                ],
                'twitter': [
                    {'hour': 9, 'minute': 0, 'day_of_week': 'Monday'},
                    {'hour': 12, 'minute': 0, 'day_of_week': 'Wednesday'},
                    {'hour': 15, 'minute': 0, 'day_of_week': 'Friday'}
                ],
                'linkedin': [
                    {'hour': 8, 'minute': 0, 'day_of_week': 'Tuesday'},
                    {'hour': 12, 'minute': 0, 'day_of_week': 'Wednesday'},
                    {'hour': 17, 'minute': 0, 'day_of_week': 'Thursday'}
                ]
            }
            
            return optimal_times.get(platform, [])
            
        except Exception as e:
            logger.error(f"Failed to get optimal posting times for {platform}: {str(e)}")
            return []

    async def bulk_schedule(self, schedules: List[Dict]) -> Dict:
        """Schedule multiple posts at once"""
        results = {
            'scheduled': 0,
            'failed': 0,
            'errors': []
        }
        
        for schedule_data in schedules:
            try:
                job_id = schedule_data['job_id']
                platforms = schedule_data['platforms']
                schedule_time = datetime.fromisoformat(schedule_data['schedule_time'])
                
                await self.schedule_job(job_id, platforms, schedule_time)
                results['scheduled'] += 1
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'job_id': schedule_data.get('job_id', 'unknown'),
                    'error': str(e)
                })
                logger.error(f"Failed to schedule job in bulk: {str(e)}")
        
        return results

    def create_tables(self):
        """Create necessary database tables"""
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS scheduled_posts (
                        id SERIAL PRIMARY KEY,
                        job_id UUID UNIQUE NOT NULL,
                        platforms JSONB NOT NULL,
                        scheduled_time TIMESTAMP NOT NULL,
                        status VARCHAR(50) DEFAULT 'scheduled',
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                
                # Create index for efficient queries
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_scheduled_posts_time_status 
                    ON scheduled_posts (scheduled_time, status)
                """))
                
                logger.info("Scheduler database tables created/verified")
                
        except Exception as e:
            logger.error(f"Failed to create scheduler tables: {str(e)}")
            raise
