"""智能检索聚合器 - GUI 标签页"""
import os
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFileDialog, QMessageBox, QTextEdit, QSplitter, QCheckBox,
    QAbstractItemView, QInputDialog,
)

from core.retrieval.retrieval import RetrievalAggregator, PaperMeta
from gui.workers import Worker


class RetrievalTab(QWidget):
    papers_imported = Signal(list)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.aggregator = RetrievalAggregator(
            pdf_dir=config.pdf_dir, max_threads=config.max_threads
        )
        self.search_results: List[PaperMeta] = []
        self._workers: List[Worker] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        search_bar = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.addItems(["arXiv", "通用URL"])
        search_bar.addWidget(QLabel("数据源:"))
        search_bar.addWidget(self.source_combo)

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("输入检索关键词 (arXiv) 或 PDF 链接 (通用URL)...")
        search_bar.addWidget(self.query_edit, 1)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 50)
        self.max_spin.setValue(10)
        search_bar.addWidget(QLabel("最大数量:"))
        search_bar.addWidget(self.max_spin)

        self.search_btn = QPushButton("检索")
        self.search_btn.clicked.connect(self._on_search)
        search_bar.addWidget(self.search_btn)

        layout.addLayout(search_bar)

        url_bar = QHBoxLayout()
        self.import_pdf_btn = QPushButton("导入本地 PDF...")
        self.import_pdf_btn.clicked.connect(self._on_import_local)
        url_bar.addWidget(self.import_pdf_btn)

        self.import_dir_btn = QPushButton("扫描 PDF 文件夹...")
        self.import_dir_btn.clicked.connect(self._on_import_dir)
        url_bar.addWidget(self.import_dir_btn)

        self.download_url_btn = QPushButton("从 URL 下载 PDF")
        self.download_url_btn.clicked.connect(self._on_download_url)
        url_bar.addWidget(self.download_url_btn)

        url_bar.addStretch()

        self.status_label = QLabel("就绪")
        url_bar.addWidget(self.status_label)

        layout.addLayout(url_bar)

        splitter = QSplitter(Qt.Vertical)

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(["选择", "标题", "作者", "年份", "来源"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        splitter.addWidget(self.results_table)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("选择一条结果查看详情...")
        splitter.addWidget(self.detail_text)

        splitter.setSizes([300, 200])
        layout.addWidget(splitter, 1)

        action_bar = QHBoxLayout()
        self.select_all_cb = QCheckBox("全选")
        self.select_all_cb.toggled.connect(self._on_select_all)
        action_bar.addWidget(self.select_all_cb)

        self.download_btn = QPushButton("下载选中到知识库")
        self.download_btn.clicked.connect(self._on_download_selected)
        action_bar.addWidget(self.download_btn)

        action_bar.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(300)
        action_bar.addWidget(self.progress_bar)

        layout.addLayout(action_bar)

        self.results_table.itemClicked.connect(self._on_row_clicked)
        self.source_combo.currentTextChanged.connect(self._on_source_changed)
        self._on_source_changed(self.source_combo.currentText())

    def _on_source_changed(self, source: str):
        if source == "通用URL":
            self.query_edit.setPlaceholderText("输入包含 PDF 链接的网页 URL 或直接输入 PDF URL...")
            self.max_spin.setEnabled(False)
        else:
            self.query_edit.setPlaceholderText("输入检索关键词 (例如: transformer attention)...")
            self.max_spin.setEnabled(True)

    def _on_search(self):
        source = self.source_combo.currentText()
        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "提示", "请输入检索内容")
            return

        self.search_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在检索...")
        self.results_table.setRowCount(0)
        self.search_results.clear()

        if source == "arXiv":
            worker = Worker(self.aggregator.search_arxiv, query, self.max_spin.value())
        else:
            worker = Worker(self._search_url, query)

        worker.signals.result.connect(self._on_search_result)
        worker.signals.error.connect(self._on_search_error)
        worker.signals.finished.connect(lambda: self.search_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _search_url(self, url: str, progress_cb=None) -> List[PaperMeta]:
        links = self.aggregator.url_downloader.extract_pdf_links(url)
        results = []
        for link in links:
            title = Path(link).stem.replace("_", " ").replace("-", " ")
            results.append(PaperMeta(
                title=title, authors=[], abstract="",
                url=url, pdf_url=link, source="URL"
            ))
        return results

    def _on_search_result(self, results: List[PaperMeta]):
        self.search_results = results
        self.progress_bar.setValue(100)
        self.status_label.setText(f"找到 {len(results)} 条结果")

        self.results_table.setRowCount(len(results))
        for row, paper in enumerate(results):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Unchecked)
            self.results_table.setItem(row, 0, checkbox_item)
            self.results_table.setItem(row, 1, QTableWidgetItem(paper.title[:100]))
            self.results_table.setItem(row, 2, QTableWidgetItem(", ".join(paper.authors[:3])))
            self.results_table.setItem(row, 3, QTableWidgetItem(str(paper.year or "")))
            self.results_table.setItem(row, 4, QTableWidgetItem(paper.source))

    def _on_search_error(self, msg: str):
        self.status_label.setText(f"检索失败: {msg}")
        QMessageBox.critical(self, "错误", f"检索失败: {msg}")

    def _on_row_clicked(self, item: QTableWidgetItem):
        row = item.row()
        if row < len(self.search_results):
            paper = self.search_results[row]
            detail = (
                f"标题: {paper.title}\n\n"
                f"作者: {', '.join(paper.authors) if paper.authors else '未知'}\n\n"
                f"来源: {paper.source} | 年份: {paper.year or '未知'}\n\n"
                f"PDF 链接: {paper.pdf_url}\n\n"
                f"摘要:\n{paper.abstract or '无'}"
            )
            self.detail_text.setPlainText(detail)

    def _on_select_all(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            if item:
                item.setCheckState(state)

    def _on_download_selected(self):
        selected_papers = []
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            if item and item.checkState() == Qt.Checked and row < len(self.search_results):
                selected_papers.append(self.search_results[row])

        if not selected_papers:
            QMessageBox.warning(self, "提示", "请至少选择一篇论文")
            return

        self.download_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"正在下载 {len(selected_papers)} 篇论文...")

        worker = Worker(
            self.aggregator.download_papers, selected_papers,
            progress_cb=lambda i, pct, err=None: None
        )
        worker.signals.progress.connect(self._on_download_progress)
        worker.signals.result.connect(self._on_download_result)
        worker.signals.error.connect(self._on_search_error)
        worker.signals.finished.connect(lambda: self.download_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _on_download_progress(self, pct: float, msg: str):
        self.progress_bar.setValue(int(pct * 100))
        if msg:
            self.status_label.setText(msg)

    def _on_download_result(self, papers: List[PaperMeta]):
        downloaded = [p for p in papers if p.local_path]
        self.progress_bar.setValue(100)
        self.status_label.setText(f"下载完成: {len(downloaded)}/{len(papers)}")
        paths = [p.local_path for p in downloaded if p.local_path]
        if paths:
            self.papers_imported.emit(paths)
        if downloaded:
            QMessageBox.information(
                self, "完成",
                f"成功下载 {len(downloaded)} 篇论文，已加入知识库队列。"
            )

    def _on_import_local(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择 PDF 文件", "", "PDF 文件 (*.pdf)"
        )
        if files:
            self.status_label.setText(f"已选择 {len(files)} 个文件")
            self.papers_imported.emit(files)
            QMessageBox.information(self, "提示", f"已添加 {len(files)} 个文件到知识库处理队列。")

    def _on_import_dir(self):
        dirpath = QFileDialog.getExistingDirectory(self, "选择包含 PDF 的文件夹")
        if dirpath:
            pdf_files = []
            for root, _, files in os.walk(dirpath):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        pdf_files.append(os.path.join(root, f))
            if pdf_files:
                self.status_label.setText(f"扫描到 {len(pdf_files)} 个 PDF 文件")
                self.papers_imported.emit(pdf_files)
                QMessageBox.information(self, "提示", f"已扫描 {len(pdf_files)} 个 PDF 文件并加入处理队列。")
            else:
                QMessageBox.warning(self, "提示", "该文件夹下未找到 PDF 文件。")

    def _on_download_url(self):
        url, ok = QInputDialog().getText(
            self, "从 URL 下载", "请输入 PDF 文件的直接链接:"
        )
        if ok and url.strip():
            self.status_label.setText("正在下载...")
            self.progress_bar.setValue(0)
            worker = Worker(
                self.aggregator.download_single, url.strip(),
                progress_cb=lambda pct, err=None: None
            )
            worker.signals.result.connect(lambda p: self._on_single_downloaded(p, url))
            worker.signals.error.connect(self._on_search_error)
            self._workers.append(worker)
            worker.start()

    def _on_single_downloaded(self, local_path, url):
        self.progress_bar.setValue(100)
        if local_path:
            self.status_label.setText(f"下载完成: {os.path.basename(local_path)}")
            self.papers_imported.emit([local_path])
            QMessageBox.information(self, "完成", "PDF 下载成功，已加入知识库。")
        else:
            self.status_label.setText("下载失败")
            QMessageBox.critical(self, "错误", f"无法从该 URL 下载 PDF。")
