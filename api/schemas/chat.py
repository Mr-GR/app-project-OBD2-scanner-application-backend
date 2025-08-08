from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

class DiagnosticContext(BaseModel):
    vin: Optional[str] = None
    dtc_codes: Optional[List[str]] = None
    sensor_data: Optional[Dict[str, Any]] = None
    vehicle_info: Optional[Dict[str, str]] = None

class ChatRequest(BaseModel):
    message: str
    context: Optional[DiagnosticContext] = None
    include_diagnostics: bool = False

class ChatMessage(BaseModel):
    content: str
    format: Literal["markdown", "plain"] = "markdown"
    timestamp: datetime
    message_type: Literal["user", "assistant", "diagnostic", "error"]
    context: Optional[DiagnosticContext] = None

class ChatResponse(BaseModel):
    message: ChatMessage
    diagnostic_data: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None

# Chat Persistence Schemas
class ConversationCreate(BaseModel):
    title: str
    context: Optional[DiagnosticContext] = None

class ConversationUpdate(BaseModel):
    title: Optional[str] = None

class MessageCreate(BaseModel):
    content: str
    message_type: Literal["user", "assistant", "diagnostic", "error"]
    format: Literal["markdown", "plain"] = "markdown"
    context: Optional[DiagnosticContext] = None
    suggestions: Optional[List[str]] = None

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    content: str
    message_type: str
    format: str
    context: Optional[DiagnosticContext] = None
    suggestions: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    title: str
    context: Optional[DiagnosticContext] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: Optional[List[MessageResponse]] = None

    class Config:
        from_attributes = True