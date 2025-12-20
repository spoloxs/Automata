"""
Pytest configuration and fixtures.
"""

import asyncio
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="function")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_screenshot():
    """Mock screenshot for testing"""
    from PIL import Image

    return Image.new("RGB", (1280, 720), color="white")


@pytest.fixture
def mock_elements():
    """Mock parsed elements for testing"""
    from web_agent.perception.screen_parser import Element

    return [
        Element(
            id=0,
            type="text",
            bbox=(0.1, 0.1, 0.3, 0.2),
            center=(0.2, 0.15),
            content="Test Button",
            interactivity=True,
            source="test",
        ),
        Element(
            id=1,
            type="icon",
            bbox=(0.5, 0.5, 0.6, 0.6),
            center=(0.55, 0.55),
            content="",
            interactivity=True,
            source="test",
        ),
    ]


@pytest.fixture
def sample_task():
    """Sample task for testing"""
    from web_agent.core.task import Task

    return Task(description="Test task", dependencies=[], metadata={"test": True})
