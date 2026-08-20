# Supabase auth email templates (bilingual PL + EN)

The copy for the two transactional emails Supabase Auth sends: **Confirm sign
up** and **Reset password**. Paste into **Supabase → Authentication → Emails →
Templates** — subject in the subject field, HTML block in the body.

This file exists because these templates live in a dashboard, not in the
codebase, and an earlier draft was lost that way. **The
dashboard is what actually sends mail; this file is the source copy.** If you
edit one, edit the other.

Not to be confused with `api/_src/emailer.py`, which sends *invitation* emails
through Resend directly and keeps its own content in code.

## Conventions and why

- **Polish first, English second**, one horizontal rule between. Supabase cannot
  detect the recipient's language, so both go in every email. Same order as the
  legal documents, where the Polish version prevails.
- **The only variable is `{{ .ConfirmationURL }}`**, used twice per language —
  once as the button href, once as a copy-paste fallback, because some corporate
  mail clients strip buttons.
- **No images, no web fonts, no external CSS.** Everything is inline styles:
  Gmail strips `<style>` blocks, and any external asset would make the email
  fetch from a third party, which the Privacy Policy does not disclose.
- **The brand is teal, not indigo.** Values come from the design system's
  `tokens/colors.css`: `#0d9488` (`--brand-700`) is the primary teal and the
  button fill, `#2dd4bf` (`--brand-500`) is the light coin half used on dark
  surfaces, `#0f172a` (`--ink-900`) is the header band and the heading ink. An
  earlier revision of this file called `#4f46e5` indigo "the app's colour"; it
  never appeared anywhere in the app. If the brand colour moves, it moves in the
  design system first and here second.
- **The logo is drawn, not fetched** — see the next section, which is the one
  genuinely non-obvious thing in these templates.
- Sender is `auth@split-dec.app` via Resend SMTP (already configured). Test with
  `delivered@resend.dev` — Resend rejects reserved domains like `example.com`.

## Why the logo is HTML instead of an image

The lockup at the top of each email is the design system's split-coin mark and
two-tone wordmark, rebuilt out of table cells, `background` and `border-radius`.
It is not an `<img>`, and that is deliberate — every way of putting the real
asset into an email is worse:

- **A hosted `<img>`** (even served from `split-dec.app`, so first-party) turns
  every open into a request carrying the recipient's IP address and the moment
  they read the mail. That is an open-tracking pixel in everything but intent,
  it is not disclosed in the Privacy Policy, and adding it would mean changing
  `src/lib/legal.ts` and bumping `LEGAL_UPDATED`. Not worth it for a logo.
- **A `data:` URI** avoids the fetch, but Gmail and Outlook both refuse `data:`
  in `img src`, so most recipients would get a broken-image box.
- **Inline `<svg>`** — which is what the real asset in
  `SplitDec DesignSystem/assets/` is — gets stripped outright by Gmail.

So the mark is two half-discs: a 14×28 cell filled `#2dd4bf` rounded on its left
edge, a 4px gap, then a 14×28 cell filled `#0d9488` rounded on its right edge.
The wordmark beside it is text, `split` in `#f1f5f9` and `dec` in `#2dd4bf` —
the design system's dark-surface pairing, because the band behind it is
`--ink-900`.

**The 2px vertical stagger is not a rounding artefact — it is the mark.** In
every real asset the left half sits higher than the right: `Logo.tsx` draws them
at y=10 and y=12, the favicon at y=12 and y=15, the design system lockup at y=8
and y=10 — consistently a drop of 6–7% of the coin's height. Here that is
carried by cell padding (`padding-bottom:2px` on the left cell,
`padding-top:2px` on the right) rather than by position, because **Outlook's
Word engine honours cell padding**. So the offset survives in clients where the
roundness does not, which is the right way round: a staggered pair of shapes
still reads as the SplitDec coin even when it is square.

If the coin is ever resized, scale the offset with it — 2px is right at 28px
tall, and a stagger that stays at 2px on a 48px coin looks like a mistake
instead of a mark.

**Its degradation is intentional**: Outlook's Word engine ignores
`border-radius`, so the coin renders there as two staggered teal rectangles —
still a deliberate-looking mark, never a broken asset. Don't "fix" that with a
VML fallback; the point of building it this way is that it cannot fail loudly.

Manrope leads the font stack so a Mac with it installed picks it up, but it is
never `@import`ed — same third-party-fetch rule as above. Everyone else gets the
system sans, which is what these templates used before anyway.

---

## 1. Confirm sign up

**Subject:**

```
Potwierdź swój adres e-mail · Confirm your email — SplitDec
```

**Body:**

```html
<div style="margin:0;padding:24px;background:#f8fafc;font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="520" style="width:100%;max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;border-collapse:separate;">

    <tr>
      <td bgcolor="#0f172a" style="background:#0f172a;padding:22px 32px;border-radius:12px 12px 0 0;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td valign="middle" style="padding-right:12px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td valign="top" style="padding:0 4px 2px 0;font-size:0;line-height:0;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td width="14" height="28" bgcolor="#2dd4bf" style="width:14px;height:28px;background:#2dd4bf;border-radius:14px 0 0 14px;font-size:0;line-height:0;">&nbsp;</td>
                      </tr>
                    </table>
                  </td>
                  <td valign="top" style="padding:2px 0 0 0;font-size:0;line-height:0;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td width="14" height="28" bgcolor="#0d9488" style="width:14px;height:28px;background:#0d9488;border-radius:0 14px 14px 0;font-size:0;line-height:0;">&nbsp;</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
            <td valign="middle" style="font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:22px;font-weight:800;letter-spacing:-0.02em;line-height:1;">
              <span style="color:#f1f5f9;">split</span><span style="color:#2dd4bf;">dec</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <tr>
      <td style="padding:32px;">

        <h1 style="margin:0 0 12px;font-size:18px;font-weight:700;color:#0f172a;">Potwierdź swój adres e-mail</h1>
        <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">
          Dziękujemy za założenie konta w SplitDec. Kliknij poniższy przycisk, żeby potwierdzić
          swój adres i zacząć dzielić wydatki ze znajomymi.
        </p>

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;">
          <tr>
            <td bgcolor="#0d9488" style="background:#0d9488;border-radius:8px;">
              <a href="{{ .ConfirmationURL }}"
                 style="display:inline-block;padding:12px 24px;font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">
                Potwierdź adres e-mail
              </a>
            </td>
          </tr>
        </table>

        <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
          Jeśli przycisk nie działa, skopiuj ten link do przeglądarki:
        </p>
        <p style="margin:0 0 20px;font-size:12px;line-height:1.5;word-break:break-all;">
          <a href="{{ .ConfirmationURL }}" style="color:#0d9488;">{{ .ConfirmationURL }}</a>
        </p>

        <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">
          Jeśli to nie Ty zakładałeś(-łaś) konto, po prostu zignoruj tę wiadomość — bez kliknięcia
          w link konto nie zostanie aktywowane.
        </p>

        <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0;">

        <h2 style="margin:0 0 12px;font-size:18px;font-weight:700;color:#0f172a;">Confirm your email</h2>
        <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">
          Thanks for signing up to SplitDec. Confirm your address with the button below and you can
          start splitting expenses with your friends.
        </p>

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;">
          <tr>
            <td bgcolor="#0d9488" style="background:#0d9488;border-radius:8px;">
              <a href="{{ .ConfirmationURL }}"
                 style="display:inline-block;padding:12px 24px;font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">
                Confirm email address
              </a>
            </td>
          </tr>
        </table>

        <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
          If the button does not work, paste this link into your browser:
        </p>
        <p style="margin:0 0 20px;font-size:12px;line-height:1.5;word-break:break-all;">
          <a href="{{ .ConfirmationURL }}" style="color:#0d9488;">{{ .ConfirmationURL }}</a>
        </p>

        <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">
          If you did not create this account, ignore this email — the account stays inactive until
          the link is used.
        </p>

        <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0 20px;">

        <p style="margin:0 0 6px;font-size:14px;font-weight:800;letter-spacing:-0.02em;">
          <span style="color:#0f172a;">split</span><span style="color:#0d9488;">dec</span>
        </p>
        <p style="margin:0;font-size:12px;line-height:1.6;color:#94a3b8;">
          <a href="https://split-dec.app" style="color:#94a3b8;">split-dec.app</a> ·
          <a href="https://split-dec.app/privacy" style="color:#94a3b8;">Prywatność / Privacy</a> ·
          <a href="https://split-dec.app/terms" style="color:#94a3b8;">Regulamin / Terms</a>
        </p>

      </td>
    </tr>

  </table>
</div>
```

---

## 2. Reset password

**Subject:**

```
Zresetuj hasło · Reset your password — SplitDec
```

**Body:**

```html
<div style="margin:0;padding:24px;background:#f8fafc;font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="520" style="width:100%;max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;border-collapse:separate;">

    <tr>
      <td bgcolor="#0f172a" style="background:#0f172a;padding:22px 32px;border-radius:12px 12px 0 0;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td valign="middle" style="padding-right:12px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td valign="top" style="padding:0 4px 2px 0;font-size:0;line-height:0;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td width="14" height="28" bgcolor="#2dd4bf" style="width:14px;height:28px;background:#2dd4bf;border-radius:14px 0 0 14px;font-size:0;line-height:0;">&nbsp;</td>
                      </tr>
                    </table>
                  </td>
                  <td valign="top" style="padding:2px 0 0 0;font-size:0;line-height:0;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td width="14" height="28" bgcolor="#0d9488" style="width:14px;height:28px;background:#0d9488;border-radius:0 14px 14px 0;font-size:0;line-height:0;">&nbsp;</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
            <td valign="middle" style="font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:22px;font-weight:800;letter-spacing:-0.02em;line-height:1;">
              <span style="color:#f1f5f9;">split</span><span style="color:#2dd4bf;">dec</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <tr>
      <td style="padding:32px;">

        <h1 style="margin:0 0 12px;font-size:18px;font-weight:700;color:#0f172a;">Zresetuj hasło</h1>
        <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">
          Otrzymaliśmy prośbę o zresetowanie hasła do Twojego konta w SplitDec. Kliknij poniższy
          przycisk, żeby ustawić nowe hasło.
        </p>

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;">
          <tr>
            <td bgcolor="#0d9488" style="background:#0d9488;border-radius:8px;">
              <a href="{{ .ConfirmationURL }}"
                 style="display:inline-block;padding:12px 24px;font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">
                Ustaw nowe hasło
              </a>
            </td>
          </tr>
        </table>

        <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
          Jeśli przycisk nie działa, skopiuj ten link do przeglądarki:
        </p>
        <p style="margin:0 0 20px;font-size:12px;line-height:1.5;word-break:break-all;">
          <a href="{{ .ConfirmationURL }}" style="color:#0d9488;">{{ .ConfirmationURL }}</a>
        </p>

        <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">
          Link jest jednorazowy i wkrótce wygaśnie. Jeśli to nie Ty prosiłeś(-łaś) o zmianę hasła,
          zignoruj tę wiadomość — Twoje obecne hasło pozostaje bez zmian.
        </p>

        <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0;">

        <h2 style="margin:0 0 12px;font-size:18px;font-weight:700;color:#0f172a;">Reset your password</h2>
        <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">
          We received a request to reset the password on your SplitDec account. Use the button below
          to choose a new one.
        </p>

        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;">
          <tr>
            <td bgcolor="#0d9488" style="background:#0d9488;border-radius:8px;">
              <a href="{{ .ConfirmationURL }}"
                 style="display:inline-block;padding:12px 24px;font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">
                Set a new password
              </a>
            </td>
          </tr>
        </table>

        <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
          If the button does not work, paste this link into your browser:
        </p>
        <p style="margin:0 0 20px;font-size:12px;line-height:1.5;word-break:break-all;">
          <a href="{{ .ConfirmationURL }}" style="color:#0d9488;">{{ .ConfirmationURL }}</a>
        </p>

        <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">
          The link can be used once and expires shortly. If you did not ask for a password reset,
          ignore this email — your current password stays unchanged.
        </p>

        <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0 20px;">

        <p style="margin:0 0 6px;font-size:14px;font-weight:800;letter-spacing:-0.02em;">
          <span style="color:#0f172a;">split</span><span style="color:#0d9488;">dec</span>
        </p>
        <p style="margin:0;font-size:12px;line-height:1.6;color:#94a3b8;">
          <a href="https://split-dec.app" style="color:#94a3b8;">split-dec.app</a> ·
          <a href="https://split-dec.app/privacy" style="color:#94a3b8;">Prywatność / Privacy</a> ·
          <a href="https://split-dec.app/terms" style="color:#94a3b8;">Regulamin / Terms</a>
        </p>

      </td>
    </tr>

  </table>
</div>
```

---

## After pasting — verify, don't assume

1. Sign up a throwaway address (`delivered@resend.dev`) and confirm the mail
   arrives through Resend rather than Supabase's default sender.
2. Click the button and check it lands on `https://split-dec.app/...` — the
   apex, not `split-dec.vercel.app`. The Site URL is already fixed, but this
   is the one click that proves it end to end.
3. For the reset template, confirm the link lands on `/reset-password` while
   signed out and that the app re-renders signed in on the same path. Click it
   in the **same browser** that asked for the reset — PKCE keeps the
   `code_verifier` in that browser's local storage, so a cross-device click
   fails at the code exchange and looks like a broken template when it isn't.
