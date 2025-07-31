from .base_avaliador import BaseAvaliador

class AvaliadorLocal(BaseAvaliador):
    """Avaliador que usa método local simples de matching por palavras-chave"""

    def calcular_score(self, curriculo, requisitos, pretensao_salarial, salario_oferecido, 
                      diferenciais=None, candidato_endereco=None, vaga_endereco=None, tipo_vaga='Presencial'):
        """Calcula score do candidato baseado em critérios inteligentes"""
        score = 0

        # Score baseado em compatibilidade salarial (25%)
        if salario_oferecido >= pretensao_salarial:
            score += 25
        else:
            # Penalizar se pretensão for muito acima
            diferenca_percentual = (pretensao_salarial - salario_oferecido) / salario_oferecido
            if diferenca_percentual <= 0.1:  # até 10% acima
                score += 20
            elif diferenca_percentual <= 0.2:  # até 20% acima
                score += 12
            else:
                score += 3

        # Score baseado em requisitos obrigatórios (50%)
        palavras_requisitos = self._extrair_palavras_chave(requisitos.lower())
        curriculo_lower = curriculo.lower()

        matches_requisitos = 0
        for palavra in palavras_requisitos:
            if palavra in curriculo_lower:
                matches_requisitos += 1

        if len(palavras_requisitos) > 0:
            score += int((matches_requisitos / len(palavras_requisitos)) * 50)

        # Score baseado em diferenciais (até +15 pontos extras)
        if diferenciais:
            palavras_diferenciais = self._extrair_palavras_chave(diferenciais.lower())
            matches_diferenciais = 0
            for palavra in palavras_diferenciais:
                if palavra in curriculo_lower:
                    matches_diferenciais += 1

            if len(palavras_diferenciais) > 0:
                bonus_diferenciais = int((matches_diferenciais / len(palavras_diferenciais)) * 15)
                score += bonus_diferenciais

        # Score baseado em localização (até +10 pontos)
        if tipo_vaga in ['Presencial', 'Híbrida'] and candidato_endereco and vaga_endereco:
            bonus_localizacao = self._calcular_bonus_localizacao(
                candidato_endereco, vaga_endereco, tipo_vaga
            )
            score += bonus_localizacao

        return min(score, 100)

    def _extrair_palavras_chave(self, texto):
        """Extrai palavras-chave relevantes do texto"""
        import re
        # Remove pontuação e divide em palavras
        palavras = re.findall(r'\b\w+\b', texto.lower())
        # Filtra palavras muito curtas e stopwords básicas
        stopwords = {'a', 'o', 'e', 'de', 'da', 'do', 'em', 'um', 'uma', 'para', 'com', 'por', 'que', 'na', 'no'}
        palavras_filtradas = [p for p in palavras if len(p) > 2 and p not in stopwords]
        return palavras_filtradas

    def _calcular_bonus_localizacao(self, candidato_endereco, vaga_endereco, tipo_vaga):
        """Calcula bonus por proximidade geográfica"""
        # Simulação simplificada de proximidade
        candidato_lower = candidato_endereco.lower()
        vaga_lower = vaga_endereco.lower()

        # Verificar se é mesma cidade/região
        palavras_candidato = candidato_lower.split()
        palavras_vaga = vaga_lower.split()

        matches_localizacao = 0
        for palavra in palavras_vaga:
            if len(palavra) > 2 and palavra in palavras_candidato:
                matches_localizacao += 1

        if matches_localizacao >= 2:  # Mesma cidade/região
            return 10 if tipo_vaga == 'Presencial' else 6
        elif matches_localizacao >= 1:  # Mesmo estado/região próxima
            return 6 if tipo_vaga == 'Presencial' else 3
        else:
            return 0

    def calcular_score_requisitos(self, texto_curriculo, requisitos_vaga):
        """Calcula score baseado nos requisitos (70% do peso total)"""
        if not texto_curriculo or not requisitos_vaga:
            return 0

        # Divide os requisitos e conta quantos aparecem no currículo
        requisitos_lista = [req.strip().lower() for req in requisitos_vaga.split(',') if req.strip()]
        texto_curriculo_lower = texto_curriculo.lower()

        if not requisitos_lista:
            return 35  # Score médio se não tiver requisitos

        requisitos_encontrados = 0
        for requisito in requisitos_lista:
            if requisito in texto_curriculo_lower:
                requisitos_encontrados += 1

        # Score baseado na porcentagem de requisitos encontrados
        porcentagem_match = requisitos_encontrados / len(requisitos_lista)
        return porcentagem_match * 70