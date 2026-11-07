"""Pembayaran order (dipakai untuk pembayaran awal maupun cicilan berikutnya).

amount_received = jumlah yang DIPAKAI membayar tagihan. Kembalian hanya
ditampilkan di layar, tidak disimpan.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Order, Payment, PaymentMethod
from app.services.ids import next_number
from app.services.pricing import OrderCalculationError, validate_payment_amount


def add_payment(
    db: Session, order: Order, method: int, amount: Decimal, pay_date: date
) -> Payment:
    if db.get(PaymentMethod, method) is None:
        raise OrderCalculationError("Metode pembayaran tidak ditemukan.")
    validate_payment_amount(amount, order.balance_due)

    payment = Payment(
        payment_id=f"PA-{next_number(db, Payment.payment_id, 'PA')}",
        order_id=order.order_id,
        payment_date=pay_date,
        payment_method=method,
        amount_received=amount,
    )
    order.payments.append(payment)
    db.flush()
    return payment