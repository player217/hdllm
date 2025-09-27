"""
시작 프로그램에 TT Launcher 바로가기 생성 스크립트
"""
import os
import sys
import win32com.client
from pathlib import Path

def create_startup_shortcut():
    """시작 프로그램 폴더에 바로가기 생성"""
    
    # 경로 설정
    project_root = Path(__file__).parent
    exe_path = project_root / "dist" / "tray_launcher.exe"
    startup_folder = Path(os.environ['APPDATA']) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut_path = startup_folder / "TT Launcher.lnk"
    
    # exe 파일 존재 확인
    if not exe_path.exists():
        print(f"❌ 실행 파일을 찾을 수 없습니다: {exe_path}")
        return False
    
    try:
        # 기존 바로가기 삭제
        if shortcut_path.exists():
            print(f"기존 바로가기 삭제 중...")
            shortcut_path.unlink()
        
        # 바로가기 생성
        print(f"바로가기 생성 중...")
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = str(exe_path)
        shortcut.WorkingDirectory = str(project_root)
        shortcut.IconLocation = str(exe_path)
        shortcut.Description = "TT Application Launcher"
        shortcut.Save()
        
        # 결과 확인
        if shortcut_path.exists():
            print(f"✅ 바로가기 생성 성공!")
            print(f"   위치: {shortcut_path}")
            print(f"   대상: {exe_path}")
            print(f"   다음 부팅 시 자동으로 실행됩니다.")
            return True
        else:
            print(f"❌ 바로가기 생성 실패")
            return False
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print(" TT Launcher 시작 프로그램 등록")
    print("=" * 60)
    print()
    
    success = create_startup_shortcut()
    
    print()
    print("=" * 60)
    
    if success:
        # 시작 폴더 열기
        startup_folder = Path(os.environ['APPDATA']) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        os.startfile(startup_folder)
    
    input("\n계속하려면 Enter를 누르세요...")