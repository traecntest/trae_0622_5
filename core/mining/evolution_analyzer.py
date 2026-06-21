"""技术演进分析与创新点挖掘"""
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TechEvolutionNode:
    """技术演进节点"""
    year: str
    title: str
    method: str
    contribution: str


@dataclass
class TechEvolutionRoadmap:
    """技术演进路线图"""
    topic: str
    timeline: List[TechEvolutionNode] = field(default_factory=list)
    trends: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class InnovationSuggestion:
    """创新方向建议"""
    title: str
    description: str
    feasibility: str
    novelty: str
    related_papers: List[str] = field(default_factory=list)
    raw_response: str = ""


class TechEvolutionAnalyzer:
    """技术演进分析器"""

    SYSTEM_PROMPT_ROADMAP = """你是一名科研趋势分析专家。请根据提供的论文摘要列表，
分析该领域的技术演进路线。严格按照以下 JSON 格式输出：
{
    "topic": "研究领域主题",
    "timeline": [
        {"year": "年份", "title": "论文标题", "method": "核心方法", "contribution": "主要贡献"}
    ],
    "trends": ["趋势1", "趋势2", ...],
    "gaps": ["研究空白1", "研究空白2", ...]
}
请按时间顺序排列 timeline，重点分析方法的演变关系。"""

    SYSTEM_PROMPT_INNOVATION = """你是一名科研创新方向顾问。请根据提供的论文库分析结果，
推荐 3-5 个有潜力的创新研究方向。严格按照以下 JSON 格式输出：
{
    "suggestions": [
        {
            "title": "方向标题",
            "description": "详细描述",
            "feasibility": "可行性评估",
            "novelty": "创新性评估",
            "related_papers": ["相关论文标题1", ...]
        }
    ]
}
建议应具体、可落地，并结合当前研究空白。"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def _parse_json(self, content: str) -> Dict[str, Any]:
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def _build_papers_context(self, summaries: List[Any]) -> str:
        parts = []
        for i, s in enumerate(summaries[:30]):
            parts.append(
                f"[{i+1}] 标题: {s.title}\n"
                f"    背景: {s.background[:300]}\n"
                f"    方法: {s.core_method[:300]}\n"
                f"    贡献: {'; '.join(s.key_contributions[:3])}\n"
            )
        return "\n".join(parts)

    def analyze_roadmap(self, summaries: List[Any],
                          topic_hint: str = "") -> TechEvolutionRoadmap:
        roadmap = TechEvolutionRoadmap(topic=topic_hint)
        if not self.llm.is_configured() or not summaries:
            roadmap.gaps = ["[LLM 未配置或无论文数据]"]
            return roadmap

        context = self._build_papers_context(summaries)
        user_prompt = f"研究领域: {topic_hint or '未指定'}\n\n论文列表:\n{context}\n\n请生成技术演进路线图。"

        resp = self.llm.chat([
            {"role": "system", "content": self.SYSTEM_PROMPT_ROADMAP},
            {"role": "user", "content": user_prompt},
        ])
        roadmap.raw_response = resp.content

        if resp.error:
            roadmap.gaps = [f"[分析失败: {resp.error}]"]
            return roadmap

        data = self._parse_json(resp.content)
        if data:
            roadmap.topic = data.get("topic", roadmap.topic)
            for node in data.get("timeline", []):
                roadmap.timeline.append(TechEvolutionNode(
                    year=str(node.get("year", "")),
                    title=node.get("title", ""),
                    method=node.get("method", ""),
                    contribution=node.get("contribution", ""),
                ))
            roadmap.trends = data.get("trends", [])
            roadmap.gaps = data.get("gaps", [])

        return roadmap

    def suggest_innovations(self, summaries: List[Any],
                              roadmap: Optional[TechEvolutionRoadmap] = None,
                              custom_focus: str = "") -> List[InnovationSuggestion]:
        suggestions = []

        if not self.llm.is_configured() or not summaries:
            suggestions.append(InnovationSuggestion(
                title="无有效数据",
                description="[LLM 未配置或无论文数据，无法生成建议]",
                feasibility="N/A",
                novelty="N/A",
            ))
            return suggestions

        context = self._build_papers_context(summaries)
        gaps_text = ""
        if roadmap and roadmap.gaps:
            gaps_text = "已识别的研究空白:\n" + "\n".join(f"- {g}" for g in roadmap.gaps)
        trends_text = ""
        if roadmap and roadmap.trends:
            trends_text = "技术趋势:\n" + "\n".join(f"- {t}" for t in roadmap.trends)

        user_prompt = (
            f"研究关注点: {custom_focus or '未指定'}\n\n"
            f"论文库数据:\n{context}\n\n"
            f"{trends_text}\n\n{gaps_text}\n\n请推荐创新研究方向。"
        )

        resp = self.llm.chat([
            {"role": "system", "content": self.SYSTEM_PROMPT_INNOVATION},
            {"role": "user", "content": user_prompt},
        ])

        if resp.error:
            suggestions.append(InnovationSuggestion(
                title="生成失败",
                description=str(resp.error),
                feasibility="N/A",
                novelty="N/A",
            ))
            return suggestions

        data = self._parse_json(resp.content)
        for s in data.get("suggestions", []):
            suggestions.append(InnovationSuggestion(
                title=s.get("title", ""),
                description=s.get("description", ""),
                feasibility=s.get("feasibility", ""),
                novelty=s.get("novelty", ""),
                related_papers=s.get("related_papers", []),
                raw_response=resp.content,
            ))

        if not suggestions and resp.content:
            suggestions.append(InnovationSuggestion(
                title="原始建议",
                description=resp.content[:3000],
                feasibility="",
                novelty="",
            ))

        return suggestions

    def compare_papers(self, summaries: List[Any],
                         paper_indices: List[int]) -> str:
        if not self.llm.is_configured():
            return "[LLM 未配置]"

        selected = [summaries[i] for i in paper_indices if i < len(summaries)]
        if len(selected) < 2:
            return "请至少选择 2 篇论文进行对比。"

        context = ""
        for i, s in enumerate(selected):
            context += (
                f"[论文{i+1}] {s.title}\n"
                f"背景: {s.background[:500]}\n"
                f"方法: {s.core_method[:500]}\n"
                f"贡献: {'; '.join(s.key_contributions[:3])}\n"
                f"局限性: {'; '.join(s.limitations[:3])}\n\n"
            )

        system = """你是一名论文对比分析专家。请从研究动机、技术路线、实验设计、
核心贡献和局限性等维度，深度对比以下论文，输出中文分析报告。"""

        resp = self.llm.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": context},
        ])

        return resp.content if not resp.error else f"[对比失败: {resp.error}]"
