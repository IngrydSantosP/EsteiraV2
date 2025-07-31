
from .avaliador_local import AvaliadorLocal
from .avaliador_hf import AvaliadorHuggingFace

def criar_avaliador(modo_ia):
    """Factory para criar o avaliador baseado no modo configurado"""
    if modo_ia == 'huggingface':
        return AvaliadorHuggingFace()
    else:
        return AvaliadorLocal()
