"""Knowledge package - seeded company knowledge."""
from app.knowledge.loader import (
    KnowledgeBase,
    create_default_knowledge,
    get_knowledge_base,
)

__all__ = [
    "KnowledgeBase",
    "create_default_knowledge",
    "get_knowledge_base",
]
