import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { PortalShell } from './layouts/PortalShell';
import { PublicShell } from './layouts/PublicShell';
import { RequireRole, SessionProvider, SignedOutOnly } from './lib/session';
import { Admin, type AdminTokens } from './views/Admin';
import { Landing } from './views/Landing';
import { ApplicantDetail } from './views/portal/ApplicantDetail';
import { CandidateApplicationDetail } from './views/portal/CandidateApplicationDetail';
import { CandidateApplications } from './views/portal/CandidateApplications';
import { CandidateDashboard } from './views/portal/CandidateDashboard';
import { CandidateProfile } from './views/portal/CandidateProfile';
import { PostRole } from './views/portal/PostRole';
import { RecruiterApplicants } from './views/portal/RecruiterApplicants';
import { RecruiterDashboard } from './views/portal/RecruiterDashboard';
import { RecruiterProfile } from './views/portal/RecruiterProfile';
import { RecruiterRoles } from './views/portal/RecruiterRoles';
import { RoleDetail } from './views/portal/RoleDetail';
import { RoleEdit } from './views/portal/RoleEdit';
import { CandidateSignIn } from './views/public/CandidateSignIn';
import { JobDetail } from './views/public/JobDetail';
import { Jobs } from './views/public/Jobs';
import { RecruiterSignIn } from './views/public/RecruiterSignIn';

function readAdmin(): AdminTokens | null {
  try {
    const raw = window.localStorage.getItem('jp.admin');
    return raw ? (JSON.parse(raw) as AdminTokens) : null;
  } catch {
    return null;
  }
}

function AdminRoute() {
  const [tokens, setTokens] = useState<AdminTokens | null>(readAdmin);

  useEffect(() => {
    document.body.dataset.world = 'admin';
  }, []);

  useEffect(() => {
    try {
      if (tokens) window.localStorage.setItem('jp.admin', JSON.stringify(tokens));
      else window.localStorage.removeItem('jp.admin');
    } catch {
      // A full or blocked storage must not break the console.
    }
  }, [tokens]);

  return <Admin tokens={tokens} onTokens={setTokens} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <Routes>
          <Route element={<PublicShell />}>
            <Route
              index
              element={
                <SignedOutOnly>
                  <Landing />
                </SignedOutOnly>
              }
            />
            <Route path="jobs" element={<Jobs />} />
            <Route path="jobs/:id" element={<JobDetail />} />
            <Route
              path="employers"
              element={
                <SignedOutOnly>
                  <RecruiterSignIn />
                </SignedOutOnly>
              }
            />
            <Route
              path="me"
              element={
                <SignedOutOnly>
                  <CandidateSignIn />
                </SignedOutOnly>
              }
            />
          </Route>

          <Route
            element={
              <RequireRole role="recruiter">
                <PortalShell />
              </RequireRole>
            }
          >
            <Route path="employers/dashboard" element={<RecruiterDashboard />} />
            <Route path="employers/profile" element={<RecruiterProfile />} />
            <Route path="employers/post" element={<PostRole />} />
            <Route path="employers/roles" element={<RecruiterRoles />} />
            <Route path="employers/roles/:id" element={<RoleDetail />} />
            <Route path="employers/roles/:id/edit" element={<RoleEdit />} />
            <Route path="employers/applicants" element={<RecruiterApplicants />} />
            <Route
              path="employers/applicants/:applicationId"
              element={<ApplicantDetail />}
            />
          </Route>

          <Route
            element={
              <RequireRole role="candidate">
                <PortalShell />
              </RequireRole>
            }
          >
            <Route path="me/dashboard" element={<CandidateDashboard />} />
            <Route path="me/profile" element={<CandidateProfile />} />
            <Route path="me/applications" element={<CandidateApplications />} />
            <Route
              path="me/applications/:applicationId"
              element={<CandidateApplicationDetail />}
            />
          </Route>

          <Route path="admin" element={<AdminRoute />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </SessionProvider>
    </BrowserRouter>
  );
}
