from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, ForeignKey, REAL, Date
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base

# Enum definitions
class AdAccountStatus(enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"

class CampaignStatus(enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"

class MessageSender(enum.Enum):
    user = "user"
    ai = "ai"

# Models
class User(Base):
    __tablename__ = "USER"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    oauth_credential = relationship("OAuthCredential", back_populates="user", uselist=False)
    ad_accounts = relationship("AdAccount", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")
    notification_pref = relationship("NotificationPreference", back_populates="user", uselist=False)

class OAuthCredential(Base):
    __tablename__ = "OAUTH_CREDENTIAL"
    user_id = Column(Integer, ForeignKey("USER.id"), primary_key=True)
    access_token = Column(String)
    refresh_token = Column(String)
    connected_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="oauth_credential")

class AdAccount(Base):
    __tablename__ = "AD_ACCOUNT"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("USER.id"), nullable=False)
    platform = Column(String, nullable=False)
    external_id = Column(String, nullable=False)
    status = Column(Enum(AdAccountStatus), nullable=False)
    connected_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="ad_accounts")
    campaigns = relationship("Campaign", back_populates="account")

class Campaign(Base):
    __tablename__ = "CAMPAIGN"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("AD_ACCOUNT.id"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(Enum(CampaignStatus), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("AdAccount", back_populates="campaigns")
    metrics = relationship("CampaignMetric", back_populates="campaign")
    suggestions = relationship("OptimizationSuggestion", back_populates="campaign")

class CampaignMetric(Base):
    __tablename__ = "CAMPAIGN_METRIC"
    campaign_id = Column(Integer, ForeignKey("CAMPAIGN.id"), primary_key=True)
    metric_date = Column(Date, primary_key=True)
    spend = Column(REAL, default=0.0, nullable=False)
    impressions = Column(Integer, default=0, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)
    ctr = Column(REAL)
    cpc = Column(REAL)
    roas = Column(REAL)
    cpp = Column(REAL, default=0.0, nullable=False)
    purchases = Column(REAL)

    campaign = relationship("Campaign", back_populates="metrics")

class OptimizationSuggestion(Base):
    __tablename__ = "OPTIMIZATION_SUGGESTION"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("CAMPAIGN.id"), nullable=False)
    category = Column(String, nullable=False)
    suggestion = Column(String, nullable=False)
    applied = Column(Boolean, default=False, nullable=False)

    campaign = relationship("Campaign", back_populates="suggestions")

class ChatSession(Base):
    __tablename__ = "CHAT_SESSION"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("USER.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session")

class ChatMessage(Base):
    __tablename__ = "CHAT_MESSAGE"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("CHAT_SESSION.id"), nullable=False)
    sender = Column(Enum(MessageSender), nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

class NotificationPreference(Base):
    __tablename__ = "NOTIFICATION_PREFERENCE"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("USER.id"), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="notification_pref")