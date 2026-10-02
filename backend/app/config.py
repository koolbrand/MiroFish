"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
import secrets
import sys
from typing import Optional

from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

# override=False: las variables de entorno reales mandan sobre el .env
if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=False)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=False)


# ---- Lectura tolerante de variables de entorno ----
# `int(os.environ.get('X', '60'))` tumba la app ENTERA al importar si X vale '' (Coolify/compose pasan vacías las
# que no tienen valor) o '30s' (un typo): el contenedor entra en bucle de reinicios sin llegar a servir nada. Aquí
# lo vacío cuenta como «sin definir» y lo inválido o fuera de rango se avisa por stderr y se usa el valor por defecto.

def _warn(name: str, raw: str, default, why: str) -> None:
    sys.stderr.write(f"[config] {name}={raw!r} {why}; se usa el valor por defecto ({default})\n")


def _env_raw(name: str):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def env_str(name: str, default: str) -> str:
    """Texto; vacío = el valor por defecto (compose pasa `VAR=` vacía cuando no se ha definido)."""
    raw = _env_raw(name)
    return default if raw is None else raw


def env_int(name: str, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    raw = _env_raw(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        _warn(name, raw, default, "no es un número entero")
        return default
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        _warn(name, raw, default, "está fuera de rango")
        return default
    return value


def env_float(name: str, default: float, minimum: Optional[float] = None, maximum: Optional[float] = None) -> float:
    raw = _env_raw(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        _warn(name, raw, default, "no es un número")
        return default
    if value != value or value in (float('inf'), float('-inf')):          # NaN / infinito
        _warn(name, raw, default, "no es un número finito")
        return default
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        _warn(name, raw, default, "está fuera de rango")
        return default
    return value


_TRUE = ('true', '1', 'yes', 'on')
_FALSE = ('false', '0', 'no', 'off')


def env_bool(name: str, default: bool) -> bool:
    """Interruptor: acepta true/1/yes/on y false/0/no/off; vacío o raro = el valor por defecto."""
    raw = _env_raw(name)
    if raw is None:
        return default
    low = raw.lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    _warn(name, raw, default, "no es un interruptor (true/false)")
    return default


def env_flag_on_by_default(name: str) -> bool:
    """
    Interruptor que está ENCENDIDO salvo que se apague de forma explícita (`false`, `0`, `no`, `off`).
    Con `== 'true'`, un valor como `1`, `yes`, `on` o ` true` dejaba la API abierta (todos admin) sin avisar.
    """
    return os.environ.get(name, 'true').strip().lower() not in ('false', '0', 'no', 'off')


class Config:
    """Flask配置类"""
    
    # Flask配置
    DEBUG = env_bool('FLASK_DEBUG', False)
    SECRET_KEY = os.environ.get('SECRET_KEY') or (secrets.token_urlsafe(32) if DEBUG else None)
    # Estricto: con `== 'true'`, valores como `1`, `yes`, `on` o ` true` dejaban la API ABIERTA (todos admin) sin avisar.
    # Solo se desactiva con un valor explícito de «apagado».
    API_AUTH_REQUIRED = env_flag_on_by_default('API_AUTH_REQUIRED')
    API_AUTH_TOKEN = os.environ.get('API_AUTH_TOKEN')
    # Proyectos creados antes del aislamiento por usuario (sin dueño): se tratan como de este usuario de
    # PocketBase. Vacío = solo el admin los ve.
    LEGACY_OWNER_ID = os.environ.get('LEGACY_OWNER_ID') or None
    POCKETBASE_URL = os.environ.get('POCKETBASE_URL') or os.environ.get(
        'VITE_POCKETBASE_URL',
        'https://pocketbase.koolgrowth.com'
    )
    API_READ_RATE_LIMIT = env_str('API_READ_RATE_LIMIT', '600 per minute')
    API_WRITE_RATE_LIMIT = env_str('API_WRITE_RATE_LIMIT', '30 per minute')
    # Nº de proxies inversos delante (Coolify/Traefik = 1). 0 si se expone directo.
    TRUSTED_PROXIES = env_int('TRUSTED_PROXIES', 1, minimum=0)
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            'CORS_ORIGINS',
            'http://localhost:5173,http://127.0.0.1:5173'
        ).split(',')
        if origin.strip()
    ]
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    # Tope de max_tokens al reintentar respuestas cortadas (modelos de razonamiento)
    LLM_MAX_TOKENS_CAP = env_int('LLM_MAX_TOKENS_CAP', 32768, minimum=256)
    # Plazo por llamada al modelo y reintentos del SDK. Sin plazo propio valían 600 s × 3 intentos = 30 min por
    # llamada, y un proveedor colgado dejaba un informe de 20 minutos esperando media hora en una sola sección.
    LLM_TIMEOUT_SECONDS = env_float('LLM_TIMEOUT_SECONDS', 240.0, minimum=5)
    LLM_MAX_RETRIES = env_int('LLM_MAX_RETRIES', 2, minimum=0, maximum=10)
    # Construcción del grafo: tope por llamada al LLM/embeddings y por fragmento
    GRAPH_LLM_TIMEOUT_SECONDS = env_float('GRAPH_LLM_TIMEOUT_SECONDS', 180.0, minimum=5)
    GRAPH_EPISODE_TIMEOUT_SECONDS = env_float('GRAPH_EPISODE_TIMEOUT_SECONDS', 900.0, minimum=5)
    # Jev (TypeSafe): filtro de entidades antes de crear agentes
    TYPESAFE_API_KEY = os.environ.get('TYPESAFE_API_KEY')
    TYPESAFE_API_URL = env_str('TYPESAFE_API_URL', 'https://api.typesafe.ai/v1/systemone')
    JEV_MODEL = env_str('JEV_MODEL', 'jev-latest')
    JEV_ENTITY_FILTER = env_bool('JEV_ENTITY_FILTER', True)
    JEV_DROP_CONFIDENCE = env_float('JEV_DROP_CONFIDENCE', 0.8, minimum=0, maximum=1)
    JEV_MIN_AUDIENCE_RATIO = env_float('JEV_MIN_AUDIENCE_RATIO', 0.4, minimum=0, maximum=1)
    # Ampliar la audiencia (desdoblar grupos en personas) si queda por debajo del mínimo
    AUDIENCE_EXPANSION = env_bool('AUDIENCE_EXPANSION', True)
    AUDIENCE_MAX_EXTRA = env_int('AUDIENCE_MAX_EXTRA', 20, minimum=0)
    AUDIENCE_MAX_VARIANTS = env_int('AUDIENCE_MAX_VARIANTS', 4, minimum=1)

    # Público con datos reales: cada persona simulada del público se ancla a un encuestado real y anónimo de la
    # encuesta oficial del PAÍS del público (CIS para España; se añaden más en `services/poblacion/fuentes.py`).
    # Uso interno de I+D hasta tener la autorización escrita de cada titular. Apagado por defecto.
    POBLACION_DATOS_REALES = env_bool('POBLACION_DATOS_REALES', False) or env_bool('POBLACION_CIS', False)
    POBLACION_CIS = POBLACION_DATOS_REALES        # nombre antiguo del mismo interruptor
    _POBLACION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'poblacion')
    POBLACION_BANCOS_DIR = env_str('POBLACION_BANCOS_DIR', _POBLACION_DIR)
    POBLACION_BANCO_PATH = env_str('POBLACION_BANCO_PATH', os.path.join(POBLACION_BANCOS_DIR, 'banco_cis.sqlite'))

    # Graphiti-specific LLM config (knowledge graph extraction).
    # Uses a DIFFERENT provider/model than the simulation LLM because graph
    # extraction needs reliable structured output (response_format=json_schema).
    # Reasoning models (MiniMax-M2.7, DeepSeek-R1) silently ignore json_schema
    # and drift to invented field names → ~50% invalid extractions.
    #
    # Recommended setup: DeepSeek-V3 (deepseek-chat) or Qwen-Plus for graph
    # extraction + MiniMax-M2.7 for simulation reasoning.
    #
    # Each var independently falls back to its LLM_* counterpart when unset,
    # so a single-provider setup still works.
    GRAPHITI_LLM_API_KEY = (
        os.environ.get('GRAPHITI_LLM_API_KEY')
        or os.environ.get('LLM_API_KEY')
    )
    GRAPHITI_LLM_BASE_URL = (
        os.environ.get('GRAPHITI_LLM_BASE_URL')
        or os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    )
    GRAPHITI_LLM_MODEL_NAME = (
        os.environ.get('GRAPHITI_LLM_MODEL_NAME')
        or os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    )
    
    # Neo4j配置（自托管Graphiti）
    # No default password is provided on purpose: a fallback like the previous
    # 'mirofish2026' was a footgun. In DEBUG (local dev) `validate()` skips the
    # check, but the env var is still required to actually reach Neo4j.
    NEO4J_URI = env_str('NEO4J_URI', 'bolt://neo4j:7687')
    NEO4J_USER = env_str('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD')

    # Embedding配置（Graphiti用）
    # Can use a different provider than the LLM (e.g. OpenAI or Aliyun for embeddings,
    # MiniMax for LLM). Falls back to LLM credentials if not explicitly set.
    EMBEDDING_MODEL = env_str('EMBEDDING_MODEL', 'text-embedding-3-small')
    EMBEDDING_API_KEY = os.environ.get('EMBEDDING_API_KEY') or os.environ.get('LLM_API_KEY')
    EMBEDDING_BASE_URL = os.environ.get('EMBEDDING_BASE_URL') or os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    
    # Vision LLM config (image → text extraction on upload).
    # Uses its own base URL and API key (defaulting to the main LLM values).
    #
    # IMPORTANT: MiniMax-VL-01 only works on the Chinese endpoint
    # (api.minimaxi.chat/v1), NOT on the international one (api.minimax.io/v1).
    # If you use the international endpoint for your main LLM, set:
    #   VISION_LLM_BASE_URL=https://api.minimaxi.chat/v1
    # or point to any other OpenAI-compatible provider that supports vision.
    #
    # If VISION_LLM_MODEL_NAME is not set (or the model is unavailable) the
    # image upload still succeeds — a warning placeholder is returned instead
    # of a full visual analysis, so the simulation can continue.
    VISION_LLM_API_KEY = (
        os.environ.get('VISION_LLM_API_KEY')
        or os.environ.get('LLM_API_KEY')
    )
    VISION_LLM_BASE_URL = (
        os.environ.get('VISION_LLM_BASE_URL')
        or os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    )
    VISION_LLM_MODEL_NAME = (
        os.environ.get('VISION_LLM_MODEL_NAME') or 'MiniMax-VL-01'
    )

    # Investigación en internet antes de la ontología (paso opcional que elige
    # el usuario). Búsqueda web en el servidor del proveedor con su API
    # compatible con Anthropic: POST {base}/anthropic/v1/messages. La base se
    # deriva de LLM_BASE_URL quitando un /v1 final (MiniMax: api.minimax.io).
    WEB_RESEARCH_ENABLED = env_bool('WEB_RESEARCH_ENABLED', True)
    WEB_RESEARCH_MODEL = (
        os.environ.get('WEB_RESEARCH_MODEL')
        or os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    )
    WEB_RESEARCH_BASE_URL = (
        os.environ.get('WEB_RESEARCH_BASE_URL')
        or os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    )
    WEB_RESEARCH_API_KEY = (
        os.environ.get('WEB_RESEARCH_API_KEY')
        or os.environ.get('LLM_API_KEY')
    )
    WEB_RESEARCH_MAX_TOKENS = env_int('WEB_RESEARCH_MAX_TOKENS', 4000, minimum=256)
    WEB_RESEARCH_TIMEOUT = env_float('WEB_RESEARCH_TIMEOUT', 240.0, minimum=10)
    # tool_choice=any: el modelo tiene que buscar al menos una vez. Sin él,
    # MiniMax-M3 puede contestar de memoria con citas [n] que no respalda nada
    # (medido el 1-oct-2026: 0 búsquedas y 11 citas sin fuente).
    WEB_RESEARCH_FORCE_SEARCH = env_bool('WEB_RESEARCH_FORCE_SEARCH', True)

    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB — solo las rutas de subida de archivos (ver UPLOAD_PATHS en app/__init__.py)
    # Cualquier otra petición: 1 MB. Con 50 MB para todo, 20 POST anónimos de 42 MB agotaban los 4 GB del contenedor
    MAX_BODY_BYTES = env_int('MAX_BODY_BYTES', 1024 * 1024, minimum=1024)
    # Topes de coste de una sola petición (el límite de tasa cuenta peticiones, no llamadas al modelo)
    MAX_UPLOAD_FILES = env_int('MAX_UPLOAD_FILES', 10, minimum=1)
    # Cada imagen = una llamada al modelo de visión. Eran 3, un tope elegido sin datos: el material real de northkin
    # trae 6 imágenes (logo, icono, retrato, estructura…) y la subida se rechazaba. 8 las cubre y el tope de archivos
    # (10) ya acota el total por petición.
    MAX_UPLOAD_IMAGES = env_int('MAX_UPLOAD_IMAGES', 8, minimum=0)
    MAX_TOTAL_TEXT_CHARS = env_int('MAX_TOTAL_TEXT_CHARS', 1000000, minimum=1000)  # ~10 libros; el grafo gasta un episodio por ~500 caracteres
    MAX_INTERVIEWS_PER_REQUEST = 20
    MAX_CHAT_MESSAGE_CHARS = 4000
    MAX_CHAT_HISTORY_TURNS = 20
    # Pipelines automáticos vivos a la vez: cada uno son horas de modelo y una simulación de ~1 GB
    MAX_ACTIVE_PIPELINES = env_int('MAX_ACTIVE_PIPELINES', 3, minimum=1)
    MAX_ACTIVE_PIPELINES_PER_USER = env_int('MAX_ACTIVE_PIPELINES_PER_USER', 2, minimum=1)
    MAX_INTERVIEW_PROMPT_CHARS = 2000
    MAX_PARALLEL_PROFILES = 8
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    # Credencial de SOLO LECTURA para `GET /api/backup/export` (copia de seguridad que recoge otra máquina). Vacía o de
    # menos de 32 caracteres = la ruta no existe (404). No es la clave de administrador y no vale para otras rutas.
    BACKUP_TOKEN = os.environ.get('BACKUP_TOKEN', '').strip()
    # Por debajo de este espacio libre en el disco de datos `/health/ready` avisa (un disco lleno corta guardados a medias)
    MIN_FREE_DISK_MB = env_int('MIN_FREE_DISK_MB', 200, minimum=0)
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'md', 'txt', 'markdown', 'png', 'jpg', 'jpeg', 'webp', 'gif'}
    IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = env_int('OASIS_DEFAULT_MAX_ROUNDS', 10, minimum=1)
    # Rondas por simulación: el servidor nunca arranca más (la configuración automática puede
    # proponer hasta 336 y cada ronda cuesta memoria y dinero de LLM). Mínimo = el de la pantalla.
    SIMULATION_MIN_ROUNDS = 10
    # Simulaciones con proceso vivo a la vez (cada una ocupa ~1 GB y el contenedor tiene 4); incluye las ya
    # terminadas que esperan entrevistas: esas se cierran solas para dejar sitio
    MAX_CONCURRENT_SIMULATIONS = env_int('MAX_CONCURRENT_SIMULATIONS', 2, minimum=1)
    SIMULATION_MAX_ROUNDS = env_int('SIMULATION_MAX_ROUNDS', 100, minimum=SIMULATION_MIN_ROUNDS)
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = env_int('REPORT_AGENT_MAX_TOOL_CALLS', 5, minimum=1)
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = env_int('REPORT_AGENT_MAX_REFLECTION_ROUNDS', 2, minimum=0)
    REPORT_AGENT_TEMPERATURE = env_float('REPORT_AGENT_TEMPERATURE', 0.5, minimum=0, maximum=2)
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY no está configurada")
        if not cls.DEBUG and not cls.SECRET_KEY:
            errors.append("SECRET_KEY no está configurada")
        if not cls.DEBUG and not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD no está configurada")
        if not cls.DEBUG and cls.NEO4J_PASSWORD == 'mirofish2026':
            # Legacy guard — even if someone reintroduces the literal as an
            # env value, reject it. The old default is well-known.
            errors.append("NEO4J_PASSWORD usa el valor por defecto inseguro")
        if cls.API_AUTH_REQUIRED and not (cls.API_AUTH_TOKEN or cls.POCKETBASE_URL):
            errors.append("API auth requiere API_AUTH_TOKEN o POCKETBASE_URL")
        return errors
