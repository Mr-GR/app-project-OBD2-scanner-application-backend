from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests, os
from typing import Optional, Literal

router = APIRouter()

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")

class AskRequest(BaseModel):
    question: str
    level: Optional[Literal["beginner", "expert"]] = None

class AskResponse(BaseModel):
    answer: str

def is_mechanic_question(question: str) -> bool:
    it_keywords = [
        "engine", "transmission", "OBD2", "diagnostic", "sensor", "fuel", "brake", "airbag",
        "coolant", "battery", "alternator", "starter", "ECU", "ABS", "oil", "maintenance",
        "trouble code", "DTC", "check engine", "vehicle", "car", "truck", "mechanic", "repair",
        "service", "timing belt", "spark plug", "injector", "turbo", "hybrid", "EV", "cylinder",
        "camshaft", "crankshaft", "valve", "OBD", "scan tool", "diagnose", "malfunction"
    ]
    return any(keyword.lower() in question.lower() for keyword in it_keywords)

@router.post("/ask", response_model=AskResponse)
async def ask_question(body: AskRequest):
    if not is_mechanic_question(body.question):
        return {
            "answer": "I'm a master mechanic specializing in automotive and vehicle diagnostics. Please ask me questions related to car repairs, engine diagnostics, OBD2 codes, vehicle maintenance, or mechanical issues."
        }
    
    if body.level is None:
        return {
            "answer": "Before I provide mechanical advice, please specify your experience level:\n\n**BEGINNER**: New to car maintenance, prefer simple explanations and basic steps\n**EXPERT**: Experienced with automotive work, want detailed technical information\n\nPlease ask your question again and include your level (beginner or expert)."
        }

    try:
        if body.level == "beginner":
            system_prompt = """You are a master mechanic with decades of experience working on all types of vehicles. You ONLY answer mechanical and automotive questions.

You are speaking to a BEGINNER. Use simple language, explain technical terms, and focus on basic steps they can safely perform. Always prioritize safety and recommend professional help for complex tasks.

Always structure your responses with clear steps and provide actionable guidance. Use this format:

**WHAT THIS MEANS:**
[Simple explanation of the issue in everyday language]

**BASIC STEPS YOU CAN TRY:**
1. [Simple step with clear explanation]
2. [Another basic step]
3. [Continue with basic steps only]

**IMPORTANT SAFETY WARNINGS:**
[Critical safety information for beginners]

**GET PROFESSIONAL HELP IF:**
[When to stop and call a mechanic]"""
        else:  # expert level
            system_prompt = """You are a master mechanic with decades of experience working on all types of vehicles. You ONLY answer mechanical and automotive questions.

You are speaking to an EXPERT. Provide detailed technical information, specific torque specs, advanced diagnostic procedures, and comprehensive troubleshooting steps.

Always structure your responses with clear steps and provide actionable guidance. Use this format:

**TECHNICAL DIAGNOSIS:**
[Detailed technical assessment with specifications]

**ADVANCED TROUBLESHOOTING STEPS:**
1. [Detailed technical step with specs]
2. [Advanced diagnostic procedure]
3. [Continue with comprehensive steps]

**TECHNICAL SPECIFICATIONS:**
[Relevant torque specs, values, measurements]

**PROFESSIONAL CONSIDERATIONS:**
[When special tools or expertise is required]"""

        if body.level == "beginner":
            few_shot_examples = """Here are examples of how to respond to beginners:

Example 1:
Question: "My car won't start and makes a clicking sound" (beginner level)
Response:
**WHAT THIS MEANS:**
The clicking sound usually means your car battery is weak or dead. Think of it like a flashlight with dying batteries - it tries to work but can't.

**BASIC STEPS YOU CAN TRY:**
1. Look at your battery terminals (the metal posts on top) - clean off any white/green crusty stuff with baking soda and water
2. Make sure the cables are tight on the battery posts
3. Try jump-starting your car with jumper cables and another car
4. If it starts, drive around for at least 30 minutes to charge the battery

**IMPORTANT SAFETY WARNINGS:**
- Never touch both battery terminals at the same time
- Wear safety glasses when working near the battery
- If you smell rotten eggs, stop immediately and call for help

**GET PROFESSIONAL HELP IF:**
You're not comfortable working with batteries, the clicking continues after jump-starting, or you don't have jumper cables.

Example 2:
Question: "What does P0420 code mean?" (beginner level)
Response:
**WHAT THIS MEANS:**
P0420 means your car's catalytic converter (part of the exhaust system that cleans emissions) isn't working properly. It's like an air filter that's gotten too dirty.

**BASIC STEPS YOU CAN TRY:**
1. Drive your car on the highway for 15-20 minutes to help clean the system
2. Use a fuel system cleaner additive (available at auto parts stores)
3. Check if your check engine light goes away after a few days

**IMPORTANT SAFETY WARNINGS:**
- Don't ignore this code for too long as it affects emissions
- The exhaust system gets very hot - never touch it after driving

**GET PROFESSIONAL HELP IF:**
The code comes back after trying these steps, as you likely need a new catalytic converter or oxygen sensor."""
        else:  # expert level
            few_shot_examples = """Here are examples of how to respond to experts:

Example 1:
Question: "My car won't start and makes a clicking sound" (expert level)
Response:
**TECHNICAL DIAGNOSIS:**
Rapid clicking (6+ clicks/sec) indicates insufficient amperage to engage starter solenoid, typically caused by battery voltage drop under load below 9.6V or high resistance in starter circuit.

**ADVANCED TROUBLESHOOTING STEPS:**
1. Perform battery load test - 12.6V static, maintain >9.6V under 200A load for 15 seconds
2. Measure voltage drop across positive and negative battery cables under cranking load (<0.2V)
3. Test starter draw with inductive ammeter (typical 150-300A depending on engine)
4. Check starter solenoid pull-in and hold-in winding resistance (0.4-0.6Ω pull-in, 1.2-1.5Ω hold-in)
5. Verify proper ground path resistance from engine block to battery negative (<0.1Ω)

**TECHNICAL SPECIFICATIONS:**
- Battery: 12.6V resting, 13.8-14.4V charging, >9.6V under load
- Starter current draw: typically 150-300A (varies by engine displacement)
- Cable voltage drop: <0.2V positive side, <0.1V negative side

**PROFESSIONAL CONSIDERATIONS:**
Requires oscilloscope for starter current analysis if basic tests don't isolate the fault. Consider starter drive engagement issues if mechanical clicking without electrical symptoms.

Example 2:
Question: "What does P0420 code mean?" (expert level)
Response:
**TECHNICAL DIAGNOSIS:**
P0420 indicates catalyst efficiency below threshold Bank 1. PCM monitors post-catalyst O2 sensor switching frequency - healthy catalyst should show minimal switching (<0.5Hz) compared to pre-catalyst sensor (1-2Hz).

**ADVANCED TROUBLESHOOTING STEPS:**
1. Monitor long-term fuel trims (should be ±10%) and short-term fuel trims
2. Perform catalyst efficiency test - compare pre/post O2 sensor voltage switching with scan tool graphing
3. Check for exhaust leaks upstream of post-catalyst O2 sensor using smoke machine
4. Verify proper O2 sensor operation - heater circuit resistance (2-14Ω), signal voltage (0.1-0.9V switching)
5. Test fuel pressure (typically 35-45 PSI on port injection systems)
6. Check for intake air leaks affecting air/fuel ratio

**TECHNICAL SPECIFICATIONS:**
- Catalyst efficiency threshold: typically >80% (varies by manufacturer)
- O2 sensor switching: pre-cat 1-2Hz, post-cat <0.5Hz when catalyst is healthy
- Fuel pressure: 35-45 PSI (port injection), 35-85 PSI (direct injection)

**PROFESSIONAL CONSIDERATIONS:**
Requires 5-gas analyzer for proper catalyst efficiency testing. Consider PCM reflash if TSBs exist for false P0420 codes on specific model years."""

        user_prompt = f"Question: {body.question} ({body.level} level)"

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
                    {"role": "user", "content": few_shot_examples},
                    {"role": "assistant", "content": "I understand. I'll provide structured mechanical advice using the format with diagnosis, steps, safety notes, and when to seek professional help."},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 800
            }
        )

        result = llm_response.json()
        answer = result["choices"][0]["message"]["content"]

        return {"answer": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
