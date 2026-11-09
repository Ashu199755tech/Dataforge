from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from backend.app.core.database import get_db
from backend.app.services.billing_service import BillingService
from backend.app.schemas.billing import (
    SubscriptionPlanResponse,
    SubscriptionPlanCreate,
    CustomerSubscriptionResponse,
    CustomerSubscriptionCreate,
    CustomerSubscriptionUpdate,
    BillingOverviewResponse
)
from backend.app.api.deps import get_current_user
from backend.app.core.rbac import require_role
from backend.app.models.user import User

router = APIRouter(prefix="/billing", tags=["Pricing & Billing"])


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
def list_subscription_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns all available commercial subscription tiers (Starter, Professional, Enterprise)."""
    return BillingService.get_available_plans(db)


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
def get_subscription_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full details and versioned pricing for a single plan."""
    plan = BillingService.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")
    
    latest_v = plan.pricing_versions[0] if plan.pricing_versions else None
    return {
        "id": plan.id,
        "plan_code": plan.plan_code,
        "name": plan.name,
        "description": plan.description,
        "tier_level": plan.tier_level,
        "is_active": plan.is_active,
        "is_custom": plan.is_custom,
        "features": plan.features,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "active_pricing": latest_v
    }


@router.get("/subscription", response_model=Optional[CustomerSubscriptionResponse])
def get_current_subscription(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves current active subscription contract for the tenant or workspace."""
    sub = BillingService.get_subscription_for_workspace(db, workspace_id)
    return sub


@router.post("/subscription", response_model=CustomerSubscriptionResponse)
def update_or_create_subscription(
    sub_in: CustomerSubscriptionCreate,
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Owner"]))
):
    """Upgrades, downgrades, or switches subscription terms."""
    try:
        return BillingService.update_subscription(
            db=db,
            plan_id=sub_in.plan_id,
            billing_period=sub_in.billing_period,
            workspace_id=workspace_id or sub_in.workspace_id,
            notes=sub_in.custom_agreement_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/overview", response_model=BillingOverviewResponse)
def get_billing_overview(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compiles complete billing overview with real execution counts and current balance."""
    return BillingService.get_billing_overview(db, workspace_id)
