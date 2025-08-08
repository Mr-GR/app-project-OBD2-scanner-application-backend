from fastapi import APIRouter, HTTPException, Depends
import requests
import os
import re
import time
import hashlib
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from api.schemas.chat import (
    ChatRequest, ChatResponse, ChatMessage, DiagnosticContext,
    ConversationCreate, ConversationUpdate, MessageCreate,
    MessageResponse, ConversationResponse
)
from api.utils.dtc import get_code_description
from api.utils.auth import get_current_user
from api.utils.orchestrator import DiagnosticOrchestrator
from db.database import get_db
from db.models import User
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
NHTSA_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"

# In-memory cache for classification results
classification_cache = {}
CACHE_MAX_SIZE = 10000
CACHE_TTL = 3600  # 1 hour

def instant_classification(question: str) -> Optional[Tuple[bool, str]]:
    """
    Tier 1: Instant classification for obvious cases
    Returns (is_automotive, reason) or None if needs further classification
    """
    question_lower = question.lower()
    question_upper = question.upper()
    
    # High confidence automotive cases
    # DTC codes - definitely automotive
    dtc_pattern = r'\b[PBCU][0-9A-F]{4}\b'
    if re.search(dtc_pattern, question_upper):
        return True, "dtc_code_detected"
    
    # DTC prefixes
    dtc_prefixes = ["P0", "P1", "P2", "P3", "B0", "B1", "B2", "B3", "C0", "C1", "C2", "C3", "U0", "U1", "U2", "U3"]
    if any(prefix in question_upper for prefix in dtc_prefixes):
        return True, "dtc_prefix_detected"
    
    # Obvious automotive terms
    high_confidence_automotive = [
        "check engine", "trouble code", "dtc", "obd2", "diagnostic", "engine", "transmission",
        "brake", "coolant", "alternator", "starter", "battery", "airbag", "abs", "ecu",
        "vehicle", "car", "truck", "automotive", "mechanic", "repair", "maintenance"
    ]
    
    if any(term in question_lower for term in high_confidence_automotive):
        return True, "automotive_keyword_detected"
    
    # High confidence non-automotive cases
    non_automotive = [
        "weather", "cooking", "recipe", "sports", "politics", "news", "music", "movie",
        "tv show", "celebrity", "fashion", "travel", "hotel", "restaurant", "food",
        "programming", "software", "computer", "phone", "social media", "dating",
        "relationship", "health", "medicine", "doctor", "hospital", "school", "education"
    ]
    
    if any(term in question_lower for term in non_automotive):
        return False, "non_automotive_keyword_detected"
    
    # If question is very short and ambiguous, require context
    if len(question.strip()) < 3:
        return False, "too_short_ambiguous"
    
    return None  # Needs further classification

async def llm_classification(question: str) -> bool:
    """
    Tier 2: LLM-based classification for edge cases
    """
    classification_prompt = f"""You are a classification system. Determine if the following question is related to automotive, vehicle maintenance, car repair, or mechanical issues.

Respond with ONLY "YES" or "NO".

Examples:
- "P0420" -> YES
- "How do I bake a cake?" -> NO  
- "My engine is overheating" -> YES
- "What's the weather?" -> NO
- "transmission slipping" -> YES
- "best pizza recipe" -> NO

Question: {question}"""

    try:
        response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {TOGETHER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/Mistral-7B-Instruct-v0.1",
                "messages": [
                    {"role": "user", "content": classification_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 5
            }
        )
        result = response.json()["choices"][0]["message"]["content"].strip()
        return result.upper() == "YES"
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return False  # Fallback to safe default

def clean_cache():
    """Remove old cache entries to prevent memory bloat"""
    global classification_cache
    current_time = time.time()
    
    # Remove expired entries
    expired_keys = [
        key for key, (_, timestamp, _) in classification_cache.items()
        if current_time - timestamp > CACHE_TTL
    ]
    
    for key in expired_keys:
        del classification_cache[key]
    
    # If still too large, remove oldest entries
    if len(classification_cache) > CACHE_MAX_SIZE:
        sorted_items = sorted(
            classification_cache.items(), 
            key=lambda x: x[1][1]  # Sort by timestamp
        )
        # Keep only the newest 80% of entries
        keep_count = int(CACHE_MAX_SIZE * 0.8)
        classification_cache = dict(sorted_items[-keep_count:])

async def hybrid_classification(question: str, context: DiagnosticContext = None) -> Tuple[bool, str, float]:
    """
    Hybrid classification system with caching
    Returns (is_automotive, classification_method, processing_time)
    """
    start_time = time.time()
    
    # If we have diagnostic context, it's definitely automotive
    if context and (context.dtc_codes or context.vin or context.vehicle_info):
        processing_time = time.time() - start_time
        return True, "diagnostic_context_present", processing_time
    
    # Tier 1: Instant classification
    instant_result = instant_classification(question)
    if instant_result is not None:
        is_automotive, reason = instant_result
        processing_time = time.time() - start_time
        return is_automotive, f"instant_{reason}", processing_time
    
    # Tier 2: Check cache
    cache_key = hashlib.md5(question.lower().encode()).hexdigest()
    current_time = time.time()
    
    if cache_key in classification_cache:
        cached_result, timestamp, method = classification_cache[cache_key]
        if current_time - timestamp < CACHE_TTL:
            processing_time = time.time() - start_time
            return cached_result, f"cached_{method}", processing_time
    
    # Tier 3: LLM classification
    llm_result = await llm_classification(question)
    
    # Cache the result
    classification_cache[cache_key] = (llm_result, current_time, "llm_classification")
    
    # Clean cache periodically
    if len(classification_cache) % 100 == 0:
        clean_cache()
    
    processing_time = time.time() - start_time
    return llm_result, "llm_classification", processing_time

# Legacy function for backwards compatibility
async def is_mechanic_question(question: str) -> bool:
    """Legacy wrapper for backwards compatibility"""
    is_automotive, _, _ = await hybrid_classification(question)
    return is_automotive

def format_diagnostic_context(context: DiagnosticContext) -> str:
    """Format diagnostic context for LLM prompt"""
    context_parts = []
    
    if context.vehicle_info:
        vehicle = f"{context.vehicle_info.get('year', '')} {context.vehicle_info.get('make', '')} {context.vehicle_info.get('model', '')}"
        context_parts.append(f"Vehicle: {vehicle.strip()}")
    
    if context.vin:
        context_parts.append(f"VIN: {context.vin}")
    
    if context.dtc_codes:
        codes_with_desc = []
        for code in context.dtc_codes:
            desc = get_code_description(code)
            codes_with_desc.append(f"{code}: {desc}")
        context_parts.append(f"Active DTC Codes: {', '.join(codes_with_desc)}")
    
    if context.sensor_data:
        sensor_info = []
        for key, value in context.sensor_data.items():
            sensor_info.append(f"{key}: {value}")
        context_parts.append(f"Sensor Data: {', '.join(sensor_info)}")
    
    return "\n".join(context_parts) if context_parts else ""

def get_vehicle_info_from_vin(vin: str) -> Dict[str, str]:
    """Get vehicle information from VIN"""
    try:
        r = requests.get(NHTSA_URL.format(vin=vin), timeout=5)
        r.raise_for_status()
        vin_data = r.json()["Results"][0]
        return {
            "make": vin_data.get("Make", "Unknown"),
            "model": vin_data.get("Model", "Unknown"),
            "year": vin_data.get("ModelYear", "Unknown"),
            "vehicle_type": vin_data.get("VehicleType", "Unknown"),
        }
    except Exception:
        return {}

def generate_enhanced_system_prompt(context: DiagnosticContext = None) -> str:
    """Generate system prompt with diagnostic context"""
    base_prompt = """You are a master mechanic with decades of experience working on all types of vehicles. You ONLY answer mechanical and automotive questions.

Provide clear, helpful explanations that are informative yet accessible. Explain technical terms when needed, focus on practical steps, and always prioritize safety by recommending professional help for complex or dangerous tasks."""

    if context:
        diagnostic_info = format_diagnostic_context(context)
        if diagnostic_info:
            base_prompt += f"""

CURRENT DIAGNOSTIC CONTEXT:
{diagnostic_info}

Use this specific diagnostic information to provide targeted advice for this exact vehicle and situation."""

    format_instructions = """

Always structure your responses in proper markdown format:

# Vehicle Diagnosis

## Current Issue Analysis
[Analysis of the problem based on provided context]

## What This Means
[Clear explanation of the issue and its implications]

## Troubleshooting Steps
1. [Step with clear explanation]
2. [Another step]
3. [Continue with steps]

## Important Safety Information
[Safety warnings and precautions]

## When to Seek Professional Help
[When to contact a mechanic or professional service]

Use proper markdown formatting with headers, lists, and emphasis."""

    return base_prompt + format_instructions

@router.post("/chat", response_model=ChatResponse)
async def chat_with_context(request: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Enhanced chat endpoint with automatic vehicle context"""
    
    # Get primary vehicle for current user
    from db.models import UserVehicle
    primary_vehicle = db.query(UserVehicle).filter(
        UserVehicle.user_id == current_user.id,
        UserVehicle.is_primary == True
    ).first()
    
    # Use provided context or auto-fill from primary vehicle
    context_to_use = request.context
    if not context_to_use and primary_vehicle:
        # Auto-create context from primary vehicle
        context_to_use = DiagnosticContext(
            vin=primary_vehicle.vin,
            vehicle_info={
                "make": primary_vehicle.make or "Unknown",
                "model": primary_vehicle.model or "Unknown", 
                "year": str(primary_vehicle.year) if primary_vehicle.year else "Unknown",
                "vehicle_type": primary_vehicle.vehicle_type or "Unknown"
            }
        )
    
    # Use hybrid classification system
    is_automotive, classification_method, processing_time = await hybrid_classification(
        request.message, 
        context_to_use
    )
    
    # Log classification metrics
    logger.info({
        "endpoint": "chat",
        "question_length": len(request.message),
        "is_automotive": is_automotive,
        "classification_method": classification_method,
        "processing_time_ms": round(processing_time * 1000, 2),
        "has_context": context_to_use is not None,
        "has_primary_vehicle": primary_vehicle is not None,
        "auto_context": request.context is None and primary_vehicle is not None,
        "level": "context_based"
    })
    
    if not is_automotive:
        message = ChatMessage(
            content=f"""# Automotive Assistant

I'm a master mechanic specializing in automotive and vehicle diagnostics. I can help you with:

- **Diagnostic trouble codes** (P0420, B1234, etc.)
- **Engine problems** and performance issues  
- **Vehicle maintenance** schedules and procedures
- **OBD2 scanning** and diagnostics
- **Brake, transmission, electrical** issues
- **Check engine lights** and warning indicators

Please ask me questions related to car repairs, diagnostics, or vehicle maintenance.

*Classification: {classification_method} ({round(processing_time * 1000, 2)}ms)*""",
            format="markdown",
            timestamp=datetime.now(),
            message_type="assistant"
        )
        return ChatResponse(message=message)
    
    try:
        # Use the context we determined earlier (either provided or auto-generated from primary vehicle)
        enhanced_context = context_to_use
        
        # If we have a VIN but no vehicle info, look it up
        if enhanced_context and enhanced_context.vin and not enhanced_context.vehicle_info:
            vehicle_info = get_vehicle_info_from_vin(enhanced_context.vin)
            if vehicle_info:
                enhanced_context.vehicle_info = vehicle_info

        # Generate system prompt with context
        system_prompt = generate_enhanced_system_prompt(enhanced_context)
        
        # Create user prompt
        user_prompt = f"Question: {request.message}"
        
        # Call LLM
        llm_response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {TOGETHER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/Mistral-7B-Instruct-v0.1",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 1000
            }
        )

        result = llm_response.json()
        answer = result["choices"][0]["message"]["content"]

        # Create response message
        message = ChatMessage(
            content=answer,
            format="markdown",
            timestamp=datetime.now(),
            message_type="assistant",
            context=enhanced_context
        )

        # Prepare diagnostic data if context provided
        diagnostic_data = None
        if enhanced_context:
            diagnostic_data = {
                "vehicle_info": enhanced_context.vehicle_info,
                "dtc_codes": enhanced_context.dtc_codes,
                "sensor_data": enhanced_context.sensor_data,
                "vin": enhanced_context.vin
            }

        # Generate suggestions based on context
        suggestions = []
        if enhanced_context and enhanced_context.dtc_codes:
            suggestions.extend([
                f"Learn more about {code}" for code in enhanced_context.dtc_codes[:3]
            ])
        suggestions.extend([
            "Check related symptoms",
            "Find nearby mechanics",
            "Schedule maintenance reminder"
        ])

        return ChatResponse(
            message=message,
            diagnostic_data=diagnostic_data,
            suggestions=suggestions[:5]  # Limit to 5 suggestions
        )

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        error_message = ChatMessage(
            content=f"# ❌ Error\n\nSorry, I encountered an error processing your request: {str(e)}",
            format="markdown",
            timestamp=datetime.now(),
            message_type="error"
        )
        return ChatResponse(message=error_message)

@router.post("/chat/quick", response_model=ChatResponse)
async def quick_chat(request: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Quick chat endpoint for simple car queries without level requirement"""
    
    # Get primary vehicle for current user
    from db.models import UserVehicle
    primary_vehicle = db.query(UserVehicle).filter(
        UserVehicle.user_id == current_user.id,
        UserVehicle.is_primary == True
    ).first()
    
    # Use provided context or auto-fill from primary vehicle
    context_to_use = request.context
    if not context_to_use and primary_vehicle:
        context_to_use = DiagnosticContext(
            vin=primary_vehicle.vin,
            vehicle_info={
                "make": primary_vehicle.make or "Unknown",
                "model": primary_vehicle.model or "Unknown", 
                "year": str(primary_vehicle.year) if primary_vehicle.year else "Unknown",
                "vehicle_type": primary_vehicle.vehicle_type or "Unknown"
            }
        )
    
    # Use hybrid classification system
    is_automotive, classification_method, processing_time = await hybrid_classification(
        request.message, 
        context_to_use
    )
    
    # Log classification metrics
    logger.info({
        "endpoint": "chat/quick",
        "question_length": len(request.message),
        "is_automotive": is_automotive,
        "classification_method": classification_method,
        "processing_time_ms": round(processing_time * 1000, 2),
        "has_context": context_to_use is not None,
        "has_primary_vehicle": primary_vehicle is not None
    })
    
    if not is_automotive:
        message = ChatMessage(
            content=f"""I'm an automotive assistant that helps with car-related questions. Please ask me about:

• Diagnostic trouble codes (P0420, B1234, etc.)
• Engine and performance issues
• Vehicle maintenance and repairs
• OBD2 diagnostics
• Check engine lights and warning indicators

*Not automotive: {classification_method} ({round(processing_time * 1000, 2)}ms)*""",
            format="markdown",
            timestamp=datetime.now(),
            message_type="assistant"
        )
        return ChatResponse(message=message)

    try:
        # Use beginner-friendly system prompt for quick responses
        enhanced_context = context_to_use
        
        # If we have a VIN but no vehicle info, look it up
        if enhanced_context and enhanced_context.vin and not enhanced_context.vehicle_info:
            vehicle_info = get_vehicle_info_from_vin(enhanced_context.vin)
            if vehicle_info:
                enhanced_context.vehicle_info = vehicle_info

        # Simple system prompt for quick responses
        system_prompt = """You are a helpful automotive assistant. Provide clear, concise answers to car-related questions. Keep responses brief but informative. Use simple language and focus on practical advice."""
        
        if enhanced_context:
            diagnostic_info = format_diagnostic_context(enhanced_context)
            if diagnostic_info:
                system_prompt += f"\n\nVehicle Context:\n{diagnostic_info}"
        
        # Create user prompt
        user_prompt = f"Quick question: {request.message}"
        
        # Call LLM with shorter max tokens for quick responses
        llm_response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {TOGETHER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/Mistral-7B-Instruct-v0.1",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500  # Shorter responses for quick queries
            }
        )

        result = llm_response.json()
        answer = result["choices"][0]["message"]["content"]

        # Create response message
        message = ChatMessage(
            content=answer,
            format="markdown",
            timestamp=datetime.now(),
            message_type="assistant",
            context=enhanced_context
        )

        # Generate simple suggestions for quick chat
        suggestions = [
            "Ask about symptoms",
            "Check maintenance schedule", 
            "Find related issues"
        ]

        return ChatResponse(
            message=message,
            suggestions=suggestions
        )

    except Exception as e:
        logger.error(f"Quick chat endpoint error: {e}")
        error_message = ChatMessage(
            content=f"Sorry, I encountered an error: {str(e)}",
            format="plain",
            timestamp=datetime.now(),
            message_type="error"
        )
        return ChatResponse(message=error_message)

@router.post("/chat/analyze-vehicle")
async def analyze_vehicle_diagnostics(request: dict):
    """AI analysis endpoint for vehicle diagnostics data"""
    try:
        vehicle_data = request.get('vehicle_data', {})
        live_data = vehicle_data.get('live_data', {})
        trouble_codes = vehicle_data.get('trouble_codes', [])
        connection_status = vehicle_data.get('connection_status', False)
        device_name = vehicle_data.get('device_name', 'Unknown')
        
        # Build AI analysis prompt with VIN data
        vin_info = ""
        if live_data.get('vin'):
            vin_info = f"VIN: {live_data.get('vin')}"
            
            # Try to get vehicle info from VIN
            try:
                vehicle_info = get_vehicle_info_from_vin(live_data.get('vin'))
                if vehicle_info and vehicle_info.get('make', 'Unknown') != 'Unknown':
                    vin_info += f"\nVehicle: {vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')}"
            except Exception as e:
                logger.warning(f"Could not get vehicle info from VIN: {e}")
        
        analysis_prompt = f"""You are a master automotive technician. Analyze this vehicle diagnostic data and provide detailed insights:

CONNECTION STATUS: {"✅ Connected" if connection_status else "❌ Disconnected"} - Device: {device_name}

{f"VEHICLE INFORMATION:\\n{vin_info}\\n" if vin_info else ""}
LIVE DATA:
- Engine RPM: {live_data.get('rpm', 'N/A')}
- Vehicle Speed: {live_data.get('speed', 'N/A')} mph
- Engine Temperature: {live_data.get('engine_temp', 'N/A')}°C
- Fuel Level: {live_data.get('fuel_level', 'N/A')}%
- Throttle Position: {live_data.get('throttle_position', 'N/A')}%

TROUBLE CODES:
{chr(10).join([f"- {code['code']}: {code['description']}" for code in trouble_codes]) if trouble_codes else "No active trouble codes detected"}

Please provide a comprehensive analysis including:
1. 🔍 Overall Vehicle Health Assessment
2. ⚠️ Problem Analysis (if any issues found)
3. 🔧 Recommended Actions
4. 💡 Maintenance Suggestions
5. 🚨 Priority Level (High/Medium/Low)

{f"Consider the specific vehicle make/model when providing recommendations." if vin_info else ""}

Format your response in markdown with clear sections and actionable advice."""

        # Call LLM for analysis
        if not TOGETHER_API_KEY:
            return {
                "response": "🤖 **AI Analysis Feature**\n\nAI analysis is currently unavailable. Please configure the TOGETHER_API_KEY environment variable to enable this feature.\n\n**Current Status:**\n- Connection: " + ("✅ Connected" if connection_status else "❌ Disconnected") + f"\n- Device: {device_name}\n- Live Data: {'Available' if live_data else 'No data'}\n- Trouble Codes: {len(trouble_codes)} active",
                "status": "success"
            }
        
        llm_response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {TOGETHER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/Mistral-7B-Instruct-v0.1",
                "messages": [
                    {"role": "system", "content": "You are a master automotive technician providing detailed vehicle diagnostics analysis."},
                    {"role": "user", "content": analysis_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 1500
            }
        )
        
        result = llm_response.json()
        ai_analysis = result["choices"][0]["message"]["content"]
        
        return {
            "response": ai_analysis,
            "status": "success",
            "metadata": {
                "connection_status": connection_status,
                "device_name": device_name,
                "live_data_points": len([v for v in live_data.values() if v is not None]),
                "trouble_codes_count": len(trouble_codes),
                "vin": live_data.get('vin'),
                "has_vin": bool(live_data.get('vin')),
                "analysis_timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Vehicle analysis error: {e}")
        return {
            "response": f"🔧 **Vehicle Analysis**\n\n❌ **Error**: Unable to analyze vehicle data at this time.\n\n**Details**: {str(e)}\n\n**Suggestion**: Please try again later or contact support if the issue persists.",
            "status": "error"
        }

@router.get("/chat/stats")
async def get_classification_stats():
    """Get classification system statistics for monitoring"""
    current_time = time.time()
    
    # Analyze cache
    total_cached = len(classification_cache)
    expired_count = sum(
        1 for _, (_, timestamp, _) in classification_cache.items()
        if current_time - timestamp > CACHE_TTL
    )
    
    # Get method distribution
    methods = {}
    for _, (_, _, method) in classification_cache.items():
        methods[method] = methods.get(method, 0) + 1
    
    return {
        "cache": {
            "total_entries": total_cached,
            "expired_entries": expired_count,
            "active_entries": total_cached - expired_count,
            "max_size": CACHE_MAX_SIZE,
            "ttl_hours": CACHE_TTL / 3600
        },
        "classification_methods": methods,
        "system_info": {
            "instant_classification_enabled": True,
            "llm_fallback_enabled": bool(TOGETHER_API_KEY),
            "cache_enabled": True
        }
    }

# Chat Persistence Endpoints
@router.post("/chat/conversations", response_model=ConversationResponse)
async def create_conversation(conversation: ConversationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new chat conversation"""
    from db.models import ChatConversation, UserVehicle
    
    try:
        
        # Get primary vehicle if available
        primary_vehicle = db.query(UserVehicle).filter(
            UserVehicle.user_id == current_user.id,
            UserVehicle.is_primary == True
        ).first()
        
        # Create conversation
        db_conversation = ChatConversation(
            user_id=current_user.id,
            vehicle_id=primary_vehicle.id if primary_vehicle else None,
            title=conversation.title,
            context_data=conversation.context.dict() if conversation.context else None
        )
        
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)
        
        return ConversationResponse(
            id=db_conversation.id,
            user_id=db_conversation.user_id,
            vehicle_id=db_conversation.vehicle_id,
            title=db_conversation.title,
            context=DiagnosticContext(**db_conversation.context_data) if db_conversation.context_data else None,
            created_at=db_conversation.created_at,
            updated_at=db_conversation.updated_at
        )
        
    except Exception as e:
        logger.error(f"Create conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create conversation")

@router.get("/chat/conversations", response_model=List[ConversationResponse])
async def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all conversations for the user"""
    from db.models import ChatConversation
    
    try:
        
        conversations = db.query(ChatConversation).filter(
            ChatConversation.user_id == current_user.id
        ).order_by(ChatConversation.updated_at.desc()).all()
        
        result = []
        for conv in conversations:
            result.append(ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                vehicle_id=conv.vehicle_id,
                title=conv.title,
                context=DiagnosticContext(**conv.context_data) if conv.context_data else None,
                created_at=conv.created_at,
                updated_at=conv.updated_at
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Get conversations error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversations")

@router.get("/chat/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a specific conversation with its messages"""
    from db.models import ChatConversation, ChatMessage
    
    try:
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages for this conversation
        messages = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        message_responses = []
        for msg in messages:
            message_responses.append(MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                content=msg.content,
                message_type=msg.message_type,
                format=msg.format_type,
                context=DiagnosticContext(**msg.context_data) if msg.context_data else None,
                suggestions=msg.suggestions,
                created_at=msg.created_at
            ))
        
        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            vehicle_id=conversation.vehicle_id,
            title=conversation.title,
            context=DiagnosticContext(**conversation.context_data) if conversation.context_data else None,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=message_responses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation")

@router.post("/chat/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def save_message(conversation_id: int, message: MessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Save a message to a conversation"""
    from db.models import ChatConversation, ChatMessage
    
    try:
        # Verify conversation exists and belongs to user
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Create message
        db_message = ChatMessage(
            conversation_id=conversation_id,
            content=message.content,
            message_type=message.message_type,
            format_type=message.format,
            context_data=message.context.dict() if message.context else None,
            suggestions=message.suggestions
        )
        
        db.add(db_message)
        
        # Update conversation updated_at timestamp
        conversation.updated_at = func.now()
        
        db.commit()
        db.refresh(db_message)
        
        return MessageResponse(
            id=db_message.id,
            conversation_id=db_message.conversation_id,
            content=db_message.content,
            message_type=db_message.message_type,
            format=db_message.format_type,
            context=DiagnosticContext(**db_message.context_data) if db_message.context_data else None,
            suggestions=db_message.suggestions,
            created_at=db_message.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save message error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save message")

@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a conversation and all its messages"""
    from db.models import ChatConversation
    
    try:
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        db.delete(conversation)
        db.commit()
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")

@router.patch("/chat/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(conversation_id: int, updates: ConversationUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update a conversation (title, experience level)"""
    from db.models import ChatConversation
    
    try:
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Update fields if provided
        if updates.title is not None:
            conversation.title = updates.title
        
        conversation.updated_at = func.now()
        
        db.commit()
        db.refresh(conversation)
        
        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            vehicle_id=conversation.vehicle_id,
            title=conversation.title,
            context=DiagnosticContext(**conversation.context_data) if conversation.context_data else None,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update conversation")

@router.post("/chat/diagnostic")
async def diagnostic_orchestrated_chat(
    request: ChatRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Enhanced diagnostic endpoint using the orchestrator"""
    
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Create orchestrator instance
        orchestrator = DiagnosticOrchestrator(
            session_id=session_id,
            db_session=db,
            user_id=current_user.id
        )
        
        # Get primary vehicle for context
        from db.models import UserVehicle
        primary_vehicle = db.query(UserVehicle).filter(
            UserVehicle.user_id == current_user.id,
            UserVehicle.is_primary == True
        ).first()
        
        # Build vehicle context
        vehicle_context = None
        if primary_vehicle:
            vehicle_context = {
                "vin": primary_vehicle.vin,
                "make": primary_vehicle.make,
                "model": primary_vehicle.model,
                "year": primary_vehicle.year,
                "dtc_codes": [],
                "sensor_data": {}
            }
        
        # Use context from request if provided
        if request.context:
            if vehicle_context:
                # Merge request context with vehicle context
                if request.context.dtc_codes:
                    vehicle_context["dtc_codes"] = request.context.dtc_codes
                if request.context.sensor_data:
                    vehicle_context["sensor_data"] = request.context.sensor_data
                if request.context.vin:
                    vehicle_context["vin"] = request.context.vin
            else:
                # Use request context directly
                vehicle_context = {
                    "vin": request.context.vin,
                    "dtc_codes": request.context.dtc_codes or [],
                    "sensor_data": request.context.sensor_data or {},
                    "vehicle_info": request.context.vehicle_info
                }
                if request.context.vehicle_info:
                    vehicle_context.update({
                        "make": request.context.vehicle_info.get("make"),
                        "model": request.context.vehicle_info.get("model"),
                        "year": request.context.vehicle_info.get("year")
                    })
        
        # Execute diagnostic workflow
        diagnostic_response = await orchestrator.diagnose(
            user_query=request.message,
            vehicle_context=vehicle_context,
            live_data=None  # Could be added from request if needed
        )
        
        # Convert orchestrator response to chat response format
        response_content = f"""# 🔧 Diagnostic Analysis
        
## Diagnostic Plan Executed
        
"""
        
        # Add step results
        for i, step in enumerate(diagnostic_response.steps):
            response_content += f"### Step {step['step']}: {step['action']}\n"
            if step['success']:
                response_content += "✅ **Completed successfully**\n"
                if step.get('data'):
                    # Format key findings
                    data = step['data']
                    if 'dtc_codes' in data and data['dtc_codes']:
                        response_content += f"- **DTC Codes Found:** {', '.join(data['dtc_codes'])}\n"
                    if 'vehicle_specifications' in data:
                        specs = data['vehicle_specifications']
                        response_content += f"- **Vehicle:** {specs.get('year')} {specs.get('make')} {specs.get('model')}\n"
                    if 'knowledge_base_results' in data:
                        response_content += f"- **Knowledge Base:** {data['knowledge_base_results'][:200]}...\n"
            else:
                response_content += f"❌ **Failed:** {step.get('error', 'Unknown error')}\n"
            response_content += "\n"
        
        # Add questions
        if diagnostic_response.questions:
            response_content += "## Follow-up Questions\n"
            for question in diagnostic_response.questions:
                response_content += f"- {question}\n"
            response_content += "\n"
            
        # Add recommendations
        if diagnostic_response.recommendations:
            response_content += "## Recommendations\n"
            for rec in diagnostic_response.recommendations:
                response_content += f"- {rec}\n"
            response_content += "\n"
            
        # Add verification status
        verification = diagnostic_response.verification
        response_content += f"## Verification Status\n"
        response_content += f"- **Status:** {verification.get('status', 'unknown')}\n"
        response_content += f"- **Confidence:** {diagnostic_response.confidence:.1%}\n"
        response_content += f"- **Execution Time:** {verification.get('execution_time', 0):.1f}s\n"
        
        # Create chat message
        message = ChatMessage(
            content=response_content,
            format="markdown",
            timestamp=datetime.now(),
            message_type="diagnostic"
        )
        
        # Build diagnostic data for response
        diagnostic_data = {}
        if vehicle_context:
            diagnostic_data = {
                "vehicle_info": {
                    "make": vehicle_context.get("make"),
                    "model": vehicle_context.get("model"), 
                    "year": vehicle_context.get("year")
                },
                "dtc_codes": vehicle_context.get("dtc_codes", []),
                "session_id": session_id,
                "orchestrator_used": True
            }
        
        return ChatResponse(
            message=message,
            diagnostic_data=diagnostic_data,
            suggestions=diagnostic_response.questions[:3] if diagnostic_response.questions else [
                "Run additional diagnostics",
                "Check vehicle history", 
                "Schedule maintenance"
            ]
        )
        
    except Exception as e:
        logger.error(f"Diagnostic orchestration error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        error_message = ChatMessage(
            content=f"""# ❌ Diagnostic Error

An error occurred during the diagnostic process:

**Error:** {str(e)}

**Suggestions:**
- Try the regular chat endpoint for basic assistance
- Ensure your vehicle information is correct
- Contact support if the issue persists

**Fallback:** You can still use the standard chat features while we resolve this issue.""",
            format="markdown",
            timestamp=datetime.now(),
            message_type="error"
        )
        
        return ChatResponse(message=error_message)