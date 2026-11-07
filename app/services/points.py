"""Poin pelanggan: masa berlaku berulang sejak tanggal daftar.

Fungsi murni (tanpa database), mudah dites.

Aturan: saat daftar, tanggal kedaluwarsa pertama = tanggal daftar + 3 bulan.
Begitu tanggal itu lewat, poin direset 0 dan tanggal kedaluwarsa maju 3 bulan lagi,
terus berulang (3 bulan, 3 bulan, dst).
"""
import calendar
from datetime import date
from typing import Optional

POINT_VALIDITY_MONTHS = 3   # satu-satunya angka masa berlaku di aplikasi (SQL EVENT memakai angka yang sama)


def add_months(day: date, months: int) -> date:
    """Tambah bulan; jika tanggalnya tidak ada (31 Mei + 1 bulan), pakai hari terakhir bulan itu."""
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def first_expiry(register_date: date) -> date:
    """Tanggal kedaluwarsa pertama untuk pelanggan yang baru daftar."""
    return add_months(register_date, POINT_VALIDITY_MONTHS)


def points_on(cust_point: int, expired_date: Optional[date], day: date) -> int:
    """Saldo poin yang berlaku pada tanggal `day`.

    Tanggal kedaluwarsa itu sendiri masih berlaku; sehari setelahnya poin hangus.
    """
    if expired_date is not None and expired_date < day:
        return 0
    return cust_point


def roll_expiry(expired_date: date, day: date) -> date:
    """Majukan tanggal kedaluwarsa per 3 bulan sampai tidak lebih kecil dari `day`."""
    n = 0
    result = expired_date
    while result < day:
        n += 1
        result = add_months(expired_date, POINT_VALIDITY_MONTHS * n)
    return result