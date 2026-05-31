#!/usr/bin/env python3
"""Точка входу: запускає Pi-Supertonic сервер."""

import sys
import os

# Додаємо корінь проєкту в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.main import run

if __name__ == "__main__":
    run()
