from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.app.products import router as products_router

from backend.app.dashboard import dashboard_stats, get_recent_sales, revenue_by_product, revenue_over_time
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(products_router)

@app.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    return dashboard_stats(db)

@app.get("/dashboard/revenue-product")
def get_revenue_product(db: Session = Depends(get_db)):
    return revenue_by_product(db)

@app.get("/dashboard/revenue-time")
def get_revenue_time(db: Session = Depends(get_db)):
    return revenue_over_time(db)

@app.get("/dashboard/recent-sales")
def recent_sales(db: Session = Depends(get_db)):
    return get_recent_sales(db)

    
