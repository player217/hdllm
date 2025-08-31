#!/usr/bin/env python3
# 최소한의 GUI 테스트로 UserTab 상태 확인

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt

# UserTab import 테스트
try:
    from ui_user_tab import UserTab
    print("SUCCESS: UserTab import SUCCESS")
    USERTAB_AVAILABLE = True
except ImportError as e:
    print(f"FAILED: UserTab import FAILED: {e}")
    USERTAB_AVAILABLE = False
    UserTab = None

class MinimalTestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UserTab 테스트")
        self.setGeometry(100, 100, 800, 600)
        
        # 탭 위젯 생성
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # UserTab 추가 시도
        if USERTAB_AVAILABLE and UserTab is not None:
            try:
                print("TRYING: UserTab instance creation...")
                self.user_tab = UserTab(self)
                print("SUCCESS: UserTab instance created")
                
                print("TRYING: Adding UserTab to tab widget...")
                self.tabs.addTab(self.user_tab, "사용자")
                print("SUCCESS: UserTab added to tabs")
                
            except Exception as e:
                print(f"FAILED: UserTab creation failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("FAILED: UserTab not available")
        
        # 테스트 탭 추가
        test_tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("테스트 탭"))
        test_tab.setLayout(layout)
        self.tabs.addTab(test_tab, "테스트")
        
        print(f"RESULT: Total tabs: {self.tabs.count()}")
        for i in range(self.tabs.count()):
            print(f"  - Tab {i}: {self.tabs.tabText(i)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    print("START: Minimal GUI test starting...")
    window = MinimalTestApp()
    window.show()
    print("SHOW: GUI window displayed")
    
    # GUI를 3초 후 자동 종료
    from PySide6.QtCore import QTimer
    QTimer.singleShot(3000, app.quit)
    
    app.exec()