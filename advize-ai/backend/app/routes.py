from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from app.schemas import UserProfileResponse
# app/routers/dashboard_router.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.Auth import get_current_user
from app.database import get_db
from app.models import User, AdAccount, Campaign, CampaignMetric
from app.schemas import DashboardMetricsResponse

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

router = APIRouter()

# Adjust the import according to your project structure; for example, if 'dependencies.py' is in the same directory as 'routes.py', use:
from app.Auth import get_current_user  # dépendance JWT
from app.models import User


@router.post("/logout", status_code=200)
def logout(current_user: User = Depends(get_current_user)):
    return {"message": "Successfully logged out. Please delete the token on the client side."}

@router.get("/me", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/metrics", response_model=DashboardMetricsResponse)
def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get all user ad accounts
    accounts = db.query(AdAccount).filter_by(user_id=current_user.id).all()
    account_ids = [account.id for account in accounts]

    # Get campaigns for these accounts
    campaigns = db.query(Campaign).filter(Campaign.account_id.in_(account_ids)).all()
    campaign_ids = [c.id for c in campaigns]

    # Aggregate metrics
    metrics = db.query(
        CampaignMetric
    ).filter(CampaignMetric.campaign_id.in_(campaign_ids)).all()

    # Sum up the numbers
    total_spend = sum(m.spend for m in metrics)
    total_clicks = sum(m.clicks for m in metrics)
    total_impressions = sum(m.impressions for m in metrics)
    total_purchases = sum(m.purchases or 0 for m in metrics)

    return {
        "total_spend": total_spend,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "total_purchases": total_purchases
    }


