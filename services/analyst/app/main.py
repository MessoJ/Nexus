import os
import json
import logging
from datetime import datetime

import pika
import requests
from bs4 import BeautifulSoup
import trafilatura
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USE_OPENAI = os.getenv("USE_OPENAI", "1") == "1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

openai_client = None
genai = None
if USE_OPENAI and OPENAI_API_KEY:
    from openai import OpenAI
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
elif (not USE_OPENAI) and GOOGLE_API_KEY:
    import google.generativeai as genai  # type: ignore
    genai.configure(api_key=GOOGLE_API_KEY)


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://%s:%s@rabbitmq:5672/" % (
    os.getenv("RABBITMQ_USER", "guest"), os.getenv("RABBITMQ_PASSWORD", "guest")
))
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

STORY_QUEUE = os.getenv("STORY_QUEUE", "story_queue")
MEDIA_QUEUE = os.getenv("MEDIA_QUEUE", "media_queue")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)


def fetch_article_text(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if extracted:
            return extracted
    # fallback
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return soup.get_text(separator='\n')[:8000]
    except Exception:
        return ""


def call_llm(article_text: str, title: str) -> dict:
    system_prompt = (
        "You are an editorial AI. Analyze the article, produce: \n"
        "- summary, \n- 5 bullet key points, \n- video script (60-90s), \n"
        "- 3 title options, \n- 10 hashtags. Return JSON with keys: summary, bullets, script, titles, hashtags."
    )
    try:
        if openai_client is not None:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Title: {title}\n\nArticle:\n{article_text[:12000]}"}
                ],
                temperature=0.4,
            )
            content = response.choices[0].message.content
        elif genai is not None:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = system_prompt + "\n\n" + f"Title: {title}\n\nArticle:\n{article_text[:12000]}"
            r = model.generate_content(prompt)
            content = r.text
        else:
            raise RuntimeError("No LLM configured")
    except Exception:
        # Fallback: produce minimal structured content locally
        preview = (article_text or "").strip()[:600]
        bullets = [b for b in [
            preview[:120], preview[120:240], preview[240:360], preview[360:480], preview[480:600]
        ] if b]
        return {
            "summary": preview,
            "bullets": bullets,
            "script": f"Title: {title}\n\n{preview}\n\n(End)",
            "titles": [title, f"Update: {title}", f"Deep Dive: {title}"],
            "hashtags": ["#news", "#tech", "#ai", "#update", "#trending"]
        }

    try:
        return json.loads(content)
    except Exception:
        return {"summary": content[:1000], "bullets": [], "script": content[:2000], "titles": [], "hashtags": []}


def handle_message(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        url = data.get("source_url", "")
        title = data.get("title", "")
        
        logger.info(f"Processing article: {title}")
        
        article_text = fetch_article_text(url)
        llm_output = call_llm(article_text, title)

        with engine.begin() as conn:
            row = conn.execute(text(
                """
                INSERT INTO content_jobs (source_url, title, source_metadata, article_text, analysis_json, script_text, status)
                VALUES (:u, :t, CAST(:m AS JSONB), :a, CAST(:j AS JSONB), :s, 'analysis_complete')
                RETURNING id
                """
            ), {
                "u": url,
                "t": title,
                "m": json.dumps(data.get("source_metadata", {})),
                "a": article_text,
                "j": json.dumps(llm_output),
                "s": llm_output.get("script", "")
            }).fetchone()
            job_id = str(row[0])

        publish_media_job({"job_id": job_id})
        logger.info(f"Analysis complete for job: {job_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def publish_media_job(message: dict):
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=MEDIA_QUEUE, durable=True)
        channel.basic_publish(exchange="", routing_key=MEDIA_QUEUE, body=json.dumps(message).encode("utf-8"),
                              properties=pika.BasicProperties(delivery_mode=2))
        connection.close()
        logger.info(f"Published media job: {message.get('job_id')}")
    except Exception as e:
        logger.error(f"Failed to publish media job: {str(e)}")
        raise


def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=STORY_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=STORY_QUEUE, on_message_callback=handle_message, auto_ack=False)
    channel.start_consuming()


if __name__ == "__main__":
    main()

