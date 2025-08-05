from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base
import secrets
from datetime import datetime, timedelta, timezone

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vehicles = relationship("UserVehicle", back_populates="user")
    diagnostic_sessions = relationship("DiagnosticSession", back_populates="user")
    magic_link_tokens = relationship("MagicLinkToken", back_populates="user")

class UserVehicle(Base):
    __tablename__ = "user_vehicles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vin = Column(String(17), unique=True, index=True)
    make = Column(String(100))
    model = Column(String(100))
    year = Column(Integer)
    vehicle_type = Column(String(100))
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="vehicles")
    diagnostic_sessions = relationship("DiagnosticSession", back_populates="vehicle")

class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("user_vehicles.id"), nullable=True)
    
    # Diagnostic data as JSON
    dtc_codes = Column(JSON)  # ["P0420", "P0171"]
    sensor_data = Column(JSON)  # {"engine_temp": "195F", "rpm": "2500"}
    
    # Session metadata
    session_name = Column(String(255))
    notes = Column(Text)
    session_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="diagnostic_sessions")
    vehicle = relationship("UserVehicle", back_populates="diagnostic_sessions")

# Full Diagnostic Scan Models
class ScanSession(Base):
    __tablename__ = "scan_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("user_vehicles.id"), nullable=True)
    scan_type = Column(String(20))  # 'quick', 'comprehensive', 'emissions', 'custom'
    status = Column(String(20), default='completed')
    vehicle_info = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    vehicle = relationship("UserVehicle")
    trouble_codes = relationship("ScanTroubleCode", back_populates="session", cascade="all, delete-orphan")
    live_parameters = relationship("ScanLiveParameter", back_populates="session", cascade="all, delete-orphan")
    readiness_monitors = relationship("ScanReadinessMonitor", back_populates="session", cascade="all, delete-orphan")

class ScanTroubleCode(Base):
    __tablename__ = "scan_trouble_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("scan_sessions.id"), nullable=False)
    code = Column(String(10), nullable=False)
    description = Column(Text)
    system = Column(String(50))  # "Powertrain", "Body", "Chassis", "Network"
    code_type = Column(String(20), default='active')  # 'active', 'pending', 'permanent'
    severity = Column(String(20))  # "Critical", "Moderate", "Low"
    
    # Relationships
    session = relationship("ScanSession", back_populates="trouble_codes")

class ScanLiveParameter(Base):
    __tablename__ = "scan_live_parameters"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("scan_sessions.id"), nullable=False)
    parameter_name = Column(String(50), nullable=False)
    parameter_value = Column(Text, nullable=False)
    unit = Column(String(20))
    min_value = Column(Float)
    max_value = Column(Float)
    
    # Relationships
    session = relationship("ScanSession", back_populates="live_parameters")

class ScanReadinessMonitor(Base):
    __tablename__ = "scan_readiness_monitors"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("scan_sessions.id"), nullable=False)
    monitor_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # "Ready", "Not Ready", "Not Supported"
    
    # Relationships
    session = relationship("ScanSession", back_populates="readiness_monitors")

class ChatHistory(Base):
    __tablename__ = "chat_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("user_vehicles.id"), nullable=True)
    
    # Chat data
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    level = Column(String(20))  # "beginner" or "expert"
    
    # Context used
    context_data = Column(JSON)  # Store the context that was used
    
    # Metadata
    response_time_ms = Column(Integer)
    classification_method = Column(String(100))
    endpoint_used = Column(String(50))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=False)  # Store email for token validation
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="magic_link_tokens")
    
    @classmethod
    def generate_token(cls) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def create_expires_at(cls) -> datetime:
        """Create expiration time (15 minutes from now)"""
        return datetime.now(timezone.utc) + timedelta(minutes=15)
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        current_time = datetime.now(timezone.utc)
        # Handle both timezone-aware and timezone-naive datetimes
        if self.expires_at.tzinfo is None:
            current_time = current_time.replace(tzinfo=None)
        return current_time > self.expires_at
    
    def is_used(self) -> bool:
        """Check if token has been used"""
        return self.used_at is not None