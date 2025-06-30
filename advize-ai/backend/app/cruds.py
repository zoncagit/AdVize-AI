from sqlalchemy.orm import Session
from . import models, schemas
from Auth import get_password_hash
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_pw = get_password_hash(user.password)
    db_user = models.User(email=user.email, password_hash=hashed_pw, firstname=user.firstname, lastname=user.lastname)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_oauth(db: Session, user_id: int):
    return db.query(models.OAuthCredential).filter(models.OAuthCredential.user_id == user_id).first()

def upsert_oauth(db: Session, user_id: int, oauth: schemas.OAuthCredentialBase):
    db_oauth = get_oauth(db, user_id)
    if db_oauth:
        for key, value in oauth.dict(exclude_unset=True).items():
            setattr(db_oauth, key, value)
    else:
        db_oauth = models.OAuthCredential(user_id=user_id, **oauth.dict())
        db.add(db_oauth)
    db.commit()
    return db_oauth

def get_ad_accounts(db: Session, user_id: int):
    return db.query(models.AdAccount).filter(models.AdAccount.user_id == user_id).all()

def create_ad_account(db: Session, ad_account: schemas.AdAccountCreate):
    db_acc = models.AdAccount(**ad_account.dict())
    db.add(db_acc)
    db.commit()
    db.refresh(db_acc)
    return db_acc

def get_campaigns(db: Session, account_id: int):
    return db.query(models.Campaign).filter(models.Campaign.account_id == account_id).all()

def create_campaign(db: Session, campaign: schemas.CampaignCreate):
    db_cmp = models.Campaign(**campaign.dict())
    db.add(db_cmp)
    db.commit()
    db.refresh(db_cmp)
    return db_cmp

def get_campaigns(db: Session, account_id: int):
    return db.query(models.Campaign).filter(models.Campaign.account_id == account_id).all()

def create_campaign(db: Session, campaign: schemas.CampaignCreate):
    db_cmp = models.Campaign(**campaign.dict())
    db.add(db_cmp)
    db.commit()
    db.refresh(db_cmp)
    return db_cmp

def get_metrics(db: Session, campaign_id: int):
    return db.query(models.CampaignMetric).filter(models.CampaignMetric.campaign_id == campaign_id).all()

def upsert_metric(db: Session, metric: schemas.CampaignMetricCreate):
    db_m = db.query(models.CampaignMetric).get((metric.campaign_id, metric.metric_date))
    if db_m:
        for key, val in metric.dict(exclude_unset=True).items():
            setattr(db_m, key, val)
    else:
        db_m = models.CampaignMetric(**metric.dict())
        db.add(db_m)
    db.commit()
    return db_m

def get_suggestions(db: Session, campaign_id: int):
    return db.query(models.OptimizationSuggestion).filter(models.OptimizationSuggestion.campaign_id == campaign_id).all()

def create_suggestion(db: Session, suggestion: schemas.OptimizationSuggestionCreate):
    db_s = models.OptimizationSuggestion(**suggestion.dict())
    db.add(db_s)
    db.commit()
    db.refresh(db_s)
    return db_s

def create_chat_session(db: Session, user_id: int):
    session = models.ChatSession(user_id=user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def create_chat_message(db: Session, message: schemas.ChatMessageCreate):
    msg = models.ChatMessage(**message.dict())
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg

def get_notification_pref(db: Session, user_id: int):
    return db.query(models.NotificationPreference).filter(models.NotificationPreference.user_id == user_id).first()

def upsert_notification_pref(db: Session, pref: schemas.NotificationPreferenceCreate):
    db_pref = get_notification_pref(db, pref.user_id)
    if db_pref:
        db_pref.enabled = pref.enabled
    else:
        db_pref = models.NotificationPreference(**pref.dict())
        db.add(db_pref)
    db.commit()
    db.refresh(db_pref)
    return db_pref


