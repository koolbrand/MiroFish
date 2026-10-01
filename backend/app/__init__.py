"""
Simuloo Backend - Flask应用工厂
"""

import json
import os
import re
import uuid
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, g, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .utils.logger import setup_logger, get_logger
from .utils.locale import t
from .utils.security import identify_bearer, is_valid_storage_id, is_internal_request
from .utils.access import ADMIN, INTERNAL, user_identity, authorize_request


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

    # Las llamadas internas del modo automático (hilo del servidor contra sus
    # propias rutas) no cuentan para el límite por IP: todas salen de
    # 127.0.0.1 y agotarían el cupo de escrituras del resto.
    @limiter.request_filter
    def _exempt_internal_requests():
        return is_internal_request(request.headers)

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

        # Informes que se estaban escribiendo: su hilo murió con el proceso. Sin esto se quedan
        # «generándose» para siempre y la pantalla del informe espera sin fin.
        try:
            from .services.report_agent import ReportManager
            orphaned = ReportManager.fail_unfinished(
                "El servidor se reinició mientras se escribía el informe. Genera el informe de nuevo."
            )
            if orphaned:
                logger.warning(f"[boot-recovery] {orphaned} informe(s) sin terminar marcados como fallidos")
        except Exception as exc:  # noqa: BLE001 — el arranque no debe caer por esto
            logger.warning(f"[boot-recovery] No se pudieron revisar los informes: {exc}")

        # Simulaciones que estaban en marcha: su subproceso murió con el servidor. Sin esto se quedan «en
        # marcha» para siempre y no se puede ni generar el informe con lo que ya hay ni reiniciarlas sin borrar.
        try:
            from .services.boot_recovery import recover_orphaned_simulations
            orphaned_sims = recover_orphaned_simulations()
            if orphaned_sims:
                logger.warning(f"[boot-recovery] {orphaned_sims} simulación(es) en marcha marcadas como fallidas")
        except Exception as exc:  # noqa: BLE001 — el arranque no debe caer por esto
            logger.warning(f"[boot-recovery] No se pudieron revisar las simulaciones: {exc}")

        # Modo automático: los hilos que encadenaban las etapas murieron con
        # el proceso. Todo pipeline en `running` pasa a `interrupted`; no se
        # reanuda solo (cuesta dinero de LLM): lo decide el usuario.
        try:
            from .services.pipeline_state import mark_running_pipelines_interrupted
            interrupted = mark_running_pipelines_interrupted()
            if interrupted:
                logger.info(f"[boot-recovery] {interrupted} pipeline(s) automáticos marcados como interrupted")
        except Exception as exc:  # noqa: BLE001 — el arranque no debe caer por esto
            logger.warning(f"[boot-recovery] No se pudieron revisar los pipelines automáticos: {exc}")

    # 请求日志中间件
    _SENSITIVE_KEYS = {
        'api_key', 'llm_api_key', 'password', 'token', 'secret',
        'authorization', 'key'
    }

    _ID_VALUE = re.compile(r'^(proj|sim|report|task)_[0-9a-f-]{6,64}$')

    def _describe_body(body) -> dict:
        """
        Forma del cuerpo de la petición para el log: claves, tipos y tamaños; los ids sí, el resto NO.
        Antes se volcaba el cuerpo entero (briefs, mensajes de chat, prompts) al archivo de log, y sin autenticar.
        """
        if not isinstance(body, dict):
            return {"tipo": type(body).__name__}
        out = {}
        for key, value in body.items():
            if key.lower() in _SENSITIVE_KEYS:
                out[key] = '***'
            elif isinstance(value, str) and _ID_VALUE.match(value):
                out[key] = value
            elif isinstance(value, (str, list, dict)):
                out[key] = f"{type(value).__name__}[{len(value)}]"
            else:
                out[key] = value if isinstance(value, (bool, int, float)) or value is None else type(value).__name__
        return out

    _INTERNAL_PATTERNS = (
        re.compile(r'(/[\w.\-]+){2,}'),                  # rutas y URLs: /app/backend/app/x.py, https://api.…/v1
        re.compile(r'\b[\w.\-]+:\d{2,5}\b'),             # host:puerto (neo4j:7687)
        re.compile(r'Traceback|File "|\bline \d+\b'),     # trazas de Python
    )

    def _looks_internal(message: str) -> bool:
        return any(p.search(message) for p in _INTERNAL_PATTERNS)

    # Rutas que reciben archivos: son las únicas con el tope de 50 MB; el resto, MAX_BODY_BYTES (1 MB)
    UPLOAD_PATHS = {'/api/graph/ontology/generate', '/api/pipeline/auto', '/api/brief/check'}

    @app.before_request
    def log_and_gate_request():
        req_logger = get_logger('mirofish.request')
        # Antes de leer NADA del cuerpo: el tope depende de la ruta
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            request.max_content_length = Config.MAX_CONTENT_LENGTH if request.path in UPLOAD_PATHS else Config.MAX_BODY_BYTES
        req_logger.debug(f"Petición: {request.method} {request.path}")

        if not (
            request.path.startswith('/api/')
            and request.path != '/api/health'
            and request.method != 'OPTIONS'
        ):
            return None

        # Quién hace la petición (aislamiento por usuario): ver utils/access.py
        if not Config.API_AUTH_REQUIRED:
            g.identity = ADMIN                      # desarrollo sin auth: ve todo
        elif is_internal_request(request.headers):
            g.identity = INTERNAL                   # llamada interna del modo automático (secreto del proceso)
        else:
            who = identify_bearer(request.headers.get('Authorization', ''))
            if who is None:
                get_logger('mirofish.security').warning(
                    f"401 unauthorized API request: {request.method} {request.path}"
                )
                return {
                    "success": False,
                    "error": "No autorizado"
                }, 401
            kind, user_id = who
            g.identity = user_identity(user_id) if kind == 'user' else ADMIN

        # Ya autenticado: ahora sí, la forma del cuerpo (nunca los valores) en el log
        if request.content_type and 'json' in request.content_type:
            body = request.get_json(silent=True)
            if body:
                req_logger.debug(f"Cuerpo de la petición: {_describe_body(body)}")

        # Lo que la petición nombra (proyecto, simulación, informe, grafo, tarea) debe poder verlo su identidad
        return authorize_request()

    @app.after_request
    def log_response(response):
        req_logger = get_logger('mirofish.request')
        req_logger.debug(f"Respuesta: {response.status_code}")

        # Cabeceras de seguridad básicas (sin CSP: la app usa estilos en línea y fuentes de Google)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        if request.path.startswith('/api/'):
            response.headers.setdefault('Cache-Control', 'no-store')       # datos de cada usuario: nada en cachés compartidas

        # Un 500 no cuenta al cliente cómo es el servidor por dentro (`Cannot resolve address neo4j:7687`, rutas,
        # trazas). Los mensajes pensados para la persona («El modelo no respondió») se respetan; los que parecen
        # internos se cambian por uno general con una referencia, y el original queda en el log con esa referencia.
        if response.status_code == 500 and response.is_json and not Config.DEBUG:
            try:
                data = response.get_json(silent=True)
                if isinstance(data, dict) and 'error' in data:
                    data.pop('traceback', None)
                    if _looks_internal(str(data.get('error'))):
                        ref = uuid.uuid4().hex[:8]
                        req_logger.error(f"500 en {request.method} {request.path} [ref {ref}]: {str(data.get('error'))[:500]}")
                        data['error'] = f"{t('api.internalError')} (ref {ref})"
                    response.set_data(json.dumps(data, ensure_ascii=False))
            except Exception:  # noqa: BLE001 — esto nunca debe romper la respuesta
                pass
        return response

    @app.errorhandler(413)
    def handle_too_large(error):
        return {"success": False, "error": t('api.payloadTooLarge')}, 413

    # Una ruta /api/* que no existe responde JSON siempre. Antes solo lo hacía la ruta comodín del frontend, que
    # existe únicamente si hay `frontend/dist`: sin esa carpeta (desarrollo solo con la API, CI) devolvía el 404 HTML
    # de Flask y el cliente no podía leer el error.
    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path == '/api' or request.path.startswith('/api/'):
            return {"success": False, "error": "Not found"}, 404
        return error

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
    from .api import graph_bp, simulation_bp, report_bp, brief_bp, pipeline_bp
    limiter.limit(api_rate_limit)(graph_bp)
    limiter.limit(api_rate_limit)(simulation_bp)
    limiter.limit(api_rate_limit)(report_bp)
    limiter.limit(api_rate_limit)(brief_bp)
    limiter.limit(api_rate_limit)(pipeline_bp)
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(brief_bp, url_prefix='/api/brief')
    app.register_blueprint(pipeline_bp, url_prefix='/api/pipeline')

    # 健康检查 — público (lo usa Coolify para health probes).
    @app.route('/health')
    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'service': 'Simuloo Backend'}

    # «Listo para trabajar»: además de que Flask responda, Neo4j contesta y el disco de datos se puede escribir.
    # Aparte de /health a propósito: si Coolify reiniciara el contenedor cada vez que Neo4j tarda en arrancar,
    # el remedio sería peor que el fallo. Esta es para un monitor externo; /health sigue siendo la del contenedor.
    @app.route('/health/ready')
    def health_ready():
        from .utils.health import readiness
        ready, checks = readiness()
        return {'status': 'ok' if ready else 'degraded', 'checks': checks}, (200 if ready else 503)

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
