"""Perception package"""
from web_agent.perception.screen_parser import ScreenParser, Element
from web_agent.perception.element_formatter import ElementFormatter

def get_omniparser():
    from web_agent.perception.omniparser_wrapper import get_omniparser as _get
    return _get()

__all__ = ["ScreenParser", "Element", "ElementFormatter", "get_omniparser"]
