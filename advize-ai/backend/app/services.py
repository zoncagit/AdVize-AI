import secrets
import string
import os
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship, Session

from app.services import EmailService
from app.Auth  import hash_password
from app.models  import User
from app.models import PasswordResetToken
from app.database import get_db

from datetime import datetime, timedelta
from typing import Optional, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.Auth import hash_password, verify_password
from app.models import User

# Import configuration
from app.config import database_settings
from app.database import SessionLocal

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Get token configuration from settings
SECRET_KEY = database_settings.secret_key
ALGORITHM = database_settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = database_settings.access_token_expire_minutes

# Create a new database session
def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_user(user_data: dict) -> User:
    """Crée un nouvel utilisateur dans la base de données."""
    db = next(get_db_session())
    try:
        print("=== Creating User in Service ===")
        print(f"Email: {user_data['email']}")
        print(f"Name: {user_data['name']} {user_data['prenom']}")
        print(f"Password length: {len(user_data['password'])}")
        
        # Hash the password
        print("\nHashing password...")
        hashed_password = hash_password(user_data["password"])
        print(f"Generated hash: {hashed_password}")
        print(f"Hash length: {len(hashed_password)}")
        
        # Create user instance
        print("\nCreating user instance...")
        user = User(
            email=user_data["email"],
            name=user_data["name"],
            prenom=user_data["prenom"],
            password_hash=hashed_password,
            is_verified=user_data.get("is_verified", False),
            is_active=user_data.get("is_active", True)
        )
        
        # Add to database
        print("\nSaving to database...")
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print("✅ User created successfully")
        print(f"User ID: {user.user_id}")
        print(f"Stored hash: {user.password_hash}")
        print(f"Stored hash length: {len(user.password_hash)}")
        
        return user
    except Exception as e:
        print(f"❌ Error creating user: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise Exception(f"Failed to create user: {str(e)}")
    finally:
        if 'db' in locals():
            db.close()

def get_user_by_email(email: str) -> User | None:
    """Récupère un utilisateur par son email."""
    db = next(get_db_session())
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()

def verify_user_password(email: str, password: str) -> bool:
    """Vérifie si les identifiants sont corrects."""
    db = next(get_db_session())
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return False
        return verify_password(password, user.password_hash)
    except Exception as e:
        raise Exception(f"Error verifying password: {str(e)}")
    finally:
        db.close()

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Dependency that will return the current user based on the JWT token.
    
    Args:
        token: The JWT token from the Authorization header
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    user = get_user_by_email(email=email)
    if user is None:
        raise credentials_exception
        
    return user


# Get frontend URL from environment variable or use default
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://127.0.0.1:5500/frontend')

# Initialize email service
email_service = EmailService.get_instance()
if not email_service.is_configured:
    raise Exception("Email service not properly configured")

class PasswordResetService:
    @staticmethod
    def generate_verification_code() -> str:
        """Generate a 6-digit verification code."""
        return ''.join(secrets.choice(string.digits) for _ in range(6))

    @staticmethod
    def send_reset_email(email: str, db: Session) -> Optional[str]:
        """
        Send a password reset email with a verification code.
        Returns the verification code if email is sent successfully, None otherwise.
        """
        try:
            # Generate verification code
            verification_code = PasswordResetService.generate_verification_code()
            
            # Get user details before sending email
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return None

            # Create a token that includes both email and verification code
            token_data = f"{email}:{verification_code}"
            
            # Store the verification code in the database with expiration time
            db.add(PasswordResetToken(
                user_id=user.user_id,
                token=verification_code,
                expires_at=datetime.utcnow() + timedelta(minutes=15)
            ))
            db.commit()

            # Send email with reset link
            reset_url = f"{FRONTEND_URL}/reset-password.html?token={verification_code}"
            email_service.send_email(
                to_email=email,
                subject="Password Reset Request",
                body=f"Dear {user.name} {user.prenom},\n\n"
                     f"We received a request to reset your password.\n\n"
                     f"Please click the following link to reset your password:\n"
                     f"{reset_url}\n\n"
                     f"This link will expire in 15 minutes.\n\n"
                     f"If you didn't request this password reset, please ignore this email.\n\n"
                     f"Best regards,\n"
                     f"The Attendify Team"
            )
            
            return verification_code

        except Exception as e:
            print(f"Error sending reset email: {str(e)}")
            return None

    @staticmethod
    def verify_reset_code_and_change_password(email: str, verification_code: str, new_password: str, db: Session) -> bool:
        """
        Verify the verification code and reset the password if valid.
        Returns True if password was successfully reset, False otherwise.
        """
        try:
            print(f"Attempting to reset password for email: {email}")
            print(f"Verification code received: {verification_code}")
            
            # Get user and token in a single query
            user = db.query(User).filter(User.email == email).first()
            if not user:
                print(f"User not found for email: {email}")
                return False

            print(f"User found with ID: {user.user_id}")
            
            token = db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user.user_id,
                PasswordResetToken.token == verification_code,
                PasswordResetToken.expires_at > datetime.utcnow()
            ).first()

            if not token:
                print(f"Token not found or expired for user {user.user_id}, email: {email}")
                return False

            print(f"Found token for user {user.user_id}")
            print(f"Token expires at: {token.expires_at}")

            # Update password
            user.password_hash = hash_password(new_password)
            
            # Delete the used token
            db.delete(token)
            
            # Commit all changes in one transaction
            db.commit()
            print(f"Password reset successful for user {user.user_id}")
            return True

        except Exception as e:
            print(f"Error resetting password: {str(e)}")
            return False
            return verification_code
        except Exception as e:
            print(f"Error sending reset email: {str(e)}")
            return None

    @staticmethod
    def verify_code_and_reset_password(email: str, verification_code: str, new_password: str) -> bool:
        """
        Verify the verification code and reset the password if valid.
        Returns True if password was successfully reset, False otherwise.
        """
        try:
            with get_db() as db:
                return PasswordResetService.verify_reset_code_and_change_password(
                    email, verification_code, new_password, db
                )
        except Exception as e:
            print(f"Error in verify_code_and_reset_password: {str(e)}")
            return False
# app/services/email_service.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from typing import Optional
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    _instance = None
    is_configured = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if self.__class__._instance is not None:
            raise ValueError("EmailService is a singleton - use get_instance() instead")

        try:
            # Load settings from Pydantic
            self.smtp_server = settings.smtp_server
            self.smtp_port = settings.smtp_port
            self.smtp_user = settings.smtp_user
            self.smtp_password = settings.smtp_password
            self.email_from = settings.email_from
            self.email_from_name = settings.email_from_name
            
            # Log configuration
            logger.info(f"SMTP Server: {self.smtp_server}")
            logger.info(f"SMTP Port: {self.smtp_port}")
            logger.info(f"SMTP User: {self.smtp_user}")
            logger.info(f"From Email: {self.email_from}")
            logger.info(f"Email From Name: {self.email_from_name}")
            logger.info("Email service initialized successfully")
            
            # Set flag to indicate email is configured
            self.is_configured = True

        except Exception as e:
            logger.error(f"Failed to initialize email service: {str(e)}", exc_info=True)
            self.is_configured = False

    def send_email(self, to_email: str, subject: str, body: str, html: Optional[str] = None) -> bool:
        if not self.is_configured:
            logger.warning("Email service is not configured - cannot send email")
            return False

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{self.email_from_name} <{self.email_from}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            if html:
                msg.attach(MIMEText(body, 'plain'))
                msg.attach(MIMEText(html, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.email_from, to_email, msg.as_string())
                logger.info(f"Email sent successfully to {to_email}")
                return True

        except smtplib.SMTPAuthenticationError:
            logger.error("Failed to authenticate with SMTP server")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error occurred: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
        