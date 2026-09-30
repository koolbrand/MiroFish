"""
Tope de memoria para el recomendador TwHIN-BERT de OASIS (red tipo X).

OASIS vuelve a codificar en cada refresco TODO el corpus (perfiles + hasta
4000 publicaciones) en lotes de 1000 textos de hasta 512 tokens. La memoria
de la atención crece con lote × longitud², así que en rondas avanzadas (más
publicaciones, perfiles alargados con «# Recent post: …») el pico superaba
los 4 GB del contenedor y el sistema mataba la simulación (código -9; caso
real: Serranova, ronda 65/72).

Se acota el lote y la longitud de cada texto. El vector que usa el
recomendador es el `pooler_output` del primer token, así que el orden de las
recomendaciones apenas cambia.

Además, OASIS recalcula en cada refresco los vectores de TODAS las
publicaciones aunque su texto no cambie: el tiempo por ronda crecía con la
simulación (medido: 107 s con 400 publicaciones, 410 s con 1200). Se guarda
el vector de cada texto ya visto y solo se codifican los nuevos (las
publicaciones de la ronda y los perfiles, que sí cambian).
"""
import os
from collections import OrderedDict
from typing import List

RECSYS_BATCH_SIZE = int(os.environ.get('RECSYS_BATCH_SIZE', '64'))
RECSYS_MAX_TOKENS = int(os.environ.get('RECSYS_MAX_TOKENS', '256'))
# ~3 KB por vector: 20000 entradas ≈ 60 MB como mucho
RECSYS_CACHE_SIZE = int(os.environ.get('RECSYS_CACHE_SIZE', '20000'))

_applied = False
_cache: "OrderedDict[str, object]" = OrderedDict()


def apply() -> bool:
    """Aplica el tope una sola vez. Devuelve False si OASIS no está disponible."""
    global _applied
    if _applied:
        return True
    # Interruptor para comparar con y sin el parche en las mismas condiciones
    if os.environ.get('RECSYS_MEMORY_PATCH', '1') == '0':
        return False
    try:
        import torch
        from oasis.social_platform import process_recsys_posts as prp
        from oasis.social_platform import recsys
    except Exception:
        return False

    original_generate = prp.generate_post_vector

    @torch.no_grad()
    def process_batch(model, tokenizer, batch_texts: List[str]):
        device = next(model.parameters()).device
        inputs = tokenizer(
            batch_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=RECSYS_MAX_TOKENS,
        )
        inputs = {key: value.to(device) for key, value in inputs.items()}
        return model(**inputs).pooler_output

    def generate_post_vector(model, tokenizer, texts, batch_size):
        keys = [t if isinstance(t, str) else str(t) for t in texts]
        missing = list(dict.fromkeys(k for k in keys if k not in _cache))
        if missing:
            vectors = original_generate(model, tokenizer, missing, min(batch_size, RECSYS_BATCH_SIZE))
            for k, v in zip(missing, vectors):
                _cache[k] = v.clone()
        for k in keys:
            _cache.move_to_end(k)
        # nunca se expulsa un texto de esta misma llamada
        limit = max(RECSYS_CACHE_SIZE, len(set(keys)))
        while len(_cache) > limit:
            _cache.popitem(last=False)
        return torch.stack([_cache[k] for k in keys])

    # generate_post_vector llama a process_batch por nombre del módulo, y
    # recsys importó generate_post_vector por nombre: se parchean los dos.
    prp.process_batch = process_batch
    prp.generate_post_vector = generate_post_vector
    recsys.generate_post_vector = generate_post_vector
    _applied = True
    return True
