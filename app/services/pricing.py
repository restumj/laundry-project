"""Perhitungan harga order: subtotal, promo, poin, total.

Semua fungsi di sini "murni": hanya menerima angka dan mengembalikan angka.
Tidak ada database dan tidak ada web, jadi mudah diuji otomatis.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

POINT_VALUE = Decimal("1000")        # 1 poin = Rp1.000 potongan
POINT_EARN_UNIT = Decimal("10000")   # setiap Rp10.000 total = 1 poin
CENT = Decimal("0.01")               # kolom uang di database: DECIMAL(12,2)


class OrderCalculationError(ValueError):
    """Input order tidak valid (pesannya boleh ditampilkan ke staff)."""


@dataclass(frozen=True)
class LineInput:
    qty: Decimal          # berat (kg), harus > 0
    unit_price: Decimal   # harga per kg saat transaksi, harus >= 0


@dataclass(frozen=True)
class PromoRule:
    promo_type: str                  # "NOMINAL" atau "PERCENT"
    promo_value: Decimal
    min_transaction: Decimal
    max_discount: Optional[Decimal]  # None = tanpa batas
    is_active: bool


@dataclass(frozen=True)
class PriceBreakdown:
    subtotal: Decimal
    promo_discount: Decimal
    pickup_fee: Decimal
    delivery_fee: Decimal
    total_before_points: Decimal
    points_used: int
    total_price: Decimal
    points_earned: int


def line_subtotal(line: LineInput) -> Decimal:
    """sub_price = qty x unit_price (tepat, tanpa pembulatan)."""
    if not line.qty.is_finite() or line.qty <= 0:
        raise OrderCalculationError("Qty layanan harus lebih dari 0.")
    if line.qty.as_tuple().exponent < -2:
        # kolom qty di database DECIMAL(6,2): maksimal 2 angka di belakang koma
        raise OrderCalculationError("Qty maksimal 2 angka di belakang koma.")
    if line.unit_price < 0:
        raise OrderCalculationError("Harga layanan tidak boleh negatif.")
    return line.qty * line.unit_price


def calc_promo_discount(subtotal: Decimal, promo: Optional[PromoRule]) -> Decimal:
    """Potongan promo. Dihitung dari subtotal layanan saja (tanpa ongkos)."""
    if promo is None:
        return Decimal("0")
    if not promo.is_active:
        raise OrderCalculationError("Promo tidak aktif.")
    if subtotal < promo.min_transaction:
        raise OrderCalculationError("Subtotal layanan belum memenuhi minimal transaksi promo.")

    if promo.promo_type == "PERCENT":
        discount = subtotal * promo.promo_value / Decimal("100")
        if promo.max_discount is not None:
            discount = min(discount, promo.max_discount)
    elif promo.promo_type == "NOMINAL":
        discount = promo.promo_value
    else:
        raise OrderCalculationError(f"Jenis promo tidak dikenal: {promo.promo_type}")

    discount = min(discount, subtotal)  # potongan tidak boleh melebihi subtotal
    return discount.quantize(CENT, rounding=ROUND_HALF_UP)


def max_points_usable(total_before_points: Decimal, point_balance: int) -> int:
    """Poin maksimal yang boleh dipakai: <= saldo dan <= lantai(total / 1.000)."""
    by_total = int(total_before_points // POINT_VALUE)
    return max(0, min(point_balance, by_total))


def calculate_order(
    lines: list[LineInput],
    pickup_fee: Decimal = Decimal("0"),
    delivery_fee: Decimal = Decimal("0"),
    promo: Optional[PromoRule] = None,
    points_used: int = 0,
    point_balance: int = 0,
) -> PriceBreakdown:
    if not lines:
        raise OrderCalculationError("Order harus memuat minimal satu layanan.")
    if pickup_fee < 0 or delivery_fee < 0:
        raise OrderCalculationError("Ongkos tidak boleh negatif.")
    if points_used < 0:
        raise OrderCalculationError("Poin yang dipakai tidak boleh negatif.")

    subtotal = sum((line_subtotal(l) for l in lines), Decimal("0"))
    promo_discount = calc_promo_discount(subtotal, promo)
    total_before_points = subtotal - promo_discount + pickup_fee + delivery_fee

    if points_used > point_balance:
        raise OrderCalculationError("Poin yang dipakai melebihi saldo poin pelanggan.")
    if points_used > int(total_before_points // POINT_VALUE):
        raise OrderCalculationError("Poin yang dipakai melebihi tagihan.")

    total_price = total_before_points - POINT_VALUE * points_used
    points_earned = int(total_price // POINT_EARN_UNIT)

    return PriceBreakdown(
        subtotal=subtotal,
        promo_discount=promo_discount,
        pickup_fee=pickup_fee,
        delivery_fee=delivery_fee,
        total_before_points=total_before_points,
        points_used=points_used,
        total_price=total_price,
        points_earned=points_earned,
    )


def _rp(value: Decimal) -> str:
    return "Rp" + f"{int(value):,}".replace(",", ".")


def validate_payment_amount(amount: Decimal, balance_due: Decimal) -> None:
    """Aturan murni: boleh dites tanpa database."""
    if not amount.is_finite() or amount <= 0:
        raise OrderCalculationError("Jumlah pembayaran harus lebih dari 0.")
    if amount.as_tuple().exponent < -2:
        raise OrderCalculationError("Jumlah pembayaran maksimal 2 angka di belakang koma.")
    if balance_due <= 0:
        raise OrderCalculationError("Order ini sudah lunas.")
    if amount > balance_due:
        raise OrderCalculationError(
            f"Jumlah pembayaran melebihi sisa tagihan ({_rp(balance_due)})."
        )