"""LLM API 客户端封装"""
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    raw: Optional[Any] = None
    error: Optional[str] = None


class BaseLLMClient:
    """LLM 客户端基类"""

    def __init__(self, config):
        self.config = config
        self.api_key = config.llm.api_key
        self.base_url = config.llm.base_url
        self.model = config.llm.model
        self.temperature = config.llm.temperature

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        raise NotImplementedError


class OpenAIClient(BaseLLMClient):
    """兼容 OpenAI 协议的 LLM 客户端"""

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
            }
            url = self.base_url.rstrip("/") + "/chat/completions"
            resp = httpx.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return LLMResponse(content=content, raw=data)
        except Exception as e:
            return LLMResponse(content="", error=str(e))


class LLMClientFactory:
    """LLM 客户端工厂"""

    @staticmethod
    def create(config) -> BaseLLMClient:
        provider = config.llm.provider.lower()
        if provider in ("openai", "custom", "azure", "deepseek", "qwen", "anthropic"):
            return OpenAIClient(config)
        return OpenAIClient(config)
