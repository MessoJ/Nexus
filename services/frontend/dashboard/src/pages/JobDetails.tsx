import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { ArrowLeft, CheckCircle, Clock, XCircle, AlertCircle, Loader2 } from 'lucide-react';
import { Job, JobStatus } from '../types';
import { jobsApi } from '../lib/api';

// Type guard for error objects
const isError = (error: unknown): error is Error => {
  return error instanceof Error;
};

// Status icons and colors
const statusIcons: Record<JobStatus, React.ReactNode> = {
  [JobStatus.PENDING]: <Clock className="h-4 w-4" />,
  [JobStatus.PROCESSING]: <Loader2 className="h-4 w-4 animate-spin" />,
  [JobStatus.COMPLETED]: <CheckCircle className="h-4 w-4" />,
  [JobStatus.FAILED]: <XCircle className="h-4 w-4" />,
  [JobStatus.PUBLISHED]: <CheckCircle className="h-4 w-4" />,
  [JobStatus.APPROVED]: <CheckCircle className="h-4 w-4" />,
  [JobStatus.REJECTED]: <XCircle className="h-4 w-4" />,
};

const statusColors: Record<JobStatus, string> = {
  [JobStatus.PENDING]: 'bg-yellow-100 text-yellow-800',
  [JobStatus.PROCESSING]: 'bg-blue-100 text-blue-800',
  [JobStatus.COMPLETED]: 'bg-green-100 text-green-800',
  [JobStatus.FAILED]: 'bg-red-100 text-red-800',
  [JobStatus.PUBLISHED]: 'bg-purple-100 text-purple-800',
  [JobStatus.APPROVED]: 'bg-green-100 text-green-800',
  [JobStatus.REJECTED]: 'bg-red-100 text-red-800',
};

const JobDetails: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  
  const { data: job, isLoading, isError: hasError, error } = useQuery<Job, Error>({
    queryKey: ['job', jobId],
    queryFn: async () => {
      if (!jobId) throw new Error('No job ID provided');
      const response = await jobsApi.getJob(jobId);
      return response.data;
    },
    enabled: !!jobId,
  });

  // Handle loading state
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  // Handle error state
  if (hasError || !job) {
    const errorMessage = error?.message || 'Failed to load job details';
    return (
      <div className="rounded-md bg-red-50 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <XCircle className="h-5 w-5 text-red-400" aria-hidden="true" />
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">
              Error loading job
            </h3>
            <div className="mt-2 text-sm text-red-700">
              <p>{errorMessage}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/jobs"
          className="inline-flex items-center text-sm font-medium text-indigo-600 hover:text-indigo-500"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to jobs
        </Link>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <div className="px-4 py-5 sm:px-6">
          <div className="mt-4 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {job.title ?? 'Untitled Job'}
              </h1>
              <div className="mt-1 flex items-center space-x-2">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    statusColors[job.status] || 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {statusIcons[job.status]}
                  <span className="ml-1">{job.status}</span>
                </span>
                <span className="text-sm text-gray-500">
                  Created on {job.created_at ? format(new Date(job.created_at), 'MMM d, yyyy') : 'Unknown date'}
                </span>
              </div>
            </div>
            <div className="flex space-x-2">
              {job.status === JobStatus.COMPLETED && (
                <button
                  type="button"
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  <CheckCircle className="-ml-1 mr-2 h-5 w-5" />
                  Approve
                </button>
              )}
              {job.status === JobStatus.FAILED && (
                <button
                  type="button"
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                >
                  <AlertCircle className="-ml-1 mr-2 h-5 w-5" />
                  Retry
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="border-t border-gray-200">
          <dl>
            <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Job ID</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2 font-mono">
                {job.id}
              </dd>
            </div>
            <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Status</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    statusColors[job.status] || 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {statusIcons[job.status]}
                  <span className="ml-1">{job.status}</span>
                </span>
              </dd>
            </div>
            <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Created</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                {job.created_at ? format(new Date(job.created_at), 'MMM d, yyyy') : 'Unknown date'}
              </dd>
            </div>
            <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Last Updated</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                {job.updated_at ? format(new Date(job.updated_at), 'MMM d, yyyy') : 'Unknown date'}
              </dd>
            </div>
            {job.media_url && (
              <div className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                <dt className="text-sm font-medium text-gray-500">Media</dt>
                <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                  {job.media_url.endsWith('.mp4') || job.media_url.endsWith('.webm') ? (
                    <video 
                      src={job.media_url} 
                      controls 
                      className="object-cover w-full h-full"
                      aria-label="Job media content"
                    />
                  ) : (
                    <img
                      src={job.media_url}
                      alt="Generated content"
                      className="object-cover w-full h-full"
                      onError={(e: React.SyntheticEvent<HTMLImageElement>) => {
                        const target = e.target as HTMLImageElement;
                        target.onerror = null;
                        target.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWltYWdlLW9mZiI+PGxpbmUgeDE9IjIiIHkxPSIyIiB4Mj0iMjIiIHkyPSIyMiIgLz48cGF0aCBkPSJNMTAgNHYxLjYxOG0wIDB2NS4zNzVjMCAuODk3LjM1OCAxLjc1NyAxIDJMMTAgMTB2MGMwLS44OTcuMzU4LTEuNzU3IDEtMmgwYy42NDItLjI0MyAxLjI5LS4zNzggMS45NjItLjM3OGg1LjM3Nm0wIDBoMi42MjZhMiAyIDAgMCAwIDItMnYtNiIgLz48cGF0aCBkPSJNMTguNTg2IDE4LjU4NkEyIDIgMCAwIDAgMjAgMTZ2LTYiLz48cGF0aCBkPSJNOC4yOTcgNC4yOTlBMS45ODcgMS45ODcgMCAwIDAgNiA0SDRhMiAyIDAgMCAwLTIgMnYxMy42N2EyIDIgMCAwIDAgLjY3OCAxLjQ5M2wxLjwvc3ZnPg==';
                      }}
                    />
                  )}
                </dd>
              </div>
            )}
          </dl>
        </div>

        <div className="border-t border-gray-200">
          <div className="divide-y divide-gray-200">
            <div className="bg-gray-50 px-4 py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Article Text</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2 whitespace-pre-line">
                {job.article_text || <span className="text-gray-500 italic">No article text available</span>}
              </dd>
            </div>
            <div className="bg-white px-4 py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Script Text</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2 whitespace-pre-line">
                {job.script_text || <span className="text-gray-500 italic">No script text available</span>}
              </dd>
            </div>
            {job.analysis_json && (
              <div className="bg-gray-50 px-4 py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
                <dt className="text-sm font-medium text-gray-500">Analysis</dt>
                <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                  <pre className="bg-gray-100 p-4 rounded-md overflow-auto text-xs">
                    {JSON.stringify(job.analysis_json, null, 2)}
                  </pre>
                </dd>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default JobDetails;
