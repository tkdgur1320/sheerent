from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime

from app.database import SessionLocal
from app.models.models import Rental, Item
from app.schemas.schemas import Rental as RentalSchema, RentalCreate
from pydantic import BaseModel

router = APIRouter(tags=["rentals"])

# ✅ 반납 시 요청 스키마
class ReturnRequest(BaseModel):
    damage_reported: bool

# DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ 1. 대여 등록 (중복 방지)
@router.post("/", response_model=RentalSchema)
def create_rental(rental: RentalCreate, db: Session = Depends(get_db)):
    db_item = db.query(Item).filter(Item.id == rental.item_id).first()
    if not db_item or db_item.status != "registered":
        raise HTTPException(status_code=400, detail="대여할 수 없는 아이템입니다.")

    active_rental = db.query(Rental).filter(
        Rental.item_id == rental.item_id,
        Rental.is_returned == False
    ).first()
    if active_rental:
        raise HTTPException(status_code=400, detail="해당 아이템은 아직 반납되지 않았습니다.")

    db_item.status = "rented"
    new_rental = Rental(
        item_id=rental.item_id,
        borrower_id=rental.borrower_id,
        start_time=datetime.utcnow(),
        end_time=rental.end_time,
        is_returned=False,
        deposit_amount=10000,  # 예시 보증금
        damage_reported=False,
        deducted_amount=0
    )
    db.add(new_rental)
    db.commit()
    db.refresh(new_rental)
    return new_rental

# ✅ 2. 전체 대여 조회 + 필터링
@router.get("/", response_model=List[RentalSchema])
def get_rentals(is_returned: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Rental).options(joinedload(Rental.item))
    if is_returned is not None:
        query = query.filter(Rental.is_returned == is_returned)
    return query.all()

# ✅ 3. 대여 반납 처리 + 보증금 정산
@router.put("/{rental_id}/return", response_model=RentalSchema)
def return_rental(rental_id: int, request: ReturnRequest, db: Session = Depends(get_db)):
    rental = db.query(Rental).filter(Rental.id == rental_id).first()
    if not rental:
        raise HTTPException(status_code=404, detail="대여 기록을 찾을 수 없습니다.")
    if rental.is_returned:
        raise HTTPException(status_code=400, detail="이미 반납된 대여입니다.")

    rental.is_returned = True
    rental.damage_reported = request.damage_reported

    if rental.damage_reported:
        rental.deducted_amount = rental.deposit_amount  # 전액 차감
    else:
        rental.deducted_amount = 0  # 전액 반환

    db_item = db.query(Item).filter(Item.id == rental.item_id).first()
    db_item.status = "registered"

    db.commit()
    db.refresh(rental)
    return rental

# ✅ 4. 대여 상세 조회
@router.get("/{rental_id}", response_model=RentalSchema)
def get_rental_detail(rental_id: int, db: Session = Depends(get_db)):
    rental = db.query(Rental).filter(Rental.id == rental_id).first()
    if not rental:
        raise HTTPException(status_code=404, detail="해당 대여 기록을 찾을 수 없습니다.")
    return rental

# ✅ 5. 사용자별 대여 통계
@router.get("/stats/{user_id}")
def get_user_rental_stats(user_id: int, db: Session = Depends(get_db)):
    total = db.query(Rental).filter(Rental.borrower_id == user_id).count()
    returned = db.query(Rental).filter(Rental.borrower_id == user_id, Rental.is_returned == True).count()
    not_returned = db.query(Rental).filter(Rental.borrower_id == user_id, Rental.is_returned == False).count()

    return {
        "user_id": user_id,
        "total_rentals": total,
        "returned": returned,
        "not_returned": not_returned
    }
