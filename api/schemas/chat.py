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
    level: Optional[Literal["beginner", "expert"]] = None
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