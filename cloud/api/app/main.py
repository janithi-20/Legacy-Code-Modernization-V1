from fastapi import FastAPI
from app.routers import health, trades
 
app = FastAPI(title="transitionx cloud trade-reporting API", version="0.1.0")
app.include_router(health.router)
app.include_router(trades.router, prefix="/api/v1")
