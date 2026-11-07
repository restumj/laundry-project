from decimal import Decimal as D

import pytest

from app.services.parsing import parse_decimal, parse_int, parse_lines
from app.services.pricing import OrderCalculationError


def test_koma_desimal_diterima():
    assert parse_decimal("3,5", "Qty") == D("3.5")


def test_kosong_memakai_default():
    assert parse_decimal("", "Ongkos", default=D("0")) == D("0")


def test_kosong_tanpa_default_ditolak():
    with pytest.raises(OrderCalculationError):
        parse_decimal("", "Qty")


@pytest.mark.parametrize("teks", ["abc", "NaN", "Infinity", "1.2.3"])
def test_bukan_angka_ditolak(teks):
    with pytest.raises(OrderCalculationError):
        parse_decimal(teks, "Qty")


def test_parse_int():
    assert parse_int("3", "Poin") == 3
    assert parse_int("", "Poin") == 0
    for buruk in ["-1", "1.5", "abc"]:
        with pytest.raises(OrderCalculationError):
            parse_int(buruk, "Poin")


def test_baris_kosong_diabaikan():
    hasil = parse_lines(["SE-1", "", "SE-2"], ["3,5", "", "2.1"], ["", "", "pakai pelembut"])
    assert hasil == [("SE-1", D("3.5"), None), ("SE-2", D("2.1"), "pakai pelembut")]


def test_qty_tanpa_layanan_ditolak():
    with pytest.raises(OrderCalculationError):
        parse_lines([""], ["2"], [""])


def test_layanan_tanpa_qty_ditolak():
    with pytest.raises(OrderCalculationError):
        parse_lines(["SE-1"], [""], [""])


def test_parse_date():
    from datetime import date
    from app.services.parsing import parse_date
    assert parse_date("2026-11-10", "Estimasi") == date(2026, 11, 10)
    assert parse_date("", "Estimasi") is None
    with pytest.raises(OrderCalculationError):
        parse_date("10/11/2026", "Estimasi")


def test_parse_name_dan_phone():
    from app.services.parsing import parse_name, parse_phone
    assert parse_name("  Made   Restu ") == "Made Restu"
    with pytest.raises(OrderCalculationError):
        parse_name(" a ")
    assert parse_phone("0812-3456 789") == "08123456789"
    assert parse_phone("+62 812 3456 789") == "+628123456789"
    for bad in ("12345", "08ab123456", "1" * 16):
        with pytest.raises(OrderCalculationError):
            parse_phone(bad)