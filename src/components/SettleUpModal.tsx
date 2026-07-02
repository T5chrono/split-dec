import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, newIdempotencyKey } from "../lib/api";
import type { GroupDetail, Settlement, SettlementPayload } from "../lib/types";
import { COMMON_CURRENCIES } from "../lib/currency";
import { useAuth } from "../hooks/useAuth";
import Modal from "./Modal";

export default function SettleUpModal({
  group,
  prefill,
  editing,
  onClose,
}: {
  group: GroupDetail;
  prefill?: SettlementPayload;
  editing?: Settlement; // when set, PUT instead of POST
  onClose: () => void;
}) {
  const { session } = useAuth();
  const myId = session?.user.id;
  const queryClient = useQueryClient();

  const source = editing ?? prefill;
  const [paidBy, setPaidBy] = useState(source?.paid_by_user_id ?? myId ?? "");
  const [paidTo, setPaidTo] = useState(
    source?.paid_to_user_id ?? group.members.find((m) => m.id !== myId)?.id ?? "",
  );
  const [amount, setAmount] = useState(source?.amount ?? "");
  const [currency, setCurrency] = useState(source?.currency ?? "PLN");

  const save = useMutation({
    mutationFn: async () => {
      const payload: SettlementPayload = {
        paid_by_user_id: paidBy,
        paid_to_user_id: paidTo,
        amount,
        currency,
      };
      if (editing) {
        return api.put<Settlement>(`/settlements/${editing.id}`, payload);
      }
      return api.post<Settlement>(
        `/groups/${group.id}/settlements`,
        payload,
        newIdempotencyKey(),
      );
    },
    onSuccess: () => {
      // Spec §4: after recording a settlement, immediately invalidate and
      // re-fetch both balances and expenses (plus the settlements list).
      queryClient.invalidateQueries({ queryKey: ["balances", group.id] });
      queryClient.invalidateQueries({ queryKey: ["expenses", group.id] });
      queryClient.invalidateQueries({ queryKey: ["settlements", group.id] });
      onClose();
    },
  });

  const label = (id: string) => {
    const m = group.members.find((x) => x.id === id);
    return id === myId ? "You" : (m?.full_name ?? m?.email ?? "Former member");
  };

  return (
    <Modal title={editing ? "Edit settlement" : "Settle up"} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
        className="space-y-4"
      >
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">Who paid</label>
            <select
              value={paidBy}
              onChange={(e) => setPaidBy(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500"
            >
              {group.members.map((m) => (
                <option key={m.id} value={m.id}>
                  {label(m.id)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Who received</label>
            <select
              value={paidTo}
              onChange={(e) => setPaidTo(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500"
            >
              {group.members.map((m) => (
                <option key={m.id} value={m.id}>
                  {label(m.id)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">Amount</label>
            <input
              required
              inputMode="decimal"
              pattern="^\d+(\.\d+)?$"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="120.50"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-teal-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Currency</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500"
            >
              {COMMON_CURRENCIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {paidBy === paidTo && (
          <p className="text-sm text-amber-600">Payer and receiver must be different people.</p>
        )}
        {save.error && <p className="text-sm text-red-600">{(save.error as Error).message}</p>}

        <button
          type="submit"
          disabled={save.isPending || paidBy === paidTo || !amount}
          className="w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {save.isPending ? "Saving…" : editing ? "Save changes" : "Record payment"}
        </button>
      </form>
    </Modal>
  );
}
