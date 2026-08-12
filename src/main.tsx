import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./hooks/useAuth";
import { I18nProvider } from "./lib/i18n";
import { enforceCanonicalOrigin } from "./lib/canonicalHost";
import "./index.css";

// Before anything mounts: on a non-canonical origin the API is a cross-origin
// hop away and every request fails, so leave without firing one.
const leaving = enforceCanonicalOrigin();

const queryClient = new QueryClient({
  defaultOptions: {
    // Data stays "fresh" for a minute: navigating between views renders from
    // cache instantly; mutations invalidate explicitly so nothing goes stale
    // where it matters.
    queries: { retry: 1, staleTime: 60_000 },
  },
});

if (!leaving) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <I18nProvider>
          {/* Inside I18nProvider so its fallback can be translated, and around
              everything else so a failed lazy chunk cannot blank the app. */}
          <ErrorBoundary>
            <AuthProvider>
              <BrowserRouter>
                <App />
              </BrowserRouter>
            </AuthProvider>
          </ErrorBoundary>
        </I18nProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
}
