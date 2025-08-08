"""
Diagnostic Orchestrator for OBD2 Scanner Backend
Phase 1 Implementation: Core Planner → Tool → Compose Loop

This orchestrator manages the diagnostic workflow using a state-driven approach
with LLM planning, tool execution, and response composition.
"""

import json
import logging
import time
import traceback
import requests
import os
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float
from sqlalchemy.sql import func

from api.utils.elm327 import ELM327Scanner
from api.utils.dtc import get_code_description, get_dtc_severity, categorize_dtc
from db.models import User, DiagnosticOrchestrationSession
import uuid

logger = logging.getLogger(__name__)

class DiagnosticState(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPOSING = "composing"
    COMPLETED = "completed"
    ERROR = "error"

class ActionType(Enum):
    OBD_READ = "obd_read"
    SPEC_LOOKUP = "spec_lookup"
    RAG_SEARCH = "rag_search"
    REQUIRE_CONSENT = "require_consent"
    VERIFY_FIX = "verify_fix"

@dataclass
class VehicleSnapshot:
    vin: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    dtc_codes: List[str] = None
    sensor_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dtc_codes is None:
            self.dtc_codes = []
        if self.sensor_data is None:
            self.sensor_data = {}

@dataclass
class LiveTelemetry:
    timestamp: datetime
    engine_rpm: Optional[float] = None
    vehicle_speed: Optional[float] = None
    engine_temp: Optional[float] = None
    fuel_level: Optional[float] = None
    throttle_position: Optional[float] = None
    additional_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_params is None:
            self.additional_params = {}

@dataclass
class DiagnosticHypothesis:
    id: str
    description: str
    confidence: float
    supporting_evidence: List[str]
    next_steps: List[str]
    created_at: datetime
    
@dataclass 
class DiagnosticAction:
    type: ActionType
    parameters: Dict[str, Any]
    require_consent: bool = False
    description: str = ""
    
@dataclass
class ActionResult:
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time: float = 0.0

@dataclass
class PlanStep:
    action: DiagnosticAction
    rationale: str
    expected_outcome: str

@dataclass
class DiagnosticPlan:
    steps: List[PlanStep]
    reasoning: str
    estimated_time: int
    requires_consent: bool

@dataclass
class DiagnosticResponse:
    steps: List[Dict[str, Any]]
    questions: List[str]
    verification: Dict[str, Any]
    recommendations: List[str]
    confidence: float
    requires_consent: bool = False
    consent_actions: List[str] = None
    
    def __post_init__(self):
        if self.consent_actions is None:
            self.consent_actions = []

class StateManager:
    """Manages diagnostic session state with Postgres persistence"""
    
    def __init__(self, session_id: str, db_session: Session, user_id: int):
        self.session_id = session_id
        self.db_session = db_session
        self.user_id = user_id
        self._session_record: Optional[DiagnosticOrchestrationSession] = None
        self._load_or_create_session()
        
    def _load_or_create_session(self):
        """Load existing session or create new one"""
        self._session_record = self.db_session.query(DiagnosticOrchestrationSession).filter(
            DiagnosticOrchestrationSession.session_id == self.session_id
        ).first()
        
        if not self._session_record:
            self._session_record = DiagnosticOrchestrationSession(
                session_id=self.session_id,
                user_id=self.user_id,
                vehicle_snapshot=None,
                live_telemetry=[],
                hypotheses=[],
                execution_history=[]
            )
            self.db_session.add(self._session_record)
            self.db_session.commit()
            
    def get_vehicle_snapshot(self) -> Optional[VehicleSnapshot]:
        if self._session_record and self._session_record.vehicle_snapshot:
            return VehicleSnapshot(**self._session_record.vehicle_snapshot)
        return None
        
    def set_vehicle_snapshot(self, snapshot: VehicleSnapshot):
        if self._session_record:
            self._session_record.vehicle_snapshot = asdict(snapshot)
            self._session_record.updated_at = func.now()
            self.db_session.commit()
            
    def add_live_telemetry(self, telemetry: LiveTelemetry):
        if self._session_record:
            current_telemetry = self._session_record.live_telemetry or []
            
            telemetry_dict = asdict(telemetry)
            telemetry_dict['timestamp'] = telemetry.timestamp.isoformat()
            current_telemetry.append(telemetry_dict)
            
            # Keep only last 100 records
            if len(current_telemetry) > 100:
                current_telemetry = current_telemetry[-50:]
                
            self._session_record.live_telemetry = current_telemetry
            self._session_record.updated_at = func.now()
            self.db_session.commit()
            
    def get_latest_telemetry(self) -> Optional[LiveTelemetry]:
        if self._session_record and self._session_record.live_telemetry:
            latest = self._session_record.live_telemetry[-1]
            latest['timestamp'] = datetime.fromisoformat(latest['timestamp'])
            return LiveTelemetry(**latest)
        return None
        
    def add_hypothesis(self, hypothesis: DiagnosticHypothesis):
        if self._session_record:
            current_hypotheses = self._session_record.hypotheses or []
            hypothesis_dict = asdict(hypothesis)
            hypothesis_dict['created_at'] = hypothesis.created_at.isoformat()
            current_hypotheses.append(hypothesis_dict)
            
            self._session_record.hypotheses = current_hypotheses
            self._session_record.updated_at = func.now()
            self.db_session.commit()
        
    def get_hypotheses(self) -> List[DiagnosticHypothesis]:
        if self._session_record and self._session_record.hypotheses:
            hypotheses = []
            for h_dict in self._session_record.hypotheses:
                h_dict['created_at'] = datetime.fromisoformat(h_dict['created_at'])
                hypotheses.append(DiagnosticHypothesis(**h_dict))
            return hypotheses
        return []
        
    def add_execution_record(self, action: DiagnosticAction, result: ActionResult):
        if self._session_record:
            current_history = self._session_record.execution_history or []
            record = {
                'timestamp': datetime.now().isoformat(),
                'action': asdict(action),
                'result': asdict(result)
            }
            current_history.append(record)
            
            self._session_record.execution_history = current_history
            self._session_record.updated_at = func.now()
            self.db_session.commit()
        
    def get_execution_history(self) -> List[Dict[str, Any]]:
        return self._session_record.execution_history or [] if self._session_record else []
    
    def set_state(self, state: DiagnosticState):
        if self._session_record:
            self._session_record.current_state = state.value
            self._session_record.updated_at = func.now()
            self.db_session.commit()
    
    def get_state(self) -> DiagnosticState:
        if self._session_record and self._session_record.current_state:
            return DiagnosticState(self._session_record.current_state)
        return DiagnosticState.PLANNING

def call_tool_json_safe(func, *args, **kwargs) -> ActionResult:
    """JSON-safe wrapper for tool calls with error handling"""
    start_time = time.time()
    
    try:
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        if isinstance(result, dict):
            data = result
        else:
            data = {"result": str(result)}
            
        return ActionResult(
            success=True,
            data=data,
            execution_time=execution_time
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Tool execution failed: {error_msg}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        
        return ActionResult(
            success=False,
            data={},
            error=error_msg,
            execution_time=execution_time
        )

class DiagnosticOrchestrator:
    """Main orchestrator for diagnostic workflow"""
    
    def __init__(self, session_id: str, db_session: Session, user_id: int):
        self.session_id = session_id
        self.user_id = user_id
        self.db_session = db_session
        self.state_manager = StateManager(session_id, db_session, user_id)
        self.current_state = self.state_manager.get_state()
        self._current_plan: Optional[DiagnosticPlan] = None
        self.together_api_key = os.getenv("TOGETHER_API_KEY")
        
    async def diagnose(self, 
                      user_query: str,
                      vehicle_context: Optional[Dict[str, Any]] = None,
                      live_data: Optional[Dict[str, Any]] = None) -> DiagnosticResponse:
        """Main diagnostic entry point"""
        
        try:
            # Update state with provided context
            if vehicle_context:
                snapshot = VehicleSnapshot(
                    vin=vehicle_context.get('vin'),
                    make=vehicle_context.get('make'),
                    model=vehicle_context.get('model'),
                    year=vehicle_context.get('year'),
                    dtc_codes=vehicle_context.get('dtc_codes', []),
                    sensor_data=vehicle_context.get('sensor_data', {})
                )
                self.state_manager.set_vehicle_snapshot(snapshot)
                
            if live_data:
                telemetry = LiveTelemetry(
                    timestamp=datetime.now(),
                    engine_rpm=live_data.get('rpm'),
                    vehicle_speed=live_data.get('speed'),
                    engine_temp=live_data.get('engine_temp'),
                    fuel_level=live_data.get('fuel_level'),
                    throttle_position=live_data.get('throttle_position'),
                    additional_params=live_data
                )
                self.state_manager.add_live_telemetry(telemetry)
            
            # Execute diagnostic workflow
            self.current_state = DiagnosticState.PLANNING
            plan = await self._plan_diagnosis(user_query)
            
            self.current_state = DiagnosticState.EXECUTING
            results = await self._execute_plan(plan)
            
            self.current_state = DiagnosticState.COMPOSING
            response = await self._compose_response(plan, results, user_query)
            
            self.current_state = DiagnosticState.COMPLETED
            return response
            
        except Exception as e:
            self.current_state = DiagnosticState.ERROR
            logger.error(f"Orchestrator error: {e}")
            return DiagnosticResponse(
                steps=[{"error": str(e)}],
                questions=["An error occurred during diagnosis. Please try again."],
                verification={"status": "error", "message": str(e)},
                recommendations=["Contact support if the issue persists"],
                confidence=0.0
            )
    
    async def _plan_diagnosis(self, user_query: str) -> DiagnosticPlan:
        """Plan diagnostic steps using LLM"""
        
        # Gather context for planning
        context = self._build_context_for_planning(user_query)
        
        if not self.together_api_key:
            # Return basic plan if no LLM available
            return self._create_basic_plan(user_query)
        
        try:
            plan_prompt = self._generate_planning_prompt(user_query, context)
            
            response = requests.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.together_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "mistralai/Mistral-7B-Instruct-v0.1",
                    "messages": [
                        {"role": "system", "content": "You are a diagnostic planning AI that creates structured diagnostic plans in JSON format."},
                        {"role": "user", "content": plan_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                plan_json = result["choices"][0]["message"]["content"]
                plan = self._parse_plan_from_llm(plan_json, user_query)
                self._current_plan = plan
                return plan
            else:
                logger.error(f"LLM planning failed: {response.status_code}")
                return self._create_basic_plan(user_query)
                
        except Exception as e:
            logger.error(f"Error in LLM planning: {e}")
            return self._create_basic_plan(user_query)
    
    def _generate_planning_prompt(self, user_query: str, context: Dict[str, Any]) -> str:
        """Generate LLM prompt for diagnostic planning"""
        
        context_str = ""
        if context.get("vehicle"):
            vehicle = context["vehicle"]
            context_str += f"Vehicle: {vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')}\n"
            if vehicle.get("dtc_codes"):
                context_str += f"DTC Codes: {', '.join(vehicle['dtc_codes'])}\n"
                
        if context.get("live_data"):
            live = context["live_data"]
            context_str += f"Live Data: RPM={live.get('engine_rpm')}, Speed={live.get('vehicle_speed')}, Temp={live.get('engine_temp')}°C\n"
        
        prompt = f"""You are an expert automotive diagnostic technician. Create a diagnostic plan for the following issue:

USER QUERY: {user_query}

CONTEXT:
{context_str if context_str else "No specific vehicle context provided"}

Create a JSON diagnostic plan with the following structure:
{{
  "steps": [
    {{
      "action_type": "obd_read|spec_lookup|rag_search",
      "parameters": {{}},
      "description": "Clear description of the action",
      "rationale": "Why this step is needed",
      "expected_outcome": "What we expect to learn",
      "requires_consent": false
    }}
  ],
  "reasoning": "Overall reasoning for this diagnostic approach",
  "estimated_time": 60,
  "requires_consent": false
}}

Focus on:
1. OBD reading for live data and DTCs
2. Specification lookups for vehicle-specific info
3. Knowledge base searches for similar issues
4. Logical progression from simple to complex diagnostics

RESPOND ONLY WITH VALID JSON."""
        
        return prompt
    
    def _parse_plan_from_llm(self, plan_json: str, user_query: str) -> DiagnosticPlan:
        """Parse LLM response into DiagnosticPlan"""
        try:
            # Extract JSON from response if it contains extra text
            if "```json" in plan_json:
                json_start = plan_json.find("```json") + 7
                json_end = plan_json.find("```", json_start)
                plan_json = plan_json[json_start:json_end].strip()
            elif "{" in plan_json:
                json_start = plan_json.find("{")
                json_end = plan_json.rfind("}") + 1
                plan_json = plan_json[json_start:json_end]
                
            plan_data = json.loads(plan_json)
            
            steps = []
            for step_data in plan_data.get("steps", []):
                action_type_str = step_data.get("action_type", "spec_lookup")
                action_type = ActionType.SPEC_LOOKUP  # default
                
                if action_type_str == "obd_read":
                    action_type = ActionType.OBD_READ
                elif action_type_str == "rag_search":
                    action_type = ActionType.RAG_SEARCH
                elif action_type_str == "spec_lookup":
                    action_type = ActionType.SPEC_LOOKUP
                    
                action = DiagnosticAction(
                    type=action_type,
                    parameters=step_data.get("parameters", {}),
                    description=step_data.get("description", ""),
                    require_consent=step_data.get("requires_consent", False)
                )
                
                step = PlanStep(
                    action=action,
                    rationale=step_data.get("rationale", ""),
                    expected_outcome=step_data.get("expected_outcome", "")
                )
                steps.append(step)
                
            return DiagnosticPlan(
                steps=steps,
                reasoning=plan_data.get("reasoning", "LLM generated plan"),
                estimated_time=plan_data.get("estimated_time", 60),
                requires_consent=plan_data.get("requires_consent", False)
            )
            
        except Exception as e:
            logger.error(f"Failed to parse LLM plan: {e}")
            return self._create_basic_plan(user_query)
    
    def _create_basic_plan(self, user_query: str) -> DiagnosticPlan:
        """Create a basic fallback plan"""
        steps = []
        
        # Always start with spec lookup
        steps.append(PlanStep(
            action=DiagnosticAction(
                type=ActionType.SPEC_LOOKUP,
                parameters={"query": user_query},
                description="Look up technical specifications and common causes"
            ),
            rationale="Gather foundational technical information",
            expected_outcome="Understanding of potential causes and diagnostic approach"
        ))
        
        # Add OBD reading if query suggests diagnostic codes or engine issues
        query_lower = user_query.lower()
        if any(term in query_lower for term in ["code", "dtc", "check engine", "light", "engine", "diagnostic"]):
            steps.append(PlanStep(
                action=DiagnosticAction(
                    type=ActionType.OBD_READ,
                    parameters={"read_dtcs": True, "read_live_data": True},
                    description="Read diagnostic trouble codes and live engine data"
                ),
                rationale="Identify active issues and current engine performance",
                expected_outcome="Current fault codes and real-time sensor readings"
            ))
            
        # Add knowledge base search
        steps.append(PlanStep(
            action=DiagnosticAction(
                type=ActionType.RAG_SEARCH,
                parameters={"query": user_query, "include_similar_cases": True},
                description="Search knowledge base for similar diagnostic cases"
            ),
            rationale="Find documented solutions for similar issues",
            expected_outcome="Historical cases and proven diagnostic approaches"
        ))
        
        return DiagnosticPlan(
            steps=steps,
            reasoning="Basic diagnostic workflow covering specifications, OBD data, and knowledge base search",
            estimated_time=45,
            requires_consent=False
        )
    
    async def _execute_plan(self, plan: DiagnosticPlan) -> List[ActionResult]:
        """Execute planned diagnostic steps"""
        results = []
        
        for step in plan.steps:
            action = step.action
            
            # Check if consent is required
            if action.require_consent:
                consent_result = await self._handle_consent_required(action)
                if not consent_result.success:
                    results.append(consent_result)
                    continue
            
            # Execute the action
            result = await self._execute_action(action)
            results.append(result)
            
            # Record execution
            self.state_manager.add_execution_record(action, result)
            
        return results
    
    async def _execute_action(self, action: DiagnosticAction) -> ActionResult:
        """Execute a single diagnostic action"""
        
        if action.type == ActionType.OBD_READ:
            return await self._execute_obd_read(action.parameters)
        elif action.type == ActionType.SPEC_LOOKUP:
            return await self._execute_spec_lookup(action.parameters)
        elif action.type == ActionType.RAG_SEARCH:
            return await self._execute_rag_search(action.parameters)
        elif action.type == ActionType.VERIFY_FIX:
            return await self._execute_verify_fix(action.parameters)
        else:
            return ActionResult(
                success=False,
                error=f"Unknown action type: {action.type}"
            )
    
    async def _compose_response(self, 
                               plan: DiagnosticPlan, 
                               results: List[ActionResult], 
                               original_query: str) -> DiagnosticResponse:
        """Compose final diagnostic response"""
        
        # Build response from execution results
        steps = []
        for i, (plan_step, result) in enumerate(zip(plan.steps, results)):
            step_data = {
                "step": i + 1,
                "action": plan_step.action.description,
                "success": result.success,
                "data": result.data if result.success else {},
                "error": result.error
            }
            steps.append(step_data)
        
        # Generate questions and recommendations based on results
        questions = self._generate_followup_questions(results)
        recommendations = self._generate_recommendations(results)
        
        # Calculate confidence based on successful executions
        successful_steps = sum(1 for r in results if r.success)
        confidence = successful_steps / len(results) if results else 0.0
        
        verification = {
            "status": "completed",
            "successful_steps": successful_steps,
            "total_steps": len(results),
            "execution_time": sum(r.execution_time for r in results)
        }
        
        return DiagnosticResponse(
            steps=steps,
            questions=questions,
            verification=verification,
            recommendations=recommendations,
            confidence=confidence,
            requires_consent=plan.requires_consent
        )
    
    async def _handle_consent_required(self, action: DiagnosticAction) -> ActionResult:
        """Handle actions that require user consent"""
        return ActionResult(
            success=False,
            data={"consent_required": True, "action": action.description},
            error="User consent required"
        )
    
    def _build_context_for_planning(self, user_query: str) -> Dict[str, Any]:
        """Build context information for LLM planning"""
        context = {
            "user_query": user_query,
            "session_id": self.session_id
        }
        
        # Add vehicle snapshot if available
        snapshot = self.state_manager.get_vehicle_snapshot()
        if snapshot:
            context["vehicle"] = asdict(snapshot)
            
        # Add latest telemetry
        telemetry = self.state_manager.get_latest_telemetry()
        if telemetry:
            context["live_data"] = asdict(telemetry)
            
        # Add hypotheses
        hypotheses = self.state_manager.get_hypotheses()
        if hypotheses:
            context["hypotheses"] = [asdict(h) for h in hypotheses]
            
        return context
    
    def _generate_followup_questions(self, results: List[ActionResult]) -> List[str]:
        """Generate follow-up questions based on execution results"""
        questions = []
        
        # Check for failed actions
        failed_actions = [r for r in results if not r.success]
        if failed_actions:
            questions.append("Some diagnostic steps failed. Would you like to retry or try alternative approaches?")
            
        # Check for DTC codes
        snapshot = self.state_manager.get_vehicle_snapshot()
        if snapshot and snapshot.dtc_codes:
            questions.append("Would you like detailed explanations of the diagnostic trouble codes found?")
            
        # Default questions
        if not questions:
            questions.extend([
                "Are you experiencing any specific symptoms?",
                "When did you first notice the issue?"
            ])
            
        return questions
    
    def _generate_recommendations(self, results: List[ActionResult]) -> List[str]:
        """Generate recommendations based on execution results"""
        recommendations = []
        
        # Check for successful data gathering
        successful_results = [r for r in results if r.success]
        if successful_results:
            recommendations.append("Continue with additional diagnostic steps based on findings")
            
        # Check vehicle snapshot for specific recommendations
        snapshot = self.state_manager.get_vehicle_snapshot()
        if snapshot and snapshot.dtc_codes:
            recommendations.append("Address diagnostic trouble codes in order of severity")
            
        # Default recommendations
        if not recommendations:
            recommendations.extend([
                "Perform a comprehensive vehicle scan",
                "Check for software updates",
                "Consult with a professional technician if issues persist"
            ])
            
        return recommendations
    
    async def _execute_obd_read(self, parameters: Dict[str, Any]) -> ActionResult:
        """Execute OBD2 read operation"""
        try:
            scanner = ELM327Scanner()
            
            # Try to connect to scanner
            if not scanner.connect():
                return ActionResult(
                    success=False,
                    error="Failed to connect to OBD2 scanner",
                    data={"connection_status": "failed"}
                )
            
            result_data = {"connection_status": "connected"}
            
            # Read DTCs if requested
            if parameters.get("read_dtcs", True):
                dtc_codes = scanner.get_dtc_codes()
                result_data["dtc_codes"] = dtc_codes
                
                # Get descriptions and severity for each code
                dtc_details = []
                for code in dtc_codes:
                    dtc_details.append({
                        "code": code,
                        "description": get_code_description(code),
                        "severity": get_dtc_severity(code),
                        "category": categorize_dtc(code)
                    })
                result_data["dtc_details"] = dtc_details
            
            # Read live data if requested
            if parameters.get("read_live_data", True):
                live_params = scanner.get_live_parameters("comprehensive")
                result_data["live_parameters"] = live_params
                
                # Get VIN if available
                vin = scanner.get_vin_from_obd2()
                if vin:
                    result_data["vin"] = vin
            
            scanner.disconnect()
            
            return ActionResult(
                success=True,
                data=result_data
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                error=f"OBD2 read failed: {str(e)}",
                data={"error_details": str(e)}
            )
    
    async def _execute_spec_lookup(self, parameters: Dict[str, Any]) -> ActionResult:
        """Execute specification lookup using existing vehicle info APIs"""
        try:
            query = parameters.get("query", "")
            result_data = {}
            
            # If we have vehicle context, get detailed specifications
            vehicle_snapshot = self.state_manager.get_vehicle_snapshot()
            if vehicle_snapshot and vehicle_snapshot.vin:
                # Use VIN to get detailed vehicle specifications
                nhtsa_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vehicle_snapshot.vin}?format=json"
                
                try:
                    response = requests.get(nhtsa_url, timeout=10)
                    if response.status_code == 200:
                        vin_data = response.json()["Results"][0]
                        
                        result_data["vehicle_specifications"] = {
                            "make": vin_data.get("Make", "Unknown"),
                            "model": vin_data.get("Model", "Unknown"),
                            "year": vin_data.get("ModelYear", "Unknown"),
                            "engine": vin_data.get("EngineModel", "Unknown"),
                            "displacement": vin_data.get("DisplacementL", "Unknown"),
                            "fuel_type": vin_data.get("FuelTypePrimary", "Unknown"),
                            "transmission": vin_data.get("TransmissionStyle", "Unknown"),
                            "drive_type": vin_data.get("DriveType", "Unknown"),
                            "vehicle_class": vin_data.get("VehicleType", "Unknown")
                        }
                except Exception as e:
                    logger.warning(f"NHTSA lookup failed: {e}")
            
            # Add general diagnostic information based on query
            if any(keyword in query.lower() for keyword in ["p0420", "catalyst", "o2", "oxygen"]):
                result_data["diagnostic_info"] = {
                    "common_causes": ["Faulty catalytic converter", "O2 sensor failure", "Exhaust leak", "Engine running rich/lean"],
                    "diagnostic_steps": ["Check O2 sensor readings", "Test catalytic converter efficiency", "Inspect exhaust system"],
                    "typical_repair_cost": "$200-$2500"
                }
            elif any(keyword in query.lower() for keyword in ["misfire", "p030", "rough idle"]):
                result_data["diagnostic_info"] = {
                    "common_causes": ["Faulty spark plugs", "Ignition coils", "Fuel injectors", "Compression issues"],
                    "diagnostic_steps": ["Check spark plugs and coils", "Test fuel pressure", "Perform compression test"],
                    "typical_repair_cost": "$100-$800"
                }
            
            return ActionResult(
                success=True,
                data=result_data
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                error=f"Specification lookup failed: {str(e)}",
                data={}
            )
    
    async def _execute_rag_search(self, parameters: Dict[str, Any]) -> ActionResult:
        """Execute RAG search using LLM knowledge base"""
        try:
            query = parameters.get("query", "")
            
            if not self.together_api_key:
                return ActionResult(
                    success=False,
                    error="LLM API not configured for knowledge search"
                )
            
            # Build search prompt
            search_prompt = f"""You are an automotive diagnostic expert with access to extensive repair and diagnostic knowledge. 
            
Search your knowledge base for information related to: {query}

Provide structured information including:
1. Common causes
2. Diagnostic procedures  
3. Typical symptoms
4. Repair recommendations
5. Parts that commonly fail
6. Estimated costs

Focus on practical, actionable diagnostic information."""
            
            response = requests.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.together_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "mistralai/Mistral-7B-Instruct-v0.1",
                    "messages": [
                        {"role": "system", "content": "You are an expert automotive diagnostic technician with comprehensive knowledge of vehicle repair and troubleshooting."},
                        {"role": "user", "content": search_prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                knowledge_content = result["choices"][0]["message"]["content"]
                
                return ActionResult(
                    success=True,
                    data={
                        "knowledge_base_results": knowledge_content,
                        "search_query": query,
                        "source": "LLM Knowledge Base"
                    }
                )
            else:
                return ActionResult(
                    success=False,
                    error=f"Knowledge search failed: HTTP {response.status_code}"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                error=f"RAG search failed: {str(e)}"
            )
    
    async def _execute_verify_fix(self, parameters: Dict[str, Any]) -> ActionResult:
        """Execute fix verification by comparing before/after telemetry"""
        try:
            # Get current telemetry
            current_telemetry = self.state_manager.get_latest_telemetry()
            
            if not current_telemetry:
                return ActionResult(
                    success=False,
                    error="No telemetry data available for verification"
                )
            
            # Compare with baseline if available
            execution_history = self.state_manager.get_execution_history()
            baseline_telemetry = None
            
            for record in execution_history:
                if record.get("action", {}).get("type") == "obd_read":
                    # Found previous OBD reading
                    baseline_telemetry = record.get("result", {}).get("data", {}).get("live_parameters")
                    break
            
            verification_results = {
                "current_status": "analyzed",
                "timestamp": current_telemetry.timestamp.isoformat(),
                "current_readings": asdict(current_telemetry)
            }
            
            if baseline_telemetry:
                verification_results["comparison"] = "baseline_available"
                verification_results["baseline_data"] = baseline_telemetry
                
                # Simple comparison logic
                improvements = []
                concerns = []
                
                # Check engine temperature
                if current_telemetry.engine_temp and baseline_telemetry.get("Engine Coolant Temperature", {}).get("value"):
                    current_temp = current_telemetry.engine_temp
                    baseline_temp = baseline_telemetry["Engine Coolant Temperature"]["value"]
                    
                    if current_temp < baseline_temp and baseline_temp > 100:
                        improvements.append("Engine temperature has decreased")
                    elif current_temp > baseline_temp + 10:
                        concerns.append("Engine temperature has increased significantly")
                
                verification_results["improvements"] = improvements
                verification_results["concerns"] = concerns
                
            return ActionResult(
                success=True,
                data=verification_results
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                error=f"Fix verification failed: {str(e)}"
            )