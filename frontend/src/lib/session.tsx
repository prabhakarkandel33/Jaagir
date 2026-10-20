import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { api, setTokenRefresher } from './api';
import type { AuthSession, Candidate, Recruiter, SessionRole } from './types';

const STORAGE_KEY = 'jp.session';

export type RecruiterSession = {
  role: 'recruiter';
  access: string;
  refresh: string;
  expiresAt: number;
  profile: Recruiter;
};

export type CandidateSession = {
  role: 'candidate';
  access: string;
  refresh: string;
  expiresAt: number;
  profile: Candidate;
};

export type StoredSession = RecruiterSession | CandidateSession;

function isProfile(value: unknown): value is Recruiter | Candidate {
  return Boolean(value && typeof value === 'object' && 'id' in value && 'email' in value);
}

function readSession(): StoredSession | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Partial<StoredSession>;
    if (data.role !== 'recruiter' && data.role !== 'candidate') return null;
    if (typeof data.access !== 'string' || typeof data.refresh !== 'string') return null;
    if (!isProfile(data.profile)) return null;
    return {
      role: data.role,
      access: data.access,
      refresh: data.refresh,
      expiresAt: typeof data.expiresAt === 'number' ? data.expiresAt : 0,
      profile: data.profile,
    } as StoredSession;
  } catch {
    return null;
  }
}

function writeSession(session: StoredSession | null): void {
  try {
    if (session) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // A full or blocked storage must not break the page.
  }
}

export function dashboardPath(session: StoredSession | null): string {
  if (!session) return '/';
  return session.role === 'recruiter' ? '/employers/dashboard' : '/me/dashboard';
}

export function signInPath(role: SessionRole, from?: string): string {
  const base = role === 'recruiter' ? '/employers' : '/me';
  if (!from || !from.startsWith('/') || from.startsWith('//')) return base;
  return `${base}?next=${encodeURIComponent(from)}`;
}

export function safeNext(value: string | null, fallback: string): string {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return fallback;
  if (value.startsWith('/admin')) return fallback;
  return value;
}

type SessionContextValue = {
  session: StoredSession | null;
  recruiter: Recruiter | null;
  candidate: Candidate | null;
  token: string | null;
  signInRecruiter: (auth: AuthSession<Recruiter>) => void;
  signInCandidate: (auth: AuthSession<Candidate>) => void;
  updateProfile: (profile: Recruiter | Candidate) => void;
  signOut: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(readSession);
  const sessionRef = useRef<StoredSession | null>(session);
  const refreshingRef = useRef<Promise<string | null> | null>(null);

  const commit = useCallback((next: StoredSession | null) => {
    sessionRef.current = next;
    writeSession(next);
    setSession(next);
  }, []);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY && event.key !== null) return;
      const next = readSession();
      sessionRef.current = next;
      setSession(next);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  useEffect(() => {
    setTokenRefresher(async () => {
      const current = sessionRef.current;
      if (!current) return null;
      if (refreshingRef.current) return refreshingRef.current;
      const promise = (async () => {
        try {
          const tokens =
            current.role === 'recruiter'
              ? await api.job.refresh(current.refresh)
              : await api.candidate.refresh(current.refresh);
          const latest = sessionRef.current;
          if (!latest) return null;
          const next = {
            ...latest,
            access: tokens.access,
            refresh: tokens.refresh,
            expiresAt: Date.now() + tokens.expiresIn * 1000,
          } as StoredSession;
          commit(next);
          return tokens.access;
        } catch {
          commit(null);
          return null;
        }
      })();
      refreshingRef.current = promise;
      try {
        return await promise;
      } finally {
        refreshingRef.current = null;
      }
    });
    return () => setTokenRefresher(null);
  }, [commit]);

  const signInRecruiter = useCallback(
    (auth: AuthSession<Recruiter>) => {
      if (!auth.recruiter) throw new Error('The sign-in response did not include your profile.');
      commit({
        role: 'recruiter',
        access: auth.access,
        refresh: auth.refresh,
        expiresAt: Date.now() + auth.expiresIn * 1000,
        profile: auth.recruiter,
      });
    },
    [commit],
  );

  const signInCandidate = useCallback(
    (auth: AuthSession<Candidate>) => {
      if (!auth.candidate) throw new Error('The sign-in response did not include your profile.');
      commit({
        role: 'candidate',
        access: auth.access,
        refresh: auth.refresh,
        expiresAt: Date.now() + auth.expiresIn * 1000,
        profile: auth.candidate,
      });
    },
    [commit],
  );

  const updateProfile = useCallback(
    (profile: Recruiter | Candidate) => {
      const current = sessionRef.current;
      if (!current) return;
      commit({ ...current, profile } as StoredSession);
    },
    [commit],
  );

  const signOut = useCallback(() => commit(null), [commit]);

  const value = useMemo<SessionContextValue>(
    () => ({
      session,
      recruiter: session?.role === 'recruiter' ? session.profile : null,
      candidate: session?.role === 'candidate' ? session.profile : null,
      token: session?.access ?? null,
      signInRecruiter,
      signInCandidate,
      updateProfile,
      signOut,
    }),
    [session, signInRecruiter, signInCandidate, updateProfile, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside SessionProvider.');
  return value;
}

/** Kick signed-in visitors away from the public sign-in and landing routes. */
export function SignedOutOnly({ children }: { children: ReactNode }) {
  const { session } = useSession();
  if (session) return <Navigate to={dashboardPath(session)} replace />;
  return <>{children}</>;
}

export function RequireRole({
  role,
  children,
}: {
  role: SessionRole;
  children: ReactNode;
}) {
  const { session } = useSession();
  const location = useLocation();

  if (!session) {
    return <Navigate to={signInPath(role, location.pathname + location.search)} replace />;
  }
  if (session.role !== role) {
    return <Navigate to={dashboardPath(session)} replace />;
  }
  return <>{children}</>;
}


