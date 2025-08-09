import os
import json
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import pika


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://%s:%s@rabbitmq:5672/" % (
    os.getenv("RABBITMQ_USER", "guest"), os.getenv("RABBITMQ_PASSWORD", "guest")
))
DATABASE_URL = os.getenv("DATABASE_URL")
DISTRIBUTION_QUEUE = os.getenv("DISTRIBUTION_QUEUE", "distribution_queue")

engine = create_engine(DATABASE_URL)

app = FastAPI(title="RelayForge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobOut(BaseModel):
    id: str
    title: Optional[str]
    status: str
    media_url: Optional[str]


def publish_distribution_job(job_id: str):
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=DISTRIBUTION_QUEUE, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=DISTRIBUTION_QUEUE,
        body=json.dumps({"job_id": job_id}).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/jobs", response_model=List[JobOut])
def list_jobs():
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, title, status, media_url FROM content_jobs ORDER BY created_at DESC LIMIT 200")).fetchall()
        return [
            JobOut(id=str(r[0]), title=r[1], status=r[2], media_url=r[3])
            for r in rows
        ]


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id, title, status, article_text, script_text, analysis_json, media_url FROM content_jobs WHERE id = :id"), {"id": job_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return {
            "id": str(row[0]),
            "title": row[1],
            "status": row[2],
            "article_text": row[3],
            "script_text": row[4],
            "analysis_json": row[5],
            "media_url": row[6]
        }


@app.post("/jobs/{job_id}/approve")
def approve(job_id: str):
    publish_distribution_job(job_id)
    return {"queued": True}

