from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.routers import customers, orders

app = FastAPI(title="Laundry App")
app.include_router(orders.router)
app.include_router(customers.router)


@app.get("/")
def home():
    return RedirectResponse("/orders")