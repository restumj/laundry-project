"""Estimasi tanggal selesai dari layanan yang dipilih (tanpa ubah tabel).

Lama pengerjaan dibaca dari teks `variant`, misalnya "3 hari" -> 3 hari,
"6 jam" -> selesai hari yang sama. Teks yang tidak terbaca diabaikan.
"""
import re
from datetime import date, timedelta
from typing import Iterable, Optional

DEFAULT_ESTIMATION_DAYS = 0   # dipakai jika tidak ada varian yang terbaca (0 = hari ini)

_DAYS = re.compile(r"(\d+)\s*hari", re.IGNORECASE)
_HOURS = re.compile(r"(\d+)\s*jam", re.IGNORECASE)


def parse_duration_days(variant: Optional[str]) -> Optional[int]:
    text = variant or ""
    match = _DAYS.search(text)
    if match:
        return int(match.group(1))
    match = _HOURS.search(text)
    if match:
        return int(match.group(1)) // 24   # di bawah 24 jam = hari yang sama
    return None


def estimate_date(today: date, variants: Iterable[str]) -> date:
    """Hari ini + lama pengerjaan layanan yang PALING LAMA."""
    days = [d for d in (parse_duration_days(v) for v in variants) if d is not None]
    return today + timedelta(days=max(days) if days else DEFAULT_ESTIMATION_DAYS)