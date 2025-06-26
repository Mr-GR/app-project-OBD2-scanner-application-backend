from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base

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