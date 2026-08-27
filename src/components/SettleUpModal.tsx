import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { GroupDetail, Settlement, SettlementPayload } from "../lib/types";
import {
  AMOUNT_PATTERN,
  COMMON_CURRENCIES,
  normalizeAmountInput,
  trimAmount,
} from "../lib/currency";
import { useAuth } from "../hooks/useAuth";
import { useAmountError } from "../hooks/useAmountError";
import { useIdempotencyKey } from "../hooks/useIdempotencyKey";
import { useI18n } from "../lib/i18n";
import Modal from "./Modal";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800";

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
  const { t } = useI18n();
  const myId = session?.user.id;
  const queryClient = useQueryClient();

  const source = editing ?? prefill;
  const [paidBy, setPaidBy] = useState(source?.paid_by_user_id ?? myId ?? "");
  const [paidTo, setPaidTo] = useState(
    source?.paid_to_user_id ?? group.members.find((m) => m.id !== myId)?.id ?? "",
  );
  const [amount, setAmount] = useState(
    source ? trimAmount(source.amount, source.currency) : "",
  );
  const [currency, setCurrency] = useState(source?.currency ?? "PLN");

  const idempotencyKey = useIdempotencyKey();

  const save = useMutation({
    mutationFn: async () => {
      const payload: SettlementPayload = {
        paid_by_user_id: paidBy,
        paid_to_user_id: paidTo,
        amount: normalizeAmountInput(amount),
        currency,
      };
      if (editing) {
        return api.put<Settlement>(`/settlements/${editing.id}`, payload);
      }
      // The same key on every attempt — see useIdempotencyKey.
      return api.post<Settlement>(
        `/groups/${group.id}/settlements`,
        payload,
        idempotencyKey,
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

  const amountError = useAmountError(amount, currency);

  const label = (id: string) => {
    const m = group.members.find((x) => x.id === id);
    return id === myId ? t("you") : (m?.full_name ?? m?.email ?? t("formerMember"));
  };

  return (
    <Modal
      title={editing ? t("editSettlement") : t("settleUp")}
      onClose={onClose}
      dismissOnBackdrop={false}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
        className="space-y-4"
      >
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">{t("whoPaid")}</label>
            <select value={paidBy} onChange={(e) => setPaidBy(e.target.value)} className={inputCls}>
              {group.members.map((m) => (
                <option key={m.id} value={m.id}>
                  {label(m.id)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">{t("whoReceived")}</label>
            <select value={paidTo} onChange={(e) => setPaidTo(e.target.value)} className={inputCls}>
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
            <label className="mb-1 block text-sm font-medium">{t("amount")}</label>
            <input
              required
              inputMode="decimal"
              pattern={AMOUNT_PATTERN}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="120,50"
              aria-invalid={amountError !== null}
              aria-describedby={amountError ? "settlement-amount-error" : undefined}
              className={`${inputCls} ${
                amountError ? "border-red-500 focus:border-red-500 dark:border-red-500" : ""
              }`}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">{t("currency")}</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className={inputCls}
            >
              {COMMON_CURRENCIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {amountError && (
          <p
            id="settlement-amount-error"
            className="-mt-2 text-sm text-red-600 dark:text-red-400"
          >
            {amountError}
          </p>
        )}
        {paidBy === paidTo && (
          <p className="text-sm text-amber-600 dark:text-amber-400">{t("samePersonWarning")}</p>
        )}
        {save.error && (
          <p className="text-sm text-red-600 dark:text-red-400">{(save.error as Error).message}</p>
        )}

        <button
          type="submit"
          disabled={save.isPending || paidBy === paidTo || !amount || amountError !== null}
          className="w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {save.isPending ? t("saving") : editing ? t("saveChanges") : t("recordPayment")}
        </button>
      </form>
    </Modal>
  );
}
