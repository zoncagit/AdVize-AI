from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional, List
import enum

# --- VerificationRequest schema ---
class VerificationRequest(BaseModel):
    verification_code: str
    email: EmailStr
    firstname: str
    lastname: str
    password: str

# --- Token schema for authentication ---
class Token(BaseModel):
    access_token: str
    token_type: str

# --- ENUMS pour schémas (reprise de SQLAlchemy enums) ---
class AdAccountStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"

class CampaignStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"

class MessageSender(str, enum.Enum):
    user = "user"
    ai = "ai"

# --- Schémas User ---
class UserBase(BaseModel):
    email: EmailStr
    firstname: str
    lastname: str

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

# --- Schémas OAuthCredential ---
class OAuthCredentialBase(BaseModel):
    access_token: Optional[str]
    refresh_token: Optional[str]
    connected_at: Optional[datetime]

class OAuthCredentialRead(OAuthCredentialBase):
    user_id: int

    class Config:
        orm_mode = True

# --- Schémas AdAccount ---
class AdAccountBase(BaseModel):
    platform: str
    external_id: str
    status: AdAccountStatus
    connected_at: Optional[datetime]

class AdAccountCreate(AdAccountBase):
    pass

class AdAccountRead(AdAccountBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True

# --- Schémas Campaign ---
class CampaignBase(BaseModel):
    name: str
    status: CampaignStatus
    start_date: Optional[date]
    end_date: Optional[date]

class CampaignCreate(CampaignBase):
    account_id: int

class CampaignRead(CampaignBase):
    id: int
    account_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# --- Schémas CampaignMetric ---
class CampaignMetricBase(BaseModel):
    metric_date: date
    spend: float
    impressions: int
    clicks: int
    ctr: Optional[float]
    cpc: Optional[float]
    roas: Optional[float]
    cpp: float
    purchases: Optional[float]

class CampaignMetricCreate(CampaignMetricBase):
    campaign_id: int

class CampaignMetricRead(CampaignMetricBase):
    campaign_id: int

    class Config:
        orm_mode = True

# --- Schémas OptimizationSuggestion ---
class OptimizationSuggestionBase(BaseModel):
    category: str
    suggestion: str
    applied: bool

class OptimizationSuggestionCreate(OptimizationSuggestionBase):
    campaign_id: int

class OptimizationSuggestionRead(OptimizationSuggestionBase):
    id: int
    campaign_id: int

    class Config:
        orm_mode = True

# --- Schémas ChatSession ---
class ChatSessionBase(BaseModel):
    started_at: Optional[datetime]
    ended_at: Optional[datetime]

class ChatSessionCreate(ChatSessionBase):
    user_id: int

class ChatSessionRead(ChatSessionBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True

# --- Schémas ChatMessage ---
class ChatMessageBase(BaseModel):
    sender: MessageSender
    content: str
    timestamp: Optional[datetime]

class ChatMessageCreate(ChatMessageBase):
    session_id: int

class ChatMessageRead(ChatMessageBase):
    id: int
    session_id: int

    class Config:
        orm_mode = True

# --- Schémas NotificationPreference ---
class NotificationPreferenceBase(BaseModel):
    enabled: bool

class NotificationPreferenceCreate(NotificationPreferenceBase):
    user_id: int

class NotificationPreferenceRead(NotificationPreferenceBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True
