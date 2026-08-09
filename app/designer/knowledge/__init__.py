"""Design knowledge base — reusable design assets, loaded and validated at startup."""

from app.designer.knowledge.loader import DesignKnowledgeBase
from app.designer.knowledge.validation import DesignKnowledgeBaseError

__all__ = ["DesignKnowledgeBase", "DesignKnowledgeBaseError"]
