"""Gemini 3 Vision Service - Production-grade image analysis.

This service provides real Gemini 3 multimodal analysis for:
- Safety violation detection from camera feeds
- Equipment wear inspection for maintenance
- Line occupancy counting

Uses gemini-3.0-flash-exp for fast, multimodal inference.
"""
import base64
import hashlib
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.config import settings
from app.utils.logging import get_agent_logger

logger = get_agent_logger("GeminiVisionService")


class GeminiVisionError(Exception):
    """Custom exception for vision service failures."""
    pass


class GeminiVisionService:
    """
    Production-grade vision analysis using Gemini 3.0 Flash.
    
    Features:
    - Real multimodal image analysis
    - Retry logic with exponential backoff
    - Thought signature tracking for audit
    - Graceful degradation on API failure
    """
    
    def __init__(self):
        """Initialize Gemini 3 vision model."""
        self._validate_api_key()
        
        self.model = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=settings.google_api_key,
            temperature=0.3,  # Lower temp for consistent analysis
        )
        
        self._analysis_cache: Dict[str, Any] = {}
        self._thought_signatures: List[Dict[str, Any]] = []
        
        logger.info("✅ GeminiVisionService initialized with gemini-3-flash-preview")
    
    def _validate_api_key(self):
        """Ensure API key is configured."""
        if not settings.google_api_key:
            raise GeminiVisionError(
                "GOOGLE_API_KEY is not set. Vision service requires a valid API key."
            )
    
    async def analyze_image(
        self,
        image_data: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Analyze an image using Gemini 3.0 Flash multimodal.
        
        Args:
            image_data: Base64-encoded image or file path
            prompt: Analysis prompt (e.g., "Detect safety violations")
            context: Optional additional context
            max_retries: Number of retry attempts on failure
            
        Returns:
            Dict with analysis results and thought signature
            
        Raises:
            GeminiVisionError: If all retries fail
        """
        # Generate cache key
        if not image_data or len(image_data) < 10:
            raise GeminiVisionError("Invalid image_data: must be a non-empty base64 string or file path")
        
        cache_key = hashlib.sha256(f"{image_data[:100]}{prompt}".encode()).hexdigest()[:16]
        
        # Evict cache if too large
        self._evict_cache_if_needed()
        
        if cache_key in self._analysis_cache:
            logger.debug(f"Cache hit for analysis {cache_key}")
            return self._analysis_cache[cache_key]
        
        # Prepare image content
        image_content = self._prepare_image_content(image_data)
        
        # Build analysis message
        full_prompt = self._build_analysis_prompt(prompt, context)
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": full_prompt},
                image_content,
            ]
        )
        
        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(max_retries):
            try:
                logger.info(f"🔍 Vision analysis attempt {attempt + 1}/{max_retries}")
                
                response = await asyncio.wait_for(
                    self.model.ainvoke([message]),
                    timeout=30.0
                )
                
                # Extract and log thought signature
                thought_signature = self._capture_thought_signature(response, prompt)
                
                result = {
                    "success": True,
                    "analysis": response.content,
                    "thought_signature": thought_signature,
                    "timestamp": datetime.now().isoformat(),
                    "cache_key": cache_key,
                }
                
                self._analysis_cache[cache_key] = result
                logger.info(f"✅ Vision analysis complete. Thought signature: {thought_signature['hash'][:8]}")
                
                return result
                
            except asyncio.TimeoutError:
                last_error = "Analysis timed out after 30 seconds"
                logger.warning(f"⏱️ Timeout on attempt {attempt + 1}")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Vision error on attempt {attempt + 1}: {e}")
            
            # Exponential backoff
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"⏳ Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        # All retries failed
        logger.error(f"❌ Vision analysis failed after {max_retries} attempts: {last_error}")
        raise GeminiVisionError(f"Analysis failed after {max_retries} attempts: {last_error}")
    
    async def detect_safety_violations(
        self,
        image_data: str,
        line_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Detect safety violations in an image using Gemini 3 vision.
        
        Args:
            image_data: Base64-encoded camera feed image
            line_number: Optional line number for context
            
        Returns:
            Dict with detected violations and confidence scores
        """
        prompt = """Analyze this production floor image for safety violations.

Look for:
1. Missing PPE (hairnets, gloves, safety glasses)
2. Blocked emergency exits or walkways
3. Spills or floor hazards
4. Unsafe proximity to machinery
5. Temperature/hygiene concerns (visible steam, open containers)

For each violation found, provide:
- Type of violation
- Location in frame (left/center/right, near/far)
- Confidence level (0.0-1.0)
- Recommended action

If no violations are detected, state "No violations detected" with confidence.
"""
        
        context = {"line_number": line_number} if line_number else None
        
        try:
            result = await self.analyze_image(image_data, prompt, context)
            return {
                "success": True,
                "violations": self._parse_violations(result["analysis"]),
                "raw_analysis": result["analysis"],
                "thought_signature": result["thought_signature"],
            }
        except GeminiVisionError as e:
            return {
                "success": False,
                "error": str(e),
                "violations": [],
                "fallback": True,
            }
    
    async def inspect_equipment(
        self,
        image_data: str,
        equipment_type: str = "conveyor motor"
    ) -> Dict[str, Any]:
        """
        Inspect equipment for wear and maintenance needs.
        
        Args:
            image_data: Base64-encoded image of equipment
            equipment_type: Type of equipment being inspected
            
        Returns:
            Dict with wear assessment and maintenance recommendations
        """
        prompt = f"""Analyze this image of a {equipment_type} for maintenance assessment.

Evaluate:
1. Visible wear patterns (scoring 1-10 severity)
2. Contamination or debris
3. Alignment issues
4. Corrosion or oxidation
5. Mechanical stress indicators

Provide:
- Overall health score (0-100)
- Predicted remaining life (hours/days/weeks)
- Recommended actions (immediate, scheduled, monitor)
- Confidence in assessment (0.0-1.0)
"""
        
        try:
            result = await self.analyze_image(image_data, prompt, {"equipment_type": equipment_type})
            return {
                "success": True,
                "equipment_type": equipment_type,
                "assessment": result["analysis"],
                "thought_signature": result["thought_signature"],
            }
        except GeminiVisionError as e:
            return {
                "success": False,
                "error": str(e),
                "equipment_type": equipment_type,
                "fallback": True,
            }
    
    def get_thought_signatures(self) -> List[Dict[str, Any]]:
        """Get all captured thought signatures for audit trail."""
        return self._thought_signatures.copy()
    
    # ========== Private Helpers ==========
    
    def _prepare_image_content(self, image_data: str) -> Dict[str, Any]:
        """Prepare image content for Gemini multimodal input."""
        # Check if it's a file path
        if Path(image_data).exists():
            with open(image_data, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode()
            return {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}
            }
        
        # Assume it's already base64
        if not image_data.startswith("data:"):
            image_data = f"data:image/jpeg;base64,{image_data}"
        
        return {
            "type": "image_url",
            "image_url": {"url": image_data}
        }
    
    def _build_analysis_prompt(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build complete analysis prompt with context."""
        parts = [prompt]
        
        if context:
            parts.append("\nAdditional Context:")
            for k, v in context.items():
                parts.append(f"- {k}: {v}")
        
        parts.append("\nProvide your analysis in a structured format.")
        
        return "\n".join(parts)
    
    def _capture_thought_signature(
        self,
        response: Any,
        prompt: str
    ) -> Dict[str, Any]:
        """
        Capture thought signature from Gemini response.
        
        This creates an audit trail of the model's reasoning process.
        """
        content = response.content if hasattr(response, 'content') else str(response)
        
        signature = {
            "hash": hashlib.sha256(content.encode()).hexdigest()[:32],
            "timestamp": datetime.now().isoformat(),
            "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest()[:16],
            "response_length": len(content),
            "model": "gemini-3-flash-preview",
        }
        
        self._thought_signatures.append(signature)
        
        return signature
    
    def _parse_violations(self, analysis: str) -> List[Dict[str, Any]]:
        """Parse violation data from analysis text."""
        violations = []
        
        # Handle None or empty analysis
        if not analysis:
            return violations
        
        # Simple parsing - look for common violation patterns
        violation_keywords = {
            "ppe": "NO_PPE",
            "hairnet": "NO_PPE",
            "gloves": "NO_PPE",
            "blocked": "BLOCKED_EXIT",
            "exit": "BLOCKED_EXIT",
            "spill": "SPILL_DETECTED",
            "puddle": "SPILL_DETECTED",
            "proximity": "UNSAFE_PROXIMITY",
            "close to": "UNSAFE_PROXIMITY",
        }
        
        analysis_lower = analysis.lower()
        
        for keyword, violation_type in violation_keywords.items():
            if keyword in analysis_lower:
                # Avoid duplicates
                if not any(v["type"] == violation_type for v in violations):
                    violations.append({
                        "type": violation_type,
                        "confidence": 0.75,  # Default confidence
                        "source": "gemini_vision",
                    })
        
        return violations
    
    def _evict_cache_if_needed(self):
        """Evict oldest cache entries if cache is too large."""
        max_cache_size = 100
        if len(self._analysis_cache) > max_cache_size:
            # Remove oldest 20 entries
            keys_to_remove = list(self._analysis_cache.keys())[:20]
            for key in keys_to_remove:
                del self._analysis_cache[key]
            logger.debug(f"Cache evicted {len(keys_to_remove)} entries")


# Lazy initialization to avoid import-time failures
_gemini_vision_service: Optional[GeminiVisionService] = None


def get_gemini_vision_service() -> GeminiVisionService:
    """Get or initialize the GeminiVisionService singleton."""
    global _gemini_vision_service
    if _gemini_vision_service is None:
        try:
            _gemini_vision_service = GeminiVisionService()
        except GeminiVisionError as e:
            logger.error(f"Failed to initialize GeminiVisionService: {e}")
            raise
    return _gemini_vision_service


# Backward compatibility alias
gemini_vision_service = None  # Will be None until first call to get_gemini_vision_service()

