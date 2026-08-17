from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from backend.app.notification_service import create_notification, resolve_subject
from backend.database import get_db
from backend.app.auth import get_current_user, require_roles
from backend.app.schemas.dispute import Dispute, DisputeCreate, DisputeUpdate, DisputeInDB
from backend.models import Dispute as DisputeModel, Sale, User

router = APIRouter(prefix="/disputes", tags=["Disputes"])

@router.get("/", response_model=List[DisputeInDB])
def list_disputes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "owner", "admin")),
):
    disputes = db.query(DisputeModel).offset(skip).limit(limit).all()
    return disputes

@router.get("/{dispute_id}", response_model=DisputeInDB)
def get_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "owner", "admin")),
):
    dispute = db.query(DisputeModel).filter(DisputeModel.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return dispute

@router.post("/", response_model=DisputeInDB, status_code=201)
def create_dispute(
    dispute: DisputeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "owner", "admin")),
):
    # Verify that the sale exists
    sale = db.query(Sale).filter(Sale.id == dispute.sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    # Verify that the buyer and seller exist
    buyer = db.query(User).filter(User.id == dispute.buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    seller = db.query(User).filter(User.id == dispute.seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # If logistics_id is provided, verify it exists
    if dispute.logistics_id:
        logistics = db.query(User).filter(User.id == dispute.logistics_id).first()
        if not logistics:
            raise HTTPException(status_code=404, detail="Logistics not found")
    
    db_dispute = DisputeModel(**dispute.dict())
    db.add(db_dispute)
    db.commit()
    db.refresh(db_dispute)
    
    # Notify the buyer and seller about the dispute
    for user_id in [dispute.buyer_id, dispute.seller_id]:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(user)
            create_notification(
                db,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                recipient_email=recipient_email,
                title="Dispute Filed",
                message=f"A dispute has been filed for order #{dispute.sale_id}. Please check the dispute resolution center for more details.",
                notification_type="system",
                severity="warning",
                action_href="/superadmin/disputes",
                background_tasks=background_tasks,
            )
    
    db.commit()
    return db_dispute

@router.patch("/{dispute_id}", response_model=DisputeInDB)
def update_dispute(
    dispute_id: int,
    dispute_update: DisputeUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "owner", "admin")),
):
    dispute = db.query(DisputeModel).filter(DisputeModel.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    update_data = dispute_update.dict(exclude_unset=True)
    
    valid_statuses = {"open", "resolved_seller", "resolved_buyer", "resolved_mutual", "arbitration", "escalated"}
    if "status" in update_data and update_data["status"] not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid dispute status: {update_data['status']}")
    
    for key, value in update_data.items():
        setattr(dispute, key, value)
    
    # If status is being updated to a resolved state, set resolved_at
    if update_data.get("status") and update_data["status"] in ["resolved_seller", "resolved_buyer", "resolved_mutual", "arbitration"]:
        from datetime import datetime
        dispute.resolved_at = datetime.now()
    
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    
    # Notify the buyer and seller about the update
    for user_id in [dispute.buyer_id, dispute.seller_id]:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            recipient_type, recipient_id, recipient_email, recipient_name = resolve_subject(user)
            create_notification(
                db,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                recipient_email=recipient_email,
                title="Dispute Updated",
                message=f"The dispute for order #{dispute.sale_id} has been updated. Status: {dispute.status}",
                notification_type="system",
                severity="info",
                action_href="/superadmin/disputes",
                background_tasks=background_tasks,
            )
    
    db.commit()
    return dispute

@router.delete("/{dispute_id}", status_code=204)
def delete_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "owner", "admin")),
):
    dispute = db.query(DisputeModel).filter(DisputeModel.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    db.delete(dispute)
    db.commit()
    return {"ok": True}