"""Un solo manejador de archivo para todos los loggers de la aplicación (cada módulo abría el suyo sobre el mismo archivo)."""

import logging
import logging.handlers

from app.utils import logger as log_mod


def _file_handlers(lg):
    return [h for h in lg.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]


def test_module_loggers_do_not_open_their_own_file_handler():
    root = log_mod.get_logger('mirofish')
    names = [f'mirofish.prueba_{i}' for i in range(5)]
    children = [log_mod.get_logger(n) for n in names]

    assert len(_file_handlers(root)) == 1
    for child in children:
        assert child.handlers == []                      # sin manejadores propios
        assert child.propagate is True                   # escribe a través del principal
        assert child.parent is root or child.parent.name.startswith('mirofish')


def test_child_records_reach_the_main_file_handler():
    root = log_mod.get_logger('mirofish')
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    cap = Capture(level=logging.DEBUG)
    root.addHandler(cap)
    try:
        log_mod.get_logger('mirofish.prueba_flujo').info('hola desde un módulo')
    finally:
        root.removeHandler(cap)
    assert 'hola desde un módulo' in seen


def test_main_logger_does_not_leak_to_root_logger():
    assert log_mod.get_logger('mirofish').propagate is False


def test_repeated_get_logger_does_not_add_handlers():
    root = log_mod.get_logger('mirofish')
    before = len(root.handlers)
    for _ in range(10):
        log_mod.get_logger('mirofish.repetido')
    assert len(root.handlers) == before
