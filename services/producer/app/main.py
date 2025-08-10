import os
import json
import io
import logging

import pika
import boto3
from botocore.client import Config
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

MEDIA_QUEUE = os.getenv("MEDIA_QUEUE", "media_queue")

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
S3_BUCKET = os.getenv("S3_BUCKET", "relayforge-assets")
S3_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
S3_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
PUBLIC_S3_BASE_URL = os.getenv("PUBLIC_S3_BASE_URL", "http://localhost:9000")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)

s3 = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    config=Config(signature_version='s3v4'),
    region_name='us-east-1'
)


def ensure_bucket():
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=S3_BUCKET)


def get_job(job_id: str):
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id, script_text FROM content_jobs WHERE id = :id"), {"id": job_id}).fetchone()
        return row


def generate_dummy_audio(script_text: str) -> bytes:
    # Minimal valid WAV with 1s silence for MVP
    import wave
    import struct
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        for _ in range(16000):
            w.writeframes(struct.pack('<h', 0))
    return buffer.getvalue()


def produce_media(job_id: str) -> str:
    job = get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    script_text = job[1] or ""

    audio_bytes = generate_dummy_audio(script_text)

    ensure_bucket()
    key = f"jobs/{job_id}/audio.wav"
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=audio_bytes, ContentType='audio/wav')
    return f"{PUBLIC_S3_BASE_URL}/{S3_BUCKET}/{key}"


def update_job_media(job_id: str, media_url: str):
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE content_jobs SET media_url = :u, status = 'media_complete' WHERE id = :id"
        ), {"u": media_url, "id": job_id})


def handle_message(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        job_id = data.get("job_id")
        
        logger.info(f"Processing media production for job: {job_id}")
        
        media_url = produce_media(job_id)
        update_job_media(job_id, media_url)
        
        logger.info(f"Media production complete for job: {job_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing media job: {str(e)}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=MEDIA_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=MEDIA_QUEUE, on_message_callback=handle_message, auto_ack=False)
    channel.start_consuming()


if __name__ == "__main__":
    main()

