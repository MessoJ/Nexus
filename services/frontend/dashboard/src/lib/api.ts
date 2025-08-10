import { Job, PaginatedJobs } from '../types';

const API_BASE_URL = '/api';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || 'An error occurred');
  }
  return response.json();
}

export const jobsApi = {
  async getJobs({
    page = 1,
  },

  async getJob(jobId: string): Promise<Job> {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
    const apiResponse = await handleResponse<Job>(response);
    return apiResponse.data;
  },

  async approveJob(jobId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/approve`, {
      method: 'POST',
    });
    await handleResponse(response);
  },

  async retryJob(jobId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/retry`, {
      method: 'POST',
    });
    await handleResponse(response);
  },

  async deleteJob(jobId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
      method: 'DELETE',
    });
    await handleResponse(response);
  },
};

export default jobsApi;
