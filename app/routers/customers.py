from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer
from app.services.points import points_on

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/search")
def search_customers(q: str = "", db: Session = Depends(get_db)):
    """Cari pelanggan berdasarkan nama, nomor telepon, atau ID (dipanggil JavaScript)."""
    q = q.strip()
    if not q:
        return []
    # contains(..., autoescape=True) -> LIKE '%q%', dan karakter % atau _ yang
    # diketik user dianggap huruf biasa, bukan wildcard.
    stmt = (
        select(Customer)
        .where(
            or_(
                Customer.cust_name.contains(q, autoescape=True),
                Customer.cust_phone.contains(q, autoescape=True),
                Customer.cust_id.contains(q, autoescape=True),
            )
        )
        .order_by(Customer.cust_name)
        .limit(30)
    )
    today = date.today()
    return [
        {
            "cust_id": c.cust_id,
            "cust_name": c.cust_name,
            "cust_phone": c.cust_phone,
            "points": points_on(c.cust_point, c.cust_point_expired_date, today),
        }
        for c in db.scalars(stmt)
    ]