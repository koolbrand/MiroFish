"""
MiroFish Backend - Flask应用工厂
"""

import os
import time
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

import urllib.error
import urllib.request

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .config import Config
from .utils.logger import setup_logger, get_logger


# --------------------------------------------------------------------------
# Security: allowed origins for the public API
# --------------------------------------------------------------------------
# Frontend is served from one of these. Anything else (curl, scrapers, other
# browsers) gets a 403 before we touch the LLM keys or the database.
# Override at deploy time with the ALLOWED_ORIGINS env var (comma-separated).
ALLOWED_ORIGINS = [
    o.strip().rstrip('/')
    for o in os.environ.get(
        'ALLOWED_ORIGINS',
        'https://mirofish.koolgrowth.com,https://mirror.koolgrowth.com'
    ).split(',')
    if o.strip()
]

# PocketBase instance used to validate user sessions. The frontend ships a
# bearer token (the PocketBase JWT) and we ask PB whether it is still valid.
POCKETBASE_URL = os.environ.get(
    'POCKETBASE_URL', 'https://pocketbase.koolgrowth.com'
).rstrip('/')

# Tiny in-process cache to avoid hammering PocketBase on every request.
# Maps token -> (expires_at_epoch, is_valid_bool).
_AUTH_CACHE: dict = {}
_AUTH_CACHE_TTL_SECONDS = 60


def _origin_allowed(req) -> bool:
    """Check if the request's Origin or Referer matches our allow-list."""
    origin = req.headers.get('Origin', '').rstrip('/')
    if origin and origin in ALLOWED_ORIGINS:
        return True
    referer = req.headers.get('Referer', '')
    if referer:
        return any(referer == o or referer.startswith(o + '/') for o in ALLOWED_ORIGINS)
    return False


def _token_valid(token: str) -> bool:
    """Validate a PocketBase bearer token by calling /auth-refresh.

    Cached for _AUTH_CACHE_TTL_SECONDS so we don't talk to PB on every API
    call. PB tokens are JWTs with their own expiry; this just confirms the
    server hasn't revoked them.
    """
    if not token:
        return False

    now = time.time()
    cached = _AUTH_CACHE.get(token)
    if cached and cached[0] > now:
        return cached[1]

    url = f"{POCKETBASE_URL}/api/collections/users/auth-refresh"
    req = urllib.request.Request(
        url,
        method='POST',
        headers={'Authorization': token, 'Content-Type': 'application/json'},
        data=b'',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            valid = 200 <= resp.status < 300
    except urllib.error.HTTPError:
        valid = False
    except (urllib.error.URLError, TimeoutError, OSError):
        # Fail closed on transport errors so an outage doesn't open the API.
        valid = False

    _AUTH_CACHE[token] = (now + _AUTH_CACHE_TTL_SECONDS, valid)
    # Cap cache growth.
    if len(_AUTH_CACHE) > 1024:
        for k in list(_AUTH_CACHE.keys())[:512]:
            _AUTH_CACHE.pop(k, None)
    return valid


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('mirofish')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("Arrancando MiroFish Backend...")
        logger.info("=" * 50)
    
    # CORS — restringido al allow-list. Sin esto cualquier origen podía
    # llamar a /api/* desde el navegador del usuario.
    CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}}, supports_credentials=True)
    if should_log_startup:
        logger.info(f"CORS allow-list: {ALLOWED_ORIGINS}")

    # Rate limit por IP. Defaults vacíos: aplicamos el límite por blueprint
    # más abajo, así rutas no-API (assets, health) quedan libres.
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
    )
    app.extensions['limiter'] = limiter

    # --------------------------------------------------------------------
    # Gate de seguridad — se ejecuta antes que CUALQUIER ruta /api/*.
    # Tres capas:
    #   1. Origin / Referer en allow-list  → bloquea curl y otros sitios
    #   2. Bearer token válido en PocketBase → bloquea usuarios sin sesión
    #   3. Rate limit por IP (más abajo)     → contiene abuso autenticado
    # /api/health queda público para los probes de Coolify.
    # --------------------------------------------------------------------
    @app.before_request
    def gate_api_requests():
        path = request.path
        if not path.startswith('/api/'):
            return None  # frontend assets, /health, etc.
        if path == '/api/health':
            return None  # public health probe
        # CORS preflight: el navegador no manda Authorization en OPTIONS.
        # flask-cors responde a OPTIONS por su cuenta; aquí dejamos pasar.
        if request.method == 'OPTIONS':
            return None

        if not _origin_allowed(request):
            get_logger('mirofish.security').warning(
                f"403 origin not allowed: {request.method} {path} "
                f"origin={request.headers.get('Origin')!r} "
                f"referer={request.headers.get('Referer')!r}"
            )
            return jsonify({'error': 'forbidden', 'success': False}), 403

        auth = request.headers.get('Authorization', '')
        # PocketBase manda el token "tal cual" en Authorization (sin prefijo
        # "Bearer "). Aceptamos ambas formas para ser robustos.
        token = auth[len('Bearer '):] if auth.lower().startswith('bearer ') else auth
        if not token or not _token_valid(token):
            get_logger('mirofish.security').warning(
                f"401 invalid/missing token: {request.method} {path}"
            )
            return jsonify({'error': 'unauthorized', 'success': False}), 401

        return None

    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Función de limpieza de procesos de simulación registrada")
    
    # 请求日志中间件
    _SENSITIVE_KEYS = {'api_key', 'llm_api_key', 'password', 'token', 'secret', 'authorization', 'key'}

    def _sanitize_body(body: dict) -> dict:
        """Redacta campos sensibles antes de loguear el cuerpo de la petición."""
        if not isinstance(body, dict):
            return body
        return {
            k: '***' if k.lower() in _SENSITIVE_KEYS else v
            for k, v in body.items()
        }

    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"Petición: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            body = request.get_json(silent=True)
            if body:
                logger.debug(f"Cuerpo de la petición: {_sanitize_body(body)}")

    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"Respuesta: {response.status_code}")
        return response
    
    # 注册蓝图 + rate limit por blueprint (30 req/min/IP).
    from .api import graph_bp, simulation_bp, report_bp
    limiter.limit("30 per minute")(graph_bp)
    limiter.limit("30 per minute")(simulation_bp)
    limiter.limit("30 per minute")(report_bp)
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')

    # 健康检查 — público (lo usa Coolify para health probes).
    @app.route('/health')
    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}

    # Servir el frontend compilado en producción
    frontend_dist = os.path.join(os.path.dirname(__file__), '../../frontend/dist')

    if os.path.exists(frontend_dist):
        from flask import send_from_directory

        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve_frontend(path):
            file_path = os.path.join(frontend_dist, path)
            if path and os.path.exists(file_path) and os.path.isfile(file_path):
                return send_from_directory(frontend_dist, path)
            return send_from_directory(frontend_dist, 'index.html')

        if should_log_startup:
            logger.info(f"Frontend servido desde: {frontend_dist}")
    else:
        if should_log_startup:
            logger.info("Frontend dist no encontrado, solo API disponible")

    if should_log_startup:
        logger.info("MiroFish Backend arrancado correctamente")

    return app

