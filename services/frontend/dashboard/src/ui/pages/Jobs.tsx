import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { 
  CheckCircle2, 
  ExternalLink, 
  RefreshCw, 
  AlertCircle,
  Filter,
  Search,
  ChevronLeft,
  ChevronRight,
  Loader2
} from 'lucide-react';
import { formatDistanceToNow, isValid } from 'date-fns';
import { ApiError } from '../../types';

type Job = {
  id: string;
  title?: string;
  status: 'pending' | 'processing' | 'completed' | 'media_complete' | 'failed' | 'published' | 'approved' | 'rejected';
  media_url?: string;
  created_at: string;
  updated_at: string;
};

type StatusFilter = 'all' | Job['status'];

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api';
const PAGE_SIZE = 10;

// Safely format relative time, falling back to 'Unknown' for invalid/missing dates
const relativeOrUnknown = (s?: string) => {
  const d = s ? new Date(s) : null;
  return d && isValid(d) ? formatDistanceToNow(d, { addSuffix: true }) : 'Unknown';
};

export const Jobs: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        limit: PAGE_SIZE.toString(),
        ...(searchTerm && { search: searchTerm }),
        ...(statusFilter !== 'all' && { status: statusFilter })
      });

      const { data } = await axios.get<{ items: Job[]; total: number }>(
        `${API_BASE}/jobs?${params.toString()}`
      );
      
      setJobs(data.items);
      setTotalPages(Math.ceil(data.total / PAGE_SIZE));
    } catch (err) {
      if (axios.isAxiosError<ApiError>(err)) {
        const msg = (err.response?.data as any)?.detail || err.response?.data?.message || err.message;
        setError(msg || 'Failed to fetch jobs');
        console.error('Error fetching jobs:', err);
      } else {
        setError('Failed to fetch jobs');
        console.error('Error fetching jobs:', err);
      }
    } finally {
      setLoading(false);
    }
  }, [currentPage, searchTerm, statusFilter]);

  useEffect(() => {
    fetchJobs();
    const id = setInterval(fetchJobs, 15000);
    return () => clearInterval(id);
  }, [fetchJobs]);

  const approve = async (jobId: string) => {
    setApprovingId(jobId);
    try {
      await axios.post(`${API_BASE}/jobs/${jobId}/approve`);
      await fetchJobs();
    } catch (err) {
      if (axios.isAxiosError<ApiError>(err)) {
        const msg = (err.response?.data as any)?.detail || err.response?.data?.message || err.message;
        setError(msg || 'Failed to approve job');
      } else {
        setError('Failed to approve job');
      }
    } finally {
      setApprovingId(null);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchJobs();
  };

  const getStatusBadge = (status: Job['status']) => {
    const statusMap = {
      pending: { color: 'bg-yellow-100 text-yellow-800', label: 'Pending' },
      processing: { color: 'bg-blue-100 text-blue-800', label: 'Processing' },
      completed: { color: 'bg-green-100 text-green-800', label: 'Completed' },
      media_complete: { color: 'bg-green-100 text-green-800', label: 'Media Complete' },
      failed: { color: 'bg-red-100 text-red-800', label: 'Failed' },
      published: { color: 'bg-purple-100 text-purple-800', label: 'Published' },
      approved: { color: 'bg-indigo-100 text-indigo-800', label: 'Approved' },
      rejected: { color: 'bg-gray-100 text-gray-800', label: 'Rejected' },
    };
    
    const { color, label } = statusMap[status] || { color: 'bg-gray-100 text-gray-800', label: status };
    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${color}`}>
        {label}
      </span>
    );
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Content Jobs</h1>
            <p className="mt-1 text-sm text-gray-500">
              Manage and monitor your content distribution jobs
            </p>
          </div>
          <button
            onClick={fetchJobs}
            disabled={loading}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed mt-4 md:mt-0"
          >
            {loading ? (
              <>
                <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4" />
                Refreshing...
              </>
            ) : (
              <>
                <RefreshCw className="-ml-1 mr-2 h-4 w-4" />
                Refresh
              </>
            )}
          </button>
        </div>

        <div className="bg-white shadow rounded-lg p-4 mb-6">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="flex flex-col md:flex-row md:items-center md:space-x-4 space-y-4 md:space-y-0">
              <div className="flex-1 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Search className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search jobs..."
                  className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div className="w-full md:w-48">
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Filter className="h-5 w-5 text-gray-400" />
                  </div>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                    className="block w-full pl-10 pr-10 py-2 text-base border border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 rounded-md"
                  >
                    <option value="all">All Statuses</option>
                    <option value="pending">Pending</option>
                    <option value="processing">Processing</option>
                    <option value="completed">Completed</option>
                    <option value="media_complete">Media Complete</option>
                    <option value="failed">Failed</option>
                    <option value="published">Published</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </div>
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full md:w-auto px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Apply Filters
              </button>
            </div>
          </form>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertCircle className="h-5 w-5 text-red-400" aria-hidden="true" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        {loading && jobs.length === 0 ? (
          <div className="py-12 flex justify-center">
            <Loader2 className="animate-spin h-8 w-8 text-indigo-600" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500">No jobs found. Try adjusting your search filters.</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {jobs.map((job) => (
              <li key={job.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <p className="text-sm font-medium text-indigo-600 truncate">
                        {job.title || 'Untitled Job'}
                      </p>
                      {getStatusBadge(job.status)}
                    </div>
                    <div className="mt-1 flex flex-col sm:flex-row sm:flex-wrap sm:space-x-6">
                      <div className="mt-1 flex items-center text-sm text-gray-500">
                        <span>Created {relativeOrUnknown(job.created_at)}</span>
                      </div>
                      {job.updated_at !== job.created_at && (
                        <div className="mt-1 flex items-center text-sm text-gray-500">
                          <span>Updated {relativeOrUnknown(job.updated_at)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="ml-4 flex-shrink-0 flex space-x-2">
                    {job.media_url && (
                      <a
                        href={job.media_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                      >
                        <ExternalLink className="-ml-0.5 mr-1.5 h-4 w-4" />
                        View
                      </a>
                    )}
                    <button
                      onClick={() => approve(job.id)}
                      disabled={job.status === 'published' || approvingId === job.id}
                      className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {approvingId === job.id ? (
                        <>
                          <Loader2 className="animate-spin -ml-1 mr-1.5 h-4 w-4" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="-ml-0.5 mr-1.5 h-4 w-4" />
                          {job.status === 'published' ? 'Published' : 'Approve & Post'}
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {totalPages > 1 && (
        <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6 mt-6 rounded-b-lg">
          <div className="flex-1 flex justify-between sm:hidden">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
          <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Showing page <span className="font-medium">{currentPage}</span> of{' '}
                <span className="font-medium">{totalPages}</span>
              </p>
            </div>
            <div>
              <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="sr-only">Previous</span>
                  <ChevronLeft className="h-5 w-5" aria-hidden="true" />
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                        currentPage === pageNum
                          ? 'z-10 bg-indigo-50 border-indigo-500 text-indigo-600'
                          : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="sr-only">Next</span>
                  <ChevronRight className="h-5 w-5" aria-hidden="true" />
                </button>
              </nav>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

