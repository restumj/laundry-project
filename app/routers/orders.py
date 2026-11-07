from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models import Customer, Order, OrderDetail, Payment, PaymentMethod, Promo, Service, Staff
from app.services import orders as order_service
from app.services.estimation import DEFAULT_ESTIMATION_DAYS, parse_duration_days
from app.services.parsing import parse_date, parse_decimal, parse_int, parse_lines
from app.services.pricing import OrderCalculationError
from app.templating import templates

router = APIRouter(prefix="/orders", tags=["orders"])

# ---------------------------------------------------------------- daftar order
@router.get("")
def list_orders(request: Request, db: Session = Depends(get_db)):
    stmt = (
        select(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.status),
            selectinload(Order.payments),
        )
        .order_by(Order.order_date.desc(), Order.order_id.desc())
    )
    orders = db.scalars(stmt).all()
    return templates.TemplateResponse(request, "orders_list.html", {"orders": orders})


# ---------------------------------------------------------------- form order baru
# PENTING: route "/new" harus ditulis SEBELUM "/{order_id}".
# Kalau terbalik, FastAPI mengira "new" adalah sebuah order_id.
def _form_page(request, db, form, error=None, status_code=200):
    services = db.scalars(
        select(Service).order_by(Service.service_name, Service.variant)
    ).all()
    context = {
        "form": form,
        "error": error,
        "today": date.today().isoformat(),
        "default_days": DEFAULT_ESTIMATION_DAYS,
        "staff_list": db.scalars(select(Staff).order_by(Staff.staff_name)).all(),
        # days = lama pengerjaan hasil baca teks variant (None jika tidak terbaca)
        "services": [{"sv": s, "days": parse_duration_days(s.variant)} for s in services],
        "promos": db.scalars(
            select(Promo).where(Promo.is_active.is_(True)).order_by(Promo.promo_code)
        ).all(),
        "payment_methods": db.scalars(
            select(PaymentMethod).order_by(PaymentMethod.payment_method)
        ).all(),
    }
    return templates.TemplateResponse(
        request, "orders_new.html", context, status_code=status_code
    )


@router.get("/new")
def new_order_form(request: Request, db: Session = Depends(get_db)):
    form = {
        "cust_id": "",
        "cust_label": "",
        "staff_id": "",
        "order_estimation": "",
        "estimation_manual": False,
        "promo_code": "",
        "pickup_fee": "0",
        "delivery_fee": "0",
        "points_used": "0",
        "consument_notes": "",
        "pay_method": "",
        "pay_amount": "",
        "pay_full": False,
        "rows": [{"service_id": "", "qty": "", "notes": ""}],
    }
    return _form_page(request, db, form)


@router.post("")
def create_order(
    request: Request,
    db: Session = Depends(get_db),
    cust_id: str = Form(...),
    staff_id: str = Form(...),
    order_estimation: str = Form(""),
    promo_code: str = Form(""),
    pickup_fee: str = Form("0"),
    delivery_fee: str = Form("0"),
    points_used: str = Form("0"),
    consument_notes: str = Form(""),
    pay_method: str = Form(""),
    pay_amount: str = Form(""),
    pay_full: str = Form(""),
    service_id: list[str] = Form([]),
    qty: list[str] = Form([]),
    notes: list[str] = Form([]),
):
    try:
        initial_payment = None
        if pay_full or pay_amount.strip():
            if not pay_method:
                raise OrderCalculationError("Pilih metode untuk pembayaran awal.")
            initial_payment = (
                parse_int(pay_method, "Metode pembayaran"),
                None if pay_full else parse_decimal(pay_amount, "Jumlah pembayaran awal"),
            )
        order = order_service.create_order(
            db,
            cust_id=cust_id,
            staff_id=staff_id,
            order_estimation=parse_date(order_estimation, "Estimasi selesai"),
            promo_code=promo_code or None,
            pickup_fee=parse_decimal(pickup_fee, "Ongkos jemput", default=Decimal("0")),
            delivery_fee=parse_decimal(delivery_fee, "Ongkos antar", default=Decimal("0")),
            points_used=parse_int(points_used, "Poin yang dipakai"),
            consument_notes=consument_notes.strip() or None,
            lines=parse_lines(service_id, qty, notes),
            initial_payment=initial_payment,
        )
        db.commit()   # order, detail, dan saldo poin tersimpan sekaligus
    except OrderCalculationError as exc:
        db.rollback()   # batalkan semuanya
        customer = db.get(Customer, cust_id) if cust_id else None
        form = {
            "cust_id": cust_id if customer else "",
            "cust_label": f"{customer.cust_id} - {customer.cust_name}" if customer else "",
            "staff_id": staff_id,
            "order_estimation": order_estimation,
            "estimation_manual": bool(order_estimation),
            "promo_code": promo_code,
            "pickup_fee": pickup_fee,
            "delivery_fee": delivery_fee,
            "points_used": points_used,
            "consument_notes": consument_notes,
            "pay_method": pay_method,
            "pay_amount": pay_amount,
            "pay_full": bool(pay_full),
            "rows": [
                {
                    "service_id": service_id[i] if i < len(service_id) else "",
                    "qty": qty[i] if i < len(qty) else "",
                    "notes": notes[i] if i < len(notes) else "",
                }
                for i in range(max(1, len(service_id)))
            ],
        }
        return _form_page(request, db, form, error=str(exc), status_code=400)
    except Exception:
        db.rollback()
        raise

    # 303 = "setelah POST, buka halaman ini dengan GET" (mencegah submit ganda saat refresh)
    return RedirectResponse(f"/orders/{order.order_id}", status_code=303)


# ---------------------------------------------------------------- detail order
@router.get("/{order_id}")
def order_detail(order_id: str, request: Request, db: Session = Depends(get_db)):
    stmt = (
        select(Order)
        .where(Order.order_id == order_id)
        .options(
            joinedload(Order.customer),
            joinedload(Order.staff),
            joinedload(Order.promo),
            joinedload(Order.status),
            selectinload(Order.details).joinedload(OrderDetail.service),
            selectinload(Order.payments).joinedload(Payment.method),
        )
    )
    order = db.scalars(stmt).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    return templates.TemplateResponse(request, "order_detail.html", {"order": order})