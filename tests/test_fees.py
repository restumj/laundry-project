from decimal import Decimal as D

import pytest

from app.services.pricing import OrderCalculationError, recalc_with_fees


def test_ongkos_naik_total_dan_poin_naik():
    # subtotal 31500, promo 3150, poin dipakai 1 -> sebelumnya ongkos 4000 = total 31350 (3 poin)
    new = recalc_with_fees(D("31500"), D("3150"), D("10000"), D("0"), 1)
    assert new.total_price == D("37350")
    assert new.points_earned == 3


def test_ongkos_diturunkan():
    new = recalc_with_fees(D("31500"), D("3150"), D("0"), D("0"), 1)
    assert new.total_price == D("27350")
    assert new.points_earned == 2


def test_ongkos_negatif_ditolak():
    with pytest.raises(OrderCalculationError):
        recalc_with_fees(D("31500"), D("3150"), D("-1"), D("0"), 1)


def test_poin_terpakai_melebihi_tagihan_baru_ditolak():
    with pytest.raises(OrderCalculationError, match="poin"):
        recalc_with_fees(D("1000"), D("0"), D("0"), D("0"), 5)