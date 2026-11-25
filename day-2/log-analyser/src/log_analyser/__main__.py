"""Allows: python -m log_analyser <logfile>"""
import sys

from .cli import main

sys.exit(main())
