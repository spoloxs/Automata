"""
Element manipulation utilities.
"""
from typing import List
from web_agent.perception.screen_parser import Element


def filter_interactive_elements(elements: List[Element]) -> List[Element]:
    """Filter only interactive elements"""
    return [e for e in elements if e.interactivity]


def filter_by_type(elements: List[Element], element_type: str) -> List[Element]:
    """Filter elements by type"""
    return [e for e in elements if e.type == element_type]


def find_element_by_content(elements: List[Element], content: str, case_sensitive: bool = False) -> List[Element]:
    """Find elements containing specific content"""
    if not case_sensitive:
        content = content.lower()
        return [e for e in elements if content in e.content.lower()]
    return [e for e in elements if content in e.content]


def find_element_by_id(elements: List[Element], element_id: int) -> Element:
    """Find element by ID"""
    for elem in elements:
        if elem.id == element_id:
            return elem
    return None


def get_elements_in_region(elements: List[Element], x1: float, y1: float, x2: float, y2: float) -> List[Element]:
    """Get elements within a bounding box region"""
    result = []
    for elem in elements:
        cx, cy = elem.center
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            result.append(elem)
    return result
