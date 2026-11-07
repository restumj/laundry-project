from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session


def next_number(db: Session, column, prefix: str) -> int:
    """Nomor berikutnya untuk ID bertipe 'PREFIX-angka', misalnya O-7 -> 8."""
    start = len(prefix) + 2   # "O-12": angka mulai karakter ke-3 (SQL mulai dari 1)
    last = db.scalar(select(func.max(cast(func.substr(column, start), Integer))))
    return (last or 0) + 1