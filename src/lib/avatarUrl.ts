/** Profile-picture URLs are attacker-controlled, so they are allow-listed.
 *
 *  `public.users.avatar_url` is copied verbatim out of `raw_user_meta_data` by
 *  the `handle_new_user` trigger, and for password signup that metadata is
 *  simply whatever the client handed to `supabase.auth.signUp` — so any account
 *  can put any string in this column, and every other member of a shared group
 *  renders it.
 *
 *  **This is not an XSS fix.** A `javascript:` URL does not execute in `<img
 *  src>`, and SVG loaded through `<img>` cannot script. What it stops is
 *  quieter: an arbitrary URL here points every group member's browser at a
 *  server the attacker owns, which hands over their IP address and the fact
 *  that they are looking at the members list right now — a tracking pixel
 *  inside the app. `referrerPolicy="no-referrer"` limits what leaks; it cannot
 *  stop the request happening.
 *
 *  Only Google's avatar CDN is accepted, because Google OAuth is the only thing
 *  that legitimately fills this column: every avatar in production today is
 *  `https://lh3.googleusercontent.com/…` (checked against the database, not
 *  assumed). Subdomains are allowed as a group because Google rotates the shard
 *  number — `lh3` through `lh6` all appear in the wild.
 *
 *  **If a second OAuth provider is ever added, its avatar host must be added
 *  here or its users silently get initials.** That trade is deliberate: a
 *  cosmetic regression that the new provider's first test login reveals, versus
 *  leaving a request-to-anywhere open for every existing member.
 */
const ALLOWED_AVATAR_HOST = "googleusercontent.com";

/** The URL to render, or null to fall back to the initials badge. */
export function safeAvatarUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;

  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return null; // relative, malformed, or not a URL at all
  }

  // https only: an http avatar would be mixed content anyway, and allowing the
  // scheme through would mean accepting a URL nobody can vouch for in transit.
  if (url.protocol !== "https:") return null;

  const host = url.hostname.toLowerCase();
  // The leading dot is load-bearing. Without it `evilgoogleusercontent.com`
  // matches; with it, only a real subdomain does. A suffix test also rejects
  // `googleusercontent.com.attacker.example`, where the real host is last.
  const allowed = host === ALLOWED_AVATAR_HOST || host.endsWith(`.${ALLOWED_AVATAR_HOST}`);
  return allowed ? url.toString() : null;
}
