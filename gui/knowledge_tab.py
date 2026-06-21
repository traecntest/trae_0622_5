"""文献知识库管理 - GUI 标签页"""
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QMessageBox, QTextEdit, QSplitter, QAbstractItemView, QMenu,
)

from core.knowledge.knowledge_base import KnowledgeBase
from gui.workers import Worker


class KnowledgeTab(QWidget):
    papers_available = Signal(list)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.kb = KnowledgeBase(config)
        self.papers_list: List[Dict[str, Any]] = []
        self._pending_files: List[str] = []
        self._workers = []
        self._build_ui()
        self.refresh_papers()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("知识库统计:"))
        self.stat_label = QLabel("0 篇文献, 0 个文本块")
        top_bar.addWidget(self.stat_label)
        top_bar.addStretch()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_papers)
        top_bar.addWidget(self.refresh_btn)

        self.process_btn = QPushButton("处理待添加文件")
        self.process_btn.clicked.connect(self._on_process_pending)
        top_bar.addWidget(self.process_btn)

        self.clear_btn = QPushButton("清空知识库")
        self.clear_btn.clicked.connect(self._on_clear_all)
        top_bar.addWidget(self.clear_btn)

        layout.addLayout(top_bar)

        pending_bar = QHBoxLayout()
        self.pending_label = QLabel("待处理: 0 个文件")
        pending_bar.addWidget(self.pending_label)
        pending_bar.addStretch()
        layout.addLayout(pending_bar)

        splitter = QSplitter(Qt.Vertical)

        self.papers_table = QTableWidget(0, 5)
        self.papers_table.setHorizontalHeaderLabels(["文件名", "标题", "作者", "年份", "页数"])
        self.papers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.papers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.papers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.papers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.papers_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.papers_table.customContextMenuRequested.connect(self._on_context_menu)
        splitter.addWidget(self.papers_table)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("选择一篇论文查看详细信息...")
        splitter.addWidget(self.detail_text)

        splitter.setSizes([300, 250])
        layout.addWidget(splitter, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMaximumWidth(400)
        bottom_bar.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        bottom_bar.addWidget(self.status_label)

        layout.addLayout(bottom_bar)

        self.papers_table.itemSelectionChanged.connect(self._on_selection_changed)

    def add_pending_files(self, files: List[str]):
        new_files = [f for f in files if f not in self._pending_files]
        self._pending_files.extend(new_files)
        self.pending_label.setText(f"待处理: {len(self._pending_files)} 个文件")

    def refresh_papers(self):
        self.papers_list = self.kb.list_papers()
        chunk_count = self.kb.count_chunks()
        self.stat_label.setText(f"{len(self.papers_list)} 篇文献, {chunk_count} 个文本块")

        self.papers_table.setRowCount(len(self.papers_list))
        for row, paper in enumerate(self.papers_list):
            self.papers_table.setItem(row, 0, QTableWidgetItem(paper.get("filename", "")))
            self.papers_table.setItem(row, 1, QTableWidgetItem(paper.get("title", "")[:100]))
            self.papers_table.setItem(row, 2, QTableWidgetItem(paper.get("authors", "")[:80]))
            self.papers_table.setItem(row, 3, QTableWidgetItem(paper.get("year", "")))
            self.papers_table.setItem(row, 4, QTableWidgetItem(paper.get("num_pages", "")))

        self.papers_available.emit(self.papers_list)

    def _on_process_pending(self):
        if not self._pending_files:
            QMessageBox.information(self, "提示", "没有待处理的文件")
            return

        files = list(self._pending_files)
        self._pending_files.clear()
        self.pending_label.setText("待处理: 0 个文件")
        self.process_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"正在处理 {len(files)} 个文件...")

        worker = Worker(self.kb.add_papers_batch, files, progress_cb=lambda p, m: None)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.result.connect(self._on_process_result)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.process_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _on_progress(self, pct: float, msg: str):
        self.progress_bar.setValue(int(pct * 100))
        if msg:
            self.status_label.setText(msg)

    def _on_process_result(self, results: Dict[str, bool]):
        self.progress_bar.setValue(100)
        success = sum(1 for v in results.values() if v)
        self.status_label.setText(f"完成: {success}/{len(results)} 成功")
        self.refresh_papers()
        QMessageBox.information(
            self, "处理完成",
            f"成功处理 {success} 个文件，失败 {len(results) - success} 个。"
        )

    def _on_error(self, msg: str):
        self.status_label.setText(f"错误: {msg}")
        QMessageBox.critical(self, "错误", msg)

    def _on_selection_changed(self):
        rows = self.papers_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row < len(self.papers_list):
            paper = self.papers_list[row]
            parsed = self.kb.get_parsed_paper(paper.get("file_path", ""))
            if parsed:
                detail = (
                    f"文件: {parsed.file_path}\n\n"
                    f"标题: {parsed.title}\n\n"
                    f"作者: {', '.join(parsed.authors) if parsed.authors else '未知'}\n\n"
                    f"年份: {parsed.year or '未知'} | 页数: {parsed.num_pages}\n\n"
                    f"摘要:\n{parsed.abstract or '无'}\n\n"
                    f"章节:\n"
                )
                for sec in parsed.sections[:20]:
                    detail += f"  - {sec.name} (第{sec.page}页)\n"
                if len(parsed.sections) > 20:
                    detail += f"  ... 共 {len(parsed.sections)} 个章节\n"
                detail += f"\n全文预览:\n{parsed.full_text[:2000]}..."
                self.detail_text.setPlainText(detail)
            else:
                detail = (
                    f"文件名: {paper.get('filename', '')}\n"
                    f"标题: {paper.get('title', '')}\n"
                    f"作者: {paper.get('authors', '')}\n"
                    f"年份: {paper.get('year', '')}\n"
                )
                self.detail_text.setPlainText(detail)

    def _on_context_menu(self, pos):
        row = self.papers_table.rowAt(pos.y())
        if row < 0 or row >= len(self.papers_list):
            return
        menu = QMenu(self)
        view_action = menu.addAction("查看详细内容")
        remove_action = menu.addAction("从知识库移除")
        action = menu.exec(self.papers_table.viewport().mapToGlobal(pos))
        if action == remove_action:
            self._on_remove_paper(row)

    def _on_remove_paper(self, row: int):
        if row >= len(self.papers_list):
            return
        paper = self.papers_list[row]
        filename = paper.get("filename", "")
        reply = QMessageBox.question(
            self, "确认", f"确定要从知识库中移除 '{filename}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.kb.remove_paper(filename)
            self.refresh_papers()
            self.status_label.setText(f"已移除: {filename}")

    def _on_clear_all(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清空整个知识库吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.kb.clear_all()
            self.refresh_papers()
            self.status_label.setText("知识库已清空")
