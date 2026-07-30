from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Plan
from app.schemas import PlanOut

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.price_usdt).all()
