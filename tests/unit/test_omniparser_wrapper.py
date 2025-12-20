"""
Unit tests for OmniParserWrapper.
"""

from unittest.mock import Mock, patch

import pytest
from PIL import Image

from web_agent.perception.omniparser_wrapper import OmniParserWrapper


@patch("web_agent.perception.omniparser_wrapper.OMNIPARSER_AVAILABLE", True)
@patch("web_agent.perception.omniparser_wrapper.Path")
@patch("web_agent.perception.omniparser_wrapper.get_yolo_model")
@patch("web_agent.perception.omniparser_wrapper.get_caption_model_processor")
def test_omniparser_initialization(mock_caption, mock_yolo, mock_path):
    """Test OmniParser wrapper initialization"""
    mock_path.return_value.exists.return_value = True
    wrapper = OmniParserWrapper()
    assert wrapper is not None


@patch("web_agent.perception.omniparser_wrapper.OMNIPARSER_AVAILABLE", True)
@patch("web_agent.perception.omniparser_wrapper.Path")
@patch("web_agent.perception.omniparser_wrapper.get_yolo_model")
@patch("web_agent.perception.omniparser_wrapper.get_caption_model_processor")
@patch("web_agent.perception.omniparser_wrapper.check_ocr_box")
@patch("web_agent.perception.omniparser_wrapper.get_som_labeled_img")
def test_parse_output_structure(mock_som, mock_ocr, mock_caption, mock_yolo, mock_path):
    """Test that parse returns correct structure"""
    mock_path.return_value.exists.return_value = True
    mock_screenshot = Image.new("RGB", (1280, 720), color="white")

    # Mock OCR output: (text, ocr_bbox), is_goal_filtered
    mock_ocr.return_value = (("text", [0, 0, 100, 100]), False)

    # Mock SOM output: labeled_img, coordinates, content_list
    mock_som.return_value = (mock_screenshot, [[0, 0, 10, 10]], ["content"])

    wrapper = OmniParserWrapper()
    result = wrapper.parse(mock_screenshot)

    # Check structure
    assert "label_coordinates" in result
    assert "parsed_content_list" in result
    assert isinstance(result["label_coordinates"], list)
    assert isinstance(result["parsed_content_list"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
