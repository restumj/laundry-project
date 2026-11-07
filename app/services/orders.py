"""Membuat order baru: validasi, hitung harga, lalu siapkan objek untuk disimpan.

Fungsi di sini TIDAK memanggil commit. Yang memutuskan commit atau rollback
adalah route, supaya semua perubahan menjadi satu transaksi.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Order, OrderDetail, Promo, Service, Staff
from app.services.estimation import estimate_date
from app.services.ids import next_number
from app.services.payments import add_payment
from app.services.points import points_on, roll_expiry
from app.services.pricing import (
    LineInput,
    OrderCalculationError,
    PromoRule,
    calculate_order,
    PriceBreakdown,
    line_subtotal,
    recalc_with_fees,
)

STATUS_PROCESS = 1          # kode di tabel order_status
STATUS_FINISHED = 2


@dataclass
class Quote:
    """Hasil hitung harga (belum disimpan)."""
    customer: Optional[Customer]
    services: dict
    promo: Optional[Promo]
    line_inputs: list
    price: PriceBreakdown
    balance: int          # saldo poin yang masih berlaku hari ini


def quote_order(
    db: Session,
    *,
    cust_id: Optional[str],
    lines: list[tuple[str, Decimal, Optional[str]]],
    promo_code: Optional[str],
    pickup_fee: Decimal,
    delivery_fee: Decimal,
    points_used: int,
    today: date,
) -> Quote:
    """Satu-satunya tempat menghitung harga. Dipakai oleh pratinjau DAN penyimpanan,
    jadi angka yang dilihat staff pasti sama dengan yang tersimpan."""
    customer = db.get(Customer, cust_id) if cust_id else None
    if cust_id and customer is None:
        raise OrderCalculationError("Pilih pelanggan dari hasil pencarian.")
    if not lines:
        raise OrderCalculationError("Order harus memuat minimal satu layanan.")

    wanted = {service_id for service_id, _, _ in lines}
    services = {
        s.service_id: s
        for s in db.scalars(select(Service).where(Service.service_id.in_(wanted)))
    }
    for service_id in wanted:
        if service_id not in services:
            raise OrderCalculationError(f"Layanan {service_id} tidak ditemukan.")

    promo = None
    rule = None
    if promo_code:
        promo = db.get(Promo, promo_code)
        if promo is None:
            raise OrderCalculationError("Promo tidak ditemukan.")
        rule = PromoRule(
            promo_type=promo.type.promo_type_info,
            promo_value=promo.promo_value,
            min_transaction=promo.min_transaction,
            max_discount=promo.max_discount,
            is_active=promo.is_active,
        )

    balance = (
        points_on(customer.cust_point, customer.cust_point_expired_date, today)
        if customer
        else 0
    )
    line_inputs = [
        LineInput(qty=qty, unit_price=services[service_id].price)
        for service_id, qty, _ in lines
    ]
    price = calculate_order(
        line_inputs, pickup_fee, delivery_fee, rule, points_used, balance
    )
    return Quote(customer, services, promo, line_inputs, price, balance)


def create_order(
    db: Session,
    *,
    cust_id: str,
    staff_id: str,
    order_estimation_date: Optional[date],
    promo_code: Optional[str],
    pickup_fee: Decimal,
    delivery_fee: Decimal,
    points_used: int,
    consument_notes: Optional[str],
    lines: list[tuple[str, Decimal, Optional[str]]],
    initial_payment: Optional[tuple[int, Optional[Decimal]]] = None,
    today: Optional[date] = None,
) -> Order:
    today = today or date.today()

    if not cust_id:
        raise OrderCalculationError("Pilih pelanggan dari hasil pencarian.")
    if db.get(Staff, staff_id) is None:
        raise OrderCalculationError("Staff tidak ditemukan.")

    q = quote_order(
        db, cust_id=cust_id, lines=lines, promo_code=promo_code,
        pickup_fee=pickup_fee, delivery_fee=delivery_fee,
        points_used=points_used, today=today,
    )
    customer, services, promo, line_inputs, price = (
        q.customer, q.services, q.promo, q.line_inputs, q.price
    )

    # --- estimasi: kalau kosong, hitung dari layanan yang PALING LAMA
    if order_estimation_date is None:
        order_estimation_date = estimate_date(
            today, [services[sid].variant for sid, _, _ in lines]
        )
    if order_estimation_date < today:
        raise OrderCalculationError("Estimasi selesai tidak boleh sebelum tanggal order.")

    # --- susun objek ORM (belum disimpan ke database)
    order_number = next_number(db, Order.order_id, "O")
    detail_number = next_number(db, OrderDetail.detail_id, "D")

    order = Order(
        order_id=f"O-{order_number}",
        order_date=today,
        order_estimation_date=order_estimation_date,
        order_status=STATUS_PROCESS,
        cust_id=cust_id,
        staff_id=staff_id,
        promo_code=promo.promo_code if promo else None,
        promo_discount_applied=price.promo_discount,
        consument_notes=consument_notes or None,
        pickup_fee=pickup_fee,
        delivery_fee=delivery_fee,
        points_used=price.points_used,
        points_earned=price.points_earned,
        total_price=price.total_price,
    )
    for i, ((service_id, qty, note), line) in enumerate(zip(lines, line_inputs)):
        order.details.append(
            OrderDetail(
                detail_id=f"D-{detail_number + i}",
                service_id=service_id,
                qty=qty,
                unit_price=line.unit_price,
                notes=note,
                sub_price=line_subtotal(line),
            )
        )

    # --- saldo poin pelanggan ikut diperbarui dalam transaksi yang sama
    # Poin yang hangus sudah tidak ikut (q.balance = 0 jika periode lama lewat).
    # Tanggal kedaluwarsa TIDAK diperpanjang karena order; ia hanya maju per periode
    # (3 bulan sejak daftar) jika periode lama sudah lewat.
    customer.cust_point = q.balance - price.points_used + price.points_earned
    if (
        customer.cust_point_expired_date is not None
        and customer.cust_point_expired_date < today
    ):
        customer.cust_point_expired_date = roll_expiry(customer.cust_point_expired_date, today)

    db.add(order)
    db.flush()   # kirim INSERT sekarang supaya error database muncul di sini

    # --- pembayaran awal (opsional) memakai fungsi yang sama dengan cicilan berikutnya
    if initial_payment is not None:
        method, amount = initial_payment
        if amount is None:                      # "bayar lunas"
            amount = order.total_price
        if amount > 0:                          # total 0 (lunas oleh poin) -> tidak ada pembayaran
            add_payment(db, order, method, amount, today)
    return order


def finish_order(db: Session, order: Order) -> None:
    """Ubah status PROCESS -> FINISHED, hanya jika tagihan sudah lunas (aturan R12).
    Trigger di MySQL menjaga aturan yang sama sebagai pengaman terakhir."""
    if order.order_status == STATUS_FINISHED:
        raise OrderCalculationError("Order ini sudah selesai.")
    if order.balance_due > 0:
        raise OrderCalculationError(
            "Order belum lunas (sisa Rp"
            + f"{int(order.balance_due):,}".replace(",", ".")
            + "). Catat pembayaran dulu."
        )
    order.order_status = STATUS_FINISHED
    db.flush()


def update_order_fees(
    db: Session, order: Order, pickup_fee: Decimal, delivery_fee: Decimal
) -> None:
    """Ubah ongkos jemput/antar order yang masih PROCESS.
    Total, poin yang didapat, dan saldo poin pelanggan ikut disesuaikan (satu transaksi)."""
    if order.order_status != STATUS_PROCESS:
        raise OrderCalculationError("Order sudah selesai, ongkos tidak bisa diubah.")
    subtotal = sum((d.sub_price for d in order.details), Decimal("0"))
    new = recalc_with_fees(
        subtotal, order.promo_discount_applied, pickup_fee, delivery_fee, order.points_used
    )
    if new.total_price < order.total_paid:
        raise OrderCalculationError(
            "Total baru lebih kecil dari yang sudah dibayar. Ongkos tidak bisa diturunkan sejauh itu."
        )
    delta = new.points_earned - order.points_earned
    customer = order.customer
    customer.cust_point = max(0, customer.cust_point + delta)

    order.pickup_fee = pickup_fee
    order.delivery_fee = delivery_fee
    order.total_price = new.total_price
    order.points_earned = new.points_earned
    db.flush()