# api/schemas/auth.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class MagicLinkRequest(BaseModel):
    """Request schema for magic link generation"""
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User's name (for new users)")

class MagicLinkResponse(BaseModel):
    """Response schema for magic link request"""
    success: bool
    message: str
    email: str
    expires_in_minutes: int = 15

class VerifyTokenRequest(BaseModel):
    """Request schema for token verification"""
    token: str = Field(..., description="Magic link token")

class AuthTokenResponse(BaseModel):
    """Response schema for successful authentication"""
    success: bool
    message: str
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = 168  # 7 days
    user: "UserInfo"

class UserInfo(BaseModel):
    """User information schema"""
    id: int
    email: str
    name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class AuthStatus(BaseModel):
    """Current authentication status"""
    authenticated: bool
    user: Optional[UserInfo] = None

class LogoutResponse(BaseModel):
    """Response schema for logout"""
    success: bool
    message: str

# Update forward references
AuthTokenResponse.model_rebuild()