export const EMPLOYMENT_TYPES = [
  'FULL_TIME',
  'PART_TIME',
  'CONTRACT',
  'INTERNSHIP',
  'TEMPORARY',
] as const;

export type EmploymentType = (typeof EMPLOYMENT_TYPES)[number];

export const EMPLOYMENT_LABELS: Record<EmploymentType, string> = {
  FULL_TIME: 'Full time',
  PART_TIME: 'Part time',
  CONTRACT: 'Contract',
  INTERNSHIP: 'Internship',
  TEMPORARY: 'Temporary',
};

export type JobStatus = 'DRAFT' | 'PUBLISHED' | 'CLOSED';

export type ApplicationStatus =
  | 'SUBMITTED'
  | 'IN_REVIEW'
  | 'SHORTLISTED'
  | 'REJECTED'
  | 'ACCEPTED';

export type Recruiter = {
  id: string;
  email: string;
  full_name: string;
  company_name: string;
  phone: string;
  created_at: string;
  updated_at: string;
};

export type Candidate = {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  headline: string;
  location: string;
  skills: string[];
  summary: string;
  resume_url: string;
  created_at: string;
  updated_at: string;
};

export type AuthSession<T> = {
  access: string;
  tokenType: string;
  expiresIn: number;
  recruiter?: T;
  candidate?: T;
};

export type Job = {
  id: string;
  title: string;
  description: string;
  company: string;
  location: string;
  employment_type: EmploymentType;
  skills: string[];
  status: JobStatus;
  version: number;
  published_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type JobWrite = {
  title: string;
  description: string;
  company: string;
  location: string;
  employment_type: EmploymentType;
  skills: string[];
};

export type JobHit = {
  id: string;
  title: string;
  company: string;
  location: string;
  employment_type: EmploymentType;
  skills: string[];
  published_at: string | null;
};

export type Page<T> = {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
};

export type Application = {
  id: string;
  job_id: string;
  status: ApplicationStatus;
  cover_letter: string;
  job_title_snapshot: string;
  company_snapshot: string;
  applied_at: string;
  status_updated_at: string;
};

export type Health = {
  status: string;
  service: string;
};

export type Readyz = {
  status: string;
  checks: {
    database: string;
    kafka: string;
    consumer?: string;
  };
};

export type OutboxStatus = {
  pending: number;
  oldestPendingAgeSeconds: number;
  lastError: string | null;
  publishedLastHour: number;
};

export type ReconcileResult = {
  mode: string;
  checked: number;
  repaired: number;
  startedAt: string;
  finishedAt: string | null;
};

export type SyncStatus = {
  lastRun: {
    id: number;
    mode: string;
    startedAt: string;
    finishedAt: string | null;
    checked: number;
    repaired: number;
    error: string | null;
  } | null;
  lastRepaired: number;
  localJobCount: number;
};

export type DlqReplayResult = {
  dryRun: boolean;
  read: number;
  published: number;
};

export type JobSnapshot = {
  id: string;
  recruiterId: string;
  title: string;
  description: string;
  company: string;
  location: string;
  employmentType: EmploymentType;
  skills: string[];
  status: JobStatus;
  version: number;
  publishedAt: string | null;
  closedAt: string | null;
  updatedAt: string;
};

export type SnapshotPage = {
  items: JobSnapshot[];
  nextAfter: string | null;
  hasMore: boolean;
};

export type SearchParams = {
  q?: string;
  employmentType?: string;
  location?: string;
  skills?: string[];
  page?: number;
  pageSize?: number;
};
