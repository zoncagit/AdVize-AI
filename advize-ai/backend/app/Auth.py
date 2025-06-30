from datetime import datetime, timedelta
import logging
import os
import random
import secrets
from typing import Any, Dict, List, Optional, Union

from fastapi import (
    APIRouter, Body, Depends, Form, HTTPException, Request, Response,
    Security, status
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes
from fastapi.responses import HTMLResponse, JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import get_db
from app import models, schemas
from app.models import OAuthCredential, User, PasswordResetToken
from app.schemas import Token, UserCreate, OAuthCredentialCreate, OAuthCredentialVerify, VerificationRequest
from app.cruds import (
    create_oauth_credential, verify_oauth_credential,
    update_oauth_credential_after_verification, create_user,
    get_user_by_email
)
from app.services import EmailService, PasswordResetService
from app.utils.password import hash_password, verify_password

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token with the provided data.
    
    Args:
        data: Dictionary containing the data to encode in the token
        expires_delta: Optional timedelta for token expiration
        
    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Create router with auth prefix and tags
router = APIRouter(prefix="", tags=["Authentication"])

# ===== Request/Response Models =====

class ResetPasswordRequest(BaseModel):
    email: EmailStr

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    verification_code: str
    new_password: str

class OAuthSignupResponse(BaseModel):
    message: str
    email: str
    verification_required: bool = True

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    scopes={
        "student": "Read access to student resources",
        "teacher": "Read and write access to teacher resources",
        "admin": "Admin access"
    }
)

# ===== Authentication Functions =====

def get_current_user(security_scopes: SecurityScopes, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get the current user from the token and verify required scopes.
    """
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = 'Bearer'
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_scopes = payload.get("scopes", [])
        token_data = {"sub": user_id, "scopes": token_scopes}
    except (JWTError, ValidationError):
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    
    # Verify scopes if any are required
    if security_scopes.scopes:
        for scope in security_scopes.scopes:
            if scope not in token_data["scopes"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not enough permissions",
                    headers={"WWW-Authenticate": authenticate_value},
                )
    
    return user

def get_current_active_user(current_user: models.User = Security(get_current_user, scopes=[])):
    """
    Get the current active user (no specific scopes required).
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_user_payload(token: str = Depends(oauth2_scheme)):
    """
    Get the current user's payload from the token.
    
    Args:
        token: JWT token from the Authorization header
        
    Returns:
        Dict: Decoded token payload
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ===== OAuth Endpoints =====

@router.post("/signup")
async def signup(user_data: UserCreate):
    """Create a new user with email verification"""
    db = next(get_db())
    try:
        print(f"=== New signup: {user_data.email} ===")

        # Check if email already exists
        if db.query(User).filter(User.email == user_data.email).first():
            db.close()
            raise HTTPException(status_code=400, detail="Email already registered")
            
        # Check if there's already an OAuth credential with this email
        existing_oauth = db.query(OAuthCredential).filter(OAuthCredential.email == user_data.email).first()
        if existing_oauth and existing_oauth.is_verified:
            db.close()
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash the password
        print("Hashing password...")
        hashed_password = hash_password(user_data.password)
        print(f"Hashed password: {hashed_password}")

        # Generate verification code
        verification_code = ''.join(secrets.choice('0123456789') for _ in range(6))
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        # Get firstname and lastname
        firstname = getattr(user_data, 'firstname', '')
        lastname = getattr(user_data, 'lastname', '')
        
        if (not firstname or not lastname) and hasattr(user_data, 'full_name') and user_data.full_name:
            parts = user_data.full_name.strip().split()
            firstname = parts[0]
            lastname = ' '.join(parts[1:]) if len(parts) > 1 else ''

        # Store in OAuthCredential table with verification code
        if existing_oauth:
            # Update existing unverified credential
            existing_oauth.password_hash = hashed_password
            existing_oauth.firstname = firstname
            existing_oauth.lastname = lastname
            existing_oauth.verification_code = verification_code
            existing_oauth.code_expires_at = expires_at
            existing_oauth.is_verified = False
            oauth_cred = existing_oauth
        else:
            # Create new OAuth credential
            oauth_cred = OAuthCredential(
                email=user_data.email,
                password_hash=hashed_password,
                firstname=firstname,
                lastname=lastname,
                verification_code=verification_code,
                code_expires_at=expires_at,
                is_verified=False,
                access_token="",  # Will be set after verification
                refresh_token=None
            )
            db.add(oauth_cred)
        
        db.commit()

        print(f"Verification code generated for {user_data.email}: {verification_code}")

        # Send verification email
        email_service = EmailService.get_instance()
        if email_service.is_configured:
            try:
                email_service.send_email(
                    to_email=user_data.email,
                    subject="Verify Your Email",
                    body=f"""
Hello {firstname} {lastname},

Thank you for signing up to our platform.

Your verification code is: {verification_code}

This code will expire in 10 minutes.

Best regards,
Support Team
"""
                )
                print("Verification email sent")
            except Exception as email_error:
                print(f"Error sending verification email: {str(email_error)}")

        return {
            "detail": "Verification email sent",
            "next_step": "/verify",
            "email": user_data.email,
            "verification_code": verification_code  # Only for testing, remove in production
        }

    except HTTPException as he:
        if 'db' in locals():
            db.rollback()
        raise he
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        print(f"Erreur lors de l'inscription: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Une erreur est survenue lors de l'inscription: {str(e)}"
        )
    finally:
        if 'db' in locals():
            db.close()

@router.post(
    "/verify",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "User verified successfully",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 1800,
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "firstname": "John",
                            "lastname": "Doe",
                            "is_active": True
                        },
                        "message": "User verified and registered successfully."
                    }
                }
            }
        },
        400: {
            "description": "Invalid verification code or code expired"
        },
        500: {
            "description": "Internal server error during verification"
        }
    }
)
@router.post("/verify", response_model=dict)
async def verify(verification: VerificationRequest = Body(...)):
    """
    Verify the user's verification code and create their account.
    """
    db = next(get_db())
    try:
        # Find the OAuth credential with the matching email and verification code
        oauth_cred = db.query(OAuthCredential).filter(
            OAuthCredential.email == verification.email,
            OAuthCredential.verification_code == str(verification.verification_code)
        ).first()
        
        if not oauth_cred:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code."
            )
            
        # Check if code is expired
        if oauth_cred.code_expires_at < datetime.utcnow():
            db.delete(oauth_cred)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired. Please sign up again."
            )
            
        # Check if user already exists (shouldn't happen due to previous checks)
        existing_user = db.query(User).filter(User.email == verification.email).first()
        if existing_user:
            # Clean up the OAuth credential since user already exists
            db.delete(oauth_cred)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered. Please log in."
            )
            
        # Create the user
        user = User(
            email=oauth_cred.email,
            password_hash=oauth_cred.password_hash,
            firstname=oauth_cred.firstname or "",
            lastname=oauth_cred.lastname or "",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(user)
        db.flush()  # Flush to get the user ID
        
        # Update OAuth credential with user ID and mark as verified
        oauth_cred.user_id = user.id
        oauth_cred.is_verified = True
        oauth_cred.verification_code = None
        oauth_cred.code_expires_at = None
        
        # Generate access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        
        # Update OAuth credential with access token
        oauth_cred.access_token = access_token
        
        db.commit()
        
        # Return token and user info
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds()),
            "user": {
                "id": user.id,
                "email": user.email,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "is_active": user.is_active
            },
            "message": "User verified and registered successfully."
        }
        
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        print(f"Erreur lors de la vérification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Une erreur est survenue lors de la vérification: {str(e)}"
        )
    finally:
        db.close()

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login, get an access token for future requests
    
    - **username**: Your email address
    - **password**: Your password
    """
    db = next(get_db())
    try:
        print("=== Login Attempt ===")
        print(f"Email: {form_data.username}")
        
        # First check if there's an unverified OAuth credential
        oauth_cred = db.query(OAuthCredential).filter(
            OAuthCredential.email == form_data.username,
            OAuthCredential.is_verified == False
        ).first()
        
        if oauth_cred:
            # If there's an unverified credential, check if the password matches
            if not verify_password(form_data.password, oauth_cred.password_hash):
                print("❌ Invalid email or password")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # If password matches but email not verified
            print("❌ Email not verified")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Please verify your email before logging in. "
                    "Check your email for the verification code or request a new one."
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # If no unverified credential, check regular user
        user = db.query(User).filter(User.email == form_data.username).first()
        
        # Verify user exists and password is correct
        if not user or not verify_password(form_data.password, user.password_hash):
            print("❌ Invalid email or password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            print("❌ Inactive user")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account has been deactivated. Please contact support."
            )
        
        # Update last login timestamp
        print("✅ User authenticated, updating last login")
        user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        
        # Update OAuth credential with new access token if exists
        oauth_cred = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user.id
        ).first()
        
        if oauth_cred:
            oauth_cred.access_token = access_token
            db.commit()
        
        print("✅ Access token created")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds()),
            "user": {
                "id": user.id,
                "email": user.email,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "is_active": user.is_active
            }
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error in login: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during login: {str(e)}"
        )
    finally:
        if 'db' in locals():
            db.close()


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint.
    
    In a production environment, you might want to implement token blacklisting here.
    For now, it's up to the client to delete the token.
    """
    try:
        print(f"✅ User {current_user.email} logged out successfully")
        # Here you could add token blacklisting logic if needed
        # For now, we'll just log the logout and let the client handle token deletion
        return {
            "message": "Successfully logged out. Please delete your access token on the client side.",
            "success": True
        }
    except Exception as e:
        print(f"❌ Error during logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout"
        )

# Password Reset Endpoints
@router.post("/request-password-reset")
async def request_password_reset(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Request a password reset. Sends a verification code to the provided email.
    
    - **email**: The email address to send the reset code to
    """
    try:
        print(f"=== Password reset request for email: {request.email} ===")
        # Use the service to handle the password reset request
        verification_code = PasswordResetService.send_reset_email(request.email, db)
        
        if not verification_code:
            logger.error(f"User not found for email: {request.email}")
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"Password reset email sent to {request.email}")
        return {"message": "Reset email sent successfully", "token": verification_code}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting password reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        )

@router.get("/reset-password")
async def reset_password_page(token: str):
    """
    Password reset page with token in URL.
    
    - **token**: The verification token received in the email
    """
    return HTMLResponse(
        content=f"""
        <html>
            <head>
                <title>Reset Password</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        max-width: 500px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background-color: #f5f5f5;
                        padding: 20px;
                        border-radius: 5px;
                        box-shadow: 0 0 10px rgba(0,0,0,0.1);
                    }}
                    .form-group {{
                        margin-bottom: 15px;
                    }}
                    label {{
                        display: block;
                        margin-bottom: 5px;
                        font-weight: bold;
                    }}
                    input[type="password"] {{
                        width: 100%;
                        padding: 8px;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        box-sizing: border-box;
                        margin-bottom: 10px;
                    }}
                    button {{
                        background-color: #4CAF50;
                        color: white;
                        padding: 10px 15px;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        width: 100%;
                    }}
                    button:hover {{
                        background-color: #45a049;
                    }}
                    .error {{
                        color: #d32f2f;
                        margin-bottom: 15px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Reset Your Password</h1>
                    <form id="resetForm" method="post" action="/auth/reset-password">
                        <input type="hidden" name="token" value="{token}">
                        <div class="form-group">
                            <label for="new_password">New Password:</label>
                            <input type="password" id="new_password" name="new_password" required minlength="8">
                        </div>
                        <div class="form-group">
                            <label for="confirm_password">Confirm New Password:</label>
                            <input type="password" id="confirm_password" name="confirm_password" required minlength="8">
                        </div>
                        <button type="submit" id="submitBtn">Reset Password</button>
                    </form>
                </div>
                <script>
                    document.getElementById('resetForm').addEventListener('submit', function(e) {{
                        const password = document.getElementById('new_password').value;
                        const confirmPassword = document.getElementById('confirm_password').value;
                        
                        if (password !== confirmPassword) {{
                            e.preventDefault();
                            alert('Passwords do not match!');
                            return false;
                        }}
                        
                        if (password.length < 8) {{
                            e.preventDefault();
                            alert('Password must be at least 8 characters long!');
                            return false;
                        }}
                        
                        // Disable the submit button to prevent double submission
                        document.getElementById('submitBtn').disabled = true;
                        return true;
                    }});
                </script>
            </body>
        </html>
        """
    )

@router.post("/reset-password")
async def reset_password_submit(request: Request, db: Session = Depends(get_db)):
    """
    Handle password reset form submission.
    
    - **token**: Verification token from email
    - **new_password**: New password to set
    - **confirm_password**: Confirmation of new password
    """
    try:
        # Get form data
        form_data = await request.form()
        token = form_data.get("token")
        new_password = form_data.get("new_password")
        confirm_password = form_data.get("confirm_password")

        if not all([token, new_password, confirm_password]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields"
            )
            
        if new_password != confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match"
            )
            
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )

        # Find the token in the database to get the associated user
        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()

        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token"
            )
            
        # Get the user
        user = db.query(User).filter(User.user_id == reset_token.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found"
            )

        logger.info(f"Password reset attempt for user ID: {user.user_id}")

        # Reset the password
        success = PasswordResetService.verify_reset_code_and_change_password(
            email=user.email,
            verification_code=token,
            new_password=new_password,
            db=db
        )
        
        if not success:
            logger.error(f"Password reset failed for user ID: {user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset failed"
            )
        
        # Delete the used token
        db.delete(reset_token)
        db.commit()
        
        logger.info(f"Password successfully reset for user ID: {user.user_id}")
        return HTMLResponse(
            content="""
            <html>
                <head>
                    <title>Password Reset Successful</title>
                    <style>
                        body {{ 
                            font-family: Arial, sans-serif; 
                            text-align: center; 
                            padding: 40px 20px;
                        }}
                        .success-message {{
                            max-width: 500px;
                            margin: 0 auto;
                            padding: 20px;
                            background-color: #dff0d8;
                            border: 1px solid #d6e9c6;
                            border-radius: 4px;
                            color: #3c763d;
                        }}
                        a {{
                            color: #3c763d;
                            font-weight: bold;
                            text-decoration: none;
                        }}
                    </style>
                </head>
                <body>
                    <div class="success-message">
                        <h2>Password Reset Successful!</h2>
                        <p>Your password has been successfully updated.</p>
                        <p><a href="/login">Click here to login</a> with your new password.</p>
                    </div>
                </body>
            </html>
            """
        )

    except HTTPException as he:
        logger.error(f"Password reset HTTP error: {str(he)}")
        raise
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting password"
        )
