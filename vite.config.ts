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
      checks: {
        // Rolldown warns when plugin hooks dominate the build, which they
        // always will here: the app builds in about a second and the Sentry
        // upload is a network round trip, so the ratio is a statement about
        // how fast the build is rather than about a plugin misbehaving. It
        // fired on every production build and there is nothing to act on.
        // Flip back to true when actually investigating build performance.
        pluginTimings: false,
      },
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
        // Workbox mirrors `build.sourcemap` for the service worker it
        // generates, and it does that in `closeBundle` — *after* the Sentry
        // plugin's `writeBundle` has already swept dist/ for maps. So with
        // source maps switched on, sw.js.map outlived the sweep and shipped.
        // Nothing here is worth mapping (generated glue plus the workbox
        // runtime), so the fix is not to emit it rather than to delete it
        // later and hope the ordering never changes again.
        sourcemap: false,
      },
    }),
    // Last in the list, and only when it has somewhere to upload to. The plugin
    // stamps a debug id into each bundle and its map, which is what lets Sentry
    // pair them later — so it has to see the final output, after the PWA plugin
    // has finished rewriting it.
    //
    // Deliberately no `url`. The org is in Sentry's EU region and an earlier
    // revision pinned `https://de.sentry.io` here on the assumption that the
    // plugin would otherwise default to the US ingest. The first production
    // build disproved it: a modern org token (`sntrys_…`) carries its own
    // region and sentry-cli prefers that over anything configured, so the
    // option was inert *and* warned on every build ("Using https://sentry.io
    // (embedded in token) rather than manually-configured URL"). A legacy
    // token with no embedded region would need `SENTRY_URL` in the
    // environment instead — there is no way to say it here without the noise.
    ...(uploadSourceMaps
      ? [
          sentryVitePlugin({
            org: "split-dec",
            project: "splitdec-frontend",
            authToken: process.env.SENTRY_AUTH_TOKEN,
            telemetry: false,
            // Without this the plugin *throws* on any upload failure and takes
            // the build down with it (its own README: "the plugin will simply
            // throw an error, thereby stopping the bundling process"). That
            // inverts what matters: an expired token, a revoked scope or a
            // Sentry outage would block a deploy of the app itself — and a
            // deploy is how this app recovers from its own incidents. Source
            // maps are a debugging convenience and must never hold the
            // release hostage, so failure is loud in the build log and
            // otherwise survivable. The cost is that a silently missing
            // upload only shows up as minified frames on the next crash.
            errorHandler: (err) => {
              console.warn(
                "[sentry] source map upload failed; shipping without readable " +
                  "stack traces for this release:",
                err.message,
              );
            },
            sourcemaps: {
              // Rolldown synthesizes this chunk (its module-loading runtime)
              // rather than compiling it from anything, so it is the one
              // emitted asset with no source map — and uploading a script
              // whose map cannot exist made sentry-cli warn on every build
              // ("could not determine a source map reference"). Excluding it
              // loses nothing: there is no original source to resolve a frame
              // in it back to, with or without the upload.
              ignore: ["**/rolldown-runtime-*.js"],
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
