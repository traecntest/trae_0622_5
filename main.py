"""科研全流程辅助系统 - 主程序入口"""
import sys
from pathlib import Path


def main():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("错误: PySide6 未安装。请运行: pip install -r requirements.txt")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("Research Assistant")
    app.setOrganizationName("ResearchLab")

    try:
        from gui.main_window import MainWindow
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
