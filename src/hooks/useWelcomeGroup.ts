import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useAuth } from "./useAuth";
import { useI18n } from "../lib/i18n";

/** Ask the API to seed this account's welcome group, once per signed-in session.
 *
 *  The backend decides whether anything is actually created (api/_src/welcome.py
 *  claims the right with a conditional UPDATE), so this is safe to fire on every
 *  mount — a replay, StrictMode's double effect and a second tab all answer
 *  `created: false`. The ref only spares the network the duplicates.
 *
 *  Keyed on the user id rather than fired once: the cache is dropped and
 *  refilled when the authenticated user changes (useAuth), and the account that
 *  signs in second on the same browser needs its own group too.
 *
 *  The current UI language rides along because the group name and the expense
 *  description are stored text, fixed at creation. It is read through a ref so
 *  toggling EN/PL later does not re-run this — the language that mattered is the
 *  one in use when the account was seeded.
 *
 *  Failure is silent by design. Nobody asked for this request, so there is no
 *  screen to put an error on; the group simply arrives on a later visit.
 */
export function useWelcomeGroup() {
  const { session } = useAuth();
  const { lang } = useI18n();
  const queryClient = useQueryClient();
  const langRef = useRef(lang);
  langRef.current = lang;
  const requestedFor = useRef<string | null>(null);

  const userId = session?.user.id ?? null;

  useEffect(() => {
    if (!userId || requestedFor.current === userId) return;
    requestedFor.current = userId;
    let active = true;
    api
      .post<{ created: boolean }>("/users/me/welcome", { lang: langRef.current })
      .then((result) => {
        // Only the request that built the group invalidates: the groups list
        // has usually already been fetched (empty) by the time this lands.
        if (result.created && active) {
          queryClient.invalidateQueries({ queryKey: ["groups"] });
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [userId, queryClient]);
}
