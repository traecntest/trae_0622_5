"""PDF 文献解析器"""
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import fitz


@dataclass
class PaperSection:
    """论文章节"""
    name: str
    text: str
    page: int
    level: int = 1


@dataclass
class PaperChunk:
    """文本分块"""
    text: str
    page: int
    chunk_id: str
    section: Optional[str] = None
    start_char: int = 0
    end_char: int = 0


@dataclass
class ParsedPaper:
    """解析后的论文"""
    file_path: str
    title: str
    authors: List[str]
    abstract: str
    year: Optional[int]
    sections: List[PaperSection] = field(default_factory=list)
    full_text: str = ""
    num_pages: int = 0

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "title": self.title,
            "authors": ", ".join(self.authors),
            "abstract": self.abstract[:500] if self.abstract else "",
            "year": str(self.year or ""),
            "num_pages": str(self.num_pages),
            "filename": Path(self.file_path).name,
        }


class PDFParser:
    """基于 PyMuPDF 的 PDF 解析器"""

    def __init__(self):
        self.section_patterns = [
            re.compile(r'^\s*(?P<num>\d+[\.\d]*)\s+(?P<name>[A-Z][A-Za-z\s]{2,80})$'),
            re.compile(r'^\s*(?P<name>Abstract|Introduction|Background|Related\s+Work|Method'
                       r's?|Methodology|Experiments?|Results?|Discussion|Conclusion'
                       r's?|References?|Appendix)[\s:]*$', re.IGNORECASE),
        ]

    def parse(self, pdf_path: str) -> ParsedPaper:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)

        title, authors = self._extract_header(doc)
        abstract = self._extract_abstract(doc)
        year = self._extract_year(doc)

        sections, full_text = self._extract_sections_and_text(doc)

        doc.close()

        return ParsedPaper(
            file_path=pdf_path,
            title=title or Path(pdf_path).stem,
            authors=authors,
            abstract=abstract,
            year=year,
            sections=sections,
            full_text=full_text,
            num_pages=num_pages,
        )

    def _extract_header(self, doc: "fitz.Document") -> Tuple[str, List[str]]:
        if len(doc) == 0:
            return "", []
        first_page = doc[0]
        blocks = first_page.get_text("blocks")
        sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

        title = ""
        authors = []
        text_lines = []
        for blk in sorted_blocks:
            text = blk[4].strip()
            if text and len(text) > 3:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                text_lines.extend(lines)

        if text_lines:
            title = text_lines[0]
            if len(text_lines) > 1:
                candidates = text_lines[1:min(len(text_lines), 5)]
                for line in candidates:
                    if re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+', line) and "@" not in line:
                        parts = re.split(r'[,;]| and ', line)
                        for p in parts:
                            p = p.strip()
                            if 2 < len(p) < 60 and "@" not in p:
                                authors.append(p)
                        break
        return title, authors

    def _extract_abstract(self, doc: "fitz.Document") -> str:
        if len(doc) == 0:
            return ""
        text = doc[0].get_text()
        match = re.search(r'(?is)abstract[:\s]*\n\s*(.+?)(?:\n\s*\n|\n\s*[1I]\.?\s+[A-Z]|$)', text)
        if match:
            abstract = match.group(1).strip()
            abstract = re.sub(r'\s+', ' ', abstract)
            return abstract[:2000]
        return ""

    def _extract_year(self, doc: "fitz.Document") -> Optional[int]:
        if len(doc) == 0:
            return None
        text = doc[0].get_text()
        match = re.search(r'\b(19|20)\d{2}\b', text)
        if match:
            return int(match.group())
        return None

    def _extract_sections_and_text(self, doc: "fitz.Document") -> Tuple[List[PaperSection], str]:
        sections: List[PaperSection] = []
        full_text_parts = []

        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            full_text_parts.append(page_text)

            lines = page_text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                for pattern in self.section_patterns:
                    m = pattern.match(line)
                    if m:
                        name = m.group("name").strip()
                        if m.groupdict().get("num"):
                            name = f"{m.group('num')} {name}"
                        sections.append(PaperSection(
                            name=name, text=line, page=page_num + 1, level=1
                        ))
                        break

        full_text = "\n".join(full_text_parts)
        full_text = re.sub(r'[ \t]+', ' ', full_text)
        return sections, full_text

    def chunk_text(self, paper: ParsedPaper, chunk_size: int = 500,
                    chunk_overlap: int = 50) -> List[PaperChunk]:
        """将解析后的论文分块"""
        chunks: List[PaperChunk] = []
        text = paper.full_text
        if not text:
            return chunks

        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = ""
        chunk_id_base = re.sub(r'[^a-zA-Z0-9]', '_', Path(paper.file_path).stem)
        chunk_idx = 0

        for sent in sentences:
            if len(current_chunk) + len(sent) + 1 <= chunk_size:
                current_chunk = (current_chunk + " " + sent).strip()
            else:
                if current_chunk:
                    chunks.append(PaperChunk(
                        text=current_chunk,
                        page=1,
                        chunk_id=f"{chunk_id_base}_{chunk_idx}",
                        section=self._find_section(paper, current_chunk),
                    ))
                    chunk_idx += 1
                overlap_start = max(0, len(current_chunk) - chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + " " + sent
                current_chunk = current_chunk.strip()

        if current_chunk:
            chunks.append(PaperChunk(
                text=current_chunk,
                page=1,
                chunk_id=f"{chunk_id_base}_{chunk_idx}",
                section=self._find_section(paper, current_chunk),
            ))

        return chunks

    def _find_section(self, paper: ParsedPaper, chunk_text: str) -> Optional[str]:
        sample = chunk_text[:100]
        for sec in paper.sections:
            if sec.name[:30] in sample:
                return sec.name
        return None
