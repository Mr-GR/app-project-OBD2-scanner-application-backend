# api/routers/auth.py
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from db.database import get_db
from db.models import User, MagicLinkToken
from api.schemas.auth import (
    MagicLinkRequest, 
    MagicLinkResponse, 
    VerifyTokenRequest,
    AuthTokenResponse, 
    UserInfo,
    AuthStatus,
    LogoutResponse
)
from api.utils.auth import AuthUtils, get_current_user, get_optional_user, is_valid_email, rate_limiter
from api.utils.email import email_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/auth/request-magic-link", response_model=MagicLinkResponse)
async def request_magic_link(
    request: MagicLinkRequest,
    db: Session = Depends(get_db)
):
    """
    Request a magic link for authentication
    
    This endpoint:
    1. Validates the email address
    2. Checks rate limiting
    3. Creates or gets existing user
    4. Generates a secure token
    5. Sends magic link email
    """
    try:
        # Validate email format
        if not is_valid_email(request.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email address format"
            )
        
        # Check rate limiting
        if not rate_limiter.is_allowed(request.email):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many magic link requests. Please wait 5 minutes."
            )
        
        # Get or create user
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            # Create new user
            user = User(
                email=request.email,
                name=request.name
            )
            db.add(user)
            try:
                db.commit()
                db.refresh(user)
                logger.info(f"Created new user: {request.email}")
            except IntegrityError:
                db.rollback()
                # Handle race condition - user might have been created by another request
                user = db.query(User).filter(User.email == request.email).first()
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Error creating user account"
                    )
        
        # Invalidate any existing tokens for this user
        db.query(MagicLinkToken).filter(
            MagicLinkToken.user_id == user.id,
            MagicLinkToken.used_at.is_(None)
        ).update({"used_at": datetime.now(timezone.utc)})
        
        # Generate new magic link token
        token = MagicLinkToken.generate_token()
        expires_at = MagicLinkToken.create_expires_at()
        
        magic_token = MagicLinkToken(
            user_id=user.id,
            token=token,
            email=request.email,
            expires_at=expires_at
        )
        
        db.add(magic_token)
        db.commit()
        
        # Send magic link email
        email_sent = email_service.send_magic_link(
            email=request.email,
            name=user.name,
            token=token
        )
        
        if not email_sent:
            logger.error(f"Failed to send magic link email to {request.email}")
            # Don't fail the request - token is still valid
            # User can still use the token if they get it through logs in dev mode
        
        logger.info(f"Magic link requested for user: {request.email}")
        
        return MagicLinkResponse(
            success=True,
            message="Magic link sent to your email address",
            email=request.email,
            expires_in_minutes=15
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in request_magic_link: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/auth/verify")
async def verify_magic_link_redirect(
    token: str = Query(..., description="Magic link token"),
    db: Session = Depends(get_db)
):
    """
    Verify magic link token and redirect to frontend with auth token
    
    This endpoint is called when user clicks the magic link in their email.
    It verifies the token and redirects to the frontend with an auth token.
    """
    try:
        # Verify the magic link token
        auth_response = await verify_token_internal(token, db)
        
        # Redirect to frontend with the JWT token
        frontend_url = email_service.frontend_url
        redirect_url = f"{frontend_url}/auth/callback?token={auth_response.access_token}"
        
        return RedirectResponse(url=redirect_url, status_code=302)
        
    except HTTPException as e:
        # Redirect to frontend with error
        frontend_url = email_service.frontend_url
        error_url = f"{frontend_url}/auth/error?message={e.detail}"
        return RedirectResponse(url=error_url, status_code=302)

@router.post("/auth/verify-token", response_model=AuthTokenResponse)
async def verify_token(
    request: VerifyTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Verify magic link token and return JWT token
    
    This endpoint is for direct API access (mobile apps, etc.)
    """
    return await verify_token_internal(request.token, db)

async def verify_token_internal(token: str, db: Session) -> AuthTokenResponse:
    """Internal function to verify token and return auth response"""
    try:
        # Find the magic link token
        magic_token = db.query(MagicLinkToken).filter(
            MagicLinkToken.token == token
        ).first()
        
        if not magic_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired magic link"
            )
        
        # Check if token is expired
        if magic_token.is_expired():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Magic link has expired"
            )
        
        # Check if token has been used
        if magic_token.is_used():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Magic link has already been used"
            )
        
        # Get the user
        user = db.query(User).filter(User.id == magic_token.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Mark token as used
        magic_token.used_at = datetime.now(timezone.utc)
        db.commit()
        
        # Generate JWT token
        user_data = {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
        
        jwt_token = AuthUtils.generate_jwt_token(user_data)
        
        logger.info(f"User authenticated successfully: {user.email}")
        
        return AuthTokenResponse(
            success=True,
            message="Authentication successful",
            access_token=jwt_token,
            token_type="bearer",
            expires_in_hours=168,  # 7 days
            user=UserInfo(
                id=user.id,
                email=user.email,
                name=user.name,
                created_at=user.created_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in verify_token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/auth/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    
    Requires: Authorization: Bearer <jwt_token>
    """
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        created_at=current_user.created_at
    )

@router.get("/auth/status", response_model=AuthStatus)
async def get_auth_status(
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get current authentication status
    
    Optional authentication - returns user info if authenticated, null if not
    """
    if current_user:
        return AuthStatus(
            authenticated=True,
            user=UserInfo(
                id=current_user.id,
                email=current_user.email,
                name=current_user.name,
                created_at=current_user.created_at
            )
        )
    else:
        return AuthStatus(authenticated=False)

@router.post("/auth/logout", response_model=LogoutResponse)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout current user
    
    Note: With JWT tokens, logout is primarily handled on the client side
    by removing the token. This endpoint is here for completeness and logging.
    """
    logger.info(f"User logged out: {current_user.email}")
    
    return LogoutResponse(
        success=True,
        message="Logged out successfully"
    )

# Debug endpoint (remove in production)
@router.get("/auth/debug/tokens")
async def debug_list_tokens(db: Session = Depends(get_db)):
    """Debug endpoint to list recent magic link tokens"""
    import os
    if os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(status_code=404, detail="Not found")
    
    tokens = db.query(MagicLinkToken).order_by(MagicLinkToken.created_at.desc()).limit(10).all()
    
    return [
        {
            "id": token.id,
            "email": token.email,
            "token": token.token,
            "expires_at": token.expires_at,
            "used_at": token.used_at,
            "is_expired": token.is_expired(),
            "is_used": token.is_used()
        }
        for token in tokens
    ]