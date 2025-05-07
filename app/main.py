from fastapi import FastAPI
from app.database import engine
from app.models import models
from app.routers import ai, users, items, rentals

app = FastAPI()

# 테이블 자동 생성
models.Base.metadata.create_all(bind=engine)

# 라우터 등록
app.include_router(users.router)
app.include_router(items.router, prefix="/items")
app.include_router(rentals.router, prefix="/rentals")
# 라우터 추가
app.include_router(ai.router, prefix="/ai")

@app.get("/")
def root():
    return {"message": "Sheerent API (MySQL) Running!"}
