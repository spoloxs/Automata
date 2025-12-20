"""
Test the enhanced element formatter with hierarchy, bbox, and overlay detection.
"""

from web_agent.perception.screen_parser import Element
from web_agent.perception.element_formatter import ElementFormatter


def test_hierarchical_formatting():
    """Test element formatting with hierarchy and overlay detection"""
    
    print("\n" + "="*80)
    print("🧪 TESTING ENHANCED ELEMENT FORMATTER")
    print("="*80)
    
    # Create mock elements simulating a page with popup overlay
    viewport_size = (1440, 900)
    
    elements = [
        # Root element - full page
        Element(
            id=0,
            type="div",
            bbox=(0.0, 0.0, 1.0, 1.0),  # Full screen
            center=(0.5, 0.5),
            content="Main page container",
            interactivity=False,
            source="test",
            dom_tag="div",
            dom_id="main-page",
            dom_class="page-wrapper"
        ),
        
        # Header - inside main page
        Element(
            id=1,
            type="header",
            bbox=(0.0, 0.0, 1.0, 0.1),  # Top 10% of page
            center=(0.5, 0.05),
            content="Website Header",
            interactivity=False,
            source="test",
            dom_tag="header",
            dom_class="site-header"
        ),
        
        # POPUP OVERLAY - large element covering most of screen
        Element(
            id=2,
            type="div",
            bbox=(0.1, 0.1, 0.9, 0.8),  # Covers 70% x 80% = 56% of screen
            center=(0.5, 0.45),
            content="Legal Terms and Privacy",
            interactivity=False,
            source="test",
            dom_tag="div",
            dom_id="privacy-modal",
            dom_class="modal-overlay"
        ),
        
        # Popup title - inside popup
        Element(
            id=3,
            type="text",
            bbox=(0.3, 0.15, 0.7, 0.25),
            center=(0.5, 0.2),
            content="We value your privacy",
            interactivity=False,
            source="test",
            dom_tag="h2",
            dom_class="modal-title"
        ),
        
        # Popup text - inside popup
        Element(
            id=4,
            type="text",
            bbox=(0.2, 0.3, 0.8, 0.5),
            center=(0.5, 0.4),
            content="By continuing, you agree to our Terms of Service...",
            interactivity=False,
            source="test",
            dom_tag="p",
            dom_class="modal-text"
        ),
        
        # CONTINUE button - inside popup
        Element(
            id=5,
            type="button",
            bbox=(0.4, 0.6, 0.6, 0.7),
            center=(0.5, 0.65),
            content="CONTINUE",
            interactivity=True,
            source="test",
            dom_tag="button",
            dom_id="continue-btn",
            dom_class="btn-primary"
        ),
        
        # Navigation link - in header
        Element(
            id=6,
            type="link",
            bbox=(0.1, 0.02, 0.2, 0.08),
            center=(0.15, 0.05),
            content="Games",
            interactivity=True,
            source="test",
            dom_tag="a",
            dom_class="nav-link"
        ),
        
        # Small element test - 10x10px button
        Element(
            id=7,
            type="button",
            bbox=(0.45, 0.12, 0.456, 0.131),  # Roughly 10x10px at 1440x900
            center=(0.453, 0.1255),
            content="X",
            interactivity=True,
            source="test",
            dom_tag="button",
            dom_id="close-btn",
            dom_class="close-button"
        ),
    ]
    
    # Format elements
    formatted = ElementFormatter.format_for_llm(
        elements=elements,
        max_elements=None,
        viewport_size=viewport_size
    )
    
    print("\n" + formatted)
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETE - Verify the output above shows:")
    print("="*80)
    print("1. ⚠️  OVERLAY/POPUP DETECTED warning")
    print("2. Hierarchical structure with └─ symbols")
    print("3. (INSIDE #XXX) parent references")
    print("4. BBOX coordinates for spatial awareness")
    print("5. Proper containment:")
    print("   - Header [ID:001] and Popup [ID:002] are inside Main page [ID:000]")
    print("   - Popup content [ID:003, 004, 005] are inside Popup [ID:002]")
    print("   - Nav link [ID:006] is inside Header [ID:001]")
    print("   - Close button [ID:007] likely in header or standalone")
    print("="*80)
    
    # Test overlay detection
    assert "⚠️  OVERLAY/POPUP DETECTED!" in formatted, "Overlay detection failed"
    assert "privacy-modal" in formatted, "Overlay element missing"
    assert "└─" in formatted, "Tree symbols missing"
    assert "(INSIDE" in formatted, "Parent references missing"
    assert "BBOX:" in formatted, "BBOX coordinates missing"
    
    print("\n✅ All assertions passed!\n")


if __name__ == "__main__":
    test_hierarchical_formatting()
