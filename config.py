#!/usr/bin/env python3
"""
Shared settings for the figure scripts (13, 29, 30, 31).
"""

from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.absolute()

# Paper-style colors (consistent across visualizations).
# Every green and red in every plot uses these two shades.
GREEN = '#7DCEA0'
RED = '#F1948A'

# Paper-figure plot area: light gray background with slightly darker gray gridlines.
# The figure margin around the axes stays white.
PANEL_BG = '#F2F2F2'
GRID_COLOR = '#E6E6E6'
GRID_LINEWIDTH = 0.6
