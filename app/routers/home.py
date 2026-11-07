from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Staff
from app.templating import templates

router = APIRouter(tags=["home"])

STAFF_COOKIE = "staff_id"


def current_staff_id(request: Request, db: Session):
    """ID staff yang sedang bertugas (dari cookie), atau None jika belum dipilih/tidak valid."""
    staff_id = request.cookies.get(STAFF_COOKIE)
    if staff_id and db.get(Staff, staff_id) is not None:
        return staff_id
    return None


def require_staff(request: Request, db: Session = Depends(get_db)) -> Staff:
    """Dependency: semua halaman kerja wajib punya staff bertugas.
    Jika belum memilih, pengguna dialihkan (303) ke Beranda."""
    staff_id = request.cookies.get(STAFF_COOKIE)
    staff = db.get(Staff, staff_id) if staff_id else None
    if staff is None:
        raise HTTPException(status_code=303, headers={"Location": "/"})
    return staff


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    staff_list = db.scalars(select(Staff).order_by(Staff.staff_name)).all()
    return templates.TemplateResponse(
        request,
        "home.html",
        {"staff_list": staff_list, "current": current_staff_id(request, db)},
    )


@router.post("/staff")
def choose_staff(staff_id: str = Form(...), db: Session = Depends(get_db)):
    if db.get(Staff, staff_id) is None:
        return RedirectResponse("/", status_code=303)
    response = RedirectResponse("/orders", status_code=303)
    # cookie berlaku 12 jam (satu shift); httponly = tidak bisa dibaca JavaScript
    response.set_cookie(STAFF_COOKIE, staff_id, max_age=12 * 3600, httponly=True, samesite="lax")
    return response