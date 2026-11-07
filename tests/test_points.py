from datetime import date

from app.services.points import points_on

TODAY = date(2026, 11, 7)


def test_belum_kedaluwarsa():
    assert points_on(5, date(2026, 11, 30), TODAY) == 5


def test_hari_terakhir_masih_berlaku():
    assert points_on(5, TODAY, TODAY) == 5


def test_sudah_lewat_hangus():
    assert points_on(5, date(2026, 11, 6), TODAY) == 0


def test_tanpa_tanggal_dianggap_berlaku():
    assert points_on(5, None, TODAY) == 5


from app.services.points import add_months, first_expiry, roll_expiry


def test_add_months_biasa_dan_akhir_bulan():
    assert add_months(date(2026, 11, 8), 3) == date(2027, 2, 8)
    assert add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_first_expiry_tiga_bulan_sejak_daftar():
    assert first_expiry(date(2026, 8, 15)) == date(2026, 11, 15)


def test_roll_expiry_maju_per_periode():
    assert roll_expiry(date(2026, 11, 30), date(2026, 11, 30)) == date(2026, 11, 30)
    assert roll_expiry(date(2026, 11, 30), date(2026, 12, 1)) == date(2027, 2, 28)
    # terlewat dua periode lebih -> tetap berpatokan pada tanggal awal (tidak melenceng)
    assert roll_expiry(date(2026, 1, 31), date(2026, 5, 1)) == date(2026, 7, 31)