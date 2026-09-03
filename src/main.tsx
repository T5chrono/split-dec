import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./hooks/useAuth";
import { I18nProvider } from "./lib/i18n";
import { enforceCanonicalOrigin } from "./lib/canonicalHost";
import { initMonitoring } from "./lib/monitoring";
import { registerServiceWorker } from "./lib/serviceWorker";
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
  // Inside the guard, for the reason the measurement products sit in App.tsx:
  // nothing may report from an origin we are already navigating away from.
  // Ahead of the render, unlike them: a crash reporter installed after mount
  // misses the mount that crashes.
  initMonitoring();

  // Only the build generates a service worker, so only the build registers one
  // — `npm run dev` has no `/sw.js` to point at. Behind the same guard as the
  // rest: a worker registered on an origin we are navigating away from outlives
  // the navigation.
  if (import.meta.env.PROD) registerServiceWorker();

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
