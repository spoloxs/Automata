"""
Tool definitions for Gemini function calling.
Defines all browser actions as callable tools.
"""

BROWSER_TOOLS = [
    {
        "name": "get_element_details",
        "description": "Get full details for specific element IDs including coordinates, bbox, dimensions, colors, DOM info. Use this if you need precise positioning information.",
        "parameters": {
            "type": "object",
            "properties": {
                "element_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of element IDs to get details for"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you need these element details"
                }
            },
            "required": ["element_ids", "reasoning"]
        }
    },
    {
        "name": "click",
        "description": "Click an element by ID. Much simpler than using coordinates!",
        "parameters": {
            "type": "object",
            "properties": {
                "element_id": {
                    "type": "integer",
                    "description": "The ID of the element to click (from the element list)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you are clicking this element"
                }
            },
            "required": ["element_id", "reasoning"]
        }
    },
    {
        "name": "type",
        "description": "Type text into an element by ID. Much simpler than using coordinates!",
        "parameters": {
            "type": "object",
            "properties": {
                "element_id": {
                    "type": "integer",
                    "description": "The ID of the element to type into (must be an input/textarea)"
                },
                "text": {
                    "type": "string",
                    "description": "The text to type"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you are typing this text"
                }
            },
            "required": ["element_id", "text", "reasoning"]
        }
    },
    {
        "name": "press_enter",
        "description": "Press the Enter key. Use after typing to submit a form or search.",
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Why you are pressing Enter"
                }
            },
            "required": ["reasoning"]
        }
    },
    {
        "name": "navigate",
        "description": "Navigate to a specific URL in the SAME tab (does NOT open new tabs). Use when you need to go to a different website or page.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to navigate to (must include protocol: http:// or https://)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you are navigating to this URL"
                }
            },
            "required": ["url", "reasoning"]
        }
    },
    {
        "name": "scroll",
        "description": "Scroll the page up or down. Use when you need to see more content.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Direction to scroll"
                },
                "amount": {
                    "type": "integer",
                    "description": "Number of pixels to scroll (default: 500)",
                    "default": 500
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you are scrolling"
                }
            },
            "required": ["direction", "reasoning"]
        }
    },
    {
        "name": "wait",
        "description": "Wait for a specified number of seconds. Use when page is loading or animation is happening.",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Number of seconds to wait"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why you are waiting"
                }
            },
            "required": ["seconds", "reasoning"]
        }
    },
    {
        "name": "analyze_visual_content",
        "description": "Deep visual analysis using Gemini Vision API to understand complex page layouts and find elements. Note: This is SLOW (5-10 seconds) and has API costs. Consider checking the element list, scrolling, and using get_element_details first - most elements are already there! Best used for: complex visual patterns (game grids, tables), overlays not in element list, or when you've thoroughly checked available elements and genuinely need visual understanding.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Comprehensive question about visual content. Ask for everything you need in ONE call for efficiency (e.g., 'Find ALL interactive elements: buttons, grid cells, input fields with coordinates')"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explain what you need visual analysis for and why the element list isn't sufficient. This helps optimize tool usage."
                }
            },
            "required": ["question", "reasoning"]
        }
    },
    {
        "name": "store_data",
        "description": "Store ANY important information, observations, patterns, or insights you discover. This is YOUR tool to remember things. Use it to store: extracted data, observed patterns, failed attempts, hypotheses, important page state, learned behaviors, or any insight that will help avoid repeating work. Think of this as your persistent memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Descriptive key for what you're storing (e.g., 'failed_passwords', 'working_strategy', 'observed_pattern', 'page_quirk')"
                },
                "value": {
                    "type": ["string", "number", "object", "array"],
                    "description": "The information to store - can be any format that's useful to you"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why this information is important to remember"
                }
            },
            "required": ["key", "value", "reasoning"]
        }
    },
    {
        "name": "get_accomplishments",
        "description": "Retrieve a summary of what has already been accomplished in this session. Use when you need to check what actions have been tried or completed.",
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Why you need to check accomplishments"
                }
            },
            "required": ["reasoning"]
        }
    },
    {
        "name": "scroll_to_result",
        "description": "Scroll the page to center on an element before marking task complete. Use this to show where you found the answer or completed the task.",
        "parameters": {
            "type": "object",
            "properties": {
                "element_id": {
                    "type": "integer",
                    "description": "The ID of the element to scroll to and center"
                },
                "reasoning": {
                    "type": "string",
                    "description": "What element/result you're scrolling to show"
                }
            },
            "required": ["element_id", "reasoning"]
        }
    },
    {
        "name": "mark_task_complete",
        "description": "Mark the current task as complete. ONLY use this when you have fully accomplished the task objective. IMPORTANT: If you interacted with specific elements, call scroll_to_result FIRST to show where you completed the task.",
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of why the task is complete and what was accomplished"
                }
            },
            "required": ["reasoning"]
        }
    }
]


PLANNING_TOOLS = [
    {
        "name": "scroll",
        "description": "Scroll the page to explore more content",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"]
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "analyze_page_structure",
        "description": "Analyze the overall page structure and layout",
        "parameters": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "What aspect to focus on (e.g., 'navigation', 'forms', 'content areas')"
                }
            },
            "required": ["focus"]
        }
    },
    {
        "name": "finish_exploration",
        "description": "Finish exploration and create the plan",
        "parameters": {
            "type": "object",
            "properties": {
                "ready": {
                    "type": "boolean",
                    "description": "Whether ready to create plan"
                }
            },
            "required": ["ready"]
        }
    }
]


def get_browser_tools():
    """Get browser action tools"""
    return BROWSER_TOOLS


def get_planning_tools():
    """Get planning/exploration tools"""
    return PLANNING_TOOLS
