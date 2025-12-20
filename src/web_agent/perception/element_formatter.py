"""
Formats parsed elements for LLM consumption.
SIMPLIFIED: Only shows essential info. Use get_element_details tool for coordinates.
"""
from typing import List, Optional, Tuple
from web_agent.perception.screen_parser import Element


class ElementFormatter:
    """Formats elements into LLM-friendly simplified strings"""
    
    @staticmethod
    def format_for_llm(
        elements: List[Element], 
        max_elements: Optional[int] = None,
        viewport_size: Optional[Tuple[int, int]] = None
    ) -> str:
        """
        Format elements in SIMPLIFIED format - coordinates available via get_element_details tool.
        
        Shows only: ID, type, content, interactivity, DOM info
        Coordinates removed to reduce token usage and prevent hallucination.
        
        Args:
            elements: List of Element objects
            max_elements: Maximum elements to include (None = all)
            viewport_size: (width, height) - used for overlay detection
        
        Returns:
            Simplified formatted string
        """
        if not elements:
            return "NO ELEMENTS FOUND ON PAGE"
        
        # Include ALL elements if max not specified
        elements_to_show = elements if max_elements is None else elements[:max_elements]
        
        lines = [
            "=" * 80,
            f"PAGE ELEMENTS ({len(elements_to_show)} total)",
            "=" * 80,
            "",
            "FORMAT:",
            "- [ID] = Element ID (use this to interact)",
            "- BBOX = Bounding box [left, top, right, bottom] in 0-1 normalized coordinates",
            "- Tree symbols (└─) = Shows containment hierarchy",
            "- (INSIDE #XXX) = Explicit parent reference",
            "",
            "CRITICAL RULES:",
            "1. Use click(element_id=X) or type(element_id=X, text=...) to interact",
            "2. Use get_element_details tool if you need coordinates/bbox/colors",
            "3. If element not here, use analyze_visual_content to find it",
            "",
            "=" * 80,
            "ELEMENTS (showing hierarchy - indented = contained within parent):",
            "=" * 80,
            ""
        ]
        
        # Build parent-child relationships based on spatial containment
        element_dict = {elem.id: elem for elem in elements_to_show}
        children_map = {elem.id: [] for elem in elements_to_show}
        root_elements = []
        
        # Find parent-child relationships
        for elem in elements_to_show:
            smallest_parent = None
            smallest_area = float('inf')
            
            for potential_parent in elements_to_show:
                if potential_parent.id == elem.id:
                    continue
                
                # Check if potential_parent spatially contains elem
                if (potential_parent.bbox[0] <= elem.bbox[0] and
                    potential_parent.bbox[1] <= elem.bbox[1] and
                    potential_parent.bbox[2] >= elem.bbox[2] and
                    potential_parent.bbox[3] >= elem.bbox[3]):
                    
                    parent_area = ((potential_parent.bbox[2] - potential_parent.bbox[0]) *
                                 (potential_parent.bbox[3] - potential_parent.bbox[1]))
                    
                    if parent_area < smallest_area:
                        smallest_area = parent_area
                        smallest_parent = potential_parent
            
            if smallest_parent:
                children_map[smallest_parent.id].append(elem.id)
            else:
                root_elements.append(elem.id)
        
        # Render hierarchy recursively with explicit tree symbols
        def render_element(elem_id: int, indent: int = 0, parent_id: Optional[int] = None):
            elem = element_dict[elem_id]
            
            # Tree symbols for visual hierarchy
            if indent == 0:
                prefix = ""
                tree_symbol = ""
            else:
                prefix = "  " * (indent - 1)
                tree_symbol = "└─ "
            
            # Element type (prefer DOM tag if available)
            if elem.dom_tag:
                elem_type = elem.dom_tag
            else:
                elem_type = elem.type
            
            # Build compact element line with interactivity indicator and parent reference
            content_preview = elem.content[:60] if elem.content else "(no text)"
            interactive_mark = "[interactive]" if elem.interactivity else "[static]"
            
            if parent_id is not None:
                lines.append(f"{prefix}{tree_symbol}[ID:{elem.id:03d}] {interactive_mark} {elem_type} \"{content_preview}\" (INSIDE #{parent_id:03d})")
            else:
                lines.append(f"{prefix}[ID:{elem.id:03d}] {interactive_mark} {elem_type} \"{content_preview}\"")
            
            # Add bbox coordinates (normalized 0-1 range)
            bbox_prefix = prefix + ("      " if indent == 0 else "   ")
            lines.append(f"{bbox_prefix}BBOX: [{elem.bbox[0]:.3f}, {elem.bbox[1]:.3f}, {elem.bbox[2]:.3f}, {elem.bbox[3]:.3f}]")
            
            # Add DOM selectors if available
            dom_parts = []
            if elem.dom_id:
                dom_parts.append(f"#{elem.dom_id}")
            if elem.dom_class:
                first_class = elem.dom_class.split()[0] if elem.dom_class else ""
                if first_class:
                    dom_parts.append(f".{first_class}")
            if elem.dom_role:
                dom_parts.append(f"role={elem.dom_role}")
            if elem.dom_placeholder:
                dom_parts.append(f"placeholder=\"{elem.dom_placeholder[:30]}\"")
            
            if dom_parts:
                lines.append(f"{bbox_prefix}DOM: {' '.join(dom_parts)}")
            
            # Render children with increased indentation
            for child_id in children_map.get(elem_id, []):
                render_element(child_id, indent + 1, parent_id=elem.id)
        
        # Render from root elements
        for root_id in root_elements:
            render_element(root_id)
        
        lines.extend([
            "",
            "=" * 80,
            f"TOTAL: {len(elements_to_show)} elements listed",
            "",
            "REMEMBER:",
            "- Use click(element_id=X) NOT coordinates!",
            "- Use get_element_details if you need precise location info",
            "=" * 80
        ])
        
        return "\n".join(lines)
    
    @staticmethod
    def get_element_details(
        elements: List[Element],
        element_ids: List[int],
        viewport_size: Tuple[int, int] = (1440, 900)
    ) -> dict:
        """
        Get full details for specific element IDs.
        Returns coordinates, bbox, dimensions, DOM info, etc.
        
        Args:
            elements: All available elements
            element_ids: List of IDs to get details for
            viewport_size: (width, height) for pixel conversion
        
        Returns:
            Dict mapping element_id -> details
        """
        result = {}
        
        # Create lookup dict
        elem_dict = {elem.id: elem for elem in elements}
        
        for elem_id in element_ids:
            if elem_id not in elem_dict:
                result[elem_id] = {"error": "Element ID not found"}
                continue
            
            elem = elem_dict[elem_id]
            
            # Calculate pixel coordinates
            width, height = viewport_size
            left_px = int(elem.bbox[0] * width)
            top_px = int(elem.bbox[1] * height)
            right_px = int(elem.bbox[2] * width)
            bottom_px = int(elem.bbox[3] * height)
            center_x_px = int(elem.center[0] * width)
            center_y_px = int(elem.center[1] * height)
            
            result[elem_id] = {
                "id": elem.id,
                "type": elem.type,
                "content": elem.content,
                "interactivity": elem.interactivity,
                "center_pixels": [center_x_px, center_y_px],
                "bbox_pixels": [left_px, top_px, right_px, bottom_px],
                "normalized_center": list(elem.center),
                "normalized_bbox": list(elem.bbox),
                "width_pixels": right_px - left_px,
                "height_pixels": bottom_px - top_px,
                "dom": {
                    "tag": elem.dom_tag,
                    "id": elem.dom_id,
                    "class": elem.dom_class,
                    "role": elem.dom_role,
                    "text": elem.dom_text,
                    "placeholder": elem.dom_placeholder
                },
                "source": elem.source
            }
        
        return result
    
    @staticmethod
    def format_hierarchical(elements: List[Element], viewport_size: tuple = (1440, 900)) -> str:
        """
        Format elements showing HIERARCHY (spatial containment).
        Simplified version without coordinates.
        
        Args:
            elements: List of Element objects
            viewport_size: Not used in simplified version
        
        Returns:
            Hierarchical formatted string
        """
        if not elements:
            return "NO ELEMENTS FOUND"
        
        lines = [
            "=" * 80,
            "HIERARCHICAL ELEMENT VIEW",
            "=" * 80,
            ""
        ]
        
        # Build parent-child relationships based on spatial containment
        element_dict = {elem.id: elem for elem in elements}
        children_map = {elem.id: [] for elem in elements}
        root_elements = []
        
        # Find parent-child relationships
        for elem in elements:
            smallest_parent = None
            smallest_area = float('inf')
            
            for potential_parent in elements:
                if potential_parent.id == elem.id:
                    continue
                
                # Check if potential_parent contains elem
                if (potential_parent.bbox[0] <= elem.bbox[0] and
                    potential_parent.bbox[1] <= elem.bbox[1] and
                    potential_parent.bbox[2] >= elem.bbox[2] and
                    potential_parent.bbox[3] >= elem.bbox[3]):
                    
                    parent_area = ((potential_parent.bbox[2] - potential_parent.bbox[0]) *
                                 (potential_parent.bbox[3] - potential_parent.bbox[1]))
                    
                    if parent_area < smallest_area:
                        smallest_area = parent_area
                        smallest_parent = potential_parent
            
            if smallest_parent:
                children_map[smallest_parent.id].append(elem.id)
            else:
                root_elements.append(elem.id)
        
        # Render hierarchy
        def render_element(elem_id: int, indent: int = 0):
            elem = element_dict[elem_id]
            prefix = "  " * indent
            content_preview = elem.content[:40] if elem.content else "(no content)"
            
            lines.append(f"{prefix}[{elem.id:03d}] {elem.type}: \"{content_preview}\"")
            
            # Render children
            for child_id in children_map.get(elem_id, []):
                render_element(child_id, indent + 1)
        
        # Render from roots
        for root_id in root_elements:
            render_element(root_id)
        
        return "\n".join(lines)
    
    @staticmethod
    def format_for_planner(elements: List[Element], viewport_size: tuple = (1440, 900)) -> str:
        """
        Format elements for planner - very concise summary.
        
        Args:
            elements: List of Element objects
            viewport_size: Not used
        
        Returns:
            Planner-friendly formatted string
        """
        if not elements:
            return "NO ELEMENTS"
        
        lines = [
            f"PAGE CONTAINS {len(elements)} ELEMENTS:",
            ""
        ]
        
        # Group by type
        by_type = {}
        for elem in elements:
            elem_type = elem.dom_tag if elem.dom_tag else elem.type
            if elem_type not in by_type:
                by_type[elem_type] = []
            by_type[elem_type].append(elem)
        
        # Show each type
        for elem_type, type_elements in sorted(by_type.items()):
            interactive_count = sum(1 for e in type_elements if e.interactivity)
            lines.append(f"{elem_type}: {len(type_elements)} total ({interactive_count} interactive)")
            
            # Show first few
            for elem in type_elements[:3]:
                content = elem.content[:40] if elem.content else ""
                lines.append(f"  [{elem.id:03d}] \"{content}\"")
            
            if len(type_elements) > 3:
                lines.append(f"  ... +{len(type_elements) - 3} more")
            
            lines.append("")
        
        return "\n".join(lines)
