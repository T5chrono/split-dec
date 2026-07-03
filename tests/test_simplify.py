"""greedy_simplify: per-currency debt simplification invariants."""

import uuid
from collections import defaultdict
from decimal import Decimal as D

from _src.balances import greedy_simplify

U = {i: uuid.UUID(int=i) for i in range(1, 10)}


def assert_fully_settles(balances, transfers):
    """Applying the transfers must zero every balance."""
    net = defaultdict(D, {u: b for u, b in balances.items()})
    for t in transfers:
        net[t["from_user_id"]] += t["amount"]
        net[t["to_user_id"]] -= t["amount"]
    assert all(v == 0 for v in net.values()), dict(net)


def test_simple_two_party():
    buckets = {"PLN": {U[1]: D("50"), U[2]: D("-50")}}
    result = greedy_simplify(buckets)
    assert result["PLN"] == [
        {"from_user_id": U[2], "to_user_id": U[1], "amount": D("50")}
    ]


def test_one_creditor_many_debtors():
    balances = {U[1]: D("100"), U[2]: D("-60"), U[3]: D("-40")}
    result = greedy_simplify({"PLN": dict(balances)})
    assert_fully_settles(balances, result["PLN"])
    assert len(result["PLN"]) == 2


def test_currencies_are_isolated():
    buckets = {
        "PLN": {U[1]: D("100"), U[2]: D("-100")},
        "EUR": {U[2]: D("25.50"), U[1]: D("-25.50")},
        "JPY": {},
    }
    result = greedy_simplify(buckets)
    assert result["JPY"] == []
    # PLN and EUR flow in opposite directions and must not offset each other.
    assert result["PLN"][0]["from_user_id"] == U[2]
    assert result["EUR"][0]["from_user_id"] == U[1]


def test_all_amounts_positive():
    balances = {U[1]: D("10"), U[2]: D("5"), U[3]: D("-7"), U[4]: D("-8")}
    result = greedy_simplify({"EUR": dict(balances)})
    assert all(t["amount"] > 0 for t in result["EUR"])
    assert_fully_settles(balances, result["EUR"])


def test_larger_group_settles_completely():
    balances = {
        U[1]: D("123.45"),
        U[2]: D("-23.45"),
        U[3]: D("-50.00"),
        U[4]: D("-100.00"),
        U[5]: D("75.00"),
        U[6]: D("-25.00"),
    }
    result = greedy_simplify({"USD": dict(balances)})
    assert_fully_settles(balances, result["USD"])
    # Greedy never needs more than (participants - 1) transfers.
    assert len(result["USD"]) <= len(balances) - 1


def test_deterministic_output():
    balances = {U[1]: D("10"), U[2]: D("10"), U[3]: D("-10"), U[4]: D("-10")}
    a = greedy_simplify({"PLN": dict(balances)})
    b = greedy_simplify({"PLN": dict(balances)})
    assert a == b
