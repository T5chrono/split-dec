/** Service worker registration — ours rather than vite-plugin-pwa's.
 *
 *  The plugin's `injectRegister` emits a `registerSW.js` whose entire body is
 *  `navigator.serviceWorker.register('/sw.js', { scope: '/' })` with nothing
 *  attached to it. A rejected registration is therefore an *unhandled*
 *  rejection, which Sentry's global handler reports as an error — and that is
 *  exactly what SPLITDEC-FRONTEND-2 was: `Error: Rejected` thrown out of a
 *  wrapped `navigator.serviceWorker` on an Android in-app browser that refuses
 *  to register workers at all.
 *
 *  There is nothing to fix in that environment and nothing to tell the user.
 *  A service worker buys offline caching and an install prompt; every screen in
 *  this app works without one, because the SW never fronts `/api` (see
 *  `navigateFallbackDenylist` in vite.config.ts). So the honest handling of a
 *  refusal is to carry on silently — not to log it, which under the `console`
 *  integration would put the same text back into Sentry as a breadcrumb.
 *
 *  Registering from here also puts the SW behind `main.tsx`'s canonical-origin
 *  guard, which the injected script sat outside of: it raced
 *  `location.replace()` and could leave a worker registered on the `www.` host
 *  the app was in the middle of leaving.
 *
 *  The URL and scope are the plugin's defaults and must keep matching the
 *  `VitePWA` options — `filename` (`sw.js`) and `scope` (the Vite base).
 */

const SW_URL = "/sw.js";
const SW_SCOPE = "/";

/** Registers the generated service worker once the page has loaded.
 *
 *  Deferred to `load` for the reason the plugin's own script defers it: the
 *  registration competes with first paint for the same connection, and nothing
 *  on screen is waiting for it.
 */
export function registerServiceWorker(
  container: ServiceWorkerContainer | undefined = window.navigator.serviceWorker,
  target: Pick<Window, "addEventListener"> = window,
): void {
  if (!container) return;
  target.addEventListener("load", () => {
    container.register(SW_URL, { scope: SW_SCOPE }).catch(() => {
      // Deliberately empty. See the note above: a browser that will not host a
      // service worker is a browser this app still works in.
    });
  });
}
