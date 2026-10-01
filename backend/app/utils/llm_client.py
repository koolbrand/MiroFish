"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from .locale import t


def strip_reasoning(content: Optional[str]) -> str:
    """Quita el razonamiento <think>…</think> (también sin cerrar) y las vallas
    de código ```json de la respuesta de un modelo de razonamiento."""
    content = content or ""
    content = re.sub(r'<think>[\s\S]*?</think>', '', content)
    content = re.sub(r'<think>[\s\S]*$', '', content).strip()
    content = re.sub(r'^```(?:json)?\s*\n?', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\n?```\s*$', '', content)
    return content.strip()


class LLMClient:
    """LLM客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=Config.LLM_TIMEOUT_SECONDS,
            max_retries=Config.LLM_MAX_RETRIES,
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        response = self.client.chat.completions.create(**kwargs)

        # Los modelos de razonamiento (MiniMax M2.7/M3, DeepSeek-R1…) gastan
        # parte del presupuesto pensando: si se corta por longitud, un reintento
        # con más margen (solo se cobra lo que se usa).
        if response.choices[0].finish_reason == 'length' and max_tokens < Config.LLM_MAX_TOKENS_CAP:
            kwargs["max_tokens"] = min(max_tokens * 4, Config.LLM_MAX_TOKENS_CAP)
            response = self.client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""
        # 部分模型（如MiniMax M2.5）会在content中包含<think>思考内容，需要移除
        content = re.sub(r'<think>[\s\S]*?</think>', '', content)
        # Razonamiento sin cerrar (respuesta cortada): no es contenido útil
        content = re.sub(r'<think>[\s\S]*$', '', content).strip()
        return content
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            解析后的JSON对象
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # 清理markdown代码块标记
        cleaned_response = response.strip()

        # Caso 1: la respuesta entera es un bloque de código
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            pass

        # Caso 2: el LLM devolvió markdown extenso con el JSON embebido en un code block
        # Buscar el primer bloque ```json ... ``` o ``` ... ```
        match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response, re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Caso 3: el JSON está suelto en el texto — extraer el objeto más externo { ... }
        first_brace = response.find('{')
        last_brace = response.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(response[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(t('api.llmInvalidJson', response=cleaned_response))

