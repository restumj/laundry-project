from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models import Order, OrderDetail, Payment

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="Laundry App")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def rupiah(value) -> str:
    return "Rp" + f"{int(value):,}".replace(",", ".")


templates.env.filters["rupiah"] = rupiah


@app.get("/")
def home():
    return RedirectResponse("/orders")


@app.get("/orders")
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


@app.get("/orders/{order_id}")
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