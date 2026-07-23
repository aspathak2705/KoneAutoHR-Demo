from pydantic import BaseModel
from typing import List, Optional, Dict

class DOMElementSummary(BaseModel):
    tag: str
    id: Optional[str] = None
    role: Optional[str] = None
    label: Optional[str] = None
    text: Optional[str] = None
    is_visible: bool = True
    bounding_box: Optional[Dict[str, float]] = None

class AccessibilityNode(BaseModel):
    role: str
    name: Optional[str] = None
    description: Optional[str] = None
    focused: bool = False

class DOMSummary(BaseModel):
    elements: List[DOMElementSummary] = []
    total_interactive_count: int = 0

class AccessibilitySummary(BaseModel):
    nodes: List[AccessibilityNode] = []
    focused_element: Optional[AccessibilityNode] = None
