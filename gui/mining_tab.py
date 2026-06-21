"""创新点挖掘引擎 - GUI 标签页"""
import os
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QMessageBox, QTextEdit, QSplitter, QAbstractItemView, QCheckBox,
    QListWidget, QListWidgetItem, QTabWidget, QFileDialog, QInputDialog,
)

from core.knowledge.knowledge_base import KnowledgeBase
from core.mining.mining_engine import (
    MiningEngine, StructuredSummary, TechEvolutionRoadmap, InnovationSuggestion,
)
from gui.workers import Worker


class MiningTab(QWidget):
    def __init__(self, config, kb: KnowledgeBase):
        super().__init__()
        self.config = config
        self.kb = kb
        self.engine = MiningEngine(config)
        self.summaries: List[StructuredSummary] = []
        self.roadmap: TechEvolutionRoadmap = None
        self.innovations: List[InnovationSuggestion] = []
        self._workers = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        status_bar = QHBoxLayout()
        self.llm_status = QLabel()
        self._update_llm_status()
        status_bar.addWidget(self.llm_status)
        status_bar.addStretch()
        self.config_btn = QPushButton("LLM 设置")
        self.config_btn.clicked.connect(self._on_show_llm_config)
        status_bar.addWidget(self.config_btn)
        layout.addLayout(status_bar)

        main_splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("选择分析的论文:"))
        self.papers_list = QListWidget()
        self.papers_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        left_layout.addWidget(self.papers_list, 1)

        list_btns = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(lambda: self.papers_list.selectAll())
        list_btns.addWidget(self.select_all_btn)
        self.clear_sel_btn = QPushButton("清除")
        self.clear_sel_btn.clicked.connect(lambda: self.papers_list.clearSelection())
        list_btns.addWidget(self.clear_sel_btn)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_papers)
        list_btns.addWidget(self.refresh_btn)
        left_layout.addLayout(list_btns)

        action_box = QVBoxLayout()
        action_box.addWidget(QLabel("主题提示 (可选):"))
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("例如: 计算机视觉中的目标检测")
        action_box.addWidget(self.topic_edit)

        self.summary_btn = QPushButton("1. 生成结构化摘要")
        self.summary_btn.clicked.connect(self._on_generate_summaries)
        action_box.addWidget(self.summary_btn)

        self.roadmap_btn = QPushButton("2. 分析技术演进路线")
        self.roadmap_btn.clicked.connect(self._on_analyze_roadmap)
        action_box.addWidget(self.roadmap_btn)

        self.innovation_btn = QPushButton("3. 推荐创新研究方向")
        self.innovation_btn.clicked.connect(self._on_suggest_innovations)
        action_box.addWidget(self.innovation_btn)

        self.compare_btn = QPushButton("对比选中论文")
        self.compare_btn.clicked.connect(self._on_compare_papers)
        action_box.addWidget(self.compare_btn)

        self.export_btn = QPushButton("导出分析报告 (Markdown)")
        self.export_btn.clicked.connect(self._on_export)
        action_box.addWidget(self.export_btn)

        left_layout.addLayout(action_box)

        main_splitter.addWidget(left_widget)

        self.result_tabs = QTabWidget()

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("生成的论文结构化摘要将显示在此处...")
        self.result_tabs.addTab(self.summary_text, "结构化摘要")

        self.roadmap_text = QTextEdit()
        self.roadmap_text.setReadOnly(True)
        self.roadmap_text.setPlaceholderText("技术演进路线图分析结果将显示在此处...")
        self.result_tabs.addTab(self.roadmap_text, "技术演进")

        self.innovation_text = QTextEdit()
        self.innovation_text.setReadOnly(True)
        self.innovation_text.setPlaceholderText("创新研究方向建议将显示在此处...")
        self.result_tabs.addTab(self.innovation_text, "创新方向")

        self.compare_text = QTextEdit()
        self.compare_text.setReadOnly(True)
        self.compare_text.setPlaceholderText("论文对比分析结果将显示在此处...")
        self.result_tabs.addTab(self.compare_text, "论文对比")

        main_splitter.addWidget(self.result_tabs)
        main_splitter.setSizes([280, 600])
        layout.addWidget(main_splitter, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMaximumWidth(400)
        bottom_bar.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        bottom_bar.addWidget(self.status_label)

        layout.addLayout(bottom_bar)

        self.refresh_papers()

    def _update_llm_status(self):
        if self.engine.is_llm_configured():
            self.llm_status.setText(
                f"✅ LLM 已配置 ({self.config.llm.provider.upper()}: {self.config.llm.model})"
            )
            self.llm_status.setStyleSheet("color: darkgreen;")
        else:
            self.llm_status.setText("⚠️ LLM 未配置 - 点击右上角设置 API")
            self.llm_status.setStyleSheet("color: darkorange;")

    def refresh_papers(self):
        self.papers_list.clear()
        papers = self.kb.list_papers()
        for p in papers:
            item = QListWidgetItem(f"{p.get('title', p.get('filename', ''))[:80]}")
            item.setData(Qt.UserRole, p)
            self.papers_list.addItem(item)

    def update_papers_from_kb(self, papers: List[Dict[str, Any]]):
        self.papers_list.clear()
        for p in papers:
            item = QListWidgetItem(f"{p.get('title', p.get('filename', ''))[:80]}")
            item.setData(Qt.UserRole, p)
            self.papers_list.addItem(item)

    def _get_selected_papers_data(self) -> List[Dict[str, Any]]:
        items = self.papers_list.selectedItems()
        if not items:
            items = [self.papers_list.item(i) for i in range(self.papers_list.count())]
        data = []
        for it in items:
            meta = it.data(Qt.UserRole) or {}
            file_path = meta.get("file_path", "")
            if file_path:
                parsed = self.kb.get_parsed_paper(file_path)
                if parsed:
                    data.append({
                        "title": parsed.title,
                        "full_text": parsed.full_text,
                        "file_path": file_path,
                    })
        return data

    def _on_generate_summaries(self):
        papers = self._get_selected_papers_data()
        if not papers:
            QMessageBox.warning(self, "提示", "没有可分析的论文")
            return
        if not self.engine.is_llm_configured():
            QMessageBox.warning(self, "提示", "请先配置 LLM API")
            return

        self.summary_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在生成摘要...")

        worker = Worker(self.engine.generate_summaries_batch, papers, progress_cb=lambda p, m: None)
        worker.signals.progress.connect(lambda p, m: (self.progress_bar.setValue(int(p * 100)), self.status_label.setText(m)))
        worker.signals.result.connect(self._on_summaries_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.summary_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _on_summaries_done(self, summaries: List[StructuredSummary]):
        self.summaries = summaries
        self.progress_bar.setValue(100)
        self.status_label.setText(f"已生成 {len(summaries)} 篇摘要")
        self.result_tabs.setCurrentIndex(0)

        text = ""
        for i, s in enumerate(summaries, 1):
            text += f"## {i}. {s.title}\n\n"
            if s.background:
                text += f"**研究背景**: {s.background}\n\n"
            if s.core_method:
                text += f"**核心方法**: {s.core_method}\n\n"
            if s.key_contributions:
                text += "**主要贡献**:\n"
                for c in s.key_contributions:
                    text += f"- {c}\n"
                text += "\n"
            if s.limitations:
                text += "**局限性**:\n"
                for l in s.limitations:
                    text += f"- {l}\n"
                text += "\n"
            if s.datasets:
                text += f"**数据集**: {', '.join(s.datasets)}\n\n"
            if s.results:
                text += f"**实验结果**: {s.results}\n\n"
            text += "---\n\n"

        self.summary_text.setMarkdown(text)

    def _on_analyze_roadmap(self):
        if not self.summaries:
            QMessageBox.warning(self, "提示", "请先生成结构化摘要")
            return

        self.roadmap_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在分析技术演进...")

        topic = self.topic_edit.text().strip()
        worker = Worker(self.engine.analyze_evolution, self.summaries, topic)
        worker.signals.result.connect(self._on_roadmap_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.roadmap_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _on_roadmap_done(self, roadmap: TechEvolutionRoadmap):
        self.roadmap = roadmap
        self.progress_bar.setValue(100)
        self.status_label.setText("技术演进分析完成")
        self.result_tabs.setCurrentIndex(1)

        text = f"# 技术演进路线图\n\n"
        text += f"**研究领域**: {roadmap.topic}\n\n"

        if roadmap.timeline:
            text += "## 时间线\n\n"
            sorted_nodes = sorted(roadmap.timeline, key=lambda x: x.year or "0")
            for node in sorted_nodes:
                text += f"### {node.year} - {node.title}\n\n"
                if node.method:
                    text += f"- **方法**: {node.method}\n"
                if node.contribution:
                    text += f"- **贡献**: {node.contribution}\n"
                text += "\n"

        if roadmap.trends:
            text += "## 技术趋势\n\n"
            for t in roadmap.trends:
                text += f"- {t}\n"
            text += "\n"

        if roadmap.gaps:
            text += "## 研究空白\n\n"
            for g in roadmap.gaps:
                text += f"- {g}\n"
            text += "\n"

        self.roadmap_text.setMarkdown(text)

    def _on_suggest_innovations(self):
        if not self.summaries:
            QMessageBox.warning(self, "提示", "请先生成结构化摘要")
            return

        self.innovation_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在生成创新建议...")

        focus = self.topic_edit.text().strip()
        worker = Worker(
            self.engine.suggest_innovations, self.summaries, self.roadmap, focus
        )
        worker.signals.result.connect(self._on_innovations_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.innovation_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _on_innovations_done(self, innovations: List[InnovationSuggestion]):
        self.innovations = innovations
        self.progress_bar.setValue(100)
        self.status_label.setText(f"已生成 {len(innovations)} 条创新建议")
        self.result_tabs.setCurrentIndex(2)

        text = "# 创新研究方向建议\n\n"
        for i, inn in enumerate(innovations, 1):
            text += f"## {i}. {inn.title}\n\n"
            text += f"**描述**: {inn.description}\n\n"
            if inn.feasibility:
                text += f"**可行性**: {inn.feasibility}\n\n"
            if inn.novelty:
                text += f"**创新性**: {inn.novelty}\n\n"
            if inn.related_papers:
                text += "**相关论文**:\n"
                for p in inn.related_papers:
                    text += f"- {p}\n"
                text += "\n"

        self.innovation_text.setMarkdown(text)

    def _on_compare_papers(self):
        if not self.summaries or len(self.summaries) < 2:
            QMessageBox.warning(self, "提示", "请先生成至少 2 篇论文的摘要")
            return

        items = self.papers_list.selectedItems()
        if len(items) < 2:
            QMessageBox.warning(self, "提示", "请至少选择 2 篇论文进行对比")
            return

        indices = []
        for it in items:
            meta = it.data(Qt.UserRole) or {}
            title = meta.get("title", "")
            for i, s in enumerate(self.summaries):
                if s.title == title or s.title in title or title in s.title:
                    indices.append(i)
                    break

        if len(indices) < 2:
            indices = list(range(min(5, len(self.summaries))))

        self.compare_btn.setEnabled(False)
        self.status_label.setText("正在对比分析...")

        worker = Worker(self.engine.compare_papers, self.summaries, indices)
        worker.signals.result.connect(self._on_compare_done)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.compare_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _on_compare_done(self, result: str):
        self.progress_bar.setValue(100)
        self.status_label.setText("对比完成")
        self.result_tabs.setCurrentIndex(3)
        self.compare_text.setMarkdown(result)

    def _on_export(self):
        if not self.summaries:
            QMessageBox.warning(self, "提示", "没有可导出的分析数据")
            return
        default = os.path.join(self.config.export_dir, "research_report.md")
        path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", default, "Markdown 文件 (*.md)"
        )
        if path:
            try:
                self.engine.export_markdown(self.summaries, self.roadmap, self.innovations, path)
                self.status_label.setText(f"报告已导出: {path}")
                QMessageBox.information(self, "完成", f"报告已导出到:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _on_show_llm_config(self):
        from PySide6.QtWidgets import QDialog, QFormLayout, QComboBox, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle("LLM API 配置")
        dlg.resize(500, 280)
        form = QFormLayout(dlg)

        provider_combo = QComboBox()
        provider_combo.addItems(["openai", "custom", "deepseek", "qwen", "azure"])
        provider_combo.setCurrentText(self.config.llm.provider)
        form.addRow("提供商:", provider_combo)

        base_url_edit = QLineEdit(self.config.llm.base_url)
        form.addRow("Base URL:", base_url_edit)

        model_edit = QLineEdit(self.config.llm.model)
        form.addRow("Model:", model_edit)

        api_key_edit = QLineEdit(self.config.llm.api_key)
        api_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", api_key_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            self.config.llm.provider = provider_combo.currentText()
            self.config.llm.base_url = base_url_edit.text().strip()
            self.config.llm.model = model_edit.text().strip()
            self.config.llm.api_key = api_key_edit.text().strip()
            self.config.save()
            self.engine = MiningEngine(self.config)
            self._update_llm_status()
            self.status_label.setText("LLM 配置已更新")

    def _on_error(self, msg: str):
        self.status_label.setText(f"错误: {msg}")
        QMessageBox.critical(self, "错误", msg)
