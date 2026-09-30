"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
brief_bp = Blueprint('brief', __name__)
pipeline_bp = Blueprint('pipeline', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import brief  # noqa: E402, F401
from . import pipeline  # noqa: E402, F401

