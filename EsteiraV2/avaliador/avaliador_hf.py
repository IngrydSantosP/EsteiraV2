
from .base_avaliador import BaseAvaliador

class AvaliadorHuggingFace(BaseAvaliador):
    """Avaliador que usa sentence-transformers do Hugging Face"""
    
    def __init__(self):
        self.modelo = None
        self._carregar_modelo()
    
    def _carregar_modelo(self):
        """Carrega o modelo do Hugging Face"""
        try:
            from sentence_transformers import SentenceTransformer
            self.modelo = SentenceTransformer('all-MiniLM-L6-v2')
            print("Modelo Hugging Face carregado com sucesso")
        except ImportError:
            print("Sentence-transformers não disponível, usando método local")
            self.modelo = None
    
    def calcular_score(self, texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido):
        """Calcula score usando Hugging Face sentence-transformers"""
        # Se o modelo não estiver disponível, usar método local
        if self.modelo is None:
            from .avaliador_local import AvaliadorLocal
            avaliador_local = AvaliadorLocal()
            return avaliador_local.calcular_score(texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido)
        
        score_requisitos = self.calcular_score_requisitos_semantico(texto_curriculo, requisitos_vaga)
        score_salarial = self.calcular_score_salarial(pretensao_salarial, salario_oferecido)
        
        score_total = score_requisitos + score_salarial
        return min(score_total, 100)
    
    def calcular_score_requisitos_semantico(self, texto_curriculo, requisitos_vaga):
        """Calcula score usando similaridade semântica"""
        if not texto_curriculo or not requisitos_vaga or self.modelo is None:
            return 0
        
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Calcular embeddings
            embedding_curriculo = self.modelo.encode([texto_curriculo])
            embedding_requisitos = self.modelo.encode([requisitos_vaga])
            
            # Calcular similaridade
            similaridade = cosine_similarity(embedding_curriculo, embedding_requisitos)[0][0]
            
            # Converter similaridade (0-1) para score (0-70)
            return max(0, min(70, similaridade * 70))
            
        except Exception as e:
            print(f"Erro no cálculo semântico: {e}")
            # Fallback para método local
            from .avaliador_local import AvaliadorLocal
            avaliador_local = AvaliadorLocal()
            return avaliador_local.calcular_score_requisitos(texto_curriculo, requisitos_vaga)
