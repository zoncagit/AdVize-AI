from datetime import datetime, timedelta
import logging
import random
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import OAuthCredential
from app.models import User
from app.models import PasswordResetToken
from app.schemas import Token, UserCreate
from app.schemas import VerificationRequest

from app.services import EmailService
from app.services import PasswordResetService
from app.services import get_current_user
from app.utils.password import hash_password

from fastapi import Form
from fastapi import APIRouter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router with auth prefix and tags
router = APIRouter(prefix="", tags=["Authentication"])

class ResetPasswordRequest(BaseModel):
    email: EmailStr

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    verification_code: str
    new_password: str

@router.post("/signup")
async def signup(user_data: UserCreate):
    """Crée un nouvel utilisateur avec vérification automatique"""
    db = next(get_db())
    try:
        print(f"=== Nouvelle inscription: {user_data.email} ===")

        # Vérifier si l'email existe déjà
        if db.query(User).filter(User.email == user_data.email).first():
            db.close()
            raise HTTPException(status_code=400, detail="Cette adresse email est déjà utilisée")

        # Hasher le mot de passe
        print("Hachage du mot de passe...")
        hashed_password = hash_password(user_data.password)
        print(f"Mot de passe haché: {hashed_password}")

        # Créer un code de vérification
        verification_code = str(random.randint(100000, 999999))
        expires_at = datetime.now() + timedelta(minutes=10)

        # Si firstname/lastname sont vides mais un champ full_name existe (pour compat), on split
        firstname = getattr(user_data, 'firstname', None)
        lastname = getattr(user_data, 'lastname', None)
        if (not firstname or not lastname) and hasattr(user_data, 'full_name') and user_data.full_name:
            parts = user_data.full_name.strip().split()
            firstname = parts[0]
            lastname = ' '.join(parts[1:]) if len(parts) > 1 else ''
        # Sinon on garde ce qui est fourni
        else:
            firstname = firstname or ''
            lastname = lastname or ''

        # (Removed) Stockage des données de pré-vérification dans la base de données
        print(f"Code de vérification généré pour {user_data.email}: {verification_code}")

        # Envoyer l'email de vérification
        email_service = EmailService.get_instance()
        if email_service.is_configured:
            try:
                email_service.send_email(
                    to_email=user_data.email,
                    subject="Vérifiez votre email",
                    body=f"""
Bonjour {firstname} {lastname},

Merci de vous être inscrit sur notre plateforme.

Votre code de vérification est : {verification_code}

Ce code expirera dans 10 minutes.

Cordialement,
L'équipe de support
"""
                )
                print("Email de vérification envoyé")
            except Exception as email_error:
                print(f"Erreur lors de l'envoi de l'email de vérification: {str(email_error)}")

        return {
            "detail": "Email de vérification envoyé",
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
                        "user": {
                            "email": "user@example.com",
                            "name": "John",
                            "prenom": "Doe",
                            "role": "student"
                        }
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
    Verify the verification code only. Accepts any non-empty code for demo.
    """
    print("=== Verification Attempt ===")
    print(f"Verification code: {verification.verification_code}")
    if verification.verification_code:
        return {"detail": "Code de vérification accepté"}
    else:
        raise HTTPException(status_code=400, detail="Code de vérification invalide")

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
        
        # Find user by email (username in OAuth2PasswordRequestForm is the email)
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
                detail="Inactive user"
            )
            
        # Check if user is verified
        if not user.is_verified:
            print("❌ Email not verified")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before logging in. Check your email for the verification code.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last login timestamp
        print("✅ User authenticated, updating last login")
        user.last_login = func.now()
        db.commit()
        db.refresh(user)
        
        # Create access token with appropriate scopes based on user role
        access_token = create_user_access_token(user)
        print("✅ Access token created")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "firstname": user.firstname,
                "lastname": user.lastname
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


from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

from app.config import database_settings
from app.models import User

# Use settings from database configuration
settings = database_settings
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT token with the given data.
    
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
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_user_access_token(user: User) -> str:
   
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(
        data={
            "sub": str(user.user_id),
            "email": user.email,
            
        },
        expires_delta=access_token_expires
    )

def verify_access_token(token: str) -> Dict:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Dict: Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception

def get_user_id_from_token(token: str) -> int:
    """
    Extract the user ID from a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        int: User ID from the token
        
    Raises:
        HTTPException: If token is invalid or doesn't contain a user ID
    """
    try:
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return int(user_id)
    except (JWTError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user_payload(token: str = Depends(OAuth2PasswordBearer(tokenUrl="login"))) -> Dict:
    """
    Get the current user's payload from the token.
    
    Args:
        token: JWT token from the Authorization header
        
    Returns:
        Dict: Decoded token payload
    """
    return verify_access_token(token)

from typing import List, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    scopes={
        "student": "Read access to student resources",
        "teacher": "Read and write access to teacher resources",
        "admin": "Admin access"
    }
)

def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Get the current user from the token and verify required scopes.
    """
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope=\"{security_scopes.scope_str}\"'
    else:
        authenticate_value = "Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        payload = verify_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_scopes = payload.get("scopes", [])
        token_data = {"sub": user_id, "scopes": token_scopes}
    except (JWTError, ValidationError):
        raise credentials_exception

    user = db.query(models.User).filter(models.User.user_id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    # Check scopes
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user

def get_current_active_user(
    current_user: models.User = Security(get_current_user, scopes=[])
) -> models.User:
    """
    Get the current active user (no specific scopes required).
    """
    return current_user