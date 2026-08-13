import { Suspense, lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/react";
import { useAuth } from "./hooks/useAuth";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import GroupsPage from "./pages/GroupsPage";
import Layout from "./components/Layout";
import Spinner from "./components/Spinner";

/* Split on the auth branch: a signed-in user never needs the marketing page,
 * and a signed-out visitor never needs the group screens, so each downloads
 * roughly its own half.
 *
 * Eager on purpose:
 *   LoginPage    — the signed-out catch-all, so any deep link renders it.
 *   GroupsPage   — where every signed-in session starts.
 *   Layout       — wraps every signed-in route.
 *   NotFoundPage — a few hundred bytes; a chunk request would cost more.
 *
 * GroupPage is the largest of these: it pulls in all four tabs, both form
 * modals, the date and category pickers, and the whole category icon table.
 * Splitting it is what makes the groups list light, and GroupsPage warms the
 * chunk on the same hover/focus intent that already prefetches group data, so
 * the usual path never waits on it. */
const LandingPage = lazy(() => import("./pages/LandingPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const LegalPage = lazy(() => import("./pages/LegalPage"));
const GroupPage = lazy(() => import("./pages/GroupPage"));

/** The pathname with dynamic segments folded back into their route pattern.
 *
 *  Speed Insights buckets every measurement by route, and a raw pathname makes
 *  each group its own bucket — so the app's busiest screen would be split
 *  across as many entries as there are groups and tell you nothing about any
 *  of them. Folding also keeps group ids out of the measurements. `/groups/:groupId`
 *  is the only dynamic segment in either branch below; add to this if that
 *  stops being true. */
export function insightsRoute(pathname: string): string {
  return pathname.replace(/^\/groups\/[^/]+/, "/groups/[groupId]");
}

/** Shared by the auth check and the lazy-route fallback, so resolving a
 *  session and then fetching its first chunk look like one wait, not two. */
function FullScreenSpinner() {
  return (
    <div className="flex h-screen items-center justify-center">
      <Spinner />
    </div>
  );
}

export default function App() {
  const { session, loading, passwordRecovery } = useAuth();
  const location = useLocation();

  if (loading) {
    return <FullScreenSpinner />;
  }

  if (!session) {
    // Marketing landing at the root; deep links (e.g. from invitation emails)
    // keep the focused sign-in screen instead of the pitch.
    return (
      <Suspense fallback={<FullScreenSpinner />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          {/* Registered in both auth branches, like /reset-password: the legal
              pages must resolve for signed-out visitors (Google's OAuth review
              fetches them cold) and must not be swallowed by the catch-all. */}
          <Route path="/privacy" element={<LegalPage doc="privacy" />} />
          <Route path="/terms" element={<LegalPage doc="terms" />} />
          <Route path="*" element={<LoginPage />} />
        </Routes>
        <Analytics />
        <SpeedInsights route={insightsRoute(location.pathname)} />
      </Suspense>
    );
  }

  // Safety net: a recovery link is supposed to land on /reset-password, but if
  // Supabase falls back to the Site URL (redirect not allow-listed), route the
  // recovery session there anyway.
  if (passwordRecovery && location.pathname !== "/reset-password") {
    return <Navigate to="/reset-password" replace />;
  }

  return (
    <Suspense fallback={<FullScreenSpinner />}>
      <Routes>
        {/* Outside Layout: the recovery screen shows no app chrome, and the
            legal pages carry their own so one URL renders identically whether
            or not you are signed in. */}
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/privacy" element={<LegalPage doc="privacy" />} />
        <Route path="/terms" element={<LegalPage doc="terms" />} />
        <Route element={<Layout />}>
          <Route path="/" element={<GroupsPage />} />
          <Route path="/groups/:groupId" element={<GroupPage />} />
          {/* A real 404 rather than a redirect to "/": silently landing on the
              groups list made a stale or mistyped link look like it had worked.
              Signed-out unmatched routes still fall through to LoginPage above,
              so a deep link from an invitation email survives sign-in. */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
      <Analytics />
      <SpeedInsights route={insightsRoute(location.pathname)} />
    </Suspense>
  );
}
