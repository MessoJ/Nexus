import os
import json
import logging

import pika
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

DISTRIBUTION_QUEUE = os.getenv("DISTRIBUTION_QUEUE", "distribution_queue")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)


def mark_published(job_id: str):
    with engine.begin() as conn:
        conn.execute(text("UPDATE content_jobs SET status = 'published' WHERE id = :id"), {"id": job_id})


def handle_message(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        job_id = data.get("job_id")
        
        logger.info(f"Processing distribution for job: {job_id}")
        
        # TODO: Integrate platform SDKs here (YouTube, TikTok, etc.)
        mark_published(job_id)
        
        logger.info(f"Distribution complete for job: {job_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing distribution job: {str(e)}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=DISTRIBUTION_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=DISTRIBUTION_QUEUE, on_message_callback=handle_message, auto_ack=False)
    channel.start_consuming()


if __name__ == "__main__":
    main()

