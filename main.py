"""科研全流程辅助系统 - 主程序入口"""
import sys
import logging
from pathlib import Path


def setup_logging():
    """配置全局日志系统"""
    log_dir = Path(__file__).parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("=" * 60)
    logging.info("科研全流程辅助系统启动")
    logging.info("=" * 60)


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

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
        logger.error(f"启动失败: {e}", exc_info=True)
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    try:
        window = MainWindow()
        window.show()
        logger.info("主窗口已显示")
    except Exception as e:
        logger.error(f"创建主窗口失败: {e}", exc_info=True)
        raise

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
