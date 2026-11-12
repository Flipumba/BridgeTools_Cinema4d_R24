# -*- coding: utf-8 -*-
"""Общий запуск всех тестов без Cinema 4D.

    python3 tests/run_all.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = loader.discover(HERE, pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
