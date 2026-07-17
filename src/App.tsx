import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import GroupsPage from "./pages/GroupsPage";
import GroupPage from "./pages/GroupPage";
import Layout from "./components/Layout";
import Spinner from "./components/Spinner";

export default function App() {
  const { session, loading, passwordRecovery } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!session) {
    // Marketing landing at the root; deep links (e.g. from invitation emails)
    // keep the focused sign-in screen instead of the pitch.
    return (
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="*" element={<LoginPage />} />
      </Routes>
    );
  }

  // Safety net: a recovery link is supposed to land on /reset-password, but if
  // Supabase falls back to the Site URL (redirect not allow-listed), route the
  // recovery session there anyway.
  if (passwordRecovery && location.pathname !== "/reset-password") {
    return <Navigate to="/reset-password" replace />;
  }

  return (
    <Routes>
      {/* Outside Layout: the recovery screen shows no app chrome. */}
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route element={<Layout />}>
        <Route path="/" element={<GroupsPage />} />
        <Route path="/groups/:groupId" element={<GroupPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
