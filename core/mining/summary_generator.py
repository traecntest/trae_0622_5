"""论文结构化摘要生成"""
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class StructuredSummary:
    """结构化论文摘要"""
    title: str = ""
    background: str = ""
    core_method: str = ""
    key_contributions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    datasets: List[str] = field(default_factory=list)
    results: str = ""
    raw_response: str = ""


class SummaryGenerator:
    """论文摘要生成器"""

    SYSTEM_PROMPT = """你是一名科研领域的专家助手。请根据提供的论文内容，生成结构化的中文摘要。
严格按照以下 JSON 格式输出，不要输出额外的解释文字：
{
    "background": "研究背景与问题动机",
    "core_method": "核心方法与技术路线",
    "key_contributions": ["贡献点1", "贡献点2", ...],
    "limitations": ["局限性1", "局限性2", ...],
    "datasets": ["使用的数据集1", ...],
    "results": "主要实验结果与结论"
}"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def _truncate_text(self, text: str, max_chars: int = 8000) -> str:
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        return text[:half] + "\n...[内容已截断]...\n" + text[-half:]

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def generate_summary(self, title: str, full_text: str) -> StructuredSummary:
        summary = StructuredSummary(title=title)

        if not self.llm.is_configured():
            summary.background = "[LLM 未配置，无法生成摘要]"
            return summary

        text = self._truncate_text(full_text)
        user_prompt = f"论文标题：{title}\n\n论文内容：\n{text}\n\n请生成结构化摘要。"

        resp = self.llm.chat([
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])

        summary.raw_response = resp.content

        if resp.error:
            summary.background = f"[生成失败: {resp.error}]"
            return summary

        data = self._parse_json_response(resp.content)
        if data:
            summary.background = data.get("background", "")
            summary.core_method = data.get("core_method", "")
            summary.key_contributions = data.get("key_contributions", [])
            summary.limitations = data.get("limitations", [])
            summary.datasets = data.get("datasets", [])
            summary.results = data.get("results", "")

        if not summary.background and resp.content:
            summary.background = resp.content[:2000]

        return summary

    def generate_batch(self, papers: List[Dict[str, Any]],
                          progress_cb=None) -> List[StructuredSummary]:
        results = []
        total = len(papers)
        for i, p in enumerate(papers):
            if progress_cb:
                progress_cb(i / max(total, 1), f"正在分析: {p.get('title', '')[:50]}")
            summary = self.generate_summary(
                p.get("title", ""), p.get("full_text", "")
            )
            results.append(summary)
        if progress_cb:
            progress_cb(1.0, "完成")
        return results
