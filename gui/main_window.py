"""主窗口 - 整合所有模块"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QStatusBar,
    QMessageBox,
)

from config.settings import AppConfig
from gui.retrieval_tab import RetrievalTab
from gui.knowledge_tab import KnowledgeTab
from gui.search_tab import SearchTab
from gui.mining_tab import MiningTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = AppConfig.load()
        self._build_ui()
        self._build_menu()
        self._connect_signals()

    def _build_ui(self):
        self.setWindowTitle("科研全流程辅助系统 - Research Assistant")
        self.resize(1280, 820)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel(
            "<h2 style='margin:0;'>🧪 科研全流程辅助系统</h2>"
            "<p style='margin:2px 0 8px 0;color:#666;'>"
            "智能检索 · 文献知识库 · 语义问答 · 创新点挖掘</p>"
        )
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.retrieval_tab = RetrievalTab(self.config)
        self.knowledge_tab = KnowledgeTab(self.config)
        self.search_tab = SearchTab(self.config, self.knowledge_tab.kb)
        self.mining_tab = MiningTab(self.config, self.knowledge_tab.kb)

        self.tabs.addTab(self.retrieval_tab, "🔍 智能检索")
        self.tabs.addTab(self.knowledge_tab, "📚 文献知识库")
        self.tabs.addTab(self.search_tab, "💬 语义检索")
        self.tabs.addTab(self.mining_tab, "💡 创新点挖掘")

        layout.addWidget(self.tabs, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("系统就绪")

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = menubar.addMenu("工具(&T)")
        refresh_kb_action = QAction("刷新知识库", self)
        refresh_kb_action.triggered.connect(self._on_refresh_kb)
        tools_menu.addAction(refresh_kb_action)

        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _connect_signals(self):
        self.retrieval_tab.papers_imported.connect(self._on_papers_imported)
        self.knowledge_tab.papers_available.connect(self.mining_tab.update_papers_from_kb)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_papers_imported(self, paths):
        self.knowledge_tab.add_pending_files(paths)
        self.status_bar.showMessage(f"已添加 {len(paths)} 个文件到待处理队列")

    def _on_refresh_kb(self):
        self.knowledge_tab.refresh_papers()
        self.status_bar.showMessage("知识库已刷新")

    def _on_tab_changed(self, index: int):
        if index == 1:
            self.knowledge_tab.refresh_papers()
        elif index == 2:
            pass
        elif index == 3:
            self.mining_tab.refresh_papers()

    def _on_about(self):
        QMessageBox.about(
            self, "关于",
            "<h3>科研全流程辅助系统</h3>"
            "<p>一款面向科研人员的一站式智能工作台。</p>"
            "<ul>"
            "<li>📚 智能检索聚合器 - arXiv 检索、批量下载、本地 PDF 导入</li>"
            "<li>📖 文献知识库 - PDF 解析、向量嵌入、ChromaDB 存储</li>"
            "<li>🔎 语义问答 - 基于向量相似度的自然语言检索</li>"
            "<li>💡 创新点挖掘 - LLM 结构化摘要、技术演进分析、创新方向推荐</li>"
            "</ul>"
            "<p><i>技术栈: Python + PySide6 + PyMuPDF + Sentence-Transformers + ChromaDB</i></p>"
        )

    def closeEvent(self, event):
        self.config.save()
        event.accept()
