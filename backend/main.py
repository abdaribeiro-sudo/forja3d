import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from database import engine, Base
from routers import generate, orders, payment, shipping, admin, price

load_dotenv()

STORAGE_PATH = os.getenv("STORAGE_PATH", "./uploads")
os.makedirs(STORAGE_PATH, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        from models.tables import Order, Generation  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="FORJA3D API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restringir em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers primeiro
app.include_router(generate.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(payment.router, prefix="/api")
app.include_router(shipping.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(price.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok"}, "error": None}


# Static files por último (mount captura tudo que não casa acima)
app.mount("/uploads", StaticFiles(directory=STORAGE_PATH), name="uploads")
