import { describe, expect, it } from "vitest";
import type { Breadcrumb, ErrorEvent } from "@sentry/react";
import { redactSelector, redactUrl, scrubBreadcrumb, scrubEvent } from "./monitoring";

/** Every case here corresponds to something the Sentry SDK would have sent if
 *  the two hooks in monitoring.ts were absent. None of them is hypothetical:
 *  the URLs are this app's real routes, and the selector is what
 *  `_htmlElementAsString` produces for the edit button in ExpensesTab. */

const GROUP_ID = "2b2f0e1c-9a71-4a51-8d0b-6d1c9b0f7e42";
const EXPENSE_ID = "8f14e45f-ceea-467a-9c4a-1d7b0c9e2a33";

describe("redactUrl", () => {
  it("replaces every identifier in a path", () => {
    expect(redactUrl(`/api/groups/${GROUP_ID}/expenses`)).toBe("/api/groups/[id]/expenses");
    expect(redactUrl(`/api/groups/${GROUP_ID}/members/${EXPENSE_ID}`)).toBe(
      "/api/groups/[id]/members/[id]",
    );
  });

  it("matches identifiers regardless of case", () => {
    expect(redactUrl(`/groups/${GROUP_ID.toUpperCase()}`)).toBe("/groups/[id]");
  });

  it("drops the OAuth authorization code with the rest of the query", () => {
    // The single most important case: this is a live credential, and it is on
    // the URL of the screen a user is most likely to hit a bug on.
    const scrubbed = redactUrl("https://split-dec.app/?code=live-oauth-code&state=xyz");
    expect(scrubbed).toBe("https://split-dec.app/");
    expect(scrubbed).not.toContain("code");
  });

  it("drops the recovery access token with the rest of the fragment", () => {
    const scrubbed = redactUrl(
      "https://split-dec.app/reset-password#access_token=live&refresh_token=live",
    );
    expect(scrubbed).toBe("https://split-dec.app/reset-password");
    expect(scrubbed).not.toContain("token");
  });

  it("keeps an absolute URL absolute and a relative one relative", () => {
    // Supabase calls are absolute, /api calls are relative; both stay legible.
    expect(redactUrl("https://kmlheefyzhhegxmtaovq.supabase.co/auth/v1/token?grant_type=pkce")).toBe(
      "https://kmlheefyzhhegxmtaovq.supabase.co/auth/v1/token",
    );
    expect(redactUrl("/api/groups")).toBe("/api/groups");
  });

  it("refuses to pass through anything that is not http(s)", () => {
    // An unrecognized string is the one whose contents nobody has checked.
    expect(redactUrl("javascript:alert(document.cookie)")).toBe("[redacted]");
    expect(redactUrl("chrome-extension://abcdef/inject.js")).toBe("[redacted]");
    expect(redactUrl("data:text/html;base64,PHNjcmlwdD4=")).toBe("[redacted]");
  });

  it("leaves an empty string alone", () => {
    expect(redactUrl("")).toBe("");
  });
});

describe("redactSelector", () => {
  it("keeps the element and drops what the user typed", () => {
    // ExpensesTab.tsx puts the expense description in the aria-label, so this
    // exact string is what a click breadcrumb would otherwise carry.
    expect(
      redactSelector('button.rounded-lg[aria-label="Edit expense: Dinner at Marco\'s"]'),
    ).toBe("button.rounded-lg[aria-label]");
  });

  it("strips every attribute value, not just the first", () => {
    expect(redactSelector('input[type="text"][name="description"][title="Rent October"]')).toBe(
      "input[type][name][title]",
    );
  });

  it("leaves a selector with no attributes untouched", () => {
    expect(redactSelector("div#root > section.flex")).toBe("div#root > section.flex");
  });
});

describe("scrubBreadcrumb", () => {
  it("redacts the element path on click breadcrumbs", () => {
    const crumb = scrubBreadcrumb({
      category: "ui.click",
      message: 'button[aria-label="Edit expense: Groceries"]',
    });
    expect(crumb.message).toBe("button[aria-label]");
  });

  it("redacts fetch URLs", () => {
    const crumb = scrubBreadcrumb({
      category: "fetch",
      data: { method: "GET", url: `/api/groups/${GROUP_ID}/balances`, status_code: 500 },
    });
    expect(crumb.data).toEqual({
      method: "GET",
      url: "/api/groups/[id]/balances",
      status_code: 500,
    });
  });

  it("redacts both ends of a navigation breadcrumb", () => {
    const crumb = scrubBreadcrumb({
      category: "navigation",
      data: { from: "/", to: `/groups/${GROUP_ID}` },
    });
    expect(crumb.data).toEqual({ from: "/", to: "/groups/[id]" });
  });

  it("does not mutate the breadcrumb it was given", () => {
    const original: Breadcrumb = { category: "fetch", data: { url: `/groups/${GROUP_ID}` } };
    scrubBreadcrumb(original);
    expect(original.data?.url).toBe(`/groups/${GROUP_ID}`);
  });
});

describe("scrubEvent", () => {
  it("redacts the page URL and the referrer", () => {
    // httpContext fills both from the document, so both name the open group.
    const event = scrubEvent({
      request: {
        url: `https://split-dec.app/groups/${GROUP_ID}?code=live`,
        headers: {
          Referer: `https://split-dec.app/groups/${GROUP_ID}`,
          "User-Agent": "Mozilla/5.0",
        },
      },
    } as unknown as ErrorEvent);
    expect(event.request?.url).toBe("https://split-dec.app/groups/[id]");
    expect(event.request?.headers?.Referer).toBe("https://split-dec.app/groups/[id]");
    expect(event.request?.headers?.["User-Agent"]).toBe("Mozilla/5.0");
    expect(JSON.stringify(event)).not.toContain(GROUP_ID);
  });

  it("drops the query string, cookies and body outright", () => {
    const event = scrubEvent({
      request: {
        url: "https://split-dec.app/",
        query_string: "code=live-oauth-code",
        cookies: "sb-access-token=live",
        data: { description: "Dinner at Marco's" },
      },
    } as unknown as ErrorEvent);
    expect(event.request?.query_string).toBeUndefined();
    expect(event.request?.cookies).toBeUndefined();
    expect(event.request?.data).toBeUndefined();
    expect(JSON.stringify(event)).not.toContain("Marco");
  });

  it("scrubs breadcrumbs again on the way out", () => {
    // beforeBreadcrumb misses anything attached straight to a scope; this is
    // the last gate before the network.
    const event = scrubEvent({
      breadcrumbs: [
        { category: "fetch", data: { url: `/api/expenses/${EXPENSE_ID}` } },
        { category: "ui.click", message: 'button[title="Rent October"]' },
      ],
    } as unknown as ErrorEvent);
    expect(event.breadcrumbs?.[0].data?.url).toBe("/api/expenses/[id]");
    expect(event.breadcrumbs?.[1].message).toBe("button[title]");
  });

  it("leaves an event with no request or breadcrumbs alone", () => {
    const event = { exception: { values: [{ type: "TypeError" }] } } as unknown as ErrorEvent;
    expect(scrubEvent(event)).toEqual(event);
  });
});
