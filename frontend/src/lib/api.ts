import type {
  Application,
  ApplicationStatus,
  AuthSession,
  Candidate,
  CandidateApplicationDetail,
  CandidateDashboard,
  DlqReplayResult,
  Health,
  Job,
  JobApplicationCount,
  JobHit,
  JobSnapshot,
  JobWrite,
  OutboxStatus,
  Page,
  Readyz,
  ReconcileResult,
  Recruiter,
  RecruiterApplication,
  RecruiterDashboard,
  RecruiterJobDashboard,
  SearchParams,
  SnapshotPage,
  SyncStatus,
  TokenPair,
} from './types';

const JOB_BASE = (import.meta.env.VITE_JOB_SERVICE_URL ?? 'http://localhost:3001').replace(
  /\/$/,
  '',
);
const CANDIDATE_BASE = (
  import.meta.env.VITE_CANDIDATE_SERVICE_URL ?? 'http://localhost:3002'
).replace(/\/$/, '');

export const BASES = { job: JOB_BASE, candidate: CANDIDATE_BASE } as const;
export type ServiceName = keyof typeof BASES;

export type WireEntry = {
  id: number;
  at: string;
  method: string;
  url: string;
  status: number;
  ms: number;
  ok: boolean;
};

const wireListeners = new Set<(entry: WireEntry) => void>();
let wireId = 1;

export function onWire(listener: (entry: WireEntry) => void): () => void {
  wireListeners.add(listener);
  return () => {
    wireListeners.delete(listener);
  };
}

function emitWire(entry: WireEntry): void {
  for (const listener of [...wireListeners]) listener(entry);
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

type QueryValue = string | number | boolean | string[] | undefined | null;

type RequestOptions = {
  method?: string;
  body?: unknown;
  form?: FormData;
  token?: string;
  internalToken?: string;
  query?: Record<string, QueryValue>;
  retried?: boolean;
};

let tokenRefresher: ((service: ServiceName) => Promise<string | null>) | null = null;

/** The session provider owns refresh tokens; it registers the single-flight refresher here. */
export function setTokenRefresher(
  refresher: ((service: ServiceName) => Promise<string | null>) | null,
): void {
  tokenRefresher = refresher;
}

function buildUrl(base: string, path: string, query?: Record<string, QueryValue>): string {
  const url = `${base}${path}`;
  if (!query) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      for (const item of value) if (item) search.append(key, item);
    } else {
      search.set(key, String(value));
    }
  }
  const suffix = search.toString();
  return suffix ? `${url}?${suffix}` : url;
}

async function parseError(response: Response): Promise<ApiError> {
  const text = await response.text();
  if (!text) {
    return new ApiError(response.status, `HTTP_${response.status}`, response.statusText, null);
  }
  try {
    const data: unknown = JSON.parse(text);
    if (data && typeof data === 'object' && 'error' in data) {
      const envelope = (data as { error: { code?: string; message?: string; details?: unknown } })
        .error;
      return new ApiError(
        response.status,
        envelope.code ?? `HTTP_${response.status}`,
        envelope.message ?? 'Request failed.',
        envelope.details ?? null,
      );
    }
    return new ApiError(
      response.status,
      `HTTP_${response.status}`,
      'The service rejected this request.',
      data,
    );
  } catch {
    return new ApiError(response.status, `HTTP_${response.status}`, text, null);
  }
}

async function request<T>(
  service: ServiceName,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = 'GET', body, form, token, internalToken, query, retried } = options;
  const url = buildUrl(BASES[service], path, query);
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined && !form) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  if (internalToken) headers['X-Internal-Token'] = internalToken;

  const started = performance.now();
  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: form ?? (body === undefined ? undefined : JSON.stringify(body)),
    });
  } catch (cause) {
    const ms = Math.round(performance.now() - started);
    emitWire({ id: wireId++, at: new Date().toISOString(), method, url, status: 0, ms, ok: false });
    throw new ApiError(
      0,
      'NETWORK_ERROR',
      `Cannot reach ${BASES[service]}. Is the service running?`,
      cause instanceof Error ? cause.message : null,
    );
  }

  const ms = Math.round(performance.now() - started);
  emitWire({ id: wireId++, at: new Date().toISOString(), method, url, status: response.status, ms, ok: response.ok });

  if (response.status === 401 && token && !retried && tokenRefresher) {
    const fresh = await tokenRefresher(service);
    if (fresh) {
      return request<T>(service, path, { ...options, token: fresh, retried: true });
    }
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}


export async function downloadFile(
  service: ServiceName,
  path: string,
  token: string,
  retried = false,
): Promise<Blob> {
  const response = await fetch(`${BASES[service]}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 401 && !retried && tokenRefresher) {
    const fresh = await tokenRefresher(service);
    if (fresh) return downloadFile(service, path, fresh, true);
  }
  if (!response.ok) throw await parseError(response);
  return response.blob();
}

export const api = {
  job: {
    health: () => request<Health>('job', '/healthz'),
    ready: () => request<Readyz>('job', '/readyz'),

    dashboard: (token: string) =>
      request<RecruiterJobDashboard>('job', '/recruiter/dashboard', { token }),

    refresh: (refresh: string) =>
      request<TokenPair>('job', '/auth/recruiters/refresh', { method: 'POST', body: { refresh } }),

    registerRecruiter: (payload: {
      email: string;
      password: string;
      full_name: string;
      company_name?: string;
      phone?: string;
    }) =>
      request<AuthSession<Recruiter>>('job', '/auth/recruiters/register', {
        method: 'POST',
        body: payload,
      }),

    loginRecruiter: (payload: { email: string; password: string }) =>
      request<AuthSession<Recruiter>>('job', '/auth/recruiters/login', {
        method: 'POST',
        body: payload,
      }),

    me: (token: string) => request<Recruiter>('job', '/recruiters/me', { token }),

    updateMe: (token: string, payload: { full_name: string; company_name: string; phone: string }) =>
      request<Recruiter>('job', '/recruiters/me', { method: 'PUT', token, body: payload }),

    listJobs: (token: string, page = 1, pageSize = 20) =>
      request<Page<Job>>('job', '/recruiter/jobs', { token, query: { page, pageSize } }),

    getJob: (token: string, id: string) =>
      request<Job>('job', `/recruiter/jobs/${id}`, { token }),

    createJob: (token: string, payload: JobWrite) =>
      request<Job>('job', '/recruiter/jobs', { method: 'POST', token, body: payload }),

    updateJob: (token: string, id: string, payload: JobWrite) =>
      request<Job>('job', `/recruiter/jobs/${id}`, { method: 'PUT', token, body: payload }),

    publishJob: (token: string, id: string) =>
      request<Job>('job', `/recruiter/jobs/${id}/publish`, { method: 'POST', token }),

    closeJob: (token: string, id: string) =>
      request<Job>('job', `/recruiter/jobs/${id}/close`, { method: 'POST', token }),

    searchJobs: (params: SearchParams) =>
      request<Page<JobHit>>('job', '/jobs', { query: { ...params } }),

    getPublicJob: (id: string) => request<Job>('job', `/jobs/${id}`),

    outbox: (internalToken: string) =>
      request<OutboxStatus>('job', '/internal/admin/outbox', { internalToken }),

    snapshot: (internalToken: string, after?: string, limit = 20) =>
      request<SnapshotPage>('job', '/internal/jobs/snapshot', {
        internalToken,
        query: { after, limit },
      }),

    internalJob: (internalToken: string, id: string) =>
      request<JobSnapshot>('job', `/internal/jobs/${id}`, { internalToken }),
  },

  candidate: {
    health: () => request<Health>('candidate', '/healthz'),
    ready: () => request<Readyz>('candidate', '/readyz'),

    register: (payload: { email: string; password: string; full_name: string; phone?: string }) =>
      request<AuthSession<Candidate>>('candidate', '/auth/candidates/register', {
        method: 'POST',
        body: payload,
      }),

    login: (payload: { email: string; password: string }) =>
      request<AuthSession<Candidate>>('candidate', '/auth/candidates/login', {
        method: 'POST',
        body: payload,
      }),

    refresh: (refresh: string) =>
      request<TokenPair>('candidate', '/auth/candidates/refresh', {
        method: 'POST',
        body: { refresh },
      }),

    dashboard: (token: string) =>
      request<CandidateDashboard>('candidate', '/candidates/me/dashboard', { token }),

    uploadResume: (token: string, file: File) => {
      const form = new FormData();
      form.append('file', file);
      return request<Candidate>('candidate', '/candidates/me/resume', {
        method: 'POST',
        token,
        form,
      });
    },

    removeResume: (token: string) =>
      request<Candidate>('candidate', '/candidates/me/resume', { method: 'DELETE', token }),

    resumeBlob: (token: string) => downloadFile('candidate', '/candidates/me/resume', token),

    me: (token: string) => request<Candidate>('candidate', '/candidates/me', { token }),

    updateMe: (
      token: string,
      payload: {
        full_name: string;
        phone: string;
        headline: string;
        location: string;
        skills: string[];
        summary: string;
        resume_url: string;
      },
    ) =>
      request<Candidate>('candidate', '/candidates/me', { method: 'PUT', token, body: payload }),

    searchJobs: (params: SearchParams) =>
      request<Page<JobHit>>('candidate', '/jobs', { query: { ...params } }),

    getJob: (id: string) => request<Job>('candidate', `/jobs/${id}`),

    apply: (token: string, jobId: string, coverLetter: string) =>
      request<Application>('candidate', `/jobs/${jobId}/applications`, {
        method: 'POST',
        token,
        body: { cover_letter: coverLetter },
      }),

    myApplications: (token: string, page = 1, pageSize = 20) =>
      request<Page<Application>>('candidate', '/candidates/me/applications', {
        token,
        query: { page, pageSize },
      }),

    myApplication: (token: string, id: string) =>
      request<CandidateApplicationDetail>('candidate', `/candidates/me/applications/${id}`, {
        token,
      }),

    jobApplications: (token: string, jobId: string, page = 1, pageSize = 20) =>
      request<Page<RecruiterApplication>>('candidate', `/recruiter/jobs/${jobId}/applications`, {
        token,
        query: { page, pageSize },
      }),

    allApplications: (token: string, page = 1, pageSize = 20) =>
      request<Page<RecruiterApplication>>('candidate', '/recruiter/applications', {
        token,
        query: { page, pageSize },
      }),

    application: (token: string, id: string) =>
      request<RecruiterApplication>('candidate', `/recruiter/applications/${id}`, { token }),

    setApplicationStatus: (token: string, id: string, status: ApplicationStatus) =>
      request<RecruiterApplication>('candidate', `/recruiter/applications/${id}/status`, {
        method: 'PATCH',
        token,
        body: { status },
      }),

    applicationCounts: (token: string) =>
      request<JobApplicationCount[]>('candidate', '/recruiter/application-counts', { token }),

    recruiterDashboard: (token: string) =>
      request<RecruiterDashboard>('candidate', '/recruiter/dashboard', { token }),

    applicationResumeBlob: (token: string, id: string) =>
      downloadFile('candidate', `/recruiter/applications/${id}/resume`, token),

    reconcile: (internalToken: string, mode: 'full' | 'incremental') =>
      request<ReconcileResult>('candidate', '/internal/admin/reconcile', {
        method: 'POST',
        internalToken,
        query: { mode },
      }),

    syncStatus: (internalToken: string) =>
      request<SyncStatus>('candidate', '/internal/admin/sync-status', { internalToken }),

    dlqReplay: (internalToken: string, limit: number, dryRun: boolean) =>
      request<DlqReplayResult>('candidate', '/internal/admin/dlq/replay', {
        method: 'POST',
        internalToken,
        query: { limit, dryRun },
      }),
  },
};

export type AdminLoginResponse = { service: string; token: string };

/** Admin-site login: the credentials live in each service `.env`. */
export function adminLogin(
  service: 'job' | 'candidate',
  username: string,
  password: string,
): Promise<AdminLoginResponse> {
  return request<AdminLoginResponse>(service, '/internal/admin/login', {
    method: 'POST',
    body: { username, password },
  });
}