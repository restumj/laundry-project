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


from app.services.pricing import SETTLE_TOLERANCE, resolve_payment, resolve_settlement


def test_anggap_lunas_menghapus_sisa_kecil():
    assert resolve_settlement(D("31000"), D("31350")) == D("31350")


def test_anggap_lunas_pas_juga_boleh():
    assert resolve_settlement(D("31350"), D("31350")) == D("31350")


def test_anggap_lunas_sisa_terlalu_besar_ditolak():
    with pytest.raises(OrderCalculationError, match="terlalu besar"):
        resolve_settlement(D("30000"), D("31350"))


def test_anggap_lunas_batas_tepat():
    assert resolve_settlement(D("30350"), D("31350")) == D("31350")
    assert SETTLE_TOLERANCE == D("1000")


def test_anggap_lunas_tetap_memeriksa_jumlah():
    with pytest.raises(OrderCalculationError):
        resolve_settlement(D("0"), D("500"))
    with pytest.raises(OrderCalculationError, match="melebihi"):
        resolve_settlement(D("32000"), D("31350"))   # fungsi ketat; jalur normal pakai resolve_payment


def test_bayar_lebih_dicatat_sisa_dan_ada_kembalian():
    assert resolve_payment(D("50000"), D("31350")) == (D("31350"), D("18650"))
    assert resolve_payment(D("99999999"), D("31350"))[0] == D("31350")   # tanpa batas atas


def test_bayar_pas_tanpa_kembalian():
    assert resolve_payment(D("31350"), D("31350")) == (D("31350"), D("0"))


def test_cicilan_dicatat_apa_adanya():
    assert resolve_payment(D("10000"), D("31350")) == (D("10000"), D("0"))


def test_kurang_dengan_anggap_lunas_dalam_batas():
    assert resolve_payment(D("31000"), D("31350"), settle=True) == (D("31350"), D("0"))


def test_kurang_dengan_anggap_lunas_melebihi_batas_ditolak():
    with pytest.raises(OrderCalculationError, match="terlalu besar"):
        resolve_payment(D("20000"), D("31350"), settle=True)


def test_lebih_dengan_anggap_lunas_tetap_boleh():
    assert resolve_payment(D("40000"), D("31350"), settle=True) == (D("31350"), D("8650"))


def test_resolve_payment_input_tidak_valid():
    for bad in (D("0"), D("-5"), D("NaN"), D("1.001")):
        with pytest.raises(OrderCalculationError):
            resolve_payment(bad, D("31350"))
    with pytest.raises(OrderCalculationError, match="lunas"):
        resolve_payment(D("1000"), D("0"))