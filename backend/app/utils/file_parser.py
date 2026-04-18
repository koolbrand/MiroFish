"""
文件解析工具
支持PDF、Markdown、TXT文件的文本提取，以及图像识别（vía LLM de visión）
"""

import base64
import io
import os
from pathlib import Path
from typing import List, Optional

from .locale import t


def _read_text_with_fallback(file_path: str) -> str:
    """
    读取文本文件，UTF-8失败时自动探测编码。
    
    采用多级回退策略：
    1. 首先尝试 UTF-8 解码
    2. 使用 charset_normalizer 检测编码
    3. 回退到 chardet 检测编码
    4. 最终使用 UTF-8 + errors='replace' 兜底
    
    Args:
        file_path: 文件路径
        
    Returns:
        解码后的文本内容
    """
    data = Path(file_path).read_bytes()
    
    # 首先尝试 UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # 尝试使用 charset_normalizer 检测编码
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # 回退到 chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # 最终兜底：使用 UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """文件解析器"""

    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt',
                             '.png', '.jpg', '.jpeg', '.webp', '.gif'}
    IMAGE_EXTENSIONS     = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        从文件中提取文本。图像文件通过视觉LLM描述后返回文本。

        Args:
            file_path: 文件路径

        Returns:
            提取的文本内容
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(t('api.fileNotFound', path=file_path))

        suffix = path.suffix.lower()

        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(t('api.fileUnsupported', ext=suffix))

        if suffix in cls.IMAGE_EXTENSIONS:
            return cls._extract_from_image(file_path)
        elif suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)

        raise ValueError(t('api.fileUnsupported', ext=suffix))
    
    @staticmethod
    def _extract_from_image(file_path: str) -> str:
        """
        Describe una imagen usando el LLM de visión configurado (por defecto MiniMax-VL-01).

        Flujo:
          1. Abre la imagen con Pillow y la redimensiona a max 1024 px en el lado mayor.
          2. La convierte a JPEG y la codifica en base64.
          3. Llama al LLM de visión usando el formato especial de MiniMax:
             el data URI se incrusta directamente en el string de content, seguido del prompt.
          4. Devuelve la descripción como texto plano para el pipeline normal.
        """
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("Se necesita Pillow para procesar imágenes: pip install pillow")

        import requests as _requests
        from ..config import Config

        # ── 1. Redimensionar y convertir a JPEG ────────────────────────────
        MAX_PX = 1024
        with Image.open(file_path) as img:
            img = img.convert('RGB')
            w, h = img.size
            if max(w, h) > MAX_PX:
                scale = MAX_PX / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            img_bytes = buf.getvalue()

        # ── 2. Codificar en base64 ──────────────────────────────────────────
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        data_uri = f"data:image/jpeg;base64,{b64}"

        # ── 3. Llamar al LLM de visión ──────────────────────────────────────
        # MiniMax-VL-01 usa un formato especial: el data URI se embebe directamente
        # en el campo content como string (no como bloque image_url de OpenAI).
        vision_prompt = (
            f"{data_uri}\n\n"
            "Analiza esta imagen en detalle para su uso en una simulación de opinión pública. "
            "Describe de forma estructurada:\n"
            "- Identidad visual: colores principales, tipografía, logo o símbolo, estilo gráfico\n"
            "- Mensaje o concepto comunicado\n"
            "- Público objetivo aparente\n"
            "- Tono emocional (moderno, clásico, disruptivo, etc.)\n"
            "- Texto visible en la imagen (transcríbelo literalmente)\n"
            "- Cualquier otro elemento relevante para entender la propuesta de valor\n"
            "Responde en español, de forma clara y detallada."
        )

        base_url = Config.LLM_BASE_URL.rstrip('/')
        resp = _requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {Config.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": Config.VISION_LLM_MODEL_NAME,
                "messages": [{"role": "user", "content": vision_prompt}],
                "max_tokens": 1200,
            },
            timeout=90,
        )
        resp.raise_for_status()

        description = resp.json()["choices"][0]["message"]["content"]

        # ── 4. Formatear como documento de texto ───────────────────────────
        filename = Path(file_path).name
        return (
            f"=== Análisis visual de imagen: {filename} ===\n\n"
            f"{description}\n"
        )

    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """从PDF提取文本"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("Se necesita instalar PyMuPDF: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """从Markdown提取文本，支持自动编码检测"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """从TXT提取文本，支持自动编码检测"""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        从多个文件提取文本并合并
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            合并后的文本
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== Documento {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== Documento {i}: {file_path} (fallo en la extracción: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    将文本分割成小块
    
    Args:
        text: 原始文本
        chunk_size: 每块的字符数
        overlap: 重叠字符数
        
    Returns:
        文本块列表
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # 尝试在句子边界处分割
        if end < len(text):
            # 查找最近的句子结束符
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # 下一个块从重叠位置开始
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

