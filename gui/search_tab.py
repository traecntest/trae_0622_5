"""语义检索 - GUI 标签页"""
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QTextEdit,
    QSplitter, QSpinBox, QAbstractItemView,
)

from core.knowledge.knowledge_base import KnowledgeBase
from core.knowledge.vector_db import SearchResult
from gui.workers import Worker


class SearchTab(QWidget):
    def __init__(self, config, kb: KnowledgeBase):
        super().__init__()
        self.config = config
        self.kb = kb
        self.results: List[SearchResult] = []
        self._workers = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        search_bar = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("用自然语言提问，例如：这篇论文使用了什么方法？Transformer 的注意力机制是如何实现的？...")
        search_bar.addWidget(self.query_edit, 1)

        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 50)
        self.topk_spin.setValue(10)
        search_bar.addWidget(QLabel("返回数量:"))
        search_bar.addWidget(self.topk_spin)

        self.search_btn = QPushButton("检索")
        self.search_btn.clicked.connect(self._on_search)
        self.search_btn.setDefault(True)
        search_bar.addWidget(self.search_btn)

        layout.addLayout(search_bar)

        hint = QLabel("提示：语义检索会基于向量相似度匹配相关段落，支持多文档联合检索。")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Vertical)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["相似度", "论文", "章节", "片段"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        splitter.addWidget(self.results_table)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("选择检索结果查看详细内容...")
        splitter.addWidget(self.detail_text)

        splitter.setSizes([250, 300])
        layout.addWidget(splitter, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        self.status_label = QLabel("就绪")
        bottom_bar.addWidget(self.status_label)

        layout.addLayout(bottom_bar)

        self.results_table.itemClicked.connect(self._on_row_clicked)
        self.query_edit.returnPressed.connect(self._on_search)

    def _on_search(self):
        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "提示", "请输入检索内容")
            return

        if self.kb.count_chunks() == 0:
            QMessageBox.warning(self, "提示", "知识库为空，请先添加文献")
            return

        self.search_btn.setEnabled(False)
        self.status_label.setText("正在检索...")
        self.results_table.setRowCount(0)
        self.results.clear()

        worker = Worker(
            self.kb.semantic_search, query, self.topk_spin.value()
        )
        worker.signals.result.connect(self._on_result)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.search_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _on_result(self, results: List[SearchResult]):
        self.results = results
        self.status_label.setText(f"找到 {len(results)} 条结果")

        self.results_table.setRowCount(len(results))
        for row, r in enumerate(results):
            score_item = QTableWidgetItem(f"{r.score:.3f}")
            score_color = QColor(0, 120, 0) if r.score > 0.6 else QColor(160, 120, 0)
            score_item.setForeground(QBrush(score_color))
            self.results_table.setItem(row, 0, score_item)
            self.results_table.setItem(row, 1, QTableWidgetItem(r.paper_title[:80]))
            self.results_table.setItem(row, 2, QTableWidgetItem(r.section or ""))
            snippet = r.text[:120].replace("\n", " ")
            if len(r.text) > 120:
                snippet += "..."
            self.results_table.setItem(row, 3, QTableWidgetItem(snippet))

    def _on_error(self, msg: str):
        self.status_label.setText(f"错误: {msg}")
        QMessageBox.critical(self, "错误", msg)

    def _on_row_clicked(self, item: QTableWidgetItem):
        row = item.row()
        if row < len(self.results):
            r = self.results[row]
            content = (
                f"【论文】{r.paper_title}\n"
                f"【相似度】{r.score:.4f}\n"
                f"【章节】{r.section or '未知'}\n\n"
                f"【内容】\n{r.text}\n\n"
                f"【元数据】\n"
            )
            for k, v in r.metadata.items():
                if k != "chunk_id":
                    content += f"  {k}: {v}\n"
            self._highlight_text(content, self.query_edit.text())

    def _highlight_text(self, content: str, query: str):
        self.detail_text.clear()
        keywords = [w for w in query.split() if len(w) > 1]

        cursor = self.detail_text.textCursor()
        fmt = QTextCharFormat()
        cursor.insertText(content)

        if keywords:
            for kw in keywords:
                cursor = self.detail_text.textCursor()
                cursor.movePosition(QTextCursor.Start)
                highlight_fmt = QTextCharFormat()
                highlight_fmt.setBackground(QColor(255, 255, 0, 100))
                while True:
                    cursor = self.detail_text.document().find(kw, cursor)
                    if cursor.isNull():
                        break
                    cursor.mergeCharFormat(highlight_fmt)
