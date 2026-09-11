import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { TileMark, Wordmark } from "../components/Logo";

const buttonCls =
  "w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50";
const linkCls = "text-sm font-medium text-teal-700 hover:underline dark:text-teal-300";

/** Where the unsubscribe link in an invitation email lands.
 *
 *  Registered in *both* auth branches of App, like /privacy and /terms: the
 *  person following this link is, in the ordinary case, someone who has never
 *  had a SplitDec account. It sits outside `Layout` for the same reason.
 *
 *  The opt-out is a button, never something this page does on mount. The API
 *  route is POST-only so that a mail client or link scanner prefetching the
 *  URL cannot unsubscribe anybody (see routers/unsubscribe.py); a page that
 *  fired the request as soon as it rendered would put that back, one layer up.
 *  It also means the reader is told what is about to happen before it does. */
export default function UnsubscribePage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<"idle" | "busy" | "done" | "failed">("idle");

  const submit = async () => {
    setState("busy");
    try {
      await api.post(`/unsubscribe?token=${encodeURIComponent(token)}`, {});
      setState("done");
    } catch {
      setState("failed");
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-4 py-10">
      <Link to="/" className="flex flex-col items-center gap-2">
        <TileMark className="h-16 w-16" />
        <h1 className="text-3xl">
          <Wordmark />
        </h1>
      </Link>

      <div className="flex w-full max-w-sm flex-col gap-4 text-center">
        {!token ? (
          <p role="alert" className="text-sm text-slate-600 dark:text-slate-300">
            {t("unsubscribeInvalid")}
          </p>
        ) : state === "done" ? (
          <p role="status" className="text-sm text-slate-600 dark:text-slate-300">
            {t("unsubscribeDone")}
          </p>
        ) : (
          <>
            <h2 className="text-lg font-semibold">{t("unsubscribeTitle")}</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300">{t("unsubscribeBody")}</p>
            <button
              type="button"
              onClick={submit}
              disabled={state === "busy"}
              className={buttonCls}
            >
              {t(state === "busy" ? "unsubscribeBusy" : "unsubscribeAction")}
            </button>
            {state === "failed" && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {t("unsubscribeFailed")}
              </p>
            )}
          </>
        )}
        <Link to="/" className={linkCls}>
          {t("unsubscribeHome")}
        </Link>
      </div>
    </div>
  );
}
