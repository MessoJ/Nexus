import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import asyncio

from platforms.youtube_publisher import YouTubePublisher
from platforms.instagram_publisher import InstagramPublisher
from platforms.twitter_publisher import TwitterPublisher
from platforms.linkedin_publisher import LinkedInPublisher

logger = logging.getLogger(__name__)

class EngagementTracker:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        
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
        
        # Platform publishers for analytics
        self.publishers = {
            'youtube': YouTubePublisher(),
            'instagram': InstagramPublisher(),
            'twitter': TwitterPublisher(),
            'linkedin': LinkedInPublisher()
        }
        
        logger.info("Engagement tracker initialized")

    async def track_publication(self, job_id: str, platform: str, publication_result: Dict):
        """Track a publication event"""
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO publication_analytics (
                        job_id, platform, platform_post_id, post_url, 
                        published_at, initial_data, created_at
                    ) VALUES (
                        :job_id, :platform, :post_id, :url, 
                        NOW(), :data, NOW()
                    )
                    ON CONFLICT (job_id, platform) DO UPDATE SET
                        platform_post_id = :post_id,
                        post_url = :url,
                        published_at = NOW(),
                        initial_data = :data,
                        updated_at = NOW()
                """), {
                    "job_id": job_id,
                    "platform": platform,
                    "post_id": publication_result.get('post_id') or publication_result.get('video_id') or publication_result.get('tweet_id') or publication_result.get('media_id'),
                    "url": publication_result.get('url'),
                    "data": json.dumps(publication_result)
                })
                
                logger.info(f"Tracked publication for job {job_id} on {platform}")
                
        except Exception as e:
            logger.error(f"Failed to track publication {job_id} on {platform}: {str(e)}")

    async def update_engagement_metrics(self, job_id: str, platform: str):
        """Update engagement metrics for a specific post"""
        try:
            # Get publication info
            with self.engine.begin() as conn:
                pub_info = conn.execute(text("""
                    SELECT platform_post_id, post_url, published_at
                    FROM publication_analytics
                    WHERE job_id = :job_id AND platform = :platform
                """), {"job_id": job_id, "platform": platform}).fetchone()
                
                if not pub_info:
                    logger.warning(f"No publication info found for job {job_id} on {platform}")
                    return
                
                post_id = pub_info[0]
                if not post_id:
                    logger.warning(f"No post ID found for job {job_id} on {platform}")
                    return
                
                # Get analytics from platform
                publisher = self.publishers.get(platform)
                if not publisher:
                    logger.warning(f"No publisher available for platform {platform}")
                    return
                
                analytics_data = None
                
                if platform == 'youtube':
                    analytics_data = await publisher.get_video_analytics(post_id)
                elif platform == 'instagram':
                    analytics_data = await publisher.get_media_analytics(post_id)
                elif platform == 'twitter':
                    analytics_data = await publisher.get_tweet_analytics(post_id)
                elif platform == 'linkedin':
                    analytics_data = await publisher.get_post_analytics(post_id)
                
                if analytics_data:
                    # Update analytics in database
                    conn.execute(text("""
                        UPDATE publication_analytics SET
                            current_metrics = :metrics,
                            last_updated = NOW(),
                            updated_at = NOW()
                        WHERE job_id = :job_id AND platform = :platform
                    """), {
                        "job_id": job_id,
                        "platform": platform,
                        "metrics": json.dumps(analytics_data)
                    })
                    
                    logger.info(f"Updated engagement metrics for job {job_id} on {platform}")
                
        except Exception as e:
            logger.error(f"Failed to update engagement metrics for {job_id} on {platform}: {str(e)}")

    async def bulk_update_metrics(self, hours_back: int = 24):
        """Update metrics for all posts published in the last N hours"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            with self.engine.begin() as conn:
                publications = conn.execute(text("""
                    SELECT DISTINCT job_id, platform
                    FROM publication_analytics
                    WHERE published_at >= :cutoff_time
                    AND platform_post_id IS NOT NULL
                    ORDER BY published_at DESC
                """), {"cutoff_time": cutoff_time}).fetchall()
                
                logger.info(f"Updating metrics for {len(publications)} publications")
                
                for pub in publications:
                    try:
                        await self.update_engagement_metrics(str(pub[0]), pub[1])
                        # Small delay to avoid rate limiting
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"Failed to update metrics for {pub[0]} on {pub[1]}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Failed to bulk update metrics: {str(e)}")

    async def get_job_analytics(self, job_id: str) -> Dict:
        """Get comprehensive analytics for a job across all platforms"""
        try:
            with self.engine.begin() as conn:
                analytics = conn.execute(text("""
                    SELECT platform, platform_post_id, post_url, published_at, 
                           initial_data, current_metrics, last_updated
                    FROM publication_analytics
                    WHERE job_id = :job_id
                    ORDER BY published_at DESC
                """), {"job_id": job_id}).fetchall()
                
                result = {
                    "job_id": job_id,
                    "platforms": {},
                    "total_engagement": {
                        "views": 0,
                        "likes": 0,
                        "comments": 0,
                        "shares": 0
                    },
                    "last_updated": None
                }
                
                for row in analytics:
                    platform = row[0]
                    current_metrics = json.loads(row[5]) if row[5] else {}
                    
                    result["platforms"][platform] = {
                        "post_id": row[1],
                        "url": row[2],
                        "published_at": row[3].isoformat() if row[3] else None,
                        "metrics": current_metrics,
                        "last_updated": row[6].isoformat() if row[6] else None
                    }
                    
                    # Aggregate metrics
                    if current_metrics:
                        result["total_engagement"]["views"] += current_metrics.get("views", 0)
                        result["total_engagement"]["likes"] += current_metrics.get("likes", 0)
                        result["total_engagement"]["comments"] += current_metrics.get("comments", 0)
                        result["total_engagement"]["shares"] += current_metrics.get("shares", 0) + current_metrics.get("retweets", 0)
                        
                        if row[6] and (not result["last_updated"] or row[6] > datetime.fromisoformat(result["last_updated"])):
                            result["last_updated"] = row[6].isoformat()
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to get job analytics for {job_id}: {str(e)}")
            raise

    async def get_platform_performance(self, platform: str, days_back: int = 30) -> Dict:
        """Get performance metrics for a specific platform"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_back)
            
            with self.engine.begin() as conn:
                # Get all posts for the platform in the time period
                posts = conn.execute(text("""
                    SELECT job_id, current_metrics, published_at
                    FROM publication_analytics
                    WHERE platform = :platform 
                    AND published_at >= :cutoff_time
                    AND current_metrics IS NOT NULL
                    ORDER BY published_at DESC
                """), {"platform": platform, "cutoff_time": cutoff_time}).fetchall()
                
                if not posts:
                    return {
                        "platform": platform,
                        "period_days": days_back,
                        "total_posts": 0,
                        "metrics": {}
                    }
                
                # Aggregate metrics
                total_metrics = {
                    "views": 0,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "engagement_rate": 0
                }
                
                valid_posts = 0
                
                for post in posts:
                    metrics = json.loads(post[1])
                    if metrics:
                        total_metrics["views"] += metrics.get("views", 0)
                        total_metrics["likes"] += metrics.get("likes", 0)
                        total_metrics["comments"] += metrics.get("comments", 0)
                        total_metrics["shares"] += metrics.get("shares", 0) + metrics.get("retweets", 0)
                        valid_posts += 1
                
                # Calculate averages
                if valid_posts > 0:
                    avg_metrics = {
                        "avg_views": total_metrics["views"] / valid_posts,
                        "avg_likes": total_metrics["likes"] / valid_posts,
                        "avg_comments": total_metrics["comments"] / valid_posts,
                        "avg_shares": total_metrics["shares"] / valid_posts
                    }
                    
                    # Calculate engagement rate (likes + comments + shares) / views
                    if total_metrics["views"] > 0:
                        engagement = total_metrics["likes"] + total_metrics["comments"] + total_metrics["shares"]
                        total_metrics["engagement_rate"] = (engagement / total_metrics["views"]) * 100
                else:
                    avg_metrics = {
                        "avg_views": 0,
                        "avg_likes": 0,
                        "avg_comments": 0,
                        "avg_shares": 0
                    }
                
                return {
                    "platform": platform,
                    "period_days": days_back,
                    "total_posts": len(posts),
                    "valid_posts": valid_posts,
                    "total_metrics": total_metrics,
                    "average_metrics": avg_metrics
                }
                
        except Exception as e:
            logger.error(f"Failed to get platform performance for {platform}: {str(e)}")
            raise

    async def get_top_performing_content(self, limit: int = 10, days_back: int = 30) -> List[Dict]:
        """Get top performing content across all platforms"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_back)
            
            with self.engine.begin() as conn:
                # Get content with engagement metrics
                content = conn.execute(text("""
                    SELECT pa.job_id, pa.platform, pa.post_url, pa.current_metrics,
                           cj.title, pa.published_at
                    FROM publication_analytics pa
                    LEFT JOIN content_jobs cj ON pa.job_id = cj.id
                    WHERE pa.published_at >= :cutoff_time
                    AND pa.current_metrics IS NOT NULL
                    ORDER BY pa.published_at DESC
                """), {"cutoff_time": cutoff_time}).fetchall()
                
                # Calculate engagement scores
                scored_content = []
                
                for row in content:
                    metrics = json.loads(row[3])
                    if not metrics:
                        continue
                    
                    # Calculate engagement score (weighted)
                    views = metrics.get("views", 0)
                    likes = metrics.get("likes", 0)
                    comments = metrics.get("comments", 0)
                    shares = metrics.get("shares", 0) + metrics.get("retweets", 0)
                    
                    # Weighted engagement score
                    engagement_score = (likes * 1) + (comments * 2) + (shares * 3)
                    if views > 0:
                        engagement_rate = (engagement_score / views) * 100
                    else:
                        engagement_rate = 0
                    
                    scored_content.append({
                        "job_id": str(row[0]),
                        "platform": row[1],
                        "url": row[2],
                        "title": row[4],
                        "published_at": row[5].isoformat() if row[5] else None,
                        "metrics": metrics,
                        "engagement_score": engagement_score,
                        "engagement_rate": engagement_rate
                    })
                
                # Sort by engagement score and return top performers
                scored_content.sort(key=lambda x: x["engagement_score"], reverse=True)
                
                return scored_content[:limit]
                
        except Exception as e:
            logger.error(f"Failed to get top performing content: {str(e)}")
            return []

    async def get_engagement_trends(self, days_back: int = 30) -> Dict:
        """Get engagement trends over time"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_back)
            
            with self.engine.begin() as conn:
                # Get daily engagement data
                trends = conn.execute(text("""
                    SELECT DATE(published_at) as date, platform, 
                           COUNT(*) as posts_count,
                           AVG(CAST(current_metrics->>'likes' AS INTEGER)) as avg_likes,
                           AVG(CAST(current_metrics->>'views' AS INTEGER)) as avg_views,
                           AVG(CAST(current_metrics->>'comments' AS INTEGER)) as avg_comments
                    FROM publication_analytics
                    WHERE published_at >= :cutoff_time
                    AND current_metrics IS NOT NULL
                    GROUP BY DATE(published_at), platform
                    ORDER BY date DESC, platform
                """), {"cutoff_time": cutoff_time}).fetchall()
                
                # Organize data by date
                trends_data = {}
                
                for row in trends:
                    date_str = row[0].isoformat()
                    platform = row[1]
                    
                    if date_str not in trends_data:
                        trends_data[date_str] = {}
                    
                    trends_data[date_str][platform] = {
                        "posts_count": row[2],
                        "avg_likes": float(row[3]) if row[3] else 0,
                        "avg_views": float(row[4]) if row[4] else 0,
                        "avg_comments": float(row[5]) if row[5] else 0
                    }
                
                return {
                    "period_days": days_back,
                    "trends": trends_data
                }
                
        except Exception as e:
            logger.error(f"Failed to get engagement trends: {str(e)}")
            return {"period_days": days_back, "trends": {}}

    def create_tables(self):
        """Create necessary database tables"""
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS publication_analytics (
                        id SERIAL PRIMARY KEY,
                        job_id UUID NOT NULL,
                        platform VARCHAR(50) NOT NULL,
                        platform_post_id VARCHAR(255),
                        post_url TEXT,
                        published_at TIMESTAMP,
                        initial_data JSONB,
                        current_metrics JSONB,
                        last_updated TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(job_id, platform)
                    )
                """))
                
                # Create indexes for efficient queries
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_publication_analytics_job_id 
                    ON publication_analytics (job_id)
                """))
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_publication_analytics_platform_published 
                    ON publication_analytics (platform, published_at)
                """))
                
                logger.info("Analytics database tables created/verified")
                
        except Exception as e:
            logger.error(f"Failed to create analytics tables: {str(e)}")
            raise
