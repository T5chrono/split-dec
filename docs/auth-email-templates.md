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
- **The only variable is `{{ .ConfirmationURL }}`**, used twice per template —
  once as the button href, once as a copy-paste fallback, because some corporate
  mail clients strip buttons.
- **No images, no web fonts, no external CSS.** Everything is inline styles:
  Gmail strips `<style>` blocks, and any external asset would make the email
  fetch from a third party, which the Privacy Policy does not disclose.
- `#4f46e5` is the app's indigo. If the brand colour moves, it moves here too.
- Sender is `auth@split-dec.app` via Resend SMTP (already configured). Test with
  `delivered@resend.dev` — Resend rejects reserved domains like `example.com`.

---

## 1. Confirm sign up

**Subject:**

```
Potwierdź swój adres e-mail · Confirm your email — SplitDec
```

**Body:**

```html
<div style="margin:0;padding:24px;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:32px;">

    <p style="margin:0 0 24px;font-size:20px;font-weight:700;color:#4f46e5;">SplitDec</p>

    <h1 style="margin:0 0 12px;font-size:18px;font-weight:600;color:#0f172a;">Potwierdź swój adres e-mail</h1>
    <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">
      Dziękujemy za założenie konta w SplitDec. Kliknij poniższy przycisk, żeby potwierdzić
      swój adres i zacząć dzielić wydatki ze znajomymi.
    </p>

    <p style="margin:0 0 24px;">
      <a href="{{ .ConfirmationURL }}"
         style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;border-radius:8px;">
        Potwierdź adres e-mail
      </a>
    </p>

    <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
      Jeśli przycisk nie działa, skopiuj ten link do przeglądarki:
    </p>
    <p style="margin:0 0 20px;font-size:12px;line-height:1.5;word-break:break-all;">
      <a href="{{ .ConfirmationURL }}" style="color:#4f46e5;">{{ .ConfirmationURL }}</a>
    </p>

    <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">
      Jeśli to nie Ty zakładałeś(-łaś) konto, po prostu zignoruj tę wiadomość — bez kliknięcia
      w link konto nie zostanie aktywowane.
    </p>

    <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0;">

    <h2 style="margin:0 0 12px;font-size:18px;font-weight:600;color:#0f172a;">Confirm your email</h2>
    <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">
      Thanks for signing up to SplitDec. Confirm your address with the button below and you can
      start splitting expenses with your friends.
    </p>

    <p style="margin:0 0 24px;">
      <a href="{{ .ConfirmationURL }}"
         style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;border-radius:8px;">
        Confirm email address
      </a>
    </p>

    <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
      If the button does not work, paste this link into your browser:
    </p>
    <p style="margin:0 0 20px;font-size:12px;line-height:1.5;word-break:break-all;">
      <a href="{{ .ConfirmationURL }}" style="color:#4f46e5;">{{ .ConfirmationURL }}</a>
    </p>

    <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">
      If you did not create this account, ignore this email — the account stays inactive until
      the link is used.
    </p>

    <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0 20px;">

    <p style="margin:0;font-size:12px;line-height:1.6;color:#94a3b8;">
      SplitDec · <a href="https://split-dec.app" style="color:#94a3b8;">split-dec.app</a> ·
      <a href="https://split-dec.app/privacy" style="color:#94a3b8;">Prywatność / Privacy</a> ·
      <a href="https://split-dec.app/terms" style="color:#94a3b8;">Regulamin / Terms</a>
    </p>

  </div>
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
<div style="margin:0;padding:24px;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:32px;">

    <p style="margin:0 0 24px;font-size:20px;font-weight:700;color:#4f46e5;">SplitDec</p>

    <h1 style="margin:0 0 12px;font-size:18px;font-weight:600;color:#0f172a;">Zresetuj hasło</h1>
    <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">
      Otrzymaliśmy prośbę o zresetowanie hasła do Twojego konta w SplitDec. Kliknij poniższy
      przycisk, żeby ustawić nowe hasło.
    </p>

    <p style="margin:0 0 24px;">
      <a href="{{ .ConfirmationURL }}"
         style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;border-radius:8px;">
        Ustaw nowe hasło
      </a>
    </p>

    <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
      Jeśli przycisk nie działa, skopiuj ten link do przeglądarki:
    </p>
    <p style="margin:0 0 20px;font-size:12px;line-height:1.5;word-break:break-all;">
      <a href="{{ .ConfirmationURL }}" style="color:#4f46e5;">{{ .ConfirmationURL }}</a>
    </p>

    <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">
      Link jest jednorazowy i wkrótce wygaśnie. Jeśli to nie Ty prosiłeś(-łaś) o zmianę hasła,
      zignoruj tę wiadomość — Twoje obecne hasło pozostaje bez zmian.
    </p>

    <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0;">

    <h2 style="margin:0 0 12px;font-size:18px;font-weight:600;color:#0f172a;">Reset your password</h2>
    <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">
      We received a request to reset the password on your SplitDec account. Use the button below
      to choose a new one.
    </p>

    <p style="margin:0 0 24px;">
      <a href="{{ .ConfirmationURL }}"
         style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;border-radius:8px;">
        Set a new password
      </a>
    </p>

    <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
      If the button does not work, paste this link into your browser:
    </p>
    <p style="margin:0 0 20px;font-size:12px;line-height:1.5;word-break:break-all;">
      <a href="{{ .ConfirmationURL }}" style="color:#4f46e5;">{{ .ConfirmationURL }}</a>
    </p>

    <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">
      The link can be used once and expires shortly. If you did not ask for a password reset,
      ignore this email — your current password stays unchanged.
    </p>

    <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0 20px;">

    <p style="margin:0;font-size:12px;line-height:1.6;color:#94a3b8;">
      SplitDec · <a href="https://split-dec.app" style="color:#94a3b8;">split-dec.app</a> ·
      <a href="https://split-dec.app/privacy" style="color:#94a3b8;">Prywatność / Privacy</a> ·
      <a href="https://split-dec.app/terms" style="color:#94a3b8;">Regulamin / Terms</a>
    </p>

  </div>
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
   signed out and that the app re-renders signed in on the same path.
