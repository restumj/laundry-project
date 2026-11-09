from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session


def next_number(db: Session, column, prefix: str, where=None) -> int:
    """Nomor berikutnya untuk ID bertipe 'PREFIX-angka', misalnya O-7 -> 8.

    `where` (opsional) membatasi hitungan, dipakai untuk ID yang hanya unik di dalam
    satu order (PK gabungan), mis. pembayaran: PA-1, PA-2 dihitung per order.
    """
    start = len(prefix) + 2   # "O-12": angka mulai karakter ke-3 (SQL mulai dari 1)
    stmt = select(func.max(cast(func.substr(column, start), Integer)))
    if where is not None:
        stmt = stmt.where(where)
    last = db.scalar(stmt)
    return (last or 0) + 1