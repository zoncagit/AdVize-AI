# app/main.py
import uuid
from fastapi import FastAPI, Depends, HTTPException, status, Request
import app.cruds as cruds
from app import models
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from pydantic import BaseModel

from app.database import engine, Base, get_db
from app import models
from app.cruds import create_ad_account, get_ad_accounts
from app import schemas
from app.Auth import router as AuthRouter, get_current_active_user
from app.models import User, Campaign, CampaignMetric, OptimizationSuggestion, ChatSession, ChatMessage, AdAccount
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

# Create tables if needed
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AdsAi API",
    description="Backend FastAPI pour AdsAi",
    version="1.0.0",
)

# Include auth router
app.include_router(AuthRouter, prefix="/auth", tags=["Authentication"])

@app.post("/logout", status_code=200)
def logout(current_user: User = Depends(get_current_user)):
    return {"message": "Successfully logged out. Please delete the token on the client side."}

@app.get("/me", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
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

@app.post("/api/accounts", response_model=schemas.AdAccountRead, status_code=status.HTTP_201_CREATED)
def create_account(
    account: schemas.AdAccountCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new ad account for the current user"""
    db_account = create_ad_account(db=db, ad_account=account, user_id=current_user.id)
    return db_account

@app.get("/api/accounts", response_model=List[schemas.AdAccountRead])
def list_accounts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all ad accounts for the current user"""
    try:
        print(f"Current user ID: {current_user.id}")
        accounts = cruds.get_ad_accounts(db=db, user_id=current_user.id)
        print(f"Retrieved accounts: {accounts}")
        return accounts
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in list_accounts: {error_details}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to retrieve ad accounts",
                "error": str(e),
                "traceback": error_details
            }
        )

# ===== Dashboard Routes =====
@app.get("/api/dashboard/chart-data")
async def get_chart_data(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get chart data for the dashboard"""
    try:
        print(f"Fetching chart data for user: {current_user.id}")
        
        # Get all user ad accounts
        accounts = cruds.get_ad_accounts(db=db, user_id=current_user.id)
        account_ids = [account.id for account in accounts]
        
        if not account_ids:
            return {"data": [], "labels": []}
            
        # Get campaigns for these accounts
        campaigns = db.query(models.Campaign).filter(
            models.Campaign.account_id.in_(account_ids)
        ).all()
        
        # Generate sample data (replace with actual data fetching)
        data = {
            "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "impressions": [100, 200, 150, 300, 200, 250, 400],
            "clicks": [10, 20, 15, 30, 25, 35, 50],
            "spend": [50.0, 100.0, 75.0, 150.0, 125.0, 175.0, 200.0]
        }
        
        return data
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_chart_data: {error_details}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to fetch chart data",
                "error": str(e),
                "traceback": error_details
            }
        )

@app.get("/api/dashboard/campaigns", response_model=List[Dict[str, Any]])
async def get_dashboard_campaigns(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get campaigns for the dashboard with their metrics
    Returns a list of campaigns with their performance metrics
    """
    try:
        print(f"Fetching dashboard campaigns for user: {current_user.id}")
        
        # Get all user's ad accounts
        accounts = cruds.get_ad_accounts(db=db, user_id=current_user.id)
        account_ids = [account.id for account in accounts]
        
        if not account_ids:
            print(f"No ad accounts found for user {current_user.id}")
            return []
        
        # Get campaigns with their metrics
        campaigns = db.query(
            models.Campaign
        ).filter(
            models.Campaign.account_id.in_(account_ids)
        ).all()
        
        # Prepare response with campaign details and metrics
        result = []
        for campaign in campaigns:
            # Get latest metrics for the campaign
            latest_metric = db.query(models.CampaignMetric).filter(
                models.CampaignMetric.campaign_id == campaign.id
            ).order_by(models.CampaignMetric.metric_date.desc()).first()
            
            campaign_data = {
                "id": campaign.id,
                "name": campaign.name,
                "status": campaign.status,
                "start_date": campaign.start_date,
                "end_date": campaign.end_date,
                "account_id": campaign.account_id,
                "metrics": {}
            }
            
            if latest_metric:
                campaign_data["metrics"] = {
                    "spend": latest_metric.spend,
                    "impressions": latest_metric.impressions,
                    "clicks": latest_metric.clicks,
                    "ctr": latest_metric.ctr,
                    "cpc": latest_metric.cpc,
                    "roas": latest_metric.roas,
                    "cpp": latest_metric.cpp,
                    "purchases": latest_metric.purchases,
                    "metric_date": latest_metric.metric_date
                }
            
            result.append(campaign_data)
        
        print(f"Returning {len(result)} campaigns with metrics")
        return result
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_dashboard_campaigns: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to fetch dashboard campaigns",
                "error": str(e),
                "traceback": error_details
            }
        )

# ===== Campaign Management Routes =====
@app.get("/api/campaigns", response_model=List[schemas.CampaignRead])
async def get_campaigns(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all campaigns for the current user
    Returns campaigns from all ad accounts owned by the user
    """
    try:
        print(f"Fetching campaigns for user: {current_user.id}")
        
        # First get all user's ad accounts
        accounts = cruds.get_ad_accounts(db=db, user_id=current_user.id)
        account_ids = [account.id for account in accounts]
        
        if not account_ids:
            print(f"No ad accounts found for user {current_user.id}")
            return []
            
        # Get campaigns from these accounts
        campaigns = db.query(models.Campaign).filter(
            models.Campaign.account_id.in_(account_ids)
        ).all()
        
        print(f"Found {len(campaigns)} campaigns for user {current_user.id}")
        return campaigns
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_campaigns: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to fetch campaigns",
                "error": str(e),
                "traceback": error_details
            }
        )

@app.post("/api/campaigns")
async def create_campaign(
    campaign_data: schemas.CampaignCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new campaign"""
    try:
        print(f"Creating campaign for user {current_user.id} with data: {campaign_data}")
        
        # Verify the account exists and belongs to the user
        account = db.query(models.AdAccount).filter(
            models.AdAccount.id == campaign_data.account_id,
            models.AdAccount.user_id == current_user.id
        ).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ad account not found or access denied"
            )
        
        # Create campaign in database
        db_campaign = models.Campaign(
            name=campaign_data.name,
            status=campaign_data.status,
            start_date=campaign_data.start_date,
            end_date=campaign_data.end_date,
            account_id=campaign_data.account_id
        )
        
        db.add(db_campaign)
        db.commit()
        db.refresh(db_campaign)
        
        return db_campaign
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in create_campaign: {error_details}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to create campaign",
                "error": str(e),
                "traceback": error_details
            }
        )

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[schemas.CampaignStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    account_id: Optional[int] = None

@app.put("/api/campaigns/{campaign_id}", response_model=schemas.CampaignRead)
async def update_campaign(
    campaign_id: int,
    campaign_data: CampaignUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing campaign
    Only updates fields that are provided in the request
    """
    try:
        print(f"Updating campaign {campaign_id} for user {current_user.id}")
        
        # Get the campaign
        campaign = db.query(models.Campaign).join(
            models.AdAccount,
            models.AdAccount.id == models.Campaign.account_id
        ).filter(
            models.Campaign.id == campaign_id,
            models.AdAccount.user_id == current_user.id
        ).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found or access denied"
            )
        
        # Verify new account_id if provided
        if campaign_data.account_id is not None:
            # Check if the new account exists and belongs to the user
            new_account = db.query(models.AdAccount).filter(
                models.AdAccount.id == campaign_data.account_id,
                models.AdAccount.user_id == current_user.id
            ).first()
            
            if not new_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target ad account not found or access denied"
                )
        
        # Update only provided fields
        update_data = campaign_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)
        
        campaign.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(campaign)
        
        return campaign
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in update_campaign: {error_details}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to update campaign",
                "error": str(e),
                "traceback": error_details
            }
        )

@app.delete("/api/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a campaign
    Also deletes all related metrics and optimizations
    """
    try:
        print(f"Deleting campaign {campaign_id} for user {current_user.id}")
        
        # Get the campaign with ownership check
        campaign = db.query(models.Campaign).join(
            models.AdAccount,
            models.AdAccount.id == models.Campaign.account_id
        ).filter(
            models.Campaign.id == campaign_id,
            models.AdAccount.user_id == current_user.id
        ).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found or access denied"
            )
        
        # Delete related metrics first (due to foreign key constraint)
        db.query(models.CampaignMetric).filter(
            models.CampaignMetric.campaign_id == campaign_id
        ).delete(synchronize_session=False)
        
        # Delete related optimization suggestions
        db.query(models.OptimizationSuggestion).filter(
            models.OptimizationSuggestion.campaign_id == campaign_id
        ).delete(synchronize_session=False)
        
        # Now delete the campaign
        db.delete(campaign)
        db.commit()
        
        return {"message": "Campaign deleted successfully"}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in delete_campaign: {error_details}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to delete campaign",
                "error": str(e),
                "traceback": error_details
            }
        )

class CampaignInsight(BaseModel):
    title: str
    description: str
    metric: str
    value: float
    change: Optional[float] = None
    suggestion: Optional[str] = None
    severity: str = "info"  # info, warning, critical

class CampaignInsightsResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    status: str
    insights: List[CampaignInsight]
    recommendations: List[Dict[str, Any]]
    performance_trend: str  # improving, declining, stable

class CampaignPerformanceResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    status: str
    metrics: List[Dict[str, Any]]
    summary: Dict[str, Any]

@app.get("/api/campaigns/{campaign_id}/performance", response_model=CampaignPerformanceResponse)
async def get_campaign_performance(
    campaign_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get performance metrics for a specific campaign
    Returns time-series metrics and summary statistics
    """
    try:
        print(f"Fetching performance for campaign {campaign_id} for user {current_user.id}")
        
        # Get the campaign with ownership check
        campaign = db.query(models.Campaign).join(
            models.AdAccount,
            models.AdAccount.id == models.Campaign.account_id
        ).filter(
            models.Campaign.id == campaign_id,
            models.AdAccount.user_id == current_user.id
        ).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found or access denied"
            )
        
        # Get all metrics for this campaign, ordered by date
        metrics = db.query(models.CampaignMetric).filter(
            models.CampaignMetric.campaign_id == campaign_id
        ).order_by(
            models.CampaignMetric.metric_date.asc()
        ).all()
        
        # Calculate summary statistics
        total_spend = sum(m.spend for m in metrics) if metrics else 0
        total_impressions = sum(m.impressions for m in metrics) if metrics else 0
        total_clicks = sum(m.clicks for m in metrics) if metrics else 0
        total_purchases = sum(m.purchases or 0 for m in metrics) if metrics else 0
        
        avg_ctr = (sum(m.ctr for m in metrics) / len(metrics)) if metrics else 0
        avg_cpc = (sum(m.cpc for m in metrics) / len(metrics)) if metrics else 0
        avg_roas = (sum(m.roas for m in metrics) / len(metrics)) if metrics else 0
        avg_cpp = (sum(m.cpp for m in metrics) / len(metrics)) if metrics else 0
        
        # Prepare response
        response = {
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "status": campaign.status,
            "metrics": [
                {
                    "date": m.metric_date.isoformat(),
                    "spend": m.spend,
                    "impressions": m.impressions,
                    "clicks": m.clicks,
                    "ctr": m.ctr,
                    "cpc": m.cpc,
                    "roas": m.roas,
                    "cpp": m.cpp,
                    "purchases": m.purchases or 0
                }
                for m in metrics
            ],
            "summary": {
                "total_spend": total_spend,
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "total_purchases": total_purchases,
                "avg_ctr": avg_ctr,
                "avg_cpc": avg_cpc,
                "avg_roas": avg_roas,
                "avg_cpp": avg_cpp,
                "date_range": {
                    "start": metrics[0].metric_date.isoformat() if metrics else None,
                    "end": metrics[-1].metric_date.isoformat() if metrics else None
                }
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_campaign_performance: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to fetch campaign performance",
                "error": str(e),
                "traceback": error_details
            }
        )

@app.get("/api/campaigns/{campaign_id}/insights", response_model=CampaignInsightsResponse)
async def get_campaign_insights(
    campaign_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get AI-powered insights and recommendations for a campaign
    Analyzes performance data to provide actionable insights
    """
    try:
        print(f"Generating insights for campaign {campaign_id} for user {current_user.id}")
        
        # Get the campaign with ownership check
        campaign = db.query(models.Campaign).join(
            models.AdAccount,
            models.AdAccount.id == models.Campaign.account_id
        ).filter(
            models.Campaign.id == campaign_id,
            models.AdAccount.user_id == current_user.id
        ).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found or access denied"
            )
        
        # Get recent metrics (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        metrics = db.query(models.CampaignMetric).filter(
            models.CampaignMetric.campaign_id == campaign_id,
            models.CampaignMetric.metric_date >= thirty_days_ago
        ).order_by(
            models.CampaignMetric.metric_date.asc()
        ).all()
        
        if not metrics:
            return {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "status": campaign.status,
                "insights": [{
                    "title": "No Data Available",
                    "description": "Not enough data to generate insights. Check back after the campaign has been running for a while.",
                    "metric": "N/A",
                    "value": 0,
                    "severity": "info"
                }],
                "recommendations": [],
                "performance_trend": "stable"
            }
        
        # Calculate metrics
        total_spend = sum(m.spend for m in metrics)
        total_impressions = sum(m.impressions for m in metrics)
        total_clicks = sum(m.clicks for m in metrics)
        total_purchases = sum(m.purchases or 0 for m in metrics)
        
        avg_ctr = (sum(m.ctr for m in metrics) / len(metrics)) if metrics else 0
        avg_cpc = (sum(m.cpc for m in metrics) / len(metrics)) if metrics else 0
        avg_roas = (sum(m.roas for m in metrics) / len(metrics)) if metrics else 0
        
        # Generate insights
        insights = []
        recommendations = []
        
        # ROAS Insight
        roas_insight = CampaignInsight(
            title="ROAS Performance",
            description=f"Your campaign's ROAS is {avg_roas:.2f}",
            metric="ROAS",
            value=avg_roas,
            severity="info"
        )
        
        if avg_roas < 1.0:
            roas_insight.severity = "warning"
            roas_insight.suggestion = "Consider optimizing your targeting or creative to improve return on ad spend."
            recommendations.append({
                "type": "optimization",
                "priority": "high",
                "action": "Review audience targeting and creative performance",
                "details": "Your ROAS is below 1.0, indicating you're spending more than you're earning."
            })
        insights.append(roas_insight.dict())
        
        # CTR Insight
        ctr_insight = CampaignInsight(
            title="Click-Through Rate",
            description=f"Your average CTR is {avg_ctr*100:.2f}%",
            metric="CTR",
            value=avg_ctr,
            severity="info"
        )
        
        if avg_ctr < 0.02:  # 2% CTR
            ctr_insight.severity = "warning"
            ctr_insight.suggestion = "Your CTR is below average. Consider testing new ad creatives or improving your targeting."
            recommendations.append({
                "type": "creative",
                "priority": "medium",
                "action": "Test new ad creatives",
                "details": "Try different images, headlines, or calls-to-action to improve engagement."
            })
        insights.append(ctr_insight.dict())
        
        # Budget Insight
        if hasattr(campaign, 'budget') and campaign.budget and total_spend > campaign.budget * 0.8:  # 80% of budget
            budget_insight = CampaignInsight(
                title="Budget Alert",
                description=f"You've spent {total_spend:.2f} of your {campaign.budget:.2f} budget ({total_spend/campaign.budget*100:.0f}%)",
                metric="Spend",
                value=total_spend,
                severity="warning",
                suggestion="Consider increasing your budget or optimizing for better efficiency."
            )
            recommendations.append({
                "type": "budget",
                "priority": "high",
                "action": "Adjust campaign budget",
                "details": "You're approaching your campaign budget limit."
            })
            insights.append(budget_insight.dict())
        
        # Determine overall trend
        if len(metrics) > 1:
            first_half = metrics[:len(metrics)//2]
            second_half = metrics[len(metrics)//2:]
            
            first_roas = sum(m.roas for m in first_half) / len(first_half) if first_half else 0
            second_roas = sum(m.roas for m in second_half) / len(second_half) if second_half else 0
            
            if second_roas > first_roas * 1.2:  # 20% improvement
                trend = "improving"
            elif second_roas < first_roas * 0.8:  # 20% decline
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "status": campaign.status,
            "insights": insights,
            "recommendations": recommendations,
            "performance_trend": trend
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_campaign_insights: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to generate campaign insights",
                "error": str(e),
                "traceback": error_details
            }
        )

# ===== Optimization Routes =====
@app.get("/api/optimization/recommendations")
async def get_recommendations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get optimization recommendations"""
    return []

class OptimizationRequest(BaseModel):
    campaign_ids: Optional[List[int]] = None
    account_ids: Optional[List[int]] = None
    include_insights: bool = True
    include_actions: bool = True

class OptimizationResponse(BaseModel):
    request_id: str
    status: str
    generated_at: datetime
    recommendations: List[Dict[str, Any]]
    summary: Dict[str, Any]

@app.post("/api/optimization/generate", response_model=OptimizationResponse)
async def generate_recommendations(
    request: OptimizationRequest = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered optimization recommendations
    
    This endpoint analyzes campaign performance and generates actionable recommendations
    to improve ad performance and efficiency.
    """
    try:
        if request is None:
            request = OptimizationRequest()
            
        print(f"Generating optimizations for user {current_user.id}")
        
        # Get user's ad accounts with ownership check
        accounts_query = db.query(models.AdAccount).filter(
            models.AdAccount.user_id == current_user.id
        )
        
        if request.account_ids:
            accounts_query = accounts_query.filter(models.AdAccount.id.in_(request.account_ids))
            
        accounts = accounts_query.all()
        
        if not accounts:
            return {
                "request_id": str(uuid.uuid4()),
                "status": "completed",
                "generated_at": datetime.utcnow(),
                "recommendations": [],
                "summary": {
                    "message": "No ad accounts found",
                    "accounts_analyzed": 0,
                    "campaigns_analyzed": 0,
                    "recommendations_generated": 0
                }
            }
        
        # Get campaigns from these accounts
        campaigns_query = db.query(models.Campaign).filter(
            models.Campaign.account_id.in_([acc.id for acc in accounts])
        )
        
        if request.campaign_ids:
            campaigns_query = campaigns_query.filter(models.Campaign.id.in_(request.campaign_ids))
            
        campaigns = campaigns_query.all()
        
        if not campaigns:
            return {
                "request_id": str(uuid.uuid4()),
                "status": "completed",
                "generated_at": datetime.utcnow(),
                "recommendations": [],
                "summary": {
                    "message": "No campaigns found matching the criteria",
                    "accounts_analyzed": len(accounts),
                    "campaigns_analyzed": 0,
                    "recommendations_generated": 0
                }
            }
        
        # Get metrics for analysis (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Generate recommendations for each campaign
        recommendations = []
        
        for campaign in campaigns:
            # Get campaign metrics
            metrics = db.query(models.CampaignMetric).filter(
                models.CampaignMetric.campaign_id == campaign.id,
                models.CampaignMetric.metric_date >= thirty_days_ago
            ).all()
            
            if not metrics:
                continue
                
            # Calculate metrics
            avg_ctr = sum(m.ctr for m in metrics) / len(metrics)
            avg_roas = sum(m.roas for m in metrics) / len(metrics)
            total_spend = sum(m.spend for m in metrics)
            
            # Generate recommendations based on performance
            if avg_roas < 1.0:
                recommendations.append({
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "type": "optimization",
                    "priority": "high",
                    "action": "Improve ROAS",
                    "details": f"Current ROAS is {avg_roas:.2f}. Consider adjusting bids, targeting, or creative.",
                    "impact": "high",
                    "estimated_improvement": "10-30%"
                })
                
            if avg_ctr < 0.02:  # 2% CTR
                recommendations.append({
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "type": "creative",
                    "priority": "medium",
                    "action": "Improve Ad Creative",
                    "details": f"Current CTR is {avg_ctr*100:.1f}%. Test new images, headlines, or CTAs.",
                    "impact": "medium",
                    "estimated_improvement": "5-15%"
                })
                
            # Add more recommendation types as needed
            
        return {
            "request_id": str(uuid.uuid4()),
            "status": "completed",
            "generated_at": datetime.utcnow(),
            "recommendations": recommendations,
            "summary": {
                "message": f"Generated {len(recommendations)} recommendations",
                "accounts_analyzed": len(accounts),
                "campaigns_analyzed": len(campaigns),
                "recommendations_generated": len(recommendations)
            }
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in generate_recommendations: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to generate recommendations",
                "error": str(e),
                "traceback": error_details
            }
        )

class RecommendationApplyResponse(BaseModel):
    success: bool
    message: str
    recommendation_id: int
    action_taken: Optional[Dict[str, Any]] = None
    timestamp: datetime

@app.post(
    "/api/optimization/apply/{recommendation_id}",
    response_model=RecommendationApplyResponse,
    responses={
        200: {"description": "Recommendation applied successfully"},
        400: {"description": "Invalid recommendation or action not allowed"},
        404: {"description": "Recommendation not found"},
        500: {"description": "Failed to apply recommendation"}
    }
)
async def apply_recommendation(
    recommendation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Apply a specific optimization recommendation
    
    This endpoint applies the recommended action to the specified campaign.
    The system will validate the recommendation and user permissions before applying.
    """
    try:
        print(f"Applying recommendation {recommendation_id} for user {current_user.id}")
        
        # Get the recommendation with campaign and account info
        recommendation = db.query(
            models.OptimizationSuggestion
        ).join(
            models.Campaign,
            models.Campaign.id == models.OptimizationSuggestion.campaign_id
        ).join(
            models.AdAccount,
            models.AdAccount.id == models.Campaign.account_id
        ).filter(
            models.OptimizationSuggestion.id == recommendation_id,
            models.AdAccount.user_id == current_user.id
        ).first()
        
        if not recommendation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recommendation not found or access denied"
            )
        
        # Initialize response with basic info
        response = {
            "success": True,
            "message": "Recommendation applied successfully",
            "recommendation_id": recommendation_id,
            "timestamp": datetime.utcnow()
        }
        
        # Apply the recommendation based on its type
        if recommendation.action_type == "budget_adjustment":
            # Example: Increase budget by 20%
            campaign = db.query(models.Campaign).get(recommendation.campaign_id)
            if campaign:
                old_budget = campaign.budget or 0
                new_budget = old_budget * 1.2  # 20% increase
                campaign.budget = new_budget
                campaign.updated_at = datetime.utcnow()
                
                # Log the action
                action_log = models.OptimizationActionLog(
                    user_id=current_user.id,
                    campaign_id=recommendation.campaign_id,
                    recommendation_id=recommendation.id,
                    action_type="budget_adjustment",
                    action_details={
                        "old_budget": old_budget,
                        "new_budget": new_budget,
                        "percentage_increase": 20
                    },
                    status="completed"
                )
                db.add(action_log)
                db.commit()
                
                response["action_taken"] = {
                    "type": "budget_adjustment",
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "old_budget": old_budget,
                    "new_budget": new_budget
                }
                
        elif recommendation.action_type == "bid_adjustment":
            # Handle bid adjustments
            # Implementation would be similar to budget adjustment
            pass
            
        elif recommendation.action_type == "targeting_update":
            # Handle targeting updates
            # Implementation would be similar to budget adjustment
            pass
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action type: {recommendation.action_type}"
            )
        
        # Update recommendation status
        recommendation.status = "applied"
        recommendation.applied_at = datetime.utcnow()
        db.commit()
        
        return response
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in apply_recommendation: {error_details}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to apply recommendation",
                "error": str(e),
                "traceback": error_details
            }
        )

class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    user_message: str
    ai_response: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None

# In-memory storage for chat sessions (replace with database in production)
chat_sessions = {}

# ===== AI Chat Routes =====
@app.post(
    "/api/ai-chat/message",
    response_model=ChatMessageResponse,
    responses={
        200: {"description": "Chat message processed successfully"},
        400: {"description": "Invalid request data"},
        500: {"description": "Failed to process chat message"}
    }
)
async def send_chat_message(
    message_data: ChatMessageRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Process a chat message and return AI response
    
    This endpoint handles both new conversations and continuing existing ones.
    It maintains conversation context and provides AI-powered responses.
    """
    try:
        print(f"Processing chat message for user {current_user.id}")
        
        # Validate message content
        if not message_data.message or not message_data.message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty"
            )
        
        # Get or create chat session
        session_id = message_data.session_id or str(uuid.uuid4())
        if session_id not in chat_sessions:
            chat_sessions[session_id] = {
                "user_id": current_user.id,
                "created_at": datetime.utcnow(),
                "messages": [],
                "context": message_data.context or {}
            }
        
        session = chat_sessions[session_id]
        
        # Add user message to session
        user_message = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": message_data.message,
            "timestamp": datetime.utcnow()
        }
        session["messages"].append(user_message)
        
        # Generate AI response (simplified example)
        # In a real implementation, this would call an AI service
        ai_response_text = generate_ai_response(
            message_data.message,
            session["messages"][-5:],  # Last 5 messages for context
            session["context"]
        )
        
        # Add AI response to session
        ai_message = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": ai_response_text,
            "timestamp": datetime.utcnow()
        }
        session["messages"].append(ai_message)
        
        # Save to database (in a real implementation)
        try:
            # Save chat message to database
            db_message = models.ChatMessage(
                session_id=session_id,
                user_id=current_user.id,
                role="user",
                content=message_data.message,
                created_at=user_message["timestamp"]
            )
            db.add(db_message)
            
            # Save AI response to database
            db_ai_message = models.ChatMessage(
                session_id=session_id,
                user_id=current_user.id,
                role="assistant",
                content=ai_response_text,
                created_at=ai_message["timestamp"]
            )
            db.add(db_ai_message)
            
            # Update or create chat session
            db_session = db.query(models.ChatSession).filter_by(
                session_id=session_id,
                user_id=current_user.id
            ).first()
            
            if not db_session:
                db_session = models.ChatSession(
                    session_id=session_id,
                    user_id=current_user.id,
                    title=message_data.message[:50],  # First 50 chars as title
                    created_at=datetime.utcnow()
                )
                db.add(db_session)
            
            db_session.updated_at = datetime.utcnow()
            db.commit()
            
        except Exception as db_error:
            db.rollback()
            print(f"Database error in send_chat_message: {str(db_error)}")
            # Continue even if database save fails
        
        return {
            "message_id": ai_message["id"],
            "session_id": session_id,
            "user_message": message_data.message,
            "ai_response": ai_response_text,
            "timestamp": ai_message["timestamp"],
            "context": session["context"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in send_chat_message: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to process chat message",
                "error": str(e),
                "traceback": error_details
            }
        )

def generate_ai_response(message: str, message_history: List[Dict], context: Dict) -> str:
    """
    Generate an AI response based on the message and context
    
    This is a simplified example. In a real implementation, you would:
    1. Call an external AI service (e.g., OpenAI, Anthropic, etc.)
    2. Format the message history appropriately for the AI model
    3. Include any relevant context from the user's account
    """
    # Simple response for demonstration
    if "hello" in message.lower():
        return "Hello! How can I help you with your advertising campaigns today?"
    elif "performance" in message.lower():
        return "I can help analyze your campaign performance. Would you like me to check your recent metrics?"
    elif "recommendation" in message.lower():
        return "Based on your campaign data, I can suggest optimizations. Would you like me to analyze your campaigns?"
    else:
        return "I'm here to help with your advertising needs. You can ask me about campaign performance, optimization recommendations, or any other questions about your ads."

class ConversationMessage(BaseModel):
    id: int
    sender: str
    content: str
    timestamp: datetime

class ConversationResponse(BaseModel):
    conversation_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: List[ConversationMessage]

@app.get(
    "/api/ai-chat/conversations/{conversation_id}",
    response_model=ConversationResponse,
    responses={
        200: {"description": "Conversation retrieved successfully"},
        403: {"description": "Access denied to conversation"},
        404: {"description": "Conversation not found"},
        500: {"description": "Failed to retrieve conversation"}
    }
)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve a specific conversation with all its messages
    
    This endpoint returns the full conversation history for a specific chat session,
    including both user messages and AI responses, ordered chronologically.
    """
    try:
        print(f"Fetching conversation {conversation_id} for user {current_user.id}")
        
        # First verify the conversation exists and belongs to the user
        conversation = db.query(models.ChatSession).filter(
            models.ChatSession.id == conversation_id,
            models.ChatSession.user_id == current_user.id
        ).first()
        
        if not conversation:
            # Check if it exists but belongs to another user (for proper 403 response)
            other_user_convo = db.query(models.ChatSession).filter(
                models.ChatSession.id == conversation_id
            ).first()
            
            if other_user_convo:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to access this conversation"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
        
        # Get all messages for this conversation, ordered by creation time
        db_messages = db.query(models.ChatMessage).filter(
            models.ChatMessage.session_id == conversation_id
        ).order_by(
            models.ChatMessage.timestamp.asc()
        ).all()
        
        # Convert to response model
        messages = [
            ConversationMessage(
                id=msg.id,
                sender=msg.sender.value,  # Convert enum to string
                content=msg.content,
                timestamp=msg.timestamp
            )
            for msg in db_messages
        ]
        
        return {
            "conversation_id": conversation.id,
            "started_at": conversation.started_at,
            "ended_at": conversation.ended_at,
            "messages": messages
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_conversation: {error_details}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to retrieve conversation",
                "error": str(e),
                "traceback": error_details
            }
        )

@app.get("/api/ai-chat/quick-questions")
async def get_quick_questions(
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, str]]:
    """Get quick question suggestions"""
    return [
        {"question": "How can I improve my ad performance?"},
        {"question": "What's my best performing campaign?"},
        {"question": "How does my CTR compare to industry average?"}
    ]



# ===== Facebook (Meta) Integration Routes =====
@app.get("/facebook/connect")
async def connect_facebook_ads():
    """Initiate Facebook OAuth flow"""
    # Implementation here
    pass

@app.get("/facebook/callback")
async def facebook_callback(request: Request):
    """Handle Facebook OAuth callback"""
    # Implementation here
    pass

@app.get("/facebook/adaccounts")
async def get_facebook_ad_accounts(access_token: str):
    # Implementation for getting Facebook ad accounts
    pass

@app.get("/facebook/campaigns")
async def get_facebook_campaigns(access_token: str, ad_account_id: str):
    """Get Facebook campaigns and KPIs"""
    # Implementation here
    pass


