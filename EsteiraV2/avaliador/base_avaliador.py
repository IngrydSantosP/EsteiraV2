
from abc import ABC, abstractmethod

class BaseAvaliador(ABC):
    """Classe base abstrata para avaliadores de matching"""
    
    @abstractmethod
    def calcular_score(self, texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido):
        """Calcula o score de compatibilidade entre currículo e vaga"""
        pass
    
    def calcular_score_salarial(self, pretensao_salarial, salario_oferecido):
        """Calcula score baseado na pretensão salarial (30% do peso total)"""
        if not pretensao_salarial or not salario_oferecido:
            return 15  # Score médio se não tiver informação salarial
        
        if pretensao_salarial <= salario_oferecido:
            return 30  # Perfeita compatibilidade
        elif pretensao_salarial <= salario_oferecido * 1.2:  # 20% acima
            return 20  # Boa compatibilidade
        elif pretensao_salarial <= salario_oferecido * 1.5:  # 50% acima
            return 10  # Compatibilidade razoável
        else:
            return 5   # Baixa compatibilidade
