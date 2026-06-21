"""创新点挖掘引擎 - 统一入口"""
from typing import List, Dict, Any, Optional, Callable

from .llm_client import LLMClientFactory, BaseLLMClient
from .summary_generator import SummaryGenerator, StructuredSummary
from .evolution_analyzer import (
    TechEvolutionAnalyzer,
    TechEvolutionRoadmap,
    InnovationSuggestion,
)


class MiningEngine:
    """创新点挖掘引擎核心类"""

    def __init__(self, config):
        self.config = config
        self.llm: BaseLLMClient = LLMClientFactory.create(config)
        self.summary_gen = SummaryGenerator(self.llm)
        self.analyzer = TechEvolutionAnalyzer(self.llm)
        self._summary_cache: Dict[str, StructuredSummary] = {}

    def is_llm_configured(self) -> bool:
        return self.llm.is_configured()

    def generate_summary(self, title: str, full_text: str) -> StructuredSummary:
        cache_key = title[:100]
        if cache_key in self._summary_cache:
            return self._summary_cache[cache_key]
        summary = self.summary_gen.generate_summary(title, full_text)
        self._summary_cache[cache_key] = summary
        return summary

    def generate_summaries_batch(self, papers_data: List[Dict[str, Any]],
                                    progress_cb: Optional[Callable] = None) -> List[StructuredSummary]:
        results = self.summary_gen.generate_batch(papers_data, progress_cb)
        for s in results:
            self._summary_cache[s.title[:100]] = s
        return results

    def analyze_evolution(self, summaries: List[StructuredSummary],
                           topic_hint: str = "") -> TechEvolutionRoadmap:
        return self.analyzer.analyze_roadmap(summaries, topic_hint)

    def suggest_innovations(self, summaries: List[StructuredSummary],
                              roadmap: Optional[TechEvolutionRoadmap] = None,
                              custom_focus: str = "") -> List[InnovationSuggestion]:
        return self.analyzer.suggest_innovations(summaries, roadmap, custom_focus)

    def compare_papers(self, summaries: List[StructuredSummary],
                         paper_indices: List[int]) -> str:
        return self.analyzer.compare_papers(summaries, paper_indices)

    def export_markdown(self, summaries: List[StructuredSummary],
                           roadmap: Optional[TechEvolutionRoadmap],
                           innovations: Optional[List[InnovationSuggestion]],
                           output_path: str) -> str:
        lines = ["# 科研项目分析报告\n"]
        lines.append(f"_共分析 {len(summaries)} 篇文献_\n")

        if roadmap:
            lines.append("\n## 技术演进路线\n")
            lines.append(f"**研究领域**: {roadmap.topic}\n")

            if roadmap.timeline:
                lines.append("### 时间线\n")
                for node in sorted(roadmap.timeline, key=lambda x: x.year):
                    lines.append(f"- **{node.year}** {node.title}")
                    if node.method:
                        lines.append(f"  - 方法: {node.method}")
                    if node.contribution:
                        lines.append(f"  - 贡献: {node.contribution}")
                    lines.append("")

            if roadmap.trends:
                lines.append("### 技术趋势\n")
                for t in roadmap.trends:
                    lines.append(f"- {t}")
                lines.append("")

            if roadmap.gaps:
                lines.append("### 研究空白\n")
                for g in roadmap.gaps:
                    lines.append(f"- {g}")
                lines.append("")

        if innovations:
            lines.append("\n## 创新方向建议\n")
            for i, inn in enumerate(innovations, 1):
                lines.append(f"### {i}. {inn.title}\n")
                lines.append(f"**描述**: {inn.description}\n")
                if inn.feasibility:
                    lines.append(f"**可行性**: {inn.feasibility}\n")
                if inn.novelty:
                    lines.append(f"**创新性**: {inn.novelty}\n")
                if inn.related_papers:
                    lines.append("**相关论文**:")
                    for p in inn.related_papers:
                        lines.append(f"- {p}")
                lines.append("")

        lines.append("\n## 文献结构化摘要\n")
        for i, s in enumerate(summaries, 1):
            lines.append(f"### {i}. {s.title}\n")
            if s.background:
                lines.append(f"**背景**: {s.background}\n")
            if s.core_method:
                lines.append(f"**核心方法**: {s.core_method}\n")
            if s.key_contributions:
                lines.append("**主要贡献**:")
                for c in s.key_contributions:
                    lines.append(f"- {c}")
                lines.append("")
            if s.limitations:
                lines.append("**局限性**:")
                for l in s.limitations:
                    lines.append(f"- {l}")
                lines.append("")
            if s.datasets:
                lines.append(f"**数据集**: {', '.join(s.datasets)}\n")
            if s.results:
                lines.append(f"**实验结果**: {s.results}\n")

        content = "\n".join(lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path

    def clear_cache(self):
        self._summary_cache.clear()
