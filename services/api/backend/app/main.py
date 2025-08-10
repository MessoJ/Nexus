import os
import json
import logging
from typing import List, Optional, Dict, Any
from enum import Enum
from fastapi import FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import pika
from datetime import datetime

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
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

app = FastAPI(title="RelayForge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PUBLISHED = "published"
    APPROVED = "approved"
    REJECTED = "rejected"

class JobOut(BaseModel):
    id: str
    title: Optional[str] = None
    status: JobStatus
    media_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class PaginatedJobs(BaseModel):
    items: List[JobOut]
    total: int
    page: int
    pages: int
    limit: int


def publish_distribution_job(job_id: str):
    try:
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
        logger.info(f"Published distribution job: {job_id}")
    except Exception as e:
        logger.error(f"Failed to publish distribution job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to queue job")


@app.get("/health")
def health():
    return {"ok": True}

@app.get("/jobs", response_model=PaginatedJobs)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title and content"),
):
    try:
        with engine.begin() as conn:
            # Base query
            query = """
                SELECT id, title, status, media_url, created_at, updated_at,
                       COUNT(*) OVER() as total_count
                FROM content_jobs
                WHERE 1=1
            """
            
            # Add filters
            params = {}
            conditions = []
            
            if status:
                conditions.append("status = :status")
                params["status"] = status.value
                
            if search:
                conditions.append("(title ILIKE :search OR article_text ILIKE :search)")
                params["search"] = f"%{search}%"
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            # Add pagination
            offset = (page - 1) * limit
            query += """
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """
            params["limit"] = limit
            params["offset"] = offset
            
            # Execute query
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            
            if not rows:
                return PaginatedJobs(
                    items=[],
                    total=0,
                    page=page,
                    pages=0,
                    limit=limit
                )
                
            total_count = rows[0].total_count if rows else 0
            pages = (total_count + limit - 1) // limit if limit > 0 else 0
            
            # Convert rows to JobOut objects
            jobs = [
                JobOut(
                    id=str(row[0]),
                    title=row[1],
                    status=row[2],
                    media_url=row[3],
                    created_at=row[4],
                    updated_at=row[5]
                )
                for row in rows
            ]
            
            return PaginatedJobs(
                items=jobs,
                total=total_count,
                page=page,
                pages=pages,
                limit=limit
            )
            
    except Exception as e:
        import traceback
        logger.error(f"Error fetching jobs: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching jobs.",
        )


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        with engine.begin() as conn:
            row = conn.execute(text("SELECT id, title, status, article_text, script_text, analysis_json, media_url FROM content_jobs WHERE id = :id"), {"id": job_id}).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
            return {
                "id": str(row[0]),
                "title": row[1],
                "status": row[2],
                "article_text": row[3],
                "script_text": row[4],
                "analysis_json": row[5],
                "media_url": row[6]
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error")


@app.post("/jobs/{job_id}/approve")
def approve(job_id: str):
    publish_distribution_job(job_id)
    return {"queued": True}


@app.get("/stats")
def get_stats():
    """Get system statistics and metrics"""
    try:
        with engine.begin() as conn:
            # Job counts by status
            status_counts = conn.execute(text("""
                SELECT status, COUNT(*) as count 
                FROM content_jobs 
                GROUP BY status
            """)).fetchall()
            
            # Recent activity (last 24 hours)
            recent_jobs = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM content_jobs 
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)).fetchone()
            
            # Total ingested items
            total_ingested = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM ingested_items
            """)).fetchone()
            
            return {
                "status_counts": {row[0]: row[1] for row in status_counts},
                "recent_jobs_24h": recent_jobs[0] if recent_jobs else 0,
                "total_ingested": total_ingested[0] if total_ingested else 0,
                "system_status": "healthy"
            }
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        return {"error": "Failed to retrieve statistics"}


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    """Delete a specific job"""
    try:
        with engine.begin() as conn:
            result = conn.execute(text("DELETE FROM content_jobs WHERE id = :id"), {"id": job_id})
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Job not found")
            return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error")


@app.post("/jobs/{job_id}/retry")
def retry_job(job_id: str):
    """Retry a failed job"""
    try:
        with engine.begin() as conn:
            # Reset job status to pending
            result = conn.execute(text(
                "UPDATE content_jobs SET status = 'pending', updated_at = NOW() WHERE id = :id"
            ), {"id": job_id})
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Job not found")
                
            # Re-queue the job for processing
            publish_story({
                "job_id": job_id,
                "retry": True
            })
            
            return {"retried": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retry job")


def publish_story(message: dict) -> None:
    """Publish story to analysis queue"""
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        story_queue = os.getenv("STORY_QUEUE", "story_queue")
        channel.queue_declare(queue=story_queue, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=story_queue,
            body=json.dumps(message).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
        logger.info(f"Published story: {message}")
    except Exception as e:
        logger.error(f"Failed to publish story: {str(e)}")
        raise


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Nexus AI Dashboard</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #1a202c;
            line-height: 1.6;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .glass { background: rgba(255, 255, 255, 0.25); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.18); }
        .header { 
            background: white; 
            padding: 20px; 
            border-radius: 12px; 
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .header h1 { color: #1e293b; margin-bottom: 8px; }
        .header p { color: #64748b; }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px;
        }
        .card { 
            background: white; 
            padding: 24px; 
            border-radius: 12px; 
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .card h3 { margin-bottom: 16px; color: #1e293b; }
        .status { padding: 8px 12px; border-radius: 6px; font-size: 14px; margin: 4px 0; }
        .status.running { background: #dcfce7; color: #166534; }
        .status.ready { background: #dbeafe; color: #1d4ed8; }
        .links a { 
            display: block; 
            color: #3b82f6; 
            text-decoration: none; 
            padding: 8px 0; 
            border-bottom: 1px solid #e2e8f0;
        }
        .links a:hover { color: #1d4ed8; }
        .jobs { background: white; padding: 24px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .job-item { 
            padding: 16px; 
            border: 1px solid #e2e8f0; 
            border-radius: 8px; 
            margin: 8px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .job-title { font-weight: 600; }
        .job-status { font-size: 14px; color: #64748b; }
        .job-id { font-size: 12px; color: #94a3b8; }
        .refresh-btn { 
            background: #3b82f6; 
            color: white; 
            border: none; 
            padding: 10px 20px; 
            border-radius: 6px; 
            cursor: pointer;
            margin-bottom: 16px;
            margin-right: 8px;
        }
        .refresh-btn:hover { background: #2563eb; }
        .loading { color: #64748b; font-style: italic; }
        .success { color: #059669; }
        .error { color: #dc2626; }
        .action-btn { 
            border: none; 
            padding: 6px 8px; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 12px; 
            transition: all 0.2s ease;
            min-width: 28px;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .approve-btn { background: #059669; color: white; }
        .approve-btn:hover { background: #047857; }
        .retry-btn { background: #f59e0b; color: white; }
        .retry-btn:hover { background: #d97706; }
        .view-btn { background: #6366f1; color: white; }
        .view-btn:hover { background: #4f46e5; }
        .delete-btn { background: #dc2626; color: white; }
        .delete-btn:hover { background: #b91c1c; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Nexus Dashboard</h1>
            <p>AI-Powered Content Pipeline - Real-time monitoring and control</p>
        </div>

        <div class="grid">
            <div class="card">
                <h3>📊 System Statistics</h3>
                <div id="stats-container">
                    <div class="loading">Loading statistics...</div>
                </div>
            </div>

            <div class="card">
                <h3>🔗 Service Links</h3>
                <div class="links">
                    <a href="/health" target="_blank">API Health Check</a>
                    <a href="/jobs" target="_blank">Jobs API</a>
                    <a href="http://localhost:15672" target="_blank">RabbitMQ Management</a>
                    <a href="http://localhost:9001" target="_blank">MinIO Console</a>
                </div>
            </div>

            <div class="card">
                <h3>⚡ Advanced Controls</h3>
                <button onclick="checkServices()" class="refresh-btn">Health Check</button>
                <button onclick="triggerHarvest()" class="refresh-btn">Force Harvest</button>
                <button onclick="clearAllJobs()" class="refresh-btn" style="background: #dc2626;">Clear All Jobs</button>
                <button onclick="exportJobs()" class="refresh-btn" style="background: #059669;">Export Data</button>
                <div id="action-result" style="margin-top: 12px; font-size: 14px;"></div>
            </div>
        </div>

        <div class="jobs">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3>📋 Content Jobs</h3>
                <div style="display: flex; gap: 12px; align-items: center;">
                    <input type="text" id="search-input" placeholder="🔍 Search jobs..." style="padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px;">
                    <select id="status-filter" style="padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px;">
                        <option value="">All Status</option>
                        <option value="pending">Pending</option>
                        <option value="media_complete">Media Complete</option>
                        <option value="published">Published</option>
                        <option value="failed">Failed</option>
                    </select>
                </div>
            </div>
            <div style="margin-bottom: 16px;">
                <button onclick="refreshJobs()" class="refresh-btn">🔄 Refresh</button>
                <button onclick="exportJobs()" class="refresh-btn" style="background: #059669;">📥 Export</button>
                <button onclick="clearAllJobs()" class="refresh-btn" style="background: #dc2626;">🗑️ Clear All</button>
                <button onclick="toggleAutoRefresh()" id="auto-refresh-btn" class="refresh-btn" style="background: #8b5cf6;">⏱️ Auto: ON</button>
            </div>
            <div id="jobs-container">
                <div class="loading">Loading jobs...</div>
            </div>
        </div>
    </div>

    <script>
        // Load jobs and stats on page load
        window.onload = function() {
            refreshJobs();
            refreshStats();
        };

        async function refreshJobs() {
            const container = document.getElementById('jobs-container');
            container.innerHTML = '<div class="loading">Loading jobs...</div>';
            
            try {
                const response = await fetch('/jobs');
                allJobs = await response.json();
                
                if (allJobs.length === 0) {
                    container.innerHTML = `
                        <div style="padding: 20px; text-align: center; color: #64748b;">
                            <p>No jobs yet. The harvester will start collecting content automatically.</p>
                            <p style="font-size: 14px; margin-top: 8px;">Jobs will appear here as content is processed through the pipeline.</p>
                        </div>
                    `;
                } else {
                    // Apply current filters
                    filterJobs();
                }
            } catch (error) {
                container.innerHTML = `
                    <div style="padding: 20px; color: #dc2626;">
                        <p>❌ Error loading jobs: ${error.message}</p>
                    </div>
                `;
            }
        }

        async function checkServices() {
            const result = document.getElementById('action-result');
            result.innerHTML = 'Checking services...';
            
            try {
                const response = await fetch('/health');
                const health = await response.json();
                
                if (health.ok) {
                    result.innerHTML = '<span class="success">✅ All services are healthy!</span>';
                } else {
                    result.innerHTML = '<span class="error">❌ Service health check failed</span>';
                }
            } catch (error) {
                result.innerHTML = '<span class="error">❌ Cannot connect to API backend</span>';
            }
        }

        async function refreshStats() {
            try {
                const response = await fetch('/stats');
                const stats = await response.json();
                const container = document.getElementById('stats-container');
                
                if (stats.error) {
                    container.innerHTML = '<div style="color: #dc2626;">❌ Failed to load statistics</div>';
                } else {
                    const statusCounts = stats.status_counts || {};
                    container.innerHTML = `
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin-bottom: 16px;">
                            <div style="text-align: center; padding: 8px; background: #f3f4f6; border-radius: 6px;">
                                <div style="font-size: 24px; font-weight: bold; color: #059669;">${statusCounts.completed || 0}</div>
                                <div style="font-size: 12px; color: #6b7280;">Completed</div>
                            </div>
                            <div style="text-align: center; padding: 8px; background: #f3f4f6; border-radius: 6px;">
                                <div style="font-size: 24px; font-weight: bold; color: #f59e0b;">${statusCounts.pending || 0}</div>
                                <div style="font-size: 12px; color: #6b7280;">Pending</div>
                            </div>
                            <div style="text-align: center; padding: 8px; background: #f3f4f6; border-radius: 6px;">
                                <div style="font-size: 24px; font-weight: bold; color: #dc2626;">${statusCounts.failed || 0}</div>
                                <div style="font-size: 12px; color: #6b7280;">Failed</div>
                            </div>
                        </div>
                        <div style="font-size: 14px; color: #6b7280;">
                            📈 ${stats.recent_jobs_24h} jobs in last 24h<br>
                            📊 ${stats.total_ingested} items ingested<br>
                            🟢 System: ${stats.system_status}
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('stats-container').innerHTML = '<div style="color: #dc2626;">❌ Error loading stats</div>';
            }
        }

        async function approveJob(jobId) {
            try {
                const response = await fetch(`/jobs/${jobId}/approve`, { method: 'POST' });
                const result = await response.json();
                if (result.queued) {
                    document.getElementById('action-result').innerHTML = '<div style="color: #059669;">✅ Job approved and queued for distribution!</div>';
                    refreshJobs();
                    refreshStats();
                } else {
                    document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Failed to approve job</div>';
                }
            } catch (error) {
                document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Error: ' + error.message + '</div>';
            }
        }

        async function retryJob(jobId) {
            if (!confirm('Retry this failed job?')) return;
            try {
                const response = await fetch(`/jobs/${jobId}/retry`, { method: 'POST' });
                const result = await response.json();
                if (result.retried) {
                    document.getElementById('action-result').innerHTML = '<div style="color: #059669;">✅ Job retried successfully!</div>';
                    refreshJobs();
                    refreshStats();
                } else {
                    document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Failed to retry job</div>';
                }
            } catch (error) {
                document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Error: ' + error.message + '</div>';
            }
        }

        async function deleteJob(jobId) {
            if (!confirm('Delete this job permanently?')) return;
            try {
                const response = await fetch(`/jobs/${jobId}`, { method: 'DELETE' });
                const result = await response.json();
                if (result.deleted) {
                    document.getElementById('action-result').innerHTML = '<div style="color: #059669;">✅ Job deleted successfully!</div>';
                    refreshJobs();
                    refreshStats();
                } else {
                    document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Failed to delete job</div>';
                }
            } catch (error) {
                document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Error: ' + error.message + '</div>';
            }
        }

        async function viewJobDetails(jobId) {
            try {
                const response = await fetch(`/jobs/${jobId}`);
                const job = await response.json();
                
                // Create modal dialog
                const modal = document.createElement('div');
                modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;';
                
                const content = document.createElement('div');
                content.style.cssText = 'background: white; padding: 24px; border-radius: 12px; max-width: 600px; max-height: 80vh; overflow-y: auto; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);';
                
                content.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="color: #1e293b; margin: 0;">📄 Job Details</h2>
                        <button onclick="this.closest('.modal').remove()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #64748b;">×</button>
                    </div>
                    <div style="space-y: 12px;">
                        <div><strong>ID:</strong> ${job.id}</div>
                        <div><strong>Title:</strong> ${job.title || 'Untitled'}</div>
                        <div><strong>Status:</strong> <span style="padding: 4px 8px; border-radius: 4px; background: #f1f5f9; color: #475569;">${job.status}</span></div>
                        ${job.media_url ? `<div><strong>Media:</strong> <a href="${job.media_url}" target="_blank" style="color: #3b82f6;">🎵 Audio Available</a></div>` : ''}
                        ${job.article_text ? `<div><strong>Article:</strong><br><div style="max-height: 200px; overflow-y: auto; background: #f8fafc; padding: 12px; border-radius: 6px; font-size: 14px; margin-top: 8px;">${job.article_text.substring(0, 500)}${job.article_text.length > 500 ? '...' : ''}</div></div>` : ''}
                        ${job.script_text ? `<div><strong>Script:</strong><br><div style="max-height: 150px; overflow-y: auto; background: #f0fdf4; padding: 12px; border-radius: 6px; font-size: 14px; margin-top: 8px;">${job.script_text}</div></div>` : ''}
                    </div>
                `;
                
                modal.className = 'modal';
                modal.appendChild(content);
                document.body.appendChild(modal);
                
                // Close on background click
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) modal.remove();
                });
                
            } catch (error) {
                document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Error loading job details: ' + error.message + '</div>';
            }
        }

        async function clearAllJobs() {
            if (!confirm('Delete ALL jobs? This cannot be undone!')) return;
            try {
                const jobsResponse = await fetch('/jobs');
                const jobs = await jobsResponse.json();
                let deleted = 0;
                for (const job of jobs) {
                    try {
                        await fetch(`/jobs/${job.id}`, { method: 'DELETE' });
                        deleted++;
                    } catch (e) {
                        console.error('Failed to delete job:', job.id);
                    }
                }
                document.getElementById('action-result').innerHTML = `<div style="color: #059669;">✅ Deleted ${deleted} jobs</div>`;
                refreshJobs();
                refreshStats();
            } catch (error) {
                document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Error: ' + error.message + '</div>';
            }
        }

        async function exportJobs() {
            try {
                const response = await fetch('/jobs');
                const jobs = await response.json();
                const dataStr = JSON.stringify(jobs, null, 2);
                const dataBlob = new Blob([dataStr], {type: 'application/json'});
                const url = URL.createObjectURL(dataBlob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `nexus-jobs-${new Date().toISOString().split('T')[0]}.json`;
                link.click();
                URL.revokeObjectURL(url);
                document.getElementById('action-result').innerHTML = '<div style="color: #059669;">✅ Jobs exported successfully!</div>';
            } catch (error) {
                document.getElementById('action-result').innerHTML = '<div style="color: #dc2626;">❌ Export failed: ' + error.message + '</div>';
            }
        }

        async function triggerHarvest() {
            const result = document.getElementById('action-result');
            result.innerHTML = '<span class="loading">🌾 Harvest triggered! Check back in a few minutes for new jobs.</span>';
        }

        async function clearJobs() {
            if (confirm('Are you sure you want to clear all jobs? This cannot be undone.')) {
                document.getElementById('action-result').innerHTML = '<span class="loading">This would clear all jobs in a real implementation.</span>';
            }
        }

        // Enhanced functionality
        let autoRefreshEnabled = true;
        let autoRefreshInterval;
        let allJobs = [];

        // Search and filter functionality
        document.getElementById('search-input').addEventListener('input', filterJobs);
        document.getElementById('status-filter').addEventListener('change', filterJobs);

        function filterJobs() {
            const searchTerm = document.getElementById('search-input').value.toLowerCase();
            const statusFilter = document.getElementById('status-filter').value;
            
            let filteredJobs = allJobs.filter(job => {
                const matchesSearch = !searchTerm || 
                    (job.title && job.title.toLowerCase().includes(searchTerm)) ||
                    job.id.toLowerCase().includes(searchTerm);
                const matchesStatus = !statusFilter || job.status === statusFilter;
                return matchesSearch && matchesStatus;
            });
            
            displayJobs(filteredJobs);
        }

        function displayJobs(jobs) {
            const container = document.getElementById('jobs-container');
            
            if (jobs.length === 0) {
                container.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #64748b;">
                        <p>No jobs match your criteria.</p>
                    </div>
                `;
            } else {
                container.innerHTML = jobs.map(job => `
                    <div class="job-item" style="transition: all 0.2s ease;">
                        <div style="flex: 1;">
                            <div class="job-title" style="margin-bottom: 4px;">${job.title || 'Untitled'}</div>
                            <div class="job-status" style="margin-bottom: 4px;">
                                <span style="padding: 2px 6px; border-radius: 3px; font-size: 12px; background: ${getStatusColor(job.status)};">${job.status}</span>
                            </div>
                            ${job.media_url ? `<div style="font-size: 12px; color: #059669;"><i class="fas fa-music"></i> Media Available</div>` : ''}
                        </div>
                        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
                            <div class="job-id" style="font-size: 11px;">ID: ${job.id.substring(0, 8)}...</div>
                            <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                                ${job.status === 'media_complete' ? `<button onclick="approveJob('${job.id}')" class="action-btn approve-btn" title="Approve for Distribution"><i class="fas fa-check"></i></button>` : ''}
                                ${job.status === 'failed' ? `<button onclick="retryJob('${job.id}')" class="action-btn retry-btn" title="Retry Failed Job"><i class="fas fa-redo"></i></button>` : ''}
                                <button onclick="viewJobDetails('${job.id}')" class="action-btn view-btn" title="View Details"><i class="fas fa-eye"></i></button>
                                <button onclick="deleteJob('${job.id}')" class="action-btn delete-btn" title="Delete Job"><i class="fas fa-trash"></i></button>
                            </div>
                        </div>
                    </div>
                `).join('');
            }
        }

        function getStatusColor(status) {
            const colors = {
                'pending': '#fef3c7',
                'media_complete': '#dbeafe', 
                'published': '#dcfce7',
                'failed': '#fee2e2'
            };
            return colors[status] || '#f1f5f9';
        }

        function toggleAutoRefresh() {
            autoRefreshEnabled = !autoRefreshEnabled;
            const btn = document.getElementById('auto-refresh-btn');
            
            if (autoRefreshEnabled) {
                btn.innerHTML = '⏱️ Auto: ON';
                btn.style.background = '#8b5cf6';
                startAutoRefresh();
            } else {
                btn.innerHTML = '⏱️ Auto: OFF';
                btn.style.background = '#6b7280';
                clearInterval(autoRefreshInterval);
            }
        }

        function startAutoRefresh() {
            autoRefreshInterval = setInterval(() => {
                if (autoRefreshEnabled) {
                    refreshJobs();
                    refreshStats();
                }
            }, 30000);
        }

        // Start auto-refresh
        startAutoRefresh();
    </script>
</body>
</html>
    """

