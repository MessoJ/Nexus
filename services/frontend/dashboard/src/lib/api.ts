import { Job, PaginatedJobs, JobStatus } from '../types';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE || '/api';

// Mock data for development when backend is not available
const mockJobs: Job[] = [
  {
    id: '1',
    title: 'Sample Content Job 1',
    status: JobStatus.COMPLETED,
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T11:00:00Z',
  },
  {
    id: '2',
    title: 'Sample Content Job 2',
    status: JobStatus.PROCESSING,
    created_at: '2024-01-15T09:15:00Z',
    updated_at: '2024-01-15T10:45:00Z',
  },
  {
    id: '3',
    title: 'Sample Content Job 3',
    status: JobStatus.PENDING,
    created_at: '2024-01-15T08:00:00Z',
    updated_at: '2024-01-15T08:00:00Z',
  },
  {
    id: '4',
    title: 'Sample Content Job 4',
    status: JobStatus.FAILED,
    created_at: '2024-01-14T16:20:00Z',
    updated_at: '2024-01-14T17:30:00Z',
  },
];

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}

export async function getJobs(page: number = 1, limit: number = 10, status?: JobStatus, search?: string): Promise<PaginatedJobs> {
  try {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('limit', String(limit));
    if (status) params.set('status', status);
    if (search) params.set('search', search);
    const response = await fetch(`${API_BASE_URL}/jobs?${params.toString()}`);
    const data = await handleResponse<PaginatedJobs & { pages?: number }>(response);
    const pages = (data as any).pages ?? Math.ceil((data.total || 0) / (data.limit || limit));
    const hasNextPage = page < pages;
    return { ...data, pages, hasNextPage } as PaginatedJobs;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      // Fallback to mock data when backend is not available
      console.warn('Backend not available, using mock data');
      const filteredJobs = mockJobs.filter(job => {
        if (status && job.status !== status) return false;
        if (search && !job.title?.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      });
      const startIndex = (page - 1) * limit;
      const endIndex = startIndex + limit;
      const items = filteredJobs.slice(startIndex, endIndex);
      const total = filteredJobs.length;
      const pages = Math.ceil(total / limit);
      const hasNextPage = page < pages;
      return { items, total, page, pages, limit, hasNextPage };
    }
    throw error;
  }
}

export async function getJob(jobId: string): Promise<Job> {
  try {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
    const job = await handleResponse<Job>(response);
    return job;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      // Fallback to mock data when backend is not available
      console.warn('Backend not available, using mock data for job details');
      const mockJob = mockJobs.find(job => job.id === jobId);
      if (!mockJob) {
        throw new Error('Job not found');
      }
      return mockJob;
    }
    throw error;
  }
}

export async function approveJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/approve`, {
    method: 'POST',
  });
  await handleResponse(response);
}

export async function retryJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/retry`, {
    method: 'POST',
  });
  await handleResponse(response);
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    method: 'DELETE',
  });
  await handleResponse(response);
}

// Default export for backward compatibility
const jobsApi = { getJobs, getJob, approveJob, retryJob, deleteJob };
export default jobsApi;
