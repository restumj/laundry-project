from datetime import date

from app.services.estimation import estimate_date, parse_duration_days

TODAY = date(2026, 11, 7)


def test_baca_hari():
    assert parse_duration_days("3 hari") == 3
    assert parse_duration_days("Reguler 2 Hari") == 2


def test_baca_jam_kurang_dari_sehari_jadi_hari_ini():
    assert parse_duration_days("6 jam") == 0
    assert parse_duration_days("48 jam") == 2


def test_tidak_terbaca():
    assert parse_duration_days("Express") is None
    assert parse_duration_days(None) is None


def test_estimasi_pakai_layanan_terlama():
    assert estimate_date(TODAY, ["1 hari", "3 hari", "2 hari"]) == date(2026, 11, 10)


def test_estimasi_default_jika_tidak_ada_yang_terbaca():
    assert estimate_date(TODAY, ["Express"]) == TODAY
    assert estimate_date(TODAY, []) == TODAY


def test_varian_tak_terbaca_diabaikan_jika_ada_yang_terbaca():
    assert estimate_date(TODAY, ["Express", "1 hari"]) == date(2026, 11, 8)