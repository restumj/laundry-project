"""Pendaftaran pelanggan baru."""
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer
from app.services.ids import next_number
from app.services.parsing import parse_name, parse_phone
from app.services.points import first_expiry
from app.services.pricing import OrderCalculationError


def register_customer(
    db: Session, name: str, phone: str, today: Optional[date] = None
) -> Customer:
    """Daftarkan pelanggan. Nomor yang sudah terdaftar ditolak (cek dulu sebelum buat)."""
    today = today or date.today()
    name = parse_name(name)
    phone = parse_phone(phone)

    existing = db.scalars(select(Customer).where(Customer.cust_phone == phone)).first()
    if existing is not None:
        raise OrderCalculationError(
            f"Nomor {phone} sudah terdaftar atas nama {existing.cust_name} ({existing.cust_id})."
        )

    customer = Customer(
        cust_id=f"CU-{next_number(db, Customer.cust_id, 'CU')}",
        cust_name=name,
        cust_phone=phone,
        cust_point=0,
        # periode poin pertama: tanggal daftar + 3 bulan (lalu berulang, lihat points.py)
        cust_point_expired_date=first_expiry(today),
    )
    db.add(customer)
    db.flush()
    return customer