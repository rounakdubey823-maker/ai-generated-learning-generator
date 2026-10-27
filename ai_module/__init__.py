"""
AI Module — standalone AI utilities and prompt engineering helpers.

This package is intentionally separate from the backend so it can be
imported independently or packaged as a library later.
"""

from ai_module.generator import (
    calculate_next_level,
    generate,
    generate_adaptive_content,
)

__all__ = [
    "generate",
    "generate_adaptive_content",
    "calculate_next_level",
]
