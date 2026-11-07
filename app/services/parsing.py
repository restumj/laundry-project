"""Mengubah isian form (teks) menjadi angka yang aman dipakai.

Form HTML selalu mengirim teks. Fungsi di sini murni (tanpa database),
jadi mudah diuji.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.services.pricing import OrderCalculationError


def parse_decimal(text: str, label: str, default: Optional[Decimal] = None) -> Decimal:
    text = (text or "").strip().replace(",", ".")   # "3,5" -> "3.5"
    if text == "":
        if default is None:
            raise OrderCalculationError(f"{label} wajib diisi.")
        return default
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise OrderCalculationError(f"{label} harus berupa angka.")
    if not value.is_finite():
        raise OrderCalculationError(f"{label} harus berupa angka.")
    return value


def parse_date(text: str, label: str) -> Optional[date]:
    """Teks 'YYYY-MM-DD' -> date. Teks kosong -> None (dihitung otomatis)."""
    text = (text or "").strip()
    if text == "":
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise OrderCalculationError(f"{label} bukan tanggal yang valid.")


def parse_int(text: str, label: str, default: int = 0) -> int:
    text = (text or "").strip()
    if text == "":
        return default
    if not text.isdigit():
        raise OrderCalculationError(f"{label} harus berupa bilangan bulat tidak negatif.")
    return int(text)


def parse_lines(service_ids: list[str], qtys: list[str], notes: list[str]):
    """Gabungkan kolom-kolom form menjadi baris layanan.

    Baris yang layanan dan qty-nya sama-sama kosong diabaikan.
    Hasil: list of (service_id, qty Decimal, catatan atau None)
    """
    result = []
    for i, service_id in enumerate(service_ids):
        qty_text = qtys[i] if i < len(qtys) else ""
        note = (notes[i] if i < len(notes) else "").strip()
        service_id = (service_id or "").strip()
        if service_id == "" and (qty_text or "").strip() == "":
            continue
        if service_id == "":
            raise OrderCalculationError(f"Baris {i + 1}: pilih layanan.")
        qty = parse_decimal(qty_text, f"Baris {i + 1}: qty")
        result.append((service_id, qty, note or None))
    return result


def parse_name(text: str) -> str:
    name = " ".join((text or "").split())      # rapikan spasi berlebih
    if len(name) < 2:
        raise OrderCalculationError("Nama pelanggan minimal 2 huruf.")
    if len(name) > 100:
        raise OrderCalculationError("Nama pelanggan maksimal 100 karakter.")
    return name


def parse_phone(text: str) -> str:
    """Terima '0812-3456 789' atau '+62 812...' -> '08123456789' / '+62812...'."""
    raw = (text or "").strip()
    plus = raw.startswith("+")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if any(not (ch.isdigit() or ch in " -()+") for ch in raw):
        raise OrderCalculationError("Nomor telepon hanya boleh berisi angka.")
    if not 8 <= len(digits) <= 15:
        raise OrderCalculationError("Nomor telepon harus 8-15 angka.")
    return ("+" if plus else "") + digits