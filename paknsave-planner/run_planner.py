#!/usr/bin/env python
"""Simple runner for the meal planner pipeline."""

import sys
import os

# Add src to path so imports work from any CWD
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ai.claude import generate_meal_plan
from planner import get_market_data

if __name__ == "__main__":
    market_data = get_market_data()
    generate_meal_plan(market_data)
