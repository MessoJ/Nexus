import os
import json

import pika
from sqlalchemy import create_engine, text


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://%s:%s@rabbitmq:5672/" % (
    os.getenv("RABBITMQ_USER", "guest"), os.getenv("RABBITMQ_PASSWORD", "guest")
))
DATABASE_URL = os.getenv("DATABASE_URL")
DISTRIBUTION_QUEUE = os.getenv("DISTRIBUTION_QUEUE", "distribution_queue")

engine = create_engine(DATABASE_URL)


def mark_published(job_id: str):
    with engine.begin() as conn:
        conn.execute(text("UPDATE content_jobs SET status = 'published' WHERE id = :id"), {"id": job_id})


def handle_message(ch, method, properties, body):
    data = json.loads(body.decode("utf-8"))
    job_id = data.get("job_id")
    # TODO: Integrate platform SDKs here
    mark_published(job_id)
    ch.basic_ack(delivery_tag=method.delivery_tag)


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

