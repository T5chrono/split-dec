import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import { sentryVitePlugin } from "@sentry/vite-plugin";

// Source maps are uploaded only where there is a token to upload them with, so
// `npm run build` on a laptop and the build CI runs behave identically to the
// old one. The token is a Vercel production env var and never reaches the repo.
const uploadSourceMaps = Boolean(process.env.SENTRY_AUTH_TOKEN);

export default defineConfig({
  build: {
    // "hidden", not true: the maps are generated for the upload below and then
    // deleted from dist/, and the omitted `//# sourceMappingURL=` comment means
    // no browser ever asks for one in the window between. Minified sources plus
    // a public map is the whole bundle, readable — this app's origin is the one
    // holding the Supabase session, so that is not a trade worth making for
    // debuggability nobody but Sentry needs.
    sourcemap: uploadSourceMaps ? "hidden" : false,
    rollupOptions: {
      output: {
        // Rolldown (vite 8) takes chunk groups here rather than the object
        // form of manualChunks, which it rejects outright: "Invalid type:
        // Expected Function but received Object". The option was named
        // `advancedChunks` until rolldown 1.2, which kept it working but
        // started warning on every build; `codeSplitting` is the same type
        // under a new name (rolldown declares the old one as an alias), so
        // this is a rename and not a change in how chunks are grouped.
        codeSplitting: {
          groups: [
            {
              // The runtime every route needs, pinned into one chunk so a
              // deploy that only touches app code leaves it cached: it is the
              // half of the bundle that changes on a dependency bump, not on a
              // feature.
              //
              // Deliberately NOT "everything in node_modules". lucide-react is
              // tree-shaken per route, so hoisting it here would drag
              // GroupPage's icon table into the chunk a signed-out visitor
              // downloads and undo the route splitting it sits behind. Same for
              // anything else that only one branch imports — leave those to
              // rolldown.
              name: "vendor",
              test: /[\\/]node_modules[\\/](?:react|react-dom|react-router|react-router-dom|scheduler|@tanstack[\\/][^\\/]+|@supabase[\\/][^\\/]+)[\\/]/,
            },
          ],
        },
      },
    },
  },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "icons/apple-touch-icon.png"],
      manifest: {
        name: "SplitDec",
        short_name: "SplitDec",
        description: "Split expenses with friends, minus the spreadsheets.",
        theme_color: "#0d9488",
        background_color: "#f8fafc",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icons/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // SPA offline fallback for client-side routes (vite-plugin-pwa sets
        // this by default; explicit so the denylist's dependency is visible).
        // API traffic must never be intercepted or served stale by the SW.
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
      },
    }),
    // Last in the list, and only when it has somewhere to upload to. The plugin
    // stamps a debug id into each bundle and its map, which is what lets Sentry
    // pair them later — so it has to see the final output, after the PWA plugin
    // has finished rewriting it.
    //
    // `url` is not optional here: the org lives in Sentry's EU region, and the
    // plugin defaults to the US ingest (sentry.io), where the upload would
    // authenticate against the wrong tenant and fail.
    ...(uploadSourceMaps
      ? [
          sentryVitePlugin({
            org: "split-dec",
            project: "splitdec-frontend",
            url: "https://de.sentry.io",
            authToken: process.env.SENTRY_AUTH_TOKEN,
            telemetry: false,
            sourcemaps: {
              // Nothing that was uploaded may also be deployed. Without this
              // the maps sit in dist/ and Vercel serves them as static files,
              // which is the same disclosure as shipping unminified source.
              filesToDeleteAfterUpload: ["dist/**/*.map"],
            },
          }),
        ]
      : []),
  ],
});
