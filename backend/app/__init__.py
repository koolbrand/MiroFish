"""
MiroFish Backend - Flask应用工厂
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .config import Config
from .utils.logger import setup_logger, get_logger
from .utils.security import validate_bearer_token


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
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
    )
    app.extensions['limiter'] = limiter

    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Función de limpieza de procesos de simulación registrada")

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

    @app.errorhandler(ValueError)
    def handle_value_error(error):
        req_logger = get_logger('mirofish.request')
        req_logger.warning(f"Petición inválida: {error}")
        return {
            "success": False,
            "error": str(error)
        }, 400

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
