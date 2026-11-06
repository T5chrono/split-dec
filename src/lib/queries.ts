/** Shared query definitions so components and prefetchers agree on keys. */

import { queryOptions } from "@tanstack/react-query";
import { api } from "./api";
import { monthRange } from "./dates";
import type {
  Balances,
  CategoryTotal,
  CurrencyTotal,
  ExpenseList,
  Group,
  GroupDetail,
  Invitation,
  MyInvitation,
  SettlementList,
} from "./types";

export const PAGE_SIZE = 20;

export const groupsQuery = () =>
  queryOptions({ queryKey: ["groups"], queryFn: () => api.get<Group[]>("/groups") });

export const groupDetailQuery = (groupId: string) =>
  queryOptions({
    queryKey: ["group", groupId],
    queryFn: () => api.get<GroupDetail>(`/groups/${groupId}`),
  });

/** `paidBy` and `month` filter the page server-side (pagination is
 *  server-side too, so filtering the fetched page in the client would leave
 *  holes). Both are part of the key, and normalized to null so the unfiltered
 *  view shares the key the prefetchers warm. `month` is "YYYY-MM". */
export const expensesQuery = (
  groupId: string,
  offset: number,
  paidBy: string | null = null,
  month: string | null = null,
) =>
  queryOptions({
    queryKey: ["expenses", groupId, offset, paidBy, month],
    queryFn: () => {
      const range = month ? monthRange(month) : null;
      return api.get<ExpenseList>(
        `/groups/${groupId}/expenses?limit=${PAGE_SIZE}&offset=${offset}` +
          (paidBy ? `&paid_by=${encodeURIComponent(paidBy)}` : "") +
          (range ? `&date_from=${range.from}&date_to=${range.to}` : ""),
      );
    },
  });

/** Per-category totals for one "YYYY-MM" month (the expenses tab's summary).
 *  Its own key root rather than under "expenses": the optimistic delete
 *  rewrites every ["expenses", groupId, …] entry as an ExpenseList. Stale
 *  immediately, so opening the summary always refetches — it is opened on
 *  demand, usually right after the edits it is meant to add up. */
export const categoryTotalsQuery = (groupId: string, month: string) =>
  queryOptions({
    queryKey: ["categoryTotals", groupId, month],
    queryFn: () => {
      const { from, to } = monthRange(month);
      return api.get<CategoryTotal[]>(
        `/groups/${groupId}/expenses/by-category?date_from=${from}&date_to=${to}`,
      );
    },
    staleTime: 0,
  });

export const balancesQuery = (groupId: string) =>
  queryOptions({
    queryKey: ["balances", groupId],
    queryFn: () => api.get<Balances>(`/groups/${groupId}/balances`),
    // Other members' expenses/settlements change this view and there is no
    // cross-client invalidation — keep it fresher than the global 60s.
    staleTime: 15_000,
  });

export const totalsQuery = (groupId: string) =>
  queryOptions({
    queryKey: ["totals", groupId],
    queryFn: () => api.get<CurrencyTotal[]>(`/groups/${groupId}/totals`),
    // Sits in the group header alongside the balances tab and moves for the
    // same reason (other members adding expenses) — same freshness.
    staleTime: 15_000,
  });

export const settlementsQuery = (groupId: string, offset = 0) =>
  queryOptions({
    // The offset belongs in the key, like the expenses one: two pages are two
    // cached entries, and a prefetcher that omits it warms page zero only.
    queryKey: ["settlements", groupId, offset],
    queryFn: () =>
      api.get<SettlementList>(
        `/groups/${groupId}/settlements?limit=${PAGE_SIZE}&offset=${offset}`,
      ),
  });

export const groupInvitationsQuery = (groupId: string) =>
  queryOptions({
    queryKey: ["invitations", groupId],
    queryFn: () => api.get<Invitation[]>(`/groups/${groupId}/invitations`),
  });

export const myInvitationsQuery = () =>
  queryOptions({
    queryKey: ["my-invitations"],
    queryFn: () => api.get<MyInvitation[]>("/invitations/mine"),
  });
