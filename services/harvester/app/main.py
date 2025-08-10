import os
import json
import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
import feedparser
import pika
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://%s:%s@rabbitmq:5672/" % (
    os.getenv("RABBITMQ_USER", "guest"), os.getenv("RABBITMQ_PASSWORD", "guest")
))
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

STORY_QUEUE = os.getenv("STORY_QUEUE", "story_queue")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)


def already_ingested(source_key: str) -> bool:
    with engine.begin() as conn:
        row = conn.execute(text("SELECT 1 FROM ingested_items WHERE source_key = :k"), {"k": source_key}).fetchone()
        return row is not None


def mark_ingested(source_key: str, title: str, url: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO ingested_items (source_key, source_url, title) VALUES (:k, :u, :t) ON CONFLICT (source_key) DO NOTHING"
        ), {"k": source_key, "u": url, "t": title})


def publish_story(message: dict) -> None:
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=STORY_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=STORY_QUEUE,
            body=json.dumps(message).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
        logger.info(f"Published story: {message.get('title', 'Unknown')}")
    except Exception as e:
        logger.error(f"Failed to publish story: {str(e)}")
        raise


def fetch_rss_items(feed_url: str):
    parsed = feedparser.parse(feed_url)
    for entry in parsed.entries:
        yield {
            "id": entry.get("id") or entry.get("link") or entry.get("title"),
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "published": entry.get("published", "")
        }


DEFAULT_FEEDS = [
    "https://news.google.com/rss/search?q=ai%20OR%20technology&hl=en-US&gl=US&ceid=US:en"
]


def harvest_once():
    feeds = os.getenv("HARVEST_FEEDS")
    feed_list = [f.strip() for f in feeds.split(",") if f.strip()] if feeds else DEFAULT_FEEDS
    
    logger.info(f"Starting harvest from {len(feed_list)} feeds")
    
    for feed in feed_list:
        try:
            logger.info(f"Processing feed: {feed}")
            items_processed = 0
            for item in fetch_rss_items(feed):
                source_key = f"{feed}|{item['id']}"
                if already_ingested(source_key):
                    continue
                message = {
                    "source_url": item["link"],
                    "title": item["title"],
                    "source_metadata": {
                        "feed": feed,
                        "summary": item.get("summary"),
                        "published": item.get("published")
                    },
                    "ingested_at": datetime.utcnow().isoformat() + "Z"
                }
                publish_story(message)
                mark_ingested(source_key, item["title"], item["link"])
                items_processed += 1
            logger.info(f"Processed {items_processed} new items from {feed}")
        except Exception as e:
            logger.error(f"Error processing feed {feed}: {str(e)}")
            continue


def main():
    interval_minutes = int(os.getenv("HARVEST_INTERVAL_MINUTES", "15"))
    mode = os.getenv("HARVEST_MODE", "schedule")
    if mode == "once":
        harvest_once()
        return
    scheduler = BlockingScheduler()
    scheduler.add_job(harvest_once, 'interval', minutes=interval_minutes, max_instances=1, coalesce=True)
    scheduler.start()


if __name__ == "__main__":
    main()

