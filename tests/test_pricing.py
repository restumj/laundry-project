from decimal import Decimal as D

import pytest

from app.services.pricing import (
    LineInput,
    OrderCalculationError,
    PromoRule,
    calculate_order,
    max_points_usable,
)

# Promo AWALNOV26: 10%, tanpa minimal, maksimal potongan Rp10.000
AWALNOV26 = PromoRule("PERCENT", D("10"), D("0"), D("10000"), True)

# Dua baris layanan dari order O-1
LINES_O1 = [
    LineInput(qty=D("3.5"), unit_price=D("6000")),   # 21.000
    LineInput(qty=D("2.1"), unit_price=D("5000")),   # 10.500
]


def test_order_o1_sesuai_laporan():
    r = calculate_order(
        LINES_O1, pickup_fee=D("4000"), promo=AWALNOV26, points_used=1, point_balance=5
    )
    assert r.subtotal == D("31500")
    assert r.promo_discount == D("3150")
    assert r.total_before_points == D("32350")
    assert r.total_price == D("31350")
    assert r.points_earned == 3


def test_tanpa_promo_dan_tanpa_poin():
    r = calculate_order(LINES_O1)
    assert r.promo_discount == 0
    assert r.total_price == D("31500")
    assert r.points_earned == 3


def test_promo_tidak_memotong_ongkos():
    # Dengan atau tanpa ongkos, potongan promo tetap sama
    tanpa = calculate_order(LINES_O1, promo=AWALNOV26)
    dengan = calculate_order(LINES_O1, pickup_fee=D("4000"), delivery_fee=D("3000"), promo=AWALNOV26)
    assert tanpa.promo_discount == dengan.promo_discount == D("3150")
    assert dengan.total_price - tanpa.total_price == D("7000")


def test_promo_persen_dibatasi_max_discount():
    besar = [LineInput(qty=D("30"), unit_price=D("6000"))]   # subtotal 180.000, 10% = 18.000
    r = calculate_order(besar, promo=AWALNOV26)
    assert r.promo_discount == D("10000")


def test_promo_nominal():
    promo = PromoRule("NOMINAL", D("5000"), D("0"), None, True)
    r = calculate_order(LINES_O1, promo=promo)
    assert r.promo_discount == D("5000")


def test_promo_nominal_tidak_melebihi_subtotal():
    promo = PromoRule("NOMINAL", D("50000"), D("0"), None, True)
    kecil = [LineInput(qty=D("1"), unit_price=D("6000"))]
    r = calculate_order(kecil, pickup_fee=D("4000"), promo=promo)
    assert r.promo_discount == D("6000")      # bukan 50.000
    assert r.total_price == D("4000")         # ongkos tetap dibayar


def test_promo_min_transaction_dibandingkan_dengan_subtotal_layanan():
    promo = PromoRule("PERCENT", D("10"), D("35000"), None, True)
    # subtotal layanan 31.500 < 35.000, walau + ongkos 4.000 = 35.500
    with pytest.raises(OrderCalculationError):
        calculate_order(LINES_O1, pickup_fee=D("4000"), promo=promo)


def test_promo_tidak_aktif_ditolak():
    promo = PromoRule("PERCENT", D("10"), D("0"), None, False)
    with pytest.raises(OrderCalculationError):
        calculate_order(LINES_O1, promo=promo)


def test_poin_memotong_total_termasuk_ongkos():
    # subtotal 6.000 + ongkos 4.000 = 10.000; 10 poin = 10.000 -> total 0
    kecil = [LineInput(qty=D("1"), unit_price=D("6000"))]
    r = calculate_order(kecil, pickup_fee=D("4000"), points_used=10, point_balance=10)
    assert r.total_price == 0
    assert r.points_earned == 0


def test_poin_dibulatkan_ke_bawah_sisa_dibayar():
    # total sebelum poin 32.350 -> maksimal 32 poin, sisa 350 tetap dibayar
    assert max_points_usable(D("32350"), point_balance=100) == 32
    r = calculate_order(
        LINES_O1, pickup_fee=D("4000"), promo=AWALNOV26, points_used=32, point_balance=100
    )
    assert r.total_price == D("350")
    assert r.points_earned == 0


def test_poin_melebihi_saldo_ditolak():
    with pytest.raises(OrderCalculationError):
        calculate_order(LINES_O1, points_used=6, point_balance=5)


def test_poin_melebihi_tagihan_ditolak():
    with pytest.raises(OrderCalculationError):
        calculate_order(LINES_O1, promo=AWALNOV26, points_used=29, point_balance=100)  # maks 28


def test_poin_didapat_dibulatkan_ke_bawah():
    sembilan = [LineInput(qty=D("1"), unit_price=D("9999"))]
    assert calculate_order(sembilan).points_earned == 0
    sepuluh = [LineInput(qty=D("1"), unit_price=D("10000"))]
    assert calculate_order(sepuluh).points_earned == 1


def test_order_tanpa_layanan_ditolak():
    with pytest.raises(OrderCalculationError):
        calculate_order([])


@pytest.mark.parametrize("qty", [D("0"), D("-1")])
def test_qty_harus_positif(qty):
    with pytest.raises(OrderCalculationError):
        calculate_order([LineInput(qty=qty, unit_price=D("6000"))])


def test_hasil_sesuai_check_sub_price_di_database():
    # CHECK database: sub_price = qty x unit_price, dan kolom uang punya 2 desimal
    r = calculate_order([LineInput(qty=D("3.33"), unit_price=D("6000"))])
    assert r.subtotal == D("19980")


def test_qty_maksimal_dua_desimal():
    with pytest.raises(OrderCalculationError):
        calculate_order([LineInput(qty=D("3.555"), unit_price=D("6000"))])
    assert calculate_order([LineInput(qty=D("3.50"), unit_price=D("6000"))]).subtotal == D("21000")