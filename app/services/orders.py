"""Membuat order baru: validasi, hitung harga, lalu siapkan objek untuk disimpan.

Fungsi di sini TIDAK memanggil commit. Yang memutuskan commit atau rollback
adalah route, supaya semua perubahan menjadi satu transaksi.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Order, OrderDetail, Promo, Service, Staff
from app.services.estimation import estimate_date
from app.services.ids import next_number
from app.services.payments import add_payment
from app.services.pricing import (
    LineInput,
    OrderCalculationError,
    PromoRule,
    calculate_order,
    line_subtotal,
)

POINT_VALIDITY_DAYS = 180   # poin berlaku 6 bulan sejak terakhir mendapat poin (bisa diubah)
STATUS_PROCESS = 1          # kode di tabel order_status


def create_order(
    db: Session,
    *,
    cust_id: str,
    staff_id: str,
    order_estimation: Optional[date],
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

    customer = db.get(Customer, cust_id)
    if customer is None:
        raise OrderCalculationError("Pilih pelanggan dari hasil pencarian.")
    if db.get(Staff, staff_id) is None:
        raise OrderCalculationError("Staff tidak ditemukan.")
    if not lines:
        raise OrderCalculationError("Order harus memuat minimal satu layanan.")

    # --- layanan: harga diambil dari tabel service saat ini (jadi snapshot unit_price)
    wanted = {service_id for service_id, _, _ in lines}
    services = {
        s.service_id: s
        for s in db.scalars(select(Service).where(Service.service_id.in_(wanted)))
    }
    for service_id in wanted:
        if service_id not in services:
            raise OrderCalculationError(f"Layanan {service_id} tidak ditemukan.")

    # --- estimasi: kalau kosong, hitung dari layanan yang PALING LAMA
    if order_estimation is None:
        order_estimation = estimate_date(today, [services[i].variant for i in wanted])
    if order_estimation < today:
        raise OrderCalculationError("Estimasi selesai tidak boleh sebelum tanggal order.")

    # --- promo (boleh kosong)
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

    # --- poin: yang sudah lewat tanggal kedaluwarsa dianggap hangus
    balance = customer.points_on(today)
    expired = balance == 0 and customer.cust_point > 0   # ada saldo, tapi sudah hangus

    line_inputs = [
        LineInput(qty=qty, unit_price=services[service_id].price)
        for service_id, qty, _ in lines
    ]
    price = calculate_order(
        line_inputs, pickup_fee, delivery_fee, rule, points_used, balance
    )

    # --- susun objek ORM (belum disimpan ke database)
    order_number = next_number(db, Order.order_id, "O")
    detail_number = next_number(db, OrderDetail.detail_id, "D")

    order = Order(
        order_id=f"O-{order_number}",
        order_date=today,
        order_estimation=order_estimation,
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
    customer.cust_point = balance - price.points_used + price.points_earned
    if price.points_earned > 0:
        customer.cust_expired_point = today + timedelta(days=POINT_VALIDITY_DAYS)
    elif expired:
        customer.cust_expired_point = None

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