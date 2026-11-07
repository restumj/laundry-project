from datetime import date
from decimal import Decimal

import math

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.routers.home import require_staff
from app.models import Customer, Order, OrderDetail, Payment, PaymentMethod, Promo, Service, Staff
from app.services import orders as order_service
from app.services.payments import add_payment
from app.services.estimation import DEFAULT_ESTIMATION_DAYS, parse_duration_days
from app.services.parsing import parse_date, parse_decimal, parse_int, parse_lines
from app.services.pricing import OrderCalculationError, max_points_usable
from app.templating import templates

router = APIRouter(prefix="/orders", tags=["orders"], dependencies=[Depends(require_staff)])

# ---------------------------------------------------------------- daftar order
PAGE_SIZE = 10


@router.get("")
def list_orders(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(Order)) or 0
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(page, pages)          # halaman di luar batas -> halaman terakhir
    stmt = (
        select(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.status),
            selectinload(Order.payments),
        )
        .order_by(Order.order_date.desc(), Order.order_id.desc())
        .limit(PAGE_SIZE)
        .offset((page - 1) * PAGE_SIZE)
    )
    orders = db.scalars(stmt).all()
    return templates.TemplateResponse(
        request,
        "orders_list.html",
        {"orders": orders, "page": page, "pages": pages, "total": total, "base_url": "/orders"},
    )


# ---------------------------------------------------------------- form order baru
# PENTING: route "/new" harus ditulis SEBELUM "/{order_id}".
# Kalau terbalik, FastAPI mengira "new" adalah sebuah order_id.
def _form_page(request, db, form, staff, error=None, status_code=200):
    services = db.scalars(
        select(Service).order_by(Service.service_name, Service.variant)
    ).all()
    context = {
        "form": form,
        "error": error,
        "today": date.today().isoformat(),
        "default_days": DEFAULT_ESTIMATION_DAYS,
        "staff": staff,
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
def new_order_form(
    request: Request,
    cust_id: str = "",
    db: Session = Depends(get_db),
    staff: Staff = Depends(require_staff),
):
    customer = db.get(Customer, cust_id) if cust_id else None   # mis. setelah daftar pelanggan baru
    form = {
        "cust_id": customer.cust_id if customer else "",
        "cust_label": f"{customer.cust_id} - {customer.cust_name}" if customer else "",
        "order_estimation_date": date.today().isoformat(),
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
    return _form_page(request, db, form, staff)


@router.post("/preview")
def preview_order(
    db: Session = Depends(get_db),
    cust_id: str = Form(""),
    promo_code: str = Form(""),
    pickup_fee: str = Form("0"),
    delivery_fee: str = Form("0"),
    points_used: str = Form("0"),
    service_id: list[str] = Form([]),
    qty: list[str] = Form([]),
    notes: list[str] = Form([]),
):
    """Hitung total untuk ditampilkan di form (tidak menyimpan apa pun).
    Memakai quote_order yang sama dengan penyimpanan, jadi angkanya pasti konsisten."""
    try:
        lines = parse_lines(service_id, qty, notes)
        if not lines:
            return {"ok": True, "empty": True}
        q = order_service.quote_order(
            db,
            cust_id=cust_id or None,
            lines=lines,
            promo_code=promo_code or None,
            pickup_fee=parse_decimal(pickup_fee, "Ongkos jemput", default=Decimal("0")),
            delivery_fee=parse_decimal(delivery_fee, "Ongkos antar", default=Decimal("0")),
            points_used=parse_int(points_used, "Poin yang dipakai"),
            today=date.today(),
        )
    except OrderCalculationError as exc:
        return {"ok": False, "error": str(exc)}
    pr = q.price
    return {
        "ok": True,
        "empty": False,
        "subtotal": str(pr.subtotal),
        "promo_discount": str(pr.promo_discount),
        "pickup_fee": str(pr.pickup_fee),
        "delivery_fee": str(pr.delivery_fee),
        "points_used": pr.points_used,
        "points_discount": str(pr.total_before_points - pr.total_price),
        "total_price": str(pr.total_price),
        "points_earned": pr.points_earned,
        "points_balance": q.balance,
        "max_points": max_points_usable(pr.total_before_points, q.balance),
    }


@router.post("")
def create_order(
    request: Request,
    db: Session = Depends(get_db),
    cust_id: str = Form(...),
    staff: Staff = Depends(require_staff),
    order_estimation_date: str = Form(""),
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
            staff_id=staff.staff_id,
            order_estimation_date=parse_date(order_estimation_date, "Estimasi selesai"),
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
            "order_estimation_date": order_estimation_date,
            "estimation_manual": bool(order_estimation_date),
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
        return _form_page(request, db, form, staff, error=str(exc), status_code=400)
    except Exception:
        db.rollback()
        raise

    # 303 = "setelah POST, buka halaman ini dengan GET" (mencegah submit ganda saat refresh)
    return RedirectResponse(f"/orders/{order.order_id}", status_code=303)


# ---------------------------------------------------------------- pembayaran (cicilan)
def _load_order_for_payment(db: Session, order_id: str) -> Order:
    stmt = (
        select(Order)
        .where(Order.order_id == order_id)
        .options(
            joinedload(Order.customer),
            joinedload(Order.status),
            selectinload(Order.details),
            selectinload(Order.payments).joinedload(Payment.method),
        )
    )
    order = db.scalars(stmt).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    return order


def _payment_page(request, db, order, form, error=None, status_code=200):
    methods = db.scalars(
        select(PaymentMethod).order_by(PaymentMethod.payment_method)
    ).all()
    return templates.TemplateResponse(
        request,
        "payments_new.html",
        {"order": order, "methods": methods, "form": form, "error": error},
        status_code=status_code,
    )


@router.get("/{order_id}/pay")
def payment_form(order_id: str, request: Request, db: Session = Depends(get_db)):
    order = _load_order_for_payment(db, order_id)
    return _payment_page(request, db, order, {"method": "", "amount": "", "settle": False})


@router.post("/{order_id}/fees")
def update_fees_route(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    pickup_fee: str = Form("0"),
    delivery_fee: str = Form("0"),
):
    order = _load_order_for_payment(db, order_id)
    try:
        order_service.update_order_fees(
            db,
            order,
            parse_decimal(pickup_fee, "Ongkos jemput", default=Decimal("0")),
            parse_decimal(delivery_fee, "Ongkos antar", default=Decimal("0")),
        )
        db.commit()
    except OrderCalculationError as exc:
        db.rollback()
        order = _load_order_for_payment(db, order_id)
        return _payment_page(
            request, db, order,
            {"method": "", "amount": "", "pickup_fee": pickup_fee, "delivery_fee": delivery_fee},
            error=str(exc), status_code=400,
        )
    except Exception:
        db.rollback()
        raise
    return RedirectResponse(f"/orders/{order_id}/pay", status_code=303)


@router.post("/{order_id}/finish")
def finish_order_route(order_id: str, request: Request, db: Session = Depends(get_db)):
    order = _load_order_for_payment(db, order_id)
    try:
        order_service.finish_order(db, order)
        db.commit()
    except OrderCalculationError as exc:
        db.rollback()
        order = _load_order_for_payment(db, order_id)
        return _payment_page(
            request, db, order, {"method": "", "amount": ""}, error=str(exc), status_code=400
        )
    except Exception:
        db.rollback()
        raise
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/{order_id}/pay")
def add_order_payment(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    method: str = Form(""),
    amount: str = Form(""),
    settle: str = Form(""),
):
    order = _load_order_for_payment(db, order_id)
    try:
        if not method:
            raise OrderCalculationError("Pilih metode pembayaran.")
        add_payment(
            db,
            order,
            parse_int(method, "Metode pembayaran"),
            parse_decimal(amount, "Jumlah pembayaran"),
            date.today(),
            settle=bool(settle),
        )
        db.commit()
    except OrderCalculationError as exc:
        db.rollback()
        order = _load_order_for_payment(db, order_id)   # muat ulang: keadaan bersih setelah rollback
        return _payment_page(
            request, db, order, {"method": method, "amount": amount, "settle": bool(settle)},
            error=str(exc), status_code=400,
        )
    except Exception:
        db.rollback()
        raise
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


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