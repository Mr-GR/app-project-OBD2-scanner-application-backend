from fastapi import APIRouter, HTTPException, Depends
import requests
import os
import re
import time
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from api.schemas.chat import ChatRequest, ChatResponse, ChatMessage, DiagnosticContext
from api.utils.dtc import get_code_description
from db.database import get_db

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

def generate_enhanced_system_prompt(level: str, context: DiagnosticContext = None) -> str:
    """Generate system prompt with diagnostic context"""
    base_prompt = f"""You are a master mechanic with decades of experience working on all types of vehicles. You ONLY answer mechanical and automotive questions.

You are speaking to a {"BEGINNER" if level == "beginner" else "EXPERT"}. {"Use simple language, explain technical terms, and focus on basic steps they can safely perform. Always prioritize safety and recommend professional help for complex tasks." if level == "beginner" else "Provide detailed technical information, specific torque specs, advanced diagnostic procedures, and comprehensive troubleshooting steps."}"""

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

## """ + ("What This Means" if level == "beginner" else "Technical Diagnosis") + """
[Explanation appropriate for """ + level + """ level]

## """ + ("Basic Steps You Can Try" if level == "beginner" else "Advanced Troubleshooting Steps") + """
1. [Step with clear explanation]
2. [Another step]
3. [Continue with steps]

## """ + ("Important Safety Warnings" if level == "beginner" else "Technical Specifications") + """
[Safety information or technical specs]

## """ + ("Get Professional Help If" if level == "beginner" else "Professional Considerations") + """
[When to seek professional assistance]

Use proper markdown formatting with headers, lists, and emphasis."""

    return base_prompt + format_instructions

@router.post("/chat", response_model=ChatResponse)
async def chat_with_context(request: ChatRequest, db: Session = Depends(get_db)):
    """Enhanced chat endpoint with automatic vehicle context"""
    
    # Get or create default user and check for primary vehicle
    from api.routers.vehicles import get_or_create_default_user
    from db.models import UserVehicle
    
    user = get_or_create_default_user(db)
    primary_vehicle = db.query(UserVehicle).filter(
        UserVehicle.user_id == user.id,
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
        "level": request.level
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
    
    if request.level is None:
        message = ChatMessage(
            content="""# Experience Level Required

Before I provide mechanical advice, please specify your experience level:

## **BEGINNER**
New to car maintenance, prefer simple explanations and basic steps

## **EXPERT** 
Experienced with automotive work, want detailed technical information

Please ask your question again and include your level (beginner or expert).""",
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
        system_prompt = generate_enhanced_system_prompt(request.level, enhanced_context)
        
        # Create user prompt
        user_prompt = f"Question: {request.message} ({request.level} level)"
        
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
async def quick_chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Quick chat endpoint for simple car queries without level requirement"""
    
    # Get or create default user and check for primary vehicle
    from api.routers.vehicles import get_or_create_default_user
    from db.models import UserVehicle
    
    user = get_or_create_default_user(db)
    primary_vehicle = db.query(UserVehicle).filter(
        UserVehicle.user_id == user.id,
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