from sqlalchemy import Column, String, DateTime, Boolean, Enum, Float, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import declarative_base, relationship
import uuid
from datetime import datetime
import enum

Base = declarative_base()

# Enum definitions
class Platform(str, enum.Enum):
    facebook = "facebook"
    tiktok = "tiktok"
    snapchat = "snapchat"

class CampaignStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    deleted = "deleted"

class SuggestionCategory(str, enum.Enum):
    creative = "Creative"
    audience = "Audience"
    budget = "Budget"

class Sender(str, enum.Enum):
    user = "user"
    ai = "ai"

# User
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# OAuth Credential (1:1 with User)
class OAuthCredential(Base):
    __tablename__ = "oauth_credentials"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    access_token = Column(String)
    refresh_token = Column(String)
    connected_at = Column(DateTime, default=datetime.utcnow)

# Ad Account
class AdAccount(Base):
    __tablename__ = "ad_accounts"
    __table_args__ = (UniqueConstraint("user_id", "platform", "external_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform = Column(Enum(Platform), nullable=False)
    external_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    connected_at = Column(DateTime, default=datetime.utcnow)

# Campaign
class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("ad_accounts.id"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(Enum(CampaignStatus), nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

# Campaign Metric (composite PK)
class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"
    __table_args__ = (PrimaryKeyConstraint("campaign_id", "metric_date"),)

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"))
    metric_date = Column(DateTime, nullable=False)
    spend = Column(Float, default=0.0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float)
    cpc = Column(Float)
    roas = Column(Float)
    cpp = Column(Float, default=0.0)
    purchases = Column(Float)

# Optimization Suggestion
class OptimizationSuggestion(Base):
    __tablename__ = "optimization_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    category = Column(Enum(SuggestionCategory), nullable=False)
    suggestion = Column(Text, nullable=False)
    applied = Column(Boolean, default=False)

# Chat Session
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)

# Chat Message
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    sender = Column(Enum(Sender), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Notification Preference
class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    enabled = Column(Boolean, default=True)