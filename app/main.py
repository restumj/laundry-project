from fastapi import FastAPI

from app.routers import customers, home, orders

app = FastAPI(title="Laundry App")
app.include_router(home.router)
app.include_router(orders.router)
app.include_router(customers.router)