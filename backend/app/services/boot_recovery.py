"""
Recuperación al arrancar de las simulaciones que estaban en marcha.

Los subprocesos de OASIS mueren con el servidor (reinicio, despliegue, memoria agotada). Sin esto, su
`run_state.json` se queda en «running» para siempre: la pantalla «reconecta» sin fin, `/start` responde que
ya hay una en marcha, y `/report/generate` se niega a escribir el informe con los datos parciales. Aquí pasan
a `failed` con el motivo, conservando los contadores y las acciones ya escritas, para que la persona pueda
generar el informe con lo que hay o reiniciarla.
"""

import os
from datetime import datetime
from typing import Any, Dict

from ..utils.fs import atomic_write_json, read_json_or_none
from ..utils.logger import get_logger
from ..utils.security import is_valid_storage_id
from .simulation_manager import SimulationManager, SimulationStatus
from .simulation_runner import RunnerStatus, SimulationRunner

logger = get_logger('mirofish.boot_recovery')

# Estados que solo pueden darse con un proceso vivo
_LIVE_RUNNER = {RunnerStatus.STARTING.value, RunnerStatus.RUNNING.value,
                RunnerStatus.PAUSED.value, RunnerStatus.STOPPING.value}
_LIVE_SIMULATION = {SimulationStatus.RUNNING.value, SimulationStatus.PAUSED.value}

DEFAULT_REASON = "El servidor se reinició mientras se ejecutaba la simulación. Se conservan las acciones ya hechas."


def recover_orphaned_simulations(reason: str = DEFAULT_REASON) -> int:
    """Devuelve cuántas simulaciones se corrigieron. Tolerante: un archivo ilegible se salta."""
    base = SimulationRunner.RUN_STATE_DIR
    if not os.path.isdir(base):
        return 0
    fixed = 0
    now = datetime.now().isoformat()
    for sim_id in sorted(os.listdir(base)):
        folder = os.path.join(base, sim_id)
        if not is_valid_storage_id(sim_id, "sim_") or not os.path.isdir(folder):
            continue
        touched = False
        try:
            run_path = os.path.join(folder, "run_state.json")
            run: Any = read_json_or_none(run_path, what=f"el estado de ejecución de {sim_id}")
            if isinstance(run, dict) and run.get("runner_status") in _LIVE_RUNNER:
                run.update(runner_status=RunnerStatus.FAILED.value, error=reason, completed_at=now,
                           twitter_running=False, reddit_running=False, updated_at=now)
                atomic_write_json(run_path, run)
                touched = True

            state_path = os.path.join(SimulationManager.SIMULATION_DATA_DIR, sim_id, "state.json")
            state: Dict[str, Any] = read_json_or_none(state_path, what=f"el estado de {sim_id}")
            if isinstance(state, dict) and state.get("status") in _LIVE_SIMULATION:
                state.update(status=SimulationStatus.FAILED.value, error=reason, updated_at=now,
                             twitter_status="failed" if state.get("twitter_status") == "running" else state.get("twitter_status"),
                             reddit_status="failed" if state.get("reddit_status") == "running" else state.get("reddit_status"))
                atomic_write_json(state_path, state)
                touched = True

            # El entorno de entrevistas ya no existe: sin esto `check_env_alive` lo daría por vivo
            env_path = os.path.join(folder, "env_status.json")
            env: Any = read_json_or_none(env_path, what=f"el entorno de {sim_id}")
            if isinstance(env, dict) and env.get("status") == "alive":
                env.update(status="stopped", timestamp=now)
                atomic_write_json(env_path, env)
                touched = True
        except OSError as exc:
            logger.warning(f"[boot-recovery] No se pudo corregir la simulación {sim_id}: {exc}")
            continue
        if touched:
            fixed += 1
            logger.warning(f"[boot-recovery] Simulación {sim_id}: estaba en marcha y su proceso murió con el servidor")
    return fixed
