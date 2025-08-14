export enum JobStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  MEDIA_COMPLETE = 'media_complete',
  FAILED = 'failed',
  PUBLISHED = 'published',
  APPROVED = 'approved',
  REJECTED = 'rejected',
}

export interface Job {
  id: string;
  title?: string | null;
  status: JobStatus;
  media_url?: string | null;
  created_at: string;
  updated_at: string;
  article_text?: string | null;
  script_text?: string | null;
  analysis_json?: Record<string, unknown> | null;
}

export interface PaginatedJobs {
  items: Job[];
  total: number;
  page: number;
  pages: number;
  limit: number;
  hasNextPage: boolean;
}

export interface ApiError {
  message: string;
  statusCode: number;
}
