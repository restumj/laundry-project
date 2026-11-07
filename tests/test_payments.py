from decimal import Decimal as D

import pytest

from app.services.pricing import OrderCalculationError, validate_payment_amount


def test_bayar_pas_dan_sebagian_diterima():
    validate_payment_amount(D("50000"), D("50000"))
    validate_payment_amount(D("20000"), D("50000"))


@pytest.mark.parametrize("amount", [D("0"), D("-1"), D("NaN"), D("10.001")])
def test_jumlah_tidak_valid(amount):
    with pytest.raises(OrderCalculationError):
        validate_payment_amount(amount, D("50000"))


def test_melebihi_sisa_ditolak():
    with pytest.raises(OrderCalculationError, match="melebihi"):
        validate_payment_amount(D("50001"), D("50000"))


def test_sudah_lunas_ditolak():
    with pytest.raises(OrderCalculationError, match="lunas"):
        validate_payment_amount(D("1000"), D("0"))