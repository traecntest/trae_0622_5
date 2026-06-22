"""智能检索聚合器 - 文献下载与数据源对接"""
import os
import re
import time
import shutil
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class PaperMeta:
    """文献元数据"""
    title: str
    authors: List[str]
    abstract: str
    url: str
    pdf_url: str
    source: str
    year: Optional[int] = None
    doi: Optional[str] = None
    local_path: Optional[str] = None


class BaseDownloader:
    """基础下载器基类"""

    def __init__(self, pdf_dir: str, timeout: int = 30):
        self.pdf_dir = Path(pdf_dir)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

    def _sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
        if len(title) > 100:
            title = title[:100]
        return title or "paper"

    def _unique_path(self, filename: str) -> Path:
        path = self.pdf_dir / f"{filename}.pdf"
        counter = 1
        while path.exists():
            path = self.pdf_dir / f"{filename}_{counter}.pdf"
            counter += 1
        return path

    def download_pdf(self, pdf_url: str, title: str,
                      progress_cb: Optional[Callable] = None) -> Optional[str]:
        try:
            resp = self.session.get(pdf_url, stream=True, timeout=self.timeout)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            filename = self._sanitize_filename(title)
            save_path = self._unique_path(filename)
            downloaded = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total:
                            progress_cb(min(downloaded / total, 1.0))
            return str(save_path)
        except Exception as e:
            if progress_cb:
                progress_cb(0.0, str(e))
            return None


class ArxivDownloader(BaseDownloader):
    """arXiv 文献下载器"""

    BASE_URL = "http://export.arxiv.org/api/query"

    def search(self, query: str, max_results: int = 10,
                progress_cb: Optional[Callable] = None) -> List[PaperMeta]:
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return self._parse_atom(resp.text)
        except Exception as e:
            return []

    def _parse_atom(self, xml_text: str) -> List[PaperMeta]:
        soup = BeautifulSoup(xml_text, "lxml-xml")
        papers = []
        for entry in soup.find_all("entry"):
            title = (entry.title.get_text(strip=True) if entry.title else "").replace("\n", " ")
            authors = [a.get_text(strip=True) for a in entry.find_all("name")]
            abstract = (entry.summary.get_text(strip=True) if entry.summary else "")
            abs_url = ""
            pdf_url = ""
            for link in entry.find_all("link"):
                href = link.get("href", "")
                t = link.get("title", "")
                if t == "pdf":
                    pdf_url = href
                elif link.get("rel") == "alternate":
                    abs_url = href
            year = None
            published = entry.published.get_text(strip=True) if entry.published else ""
            if published:
                try:
                    year = int(published[:4])
                except ValueError:
                    pass
            doi_tag = entry.find("arxiv:doi")
            doi = doi_tag.get_text(strip=True) if doi_tag else None
            papers.append(PaperMeta(
                title=title, authors=authors, abstract=abstract,
                url=abs_url, pdf_url=pdf_url if pdf_url.endswith(".pdf") else pdf_url + ".pdf",
                source="arXiv", year=year, doi=doi
            ))
        return papers


class URLDownloader(BaseDownloader):
    """通用 URL 文献下载器"""

    def download_from_url(self, url: str, progress_cb: Optional[Callable] = None) -> Optional[str]:
        parsed = urlparse(url)
        filename = Path(parsed.path).stem or "paper"
        return self.download_pdf(url, filename, progress_cb)

    def extract_pdf_links(self, page_url: str) -> List[str]:
        try:
            resp = self.session.get(page_url, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.lower().endswith(".pdf"):
                    if not href.startswith("http"):
                        from urllib.parse import urljoin
                        href = urljoin(page_url, href)
                    links.append(href)
            return links
        except Exception:
            return []


class RetrievalAggregator:
    """智能检索聚合器"""

    def __init__(self, pdf_dir: str, max_threads: int = 4):
        self.pdf_dir = pdf_dir
        self.max_threads = max_threads
        self.arxiv = ArxivDownloader(pdf_dir)
        self.url_downloader = URLDownloader(pdf_dir)

    def search_arxiv(self, query: str, max_results: int = 10,
                      progress_cb: Optional[Callable] = None) -> List[PaperMeta]:
        return self.arxiv.search(query, max_results, progress_cb)

    def download_papers(self, papers: List[PaperMeta],
                          progress_cb: Optional[Callable] = None) -> List[PaperMeta]:
        results = []
        total = len(papers)
        completed_count = 0
        per_paper_progress = [0.0] * total

        def update_overall():
            if progress_cb and total > 0:
                overall = sum(per_paper_progress) / total
                progress_cb(overall, f"下载进度 {int(overall * 100)}% ({completed_count}/{total})")

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {}
            for i, paper in enumerate(papers):
                def make_cb(idx):
                    def cb(pct, err=None):
                        per_paper_progress[idx] = max(0.0, min(1.0, pct))
                        update_overall()
                    return cb
                future = executor.submit(
                    self.arxiv.download_pdf,
                    paper.pdf_url, paper.title, make_cb(i)
                )
                futures[future] = (i, paper)
            for future in as_completed(futures):
                idx, paper = futures[future]
                local_path = future.result()
                if local_path:
                    paper.local_path = local_path
                completed_count += 1
                per_paper_progress[idx] = 1.0
                update_overall()
                results.append(paper)
        if progress_cb:
            progress_cb(1.0, f"下载完成 {completed_count}/{total}")
        return results

    def download_single(self, url: str,
                      progress_cb: Optional[Callable] = None) -> Optional[str]:
        return self.url_downloader.download_from_url(url, progress_cb)
