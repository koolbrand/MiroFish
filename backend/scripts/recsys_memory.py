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
recomendaciones apenas cambia; el cómputo total es el mismo, solo se reparte
en lotes más pequeños.
"""
import os
from typing import List

RECSYS_BATCH_SIZE = int(os.environ.get('RECSYS_BATCH_SIZE', '64'))
RECSYS_MAX_TOKENS = int(os.environ.get('RECSYS_MAX_TOKENS', '256'))

_applied = False


def apply() -> bool:
    """Aplica el tope una sola vez. Devuelve False si OASIS no está disponible."""
    global _applied
    if _applied:
        return True
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
        return original_generate(model, tokenizer, texts, min(batch_size, RECSYS_BATCH_SIZE))

    # generate_post_vector llama a process_batch por nombre del módulo, y
    # recsys importó generate_post_vector por nombre: se parchean los dos.
    prp.process_batch = process_batch
    prp.generate_post_vector = generate_post_vector
    recsys.generate_post_vector = generate_post_vector
    _applied = True
    return True
