"""
Knowledge base loader for seeded company documents.

Loads and serves company-specific knowledge (handbook, policies,
procedures, SOPs) to ground Gemini's reasoning in realistic context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class KnowledgeBase:
    """
    Loads and serves seeded company knowledge.
    
    Knowledge is organized into categories:
    - Handbook: Employee guidelines
    - Policies: Safety, quality, escalation rules
    - Procedures: Step-by-step instructions
    - SOPs: Standard Operating Procedures
    
    Attributes:
        handbook: Loaded handbook content
        policies: Dictionary of policy documents
        procedures: Dictionary of procedure documents
        sops: Dictionary of SOP documents
    """
    handbook: Dict[str, str] = field(default_factory=dict)
    policies: Dict[str, str] = field(default_factory=dict)
    procedures: Dict[str, str] = field(default_factory=dict)
    sops: Dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def load(cls, base_path: Path) -> KnowledgeBase:
        """
        Load knowledge base from directory structure.
        
        Expected structure:
            base_path/
            ├── handbook/
            ├── policies/
            ├── procedures/
            └── sops/
        
        Args:
            base_path: Root directory of knowledge base
            
        Returns:
            Loaded KnowledgeBase instance
        """
        kb = cls()
        
        # Load each category
        for category, storage in [
            ("handbook", kb.handbook),
            ("policies", kb.policies),
            ("procedures", kb.procedures),
            ("sops", kb.sops),
        ]:
            category_path = base_path / category
            if category_path.exists():
                for file_path in category_path.glob("*.md"):
                    name = file_path.stem
                    storage[name] = file_path.read_text(encoding="utf-8")
        
        return kb
    
    def get_context_for_signal(
        self,
        signal_type: str,
        keywords: Optional[List[str]] = None
    ) -> str:
        """
        Get relevant knowledge for a signal type.
        
        Matches signal keywords to relevant documents.
        
        Args:
            signal_type: Type of signal (e.g., "temperature_violation")
            keywords: Additional keywords to match
            
        Returns:
            Concatenated relevant knowledge excerpts
        """
        relevant = []
        search_terms = [signal_type.lower()]
        if keywords:
            search_terms.extend([k.lower() for k in keywords])
        
        # Search all documents
        for doc_name, content in self._all_documents():
            for term in search_terms:
                if term in doc_name.lower() or term in content.lower():
                    relevant.append(f"## {doc_name}\n\n{content}")
                    break
        
        return "\n\n---\n\n".join(relevant[:5])  # Limit to 5 docs
    
    def _all_documents(self):
        """Iterate over all documents."""
        for name, content in self.handbook.items():
            yield f"handbook/{name}", content
        for name, content in self.policies.items():
            yield f"policies/{name}", content
        for name, content in self.procedures.items():
            yield f"procedures/{name}", content
        for name, content in self.sops.items():
            yield f"sops/{name}", content
    
    def get_policy(self, name: str) -> Optional[str]:
        """Get a specific policy by name."""
        return self.policies.get(name)
    
    def get_procedure(self, name: str) -> Optional[str]:
        """Get a specific procedure by name."""
        return self.procedures.get(name)
    
    def get_sop(self, name: str) -> Optional[str]:
        """Get a specific SOP by name."""
        return self.sops.get(name)


# Default knowledge for demo (inline)
DEFAULT_KNOWLEDGE = {
    "policies": {
        "safety_policy": """
# Safety Policy

## General Requirements
- All personnel must wear appropriate PPE at all times
- Report safety hazards immediately to supervisor
- Emergency exits must remain unobstructed

## Escalation
- Minor incidents: Log and inform supervisor within 1 hour
- Moderate incidents: Stop work, secure area, notify supervisor immediately
- Critical incidents: Activate emergency alarm, evacuate if necessary

## PPE Requirements by Zone
- Production floor: Hard hat, safety glasses, steel-toe boots
- Cold storage: Add thermal gloves, insulated jacket
- Machinery areas: Add hearing protection
""",
        "quality_policy": """
# Quality Policy

## Standards
- All products must meet FDA food safety standards
- HACCP critical control points must be monitored continuously
- Non-conforming products must be quarantined immediately

## Temperature Requirements
- Cold storage: 0-4°C
- Freezer storage: -18°C or below
- Production floor: 15-25°C

## Documentation
- All quality checks must be logged with timestamp
- Deviations must be reported within 15 minutes
""",
        "escalation_policy": """
# Escalation Policy

## Decision Authority Levels

### Level 1 (Operator)
- Minor adjustments within parameters
- Logging observations
- Routine maintenance requests

### Level 2 (Supervisor)
- Production line stoppages < 30 minutes
- Staff reassignments within shift
- Equipment repairs < $5,000

### Level 3 (Manager)
- Production line stoppages > 30 minutes
- Major equipment repairs
- Compliance violations
- Staff overtime/callouts

### Level 4 (Director)
- Plant-wide stoppages
- Safety evacuations
- Regulatory notifications
""",
    },
    "procedures": {
        "line_shutdown": """
# Line Shutdown Procedure

## Planned Shutdown
1. Notify all affected personnel 15 minutes in advance
2. Complete current production batch
3. Clear line of all product
4. Power down equipment in sequence
5. Lock out/tag out all energy sources
6. Log shutdown time and reason

## Emergency Shutdown
1. Press emergency stop immediately
2. Clear personnel from danger zone
3. Notify supervisor and safety officer
4. Do not restart until authorized
""",
        "maintenance_procedure": """
# Maintenance Procedure

## Preventive Maintenance
- Daily: Visual inspection, lubrication check
- Weekly: Full equipment inspection, filter change
- Monthly: Calibration verification, belt tension

## Corrective Maintenance
1. Log issue in maintenance system
2. Assess severity (Critical/High/Medium/Low)
3. Isolate equipment if safety risk
4. Schedule repair based on priority
5. Document repair and test before restart
""",
    },
    "sops": {
        "temperature_monitoring": """
# SOP-001: Temperature Monitoring

## Purpose
Ensure cold chain integrity and HACCP compliance.

## Procedure
1. Check temperature displays every 30 minutes
2. Log readings on temperature log sheet
3. If reading outside 0-4°C range:
   a. Verify sensor calibration
   b. Check refrigeration unit operation
   c. If actual deviation, notify supervisor immediately
4. Critical deviation (>6°C): Quarantine affected product

## Documentation
- Electronic logs preferred
- Manual logs acceptable as backup
- Retain records for 2 years
""",
        "ppe_requirements": """
# SOP-002: Personal Protective Equipment

## Required PPE by Area

### Production Floor
- Hard hat
- Safety glasses
- Steel-toe boots
- High-visibility vest

### Cold Storage
- All above plus:
- Thermal gloves
- Insulated jacket
- Face protection below -10°C

## Inspection
- Inspect PPE before each shift
- Report damaged equipment immediately
- Replace worn items within 24 hours
""",
        "break_scheduling": """
# SOP-003: Break Scheduling

## Requirements
- 15-minute break after 4 hours of work
- 30-minute meal break for shifts > 6 hours
- Breaks cannot reduce line coverage below minimum (2 per line)

## Scheduling Process
1. Stagger breaks to maintain coverage
2. High-priority lines take precedence
3. Fatigue management: no worker > 6 hours without break
4. Log break times for labor compliance

## Emergency Override
- Breaks may be delayed (not cancelled) for critical production
- Maximum delay: 30 minutes
- Supervisor approval required
""",
    },
}


def create_default_knowledge() -> KnowledgeBase:
    """Create knowledge base with embedded default knowledge."""
    kb = KnowledgeBase()
    
    for category, docs in DEFAULT_KNOWLEDGE.items():
        storage = getattr(kb, category)
        for name, content in docs.items():
            storage[name] = content
    
    return kb


# Singleton for easy access
_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """Get or create the singleton knowledge base."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = create_default_knowledge()
    return _knowledge_base
