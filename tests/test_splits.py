"""compute_splits: split math, banker's rounding, remainder distribution."""

import uuid
from decimal import Decimal as D

import pytest
from fastapi import HTTPException

from _src.schemas import SplitInput
from _src.splits import compute_splits

U1, U2, U3 = (uuid.UUID(int=i) for i in (1, 2, 3))


def si(u, **kw):
    return SplitInput(user_id=u, **kw)


class TestEqual:
    def test_divides_evenly(self):
        shares = compute_splits("EQUAL", D("30.00"), "PLN", U1, [si(U1), si(U2), si(U3)])
        assert shares == {U1: D("10.00"), U2: D("10.00"), U3: D("10.00")}

    def test_payer_absorbs_remainder_first(self):
        shares = compute_splits("EQUAL", D("100.00"), "USD", U2, [si(U1), si(U2), si(U3)])
        assert sum(shares.values()) == D("100.00")
        assert shares[U2] == D("33.34")  # payer gets the extra cent
        assert shares[U1] == shares[U3] == D("33.33")

    def test_zero_decimal_currency(self):
        shares = compute_splits("EQUAL", D("100"), "JPY", U1, [si(U1), si(U2), si(U3)])
        assert sum(shares.values()) == D("100")
        assert shares[U1] == D("34")
        assert sorted(v for k, v in shares.items() if k != U1) == [D("33"), D("33")]

    def test_three_decimal_currency(self):
        shares = compute_splits("EQUAL", D("10.000"), "KWD", U1, [si(U1), si(U2), si(U3)])
        assert sum(shares.values()) == D("10.000")
        assert shares[U1] == D("3.334")

    def test_bankers_rounding_half_to_even(self):
        # 0.25 / 2 = 0.125 -> rounds to 0.12 (half to even); payer tops up.
        shares = compute_splits("EQUAL", D("0.25"), "USD", U1, [si(U1), si(U2)])
        assert shares == {U1: D("0.13"), U2: D("0.12")}

    def test_sum_invariant_over_many_cases(self):
        users = [uuid.UUID(int=i) for i in range(1, 8)]
        for cents in range(1, 200):
            total = D(cents) / D(100)
            for n in (2, 3, 5, 7):
                shares = compute_splits(
                    "EQUAL", total, "EUR", users[0], [si(u) for u in users[:n]]
                )
                assert sum(shares.values()) == total, (total, n)

    def test_too_many_decimals_rejected(self):
        with pytest.raises(HTTPException) as e:
            compute_splits("EQUAL", D("10.001"), "USD", U1, [si(U1)])
        assert e.value.status_code == 422

    def test_jpy_fractional_total_rejected(self):
        with pytest.raises(HTTPException):
            compute_splits("EQUAL", D("100.50"), "JPY", U1, [si(U1), si(U2)])


class TestExact:
    def test_valid(self):
        shares = compute_splits(
            "EXACT", D("30.00"), "PLN", U1,
            [si(U1, amount=D("12.50")), si(U2, amount=D("17.50"))],
        )
        assert shares == {U1: D("12.50"), U2: D("17.50")}

    def test_sum_mismatch_rejected(self):
        with pytest.raises(HTTPException) as e:
            compute_splits(
                "EXACT", D("30.00"), "PLN", U1,
                [si(U1, amount=D("12.50")), si(U2, amount=D("17.00"))],
            )
        assert e.value.status_code == 422

    def test_missing_amount_rejected(self):
        with pytest.raises(HTTPException):
            compute_splits("EXACT", D("30.00"), "PLN", U1, [si(U1, amount=D("30.00")), si(U2)])

    def test_amount_precision_beyond_currency_rejected(self):
        with pytest.raises(HTTPException):
            compute_splits(
                "EXACT", D("30.00"), "PLN", U1,
                [si(U1, amount=D("15.001")), si(U2, amount=D("14.999"))],
            )


class TestPercentage:
    def test_valid_with_remainder_distribution(self):
        shares = compute_splits(
            "PERCENTAGE", D("200.00"), "EUR", U3,
            [
                si(U1, percentage=D("33.33")),
                si(U2, percentage=D("33.33")),
                si(U3, percentage=D("33.34")),
            ],
        )
        assert sum(shares.values()) == D("200.00")

    def test_not_100_rejected(self):
        with pytest.raises(HTTPException) as e:
            compute_splits(
                "PERCENTAGE", D("100.00"), "EUR", U1,
                [si(U1, percentage=D("50")), si(U2, percentage=D("49"))],
            )
        assert e.value.status_code == 422

    def test_missing_percentage_rejected(self):
        with pytest.raises(HTTPException):
            compute_splits(
                "PERCENTAGE", D("100.00"), "EUR", U1,
                [si(U1, percentage=D("100")), si(U2)],
            )


class TestValidation:
    def test_empty_participants_rejected(self):
        with pytest.raises(HTTPException):
            compute_splits("EQUAL", D("10.00"), "PLN", U1, [])

    def test_duplicate_participant_rejected(self):
        with pytest.raises(HTTPException):
            compute_splits("EQUAL", D("10.00"), "PLN", U1, [si(U1), si(U1)])

    def test_unknown_split_type_rejected(self):
        with pytest.raises(HTTPException):
            compute_splits("HALFSIES", D("10.00"), "PLN", U1, [si(U1)])
