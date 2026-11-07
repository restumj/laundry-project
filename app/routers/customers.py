from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer
from app.routers.home import require_staff
from app.services.customers import register_customer
from app.services.points import points_on
from app.services.pricing import OrderCalculationError
from app.templating import templates

router = APIRouter(prefix="/customers", tags=["customers"], dependencies=[Depends(require_staff)])


def _find(db: Session, q: str, limit: int):
    # contains(..., autoescape=True) -> LIKE '%q%'; karakter % dan _ dianggap huruf biasa
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
        .limit(limit)
    )
    return db.scalars(stmt).all()


@router.get("/search")
def search_customers(q: str = "", db: Session = Depends(get_db)):
    """Cari pelanggan (dipanggil JavaScript di form order)."""
    q = q.strip()
    if not q:
        return []
    today = date.today()
    return [
        {
            "cust_id": c.cust_id,
            "cust_name": c.cust_name,
            "cust_phone": c.cust_phone,
            "points": points_on(c.cust_point, c.cust_point_expired_date, today),
        }
        for c in _find(db, q, 30)
    ]


def _page(request, db, q, form, error=None, status_code=200):
    today = date.today()
    found = _find(db, q, 30) if q else []
    rows = [
        {"c": c, "points": points_on(c.cust_point, c.cust_point_expired_date, today)}
        for c in found
    ]
    return templates.TemplateResponse(
        request,
        "customers.html",
        {"q": q, "rows": rows, "searched": bool(q), "form": form, "error": error},
        status_code=status_code,
    )


@router.get("")
def customers_page(request: Request, q: str = "", db: Session = Depends(get_db)):
    """Cek dulu apakah pelanggan sudah ada; kalau belum, daftarkan lewat form di bawahnya."""
    q = q.strip()
    return _page(request, db, q, {"name": q if not q.replace("+", "").isdigit() else "",
                                  "phone": q if q.replace("+", "").isdigit() else ""})


@router.post("")
def create_customer(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(""),
    phone: str = Form(""),
):
    try:
        customer = register_customer(db, name, phone)
        db.commit()
    except OrderCalculationError as exc:
        db.rollback()
        return _page(request, db, "", {"name": name, "phone": phone}, error=str(exc), status_code=400)
    except Exception:
        db.rollback()
        raise
    # langsung lanjut buat order untuk pelanggan ini
    return RedirectResponse(f"/orders/new?cust_id={customer.cust_id}", status_code=303)