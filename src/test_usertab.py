#!/usr/bin/env python3
# UserTab import 테스트

import sys
import os

print("Current working directory:", os.getcwd())
print("Python path:", sys.path[:3])

# UserTab import 시도
try:
    from ui_user_tab import UserTab
    print("SUCCESS: UserTab import success")
    print("UserTab class:", UserTab)
    # Check signals
    signals = []
    for name in dir(UserTab):
        attr = getattr(UserTab, name)
        if hasattr(attr, 'connect'):  # Signal objects have connect method
            signals.append(name)
    print("UserTab signals:", signals)
except ImportError as e:
    print("ERROR: Could not import UserTab:", e)
    print("UserTab will be disabled")
    UserTab = None

print("Final UserTab value:", UserTab)