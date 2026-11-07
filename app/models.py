from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, FetchedValue, func
from sqlalchemy.dialects.mysql import INTEGER, TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------- Tabel referensi ----------
class PromoType(Base):
    __tablename__ = "promo_type"

    promo_type: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), primary_key=True, autoincrement=False
    )
    promo_type_info: Mapped[str] = mapped_column(String(100), unique=True)

    promos: Mapped[list["Promo"]] = relationship(back_populates="type")


class OrderStatus(Base):
    __tablename__ = "order_status"

    order_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), primary_key=True, autoincrement=False
    )
    order_status_info: Mapped[str] = mapped_column(String(100), unique=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="status")


class PaymentMethod(Base):
    __tablename__ = "payment_method"

    payment_method: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), primary_key=True, autoincrement=False
    )
    payment_method_info: Mapped[str] = mapped_column(String(100), unique=True)

    payments: Mapped[list["Payment"]] = relationship(back_populates="method")


# ---------- Tabel inti ----------
class Customer(Base):
    __tablename__ = "customer"

    cust_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    cust_name: Mapped[str] = mapped_column(String(100))
    cust_phone: Mapped[str] = mapped_column(String(20))
    cust_point: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0)
    cust_point_expired_date: Mapped[Optional[date]] = mapped_column(Date)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

    def points_on(self, day: date) -> int:
        """Saldo poin yang masih berlaku pada tanggal tertentu."""
        if self.cust_point_expired_date is not None and self.cust_point_expired_date < day:
            return 0
        return self.cust_point


class Staff(Base):
    __tablename__ = "staff"

    staff_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    staff_name: Mapped[str] = mapped_column(String(100))
    staff_phone: Mapped[str] = mapped_column(String(20))

    orders: Mapped[list["Order"]] = relationship(back_populates="staff")


class Service(Base):
    __tablename__ = "service"

    service_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    service_name: Mapped[str] = mapped_column(String(100))
    variant: Mapped[str] = mapped_column(String(50))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    details: Mapped[list["OrderDetail"]] = relationship(back_populates="service")


class Promo(Base):
    __tablename__ = "promo"

    promo_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    promo_name: Mapped[str] = mapped_column(String(100))
    promo_type: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), ForeignKey("promo_type.promo_type")
    )
    promo_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    min_transaction: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    max_discount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    type: Mapped["PromoType"] = relationship(back_populates="promos")
    orders: Mapped[list["Order"]] = relationship(back_populates="promo")


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    order_date: Mapped[date] = mapped_column(Date)
    order_estimation_date: Mapped[date] = mapped_column(Date)
    order_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), ForeignKey("order_status.order_status"), default=1
    )
    cust_id: Mapped[str] = mapped_column(ForeignKey("customer.cust_id"))
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.staff_id"))
    promo_code: Mapped[Optional[str]] = mapped_column(ForeignKey("promo.promo_code"))
    promo_discount_applied: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    consument_notes: Mapped[Optional[str]] = mapped_column(String(255))
    pickup_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    points_used: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0)
    points_earned: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    status: Mapped["OrderStatus"] = relationship(back_populates="orders")
    customer: Mapped["Customer"] = relationship(back_populates="orders")
    staff: Mapped["Staff"] = relationship(back_populates="orders")
    promo: Mapped[Optional["Promo"]] = relationship(back_populates="orders")
    details: Mapped[list["OrderDetail"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), server_onupdate=FetchedValue())
    @property
    def total_paid(self) -> Decimal:
        return sum((p.amount_received for p in self.payments), Decimal("0"))
    @property
    def balance_due(self) -> Decimal:
        return self.total_price - self.total_paid


class OrderDetail(Base):
    __tablename__ = "order_detail"

    detail_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"))
    service_id: Mapped[str] = mapped_column(ForeignKey("service.service_id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    notes: Mapped[Optional[str]] = mapped_column(String(255))
    sub_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped["Order"] = relationship(back_populates="details")
    service: Mapped["Service"] = relationship(back_populates="details")


class Payment(Base):
    __tablename__ = "payment"

    payment_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"))
    payment_date: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), ForeignKey("payment_method.payment_method")
    )
    amount_received: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped["Order"] = relationship(back_populates="payments")
    method: Mapped["PaymentMethod"] = relationship(back_populates="payments")