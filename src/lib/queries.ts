/** Shared query definitions so components and prefetchers agree on keys. */

import { queryOptions } from "@tanstack/react-query";
import { api } from "./api";
import type {
  Balances,
  ExpenseList,
  Group,
  GroupDetail,
  Invitation,
  MyInvitation,
  Settlement,
} from "./types";

export const PAGE_SIZE = 20;

export const groupsQuery = () =>
  queryOptions({ queryKey: ["groups"], queryFn: () => api.get<Group[]>("/groups") });

export const groupDetailQuery = (groupId: string) =>
  queryOptions({
    queryKey: ["group", groupId],
    queryFn: () => api.get<GroupDetail>(`/groups/${groupId}`),
  });

/** `paidBy` filters the page server-side (pagination is server-side too, so
 *  filtering the fetched page in the client would leave holes). It is part of
 *  the key, and normalized to null so the unfiltered view shares the key the
 *  prefetchers warm. */
export const expensesQuery = (
  groupId: string,
  offset: number,
  paidBy: string | null = null,
) =>
  queryOptions({
    queryKey: ["expenses", groupId, offset, paidBy],
    queryFn: () =>
      api.get<ExpenseList>(
        `/groups/${groupId}/expenses?limit=${PAGE_SIZE}&offset=${offset}` +
          (paidBy ? `&paid_by=${encodeURIComponent(paidBy)}` : ""),
      ),
  });

export const balancesQuery = (groupId: string) =>
  queryOptions({
    queryKey: ["balances", groupId],
    queryFn: () => api.get<Balances>(`/groups/${groupId}/balances`),
    // Other members' expenses/settlements change this view and there is no
    // cross-client invalidation — keep it fresher than the global 60s.
    staleTime: 15_000,
  });

export const settlementsQuery = (groupId: string) =>
  queryOptions({
    queryKey: ["settlements", groupId],
    queryFn: () => api.get<Settlement[]>(`/groups/${groupId}/settlements`),
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
