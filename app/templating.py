from pathlib import Path

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def rupiah(value) -> str:
    return "Rp" + f"{int(value):,}".replace(",", ".")


templates.env.filters["rupiah"] = rupiah