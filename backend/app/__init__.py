"""
Simuloo Backend - Flask应用工厂
"""

import json
import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .utils.logger import setup_logger, get_logger
from .utils.security import validate_bearer_token, is_valid_storage_id


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
        logger.info("Arrancando Simuloo Backend...")
        logger.info("=" * 50)

    # CORS cerrado por configuración. En producción, si frontend y backend
    # comparten dominio, no hace falta añadir el dominio público aquí.
    CORS(
        app,
        resources={r"/api/*": {"origins": Config.CORS_ORIGINS}},
        allow_headers=["Content-Type", "Authorization", "Accept-Language"],
        methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        supports_credentials=True,
    )
    if should_log_startup:
        logger.info(f"CORS allow-list: {Config.CORS_ORIGINS}")

    # Rate limit por IP. Defaults vacíos: aplicamos el límite por blueprint
    # más abajo, así rutas no-API (assets, health) quedan libres.
    # Detrás del proxy de Coolify (Traefik) la IP del cliente llega en
    # X-Forwarded-For; sin esto todos los usuarios comparten la IP del proxy.
    if Config.TRUSTED_PROXIES > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=Config.TRUSTED_PROXIES, x_proto=Config.TRUSTED_PROXIES)

    def api_rate_limit():
        # El frontend hace polling de estado cada 1,5-3 s en varias rutas a la
        # vez: las lecturas llevan un límite holgado; las escrituras (las que
        # disparan LLM y simulaciones) uno estricto.
        # Los endpoints de estado por POST (prepare/status, env-status,
        # generate/status) también se consultan en bucle: cuentan como lectura.
        if request.method in ('GET', 'HEAD', 'OPTIONS') or request.path.endswith('status'):
            return Config.API_READ_RATE_LIMIT
        return Config.API_WRITE_RATE_LIMIT

    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
        storage_uri='memory://',
    )
    app.extensions['limiter'] = limiter

    @app.errorhandler(429)
    def handle_rate_limit(error):
        return {
            "success": False,
            "error": "Demasiadas peticiones, espera unos segundos"
        }, 429

    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Función de limpieza de procesos de simulación registrada")

    # Security: warn loudly if the static bearer fallback is enabled.
    # API_AUTH_TOKEN bypasses PocketBase entirely — anyone who learns the
    # value gets full /api/* access. It exists for break-glass scenarios
    # (e.g. PocketBase down) but should never be left set in production.
    if should_log_startup and Config.API_AUTH_TOKEN:
        logger.warning(
            "[security] API_AUTH_TOKEN is set — static bearer auth is "
            "enabled and bypasses PocketBase. Unset this env var in "
            "production unless you intentionally need a break-glass token."
        )

    # Security: warn loudly if /api/* auth is fully disabled. This was
    # added so dev environments could skip auth, but enabling it in prod
    # exposes every endpoint anonymously.
    if should_log_startup and not Config.API_AUTH_REQUIRED:
        logger.warning(
            "[security] API_AUTH_REQUIRED=false — /api/* is OPEN to "
            "anonymous callers. This must only be used in local dev."
        )

    # Boot-time orphan recovery: any project still marked GRAPH_BUILDING
    # cannot have a live build thread (we just booted), so it would stay
    # stuck in that state forever blocking the user. Mark them FAILED with
    # a clear message so the UI can offer a retry. We do this in the main
    # boot, not in the reloader child, to avoid running it twice in DEBUG.
    if should_log_startup:
        try:
            from .models.project import ProjectManager, ProjectStatus
            stale = [
                p for p in ProjectManager.list_projects(limit=1000)
                if p.status == ProjectStatus.GRAPH_BUILDING
            ]
            for p in stale:
                p.status = ProjectStatus.FAILED
                p.error = (
                    "El servidor se reinició mientras se construía el grafo. "
                    "Vuelve a lanzar la construcción para reintentar."
                )
                p.graph_build_task_id = None
                ProjectManager.save_project(p)
                logger.warning(
                    f"[boot-recovery] Marked project {p.project_id} as FAILED "
                    f"(was stuck in GRAPH_BUILDING with no live thread)"
                )
            if stale:
                logger.info(f"[boot-recovery] Reconciled {len(stale)} orphaned project(s)")
        except Exception as exc:  # noqa: BLE001 — boot must not abort on this
            logger.warning(f"[boot-recovery] Skipped orphan reconciliation: {exc}")

    # 请求日志中间件
    _SENSITIVE_KEYS = {
        'api_key', 'llm_api_key', 'password', 'token', 'secret',
        'authorization', 'key'
    }

    def _sanitize_body(body: dict) -> dict:
        """Redacta campos sensibles antes de loguear el cuerpo de la petición."""
        if not isinstance(body, dict):
            return body
        return {
            k: '***' if k.lower() in _SENSITIVE_KEYS else v
            for k, v in body.items()
        }

    @app.before_request
    def log_and_gate_request():
        req_logger = get_logger('mirofish.request')
        req_logger.debug(f"Petición: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            body = request.get_json(silent=True)
            if body:
                req_logger.debug(f"Cuerpo de la petición: {_sanitize_body(body)}")

        if not (
            Config.API_AUTH_REQUIRED
            and request.path.startswith('/api/')
            and request.path != '/api/health'
            and request.method != 'OPTIONS'
        ):
            return None

        auth_header = request.headers.get('Authorization', '')
        if not validate_bearer_token(auth_header):
            get_logger('mirofish.security').warning(
                f"401 unauthorized API request: {request.method} {request.path}"
            )
            return {
                "success": False,
                "error": "No autorizado"
            }, 401

        return None

    @app.after_request
    def log_response(response):
        req_logger = get_logger('mirofish.request')
        req_logger.debug(f"Respuesta: {response.status_code}")
        return response

    # IDs de almacenamiento en la URL: se validan antes de entrar en la ruta,
    # así un ID manipulado da 400 y no un 500 desde el try/except de cada vista.
    _STORAGE_ID_PREFIXES = {
        'project_id': 'proj_',
        'simulation_id': 'sim_',
        'report_id': 'report_',
    }

    @app.before_request
    def validate_storage_ids_in_url():
        for arg, prefix in _STORAGE_ID_PREFIXES.items():
            value = (request.view_args or {}).get(arg)
            if value is not None and not is_valid_storage_id(value, prefix):
                return {"success": False, "error": "Identificador no válido"}, 400
        return None

    @app.errorhandler(ValueError)
    def handle_value_error(error):
        # Un JSON corrupto en disco es un fallo del servidor, no del cliente
        if isinstance(error, json.JSONDecodeError):
            get_logger('mirofish.request').error(f"JSON corrupto: {error}")
            return {"success": False, "error": "Error interno"}, 500
        req_logger = get_logger('mirofish.request')
        req_logger.warning(f"Petición inválida: {error}")
        return {
            "success": False,
            "error": str(error)
        }, 400

    # 注册蓝图 + rate limit por blueprint (ver api_rate_limit).
    from .api import graph_bp, simulation_bp, report_bp, brief_bp
    limiter.limit(api_rate_limit)(graph_bp)
    limiter.limit(api_rate_limit)(simulation_bp)
    limiter.limit(api_rate_limit)(report_bp)
    limiter.limit(api_rate_limit)(brief_bp)
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(brief_bp, url_prefix='/api/brief')

    # 健康检查 — público (lo usa Coolify para health probes).
    @app.route('/health')
    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'service': 'Simuloo Backend'}

    # Servir el frontend compilado en producción
    frontend_dist = os.path.join(os.path.dirname(__file__), '../../frontend/dist')

    if os.path.exists(frontend_dist):
        from flask import send_from_directory

        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve_frontend(path):
            # Una ruta /api/* inexistente debe dar 404 JSON, no el index.html del SPA
            if path == 'api' or path.startswith('api/'):
                return {'success': False, 'error': 'Not found'}, 404
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
        logger.info("Simuloo Backend arrancado correctamente")

    return app
