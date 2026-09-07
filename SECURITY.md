# Security Policy

SplitDec is a personal expense-splitting app run by a single maintainer at
<https://split-dec.app>. Thank you for taking the time to report something.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

- Preferred: [private vulnerability reporting](https://github.com/T5chrono/split-dec/security/advisories/new)
  on this repository. It keeps the report private until there is a fix, and it
  gives us one place to discuss it.
- Alternatively: email **privacy@split-dec.app**.

Useful things to include, if you have them: what you did, what happened, what
you expected instead, and roughly how someone would reproduce it. A proof of
concept helps but is not required — a clear description of the flaw is enough.

## What to expect

This is a hobby project maintained by one person, so please read these as
honest intentions rather than a contractual SLA:

| | |
| --- | --- |
| First reply | within 7 days |
| Assessment and a plan | within 14 days |
| Fix for a confirmed high-severity issue | as quickly as I can, deployed straight to production |

Production deploys from `master` automatically, so a fix reaches users as soon
as it merges. I will tell you when it has shipped, and I am happy to credit you
in the advisory — say so in your report if you would rather stay anonymous.

## Scope

In scope: <https://split-dec.app> and this repository.

Out of scope, because they are not ours to fix — report those to the vendor:
Supabase (auth and database), Vercel (hosting and CDN), Resend (email delivery)
and Sentry (error monitoring).

Also out of scope: reports produced solely by a scanner with no demonstrated
impact, missing headers with no exploit path, denial of service through sheer
volume, and social engineering of the maintainer or of other users.

## Please do not

Access, modify or delete data belonging to anyone but yourself; degrade the
service for other users; or run automated scans heavy enough to look like an
attack. Create your own account and your own group to test against — that is
what the welcome group exists for.

Testing that stays within the above is welcome, and I will not pursue anything
over a good-faith report made under this policy.
