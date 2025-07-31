import sqlite3
from datetime import datetime, timedelta
import json


def gerar_relatorio_completo(empresa_id, filtro_vagas=None):
    """Gera relatório estratégico e gerencial completo para a empresa"""
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    try:
        # Dados básicos da empresa
        cursor.execute('SELECT nome FROM empresas WHERE id = ?',
                       (empresa_id, ))
        empresa_nome = cursor.fetchone()[0]

        # Total de vagas (com filtro opcional)
        if filtro_vagas:
            vagas_query = 'SELECT COUNT(*) FROM vagas WHERE empresa_id = ? AND id IN ({})'.format(
                ','.join('?' * len(filtro_vagas)))
            cursor.execute(vagas_query, [empresa_id] + filtro_vagas)
        else:
            cursor.execute('SELECT COUNT(*) FROM vagas WHERE empresa_id = ?',
                           (empresa_id, ))
        total_vagas = cursor.fetchone()[0]

        # Total de candidaturas
        if filtro_vagas:
            candidaturas_query = '''
                SELECT COUNT(*) FROM candidaturas cand 
                JOIN vagas v ON v.id = cand.vaga_id 
                WHERE v.empresa_id = ? AND v.id IN ({})
            '''.format(','.join('?' * len(filtro_vagas)))
            cursor.execute(candidaturas_query, [empresa_id] + filtro_vagas)
        else:
            cursor.execute(
                '''
                SELECT COUNT(*) FROM candidaturas cand 
                JOIN vagas v ON v.id = cand.vaga_id 
                WHERE v.empresa_id = ?
            ''', (empresa_id, ))
        total_candidaturas = cursor.fetchone()[0]

        # Score médio geral
        if filtro_vagas:
            score_query = '''
                SELECT AVG(cand.score) FROM candidaturas cand 
                JOIN vagas v ON v.id = cand.vaga_id 
                WHERE v.empresa_id = ? AND v.id IN ({})
            '''.format(','.join('?' * len(filtro_vagas)))
            cursor.execute(score_query, [empresa_id] + filtro_vagas)
        else:
            cursor.execute(
                '''
                SELECT AVG(cand.score) FROM candidaturas cand 
                JOIN vagas v ON v.id = cand.vaga_id 
                WHERE v.empresa_id = ?
            ''', (empresa_id, ))
        score_geral = cursor.fetchone()[0] or 0

        # Vaga com mais candidatos
        if filtro_vagas:
            vaga_candidatos_query = '''
                SELECT v.titulo, COUNT(cand.id) as total_candidatos
                FROM vagas v
                LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
                WHERE v.empresa_id = ? AND v.id IN ({})
                GROUP BY v.id, v.titulo
                ORDER BY total_candidatos DESC
                LIMIT 1
            '''.format(','.join('?' * len(filtro_vagas)))
            cursor.execute(vaga_candidatos_query, [empresa_id] + filtro_vagas)
        else:
            cursor.execute(
                '''
                SELECT v.titulo, COUNT(cand.id) as total_candidatos
                FROM vagas v
                LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
                WHERE v.empresa_id = ?
                GROUP BY v.id, v.titulo
                ORDER BY total_candidatos DESC
                LIMIT 1
            ''', (empresa_id, ))
        vaga_mais_candidatos = cursor.fetchone()

        # Vaga com maior score médio
        if filtro_vagas:
            vaga_score_query = '''
                SELECT v.titulo, AVG(cand.score) as score_medio
                FROM vagas v
                LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
                WHERE v.empresa_id = ? AND v.id IN ({}) AND cand.score IS NOT NULL
                GROUP BY v.id, v.titulo
                ORDER BY score_medio DESC
                LIMIT 1
            '''.format(','.join('?' * len(filtro_vagas)))
            cursor.execute(vaga_score_query, [empresa_id] + filtro_vagas)
        else:
            cursor.execute(
                '''
                SELECT v.titulo, AVG(cand.score) as score_medio
                FROM vagas v
                LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
                WHERE v.empresa_id = ? AND cand.score IS NOT NULL
                GROUP BY v.id, v.titulo
                ORDER BY score_medio DESC
                LIMIT 1
            ''', (empresa_id, ))
        vaga_maior_score = cursor.fetchone()

        # Lista detalhada de todas as vagas
        if filtro_vagas:
            vagas_detalhes_query = '''
                SELECT v.id, v.titulo, v.status, 
                       COUNT(cand.id) as total_candidatos,
                       AVG(cand.score) as score_medio,
                       COUNT(CASE WHEN cand.score >= 80 THEN 1 END) as candidatos_excelentes,
                       COUNT(CASE WHEN cand.score >= 60 AND cand.score < 80 THEN 1 END) as candidatos_bons,
                       COUNT(CASE WHEN cand.score < 60 THEN 1 END) as candidatos_baixos,
                       v.data_criacao
                FROM vagas v
                LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
                WHERE v.empresa_id = ? AND v.id IN ({})
                GROUP BY v.id, v.titulo, v.status, v.data_criacao
                ORDER BY v.data_criacao DESC
            '''.format(','.join('?' * len(filtro_vagas)))
            cursor.execute(vagas_detalhes_query, [empresa_id] + filtro_vagas)
        else:
            cursor.execute(
                '''
                SELECT v.id, v.titulo, v.status, 
                       COUNT(cand.id) as total_candidatos,
                       AVG(cand.score) as score_medio,
                       COUNT(CASE WHEN cand.score >= 80 THEN 1 END) as candidatos_excelentes,
                       COUNT(CASE WHEN cand.score >= 60 AND cand.score < 80 THEN 1 END) as candidatos_bons,
                       COUNT(CASE WHEN cand.score < 60 THEN 1 END) as candidatos_baixos,
                       v.data_criacao
                FROM vagas v
                LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
                WHERE v.empresa_id = ?
                GROUP BY v.id, v.titulo, v.status, v.data_criacao
                ORDER BY v.data_criacao DESC
            ''', (empresa_id, ))
        vagas_detalhes = cursor.fetchall()

        # Análise temporal (últimos 30 dias)
        data_limite = datetime.now() - timedelta(days=30)
        cursor.execute(
            '''
            SELECT DATE(cand.data_candidatura) as data, COUNT(cand.id) as candidaturas
            FROM candidaturas cand
            JOIN vagas v ON v.id = cand.vaga_id
            WHERE v.empresa_id = ? AND cand.data_candidatura >= ?
            GROUP BY DATE(cand.data_candidatura)
            ORDER BY data DESC
        ''', (empresa_id, data_limite))
        tendencia_candidaturas = cursor.fetchall()

        # Distribuição geográfica básica
        cursor.execute(
            '''
            SELECT SUBSTR(c.endereco_completo, -8, 2) as estado_provavel, COUNT(*) as total
            FROM candidatos c
            JOIN candidaturas cand ON c.id = cand.candidato_id
            JOIN vagas v ON v.id = cand.vaga_id
            WHERE v.empresa_id = ? AND c.endereco_completo IS NOT NULL
            GROUP BY estado_provavel
            ORDER BY total DESC
            LIMIT 10
        ''', (empresa_id, ))
        distribuicao_geografica = cursor.fetchall()

        conn.close()

        return {
            'empresa_nome': empresa_nome,
            'total_vagas': total_vagas,
            'total_candidaturas': total_candidaturas,
            'score_geral': round(score_geral, 1),
            'vaga_mais_candidatos': vaga_mais_candidatos,
            'vaga_maior_score': vaga_maior_score,
            'vagas_detalhes': vagas_detalhes,
            'tendencia_candidaturas': tendencia_candidaturas,
            'distribuicao_geografica': distribuicao_geografica,
            'data_geracao': datetime.now().strftime('%d/%m/%Y às %H:%M')
        }

    except Exception as e:
        conn.close()
        raise e


def gerar_html_relatorio(dados):
    """Gera HTML do relatório formatado profissionalmente"""

    # Calcular métricas adicionais
    vagas_ativas = sum(1 for v in dados['vagas_detalhes']
                       if v[2] == 'Ativa' or v[2] is None)
    vagas_concluidas = sum(1 for v in dados['vagas_detalhes']
                           if v[2] == 'Concluída')
    vagas_congeladas = sum(1 for v in dados['vagas_detalhes']
                           if v[2] == 'Congelada')

    media_candidatos_por_vaga = dados['total_candidaturas'] / dados[
        'total_vagas'] if dados['total_vagas'] > 0 else 0

    # Identificar vagas com baixo desempenho (menos de 3 candidatos ou score médio < 50)
    vagas_baixo_desempenho = [
        v for v in dados['vagas_detalhes'] if v[3] < 3 or (v[4] and v[4] < 50)
    ]

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Relatório Estratégico - {dados['empresa_nome']}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 3px solid #2563eb; padding-bottom: 20px; margin-bottom: 30px; }}
            .header h1 {{ color: #1e40af; margin: 0; font-size: 2.5em; }}
            .header p {{ color: #64748b; margin: 5px 0; }}
            .section {{ margin: 30px 0; }}
            .section h2 {{ color: #1e40af; border-left: 4px solid #3b82f6; padding-left: 15px; }}
            .section h3 {{ color: #374151; }}
            .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
            .metric-card {{ background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; padding: 20px; border-radius: 10px; text-align: center; }}
            .metric-card h3 {{ margin: 0 0 10px 0; font-size: 2.5em; }}
            .metric-card p {{ margin: 0; opacity: 0.9; }}
            .table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .table th, .table td {{ border: 1px solid #e5e7eb; padding: 12px; text-align: left; }}
            .table th {{ background-color: #f3f4f6; font-weight: 600; color: #374151; }}
            .table tr:nth-child(even) {{ background-color: #f9fafb; }}
            .status-ativa {{ background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-size: 0.875em; }}
            .status-concluida {{ background: #dbeafe; color: #1e40af; padding: 4px 8px; border-radius: 4px; font-size: 0.875em; }}
            .status-congelada {{ background: #fef3c7; color: #92400e; padding: 4px 8px; border-radius: 4px; font-size: 0.875em; }}
            .alert {{ padding: 15px; border-radius: 8px; margin: 15px 0; }}
            .alert-info {{ background: #eff6ff; border-left: 4px solid #3b82f6; color: #1e40af; }}
            .alert-warning {{ background: #fffbeb; border-left: 4px solid #f59e0b; color: #92400e; }}
            .alert-success {{ background: #f0fdf4; border-left: 4px solid #22c55e; color: #166534; }}
            .recommendations {{ background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .recommendations ul {{ margin: 10px 0; padding-left: 20px; }}
            .recommendations li {{ margin: 8px 0; }}
            .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #64748b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Relatório Estratégico de Recrutamento</h1>
                <p><strong>{dados['empresa_nome']}</strong></p>
                <p>Gerado em {dados['data_geracao']}</p>
            </div>

            <div class="section">
                <h2>📈 Resumo Operacional</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>{dados['total_vagas']}</h3>
                        <p>Vagas Criadas</p>
                    </div>
                    <div class="metric-card">
                        <h3>{dados['total_candidaturas']}</h3>
                        <p>Candidaturas Recebidas</p>
                    </div>
                    <div class="metric-card">
                        <h3>{dados['score_geral']}%</h3>
                        <p>Score Médio Geral</p>
                    </div>
                    <div class="metric-card">
                        <h3>{media_candidatos_por_vaga:.1f}</h3>
                        <p>Candidatos por Vaga</p>
                    </div>
                </div>

                <div class="alert alert-info">
                    <strong>🎯 Destaque de Engajamento:</strong> 
                    {dados['vaga_mais_candidatos'][0] if dados['vaga_mais_candidatos'] else 'Nenhuma candidatura ainda'} 
                    {f"({dados['vaga_mais_candidatos'][1]} candidatos)" if dados['vaga_mais_candidatos'] else ''}
                </div>

                <div class="alert alert-success">
                    <strong>⭐ Melhor Score Médio:</strong> 
                    {dados['vaga_maior_score'][0] if dados['vaga_maior_score'] else 'Nenhum score calculado ainda'} 
                    {f"({dados['vaga_maior_score'][1]:.1f}%)" if dados['vaga_maior_score'] else ''}
                </div>
            </div>

            <div class="section">
                <h2>📋 Status das Vagas</h2>
                <div class="metrics-grid">
                    <div class="metric-card" style="background: linear-gradient(135deg, #22c55e, #16a34a);">
                        <h3>{vagas_ativas}</h3>
                        <p>Vagas Ativas</p>
                    </div>
                    <div class="metric-card" style="background: linear-gradient(135deg, #3b82f6, #1d4ed8);">
                        <h3>{vagas_concluidas}</h3>
                        <p>Vagas Concluídas</p>
                    </div>
                    <div class="metric-card" style="background: linear-gradient(135deg, #f59e0b, #d97706);">
                        <h3>{vagas_congeladas}</h3>
                        <p>Vagas Congeladas</p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>📊 Detalhamento por Vaga</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Vaga</th>
                            <th>Status</th>
                            <th>Candidatos</th>
                            <th>Score Médio</th>
                            <th>Excelentes (80%+)</th>
                            <th>Bons (60-79%)</th>
                            <th>Baixo (<60%)</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    for vaga in dados['vagas_detalhes']:
        status_class = {
            'Ativa': 'status-ativa',
            'Concluída': 'status-concluida',
            'Congelada': 'status-congelada'
        }.get(vaga[2] or 'Ativa', 'status-ativa')

        score_medio = f"{vaga[4]:.1f}%" if vaga[4] else "N/A"

        html += f"""
                        <tr>
                            <td><strong>{vaga[1]}</strong></td>
                            <td><span class="{status_class}">{vaga[2] or 'Ativa'}</span></td>
                            <td>{vaga[3]}</td>
                            <td>{score_medio}</td>
                            <td>{vaga[5]}</td>
                            <td>{vaga[6]}</td>
                            <td>{vaga[7]}</td>
                        </tr>
        """

    html += """
                    </tbody>
                </table>
            </div>
    """

    # Análise de vagas com baixo desempenho
    if vagas_baixo_desempenho:
        html += f"""
            <div class="section">
                <h2>⚠️ Vagas com Baixo Desempenho</h2>
                <div class="alert alert-warning">
                    <strong>Atenção:</strong> {len(vagas_baixo_desempenho)} vaga(s) precisam de revisão:
                    <ul>
        """
        for vaga in vagas_baixo_desempenho[:
                                           5]:  # Mostrar apenas as 5 primeiras
            motivo = []
            if vaga[3] < 3:
                motivo.append("poucos candidatos")
            if vaga[4] and vaga[4] < 50:
                motivo.append("score médio baixo")
            html += f"<li><strong>{vaga[1]}</strong> - {', '.join(motivo)}</li>"

        html += """
                    </ul>
                </div>
            </div>
        """

    # Conclusão estratégica e recomendações
    html += f"""
            <div class="section">
                <h2>🎯 Conclusão Estratégica</h2>
                <div class="recommendations">
                    <h3>💡 Oportunidades Identificadas:</h3>
                    <ul>
    """

    if dados['score_geral'] >= 70:
        html += "<li>✅ <strong>Excelente qualidade dos candidatos</strong> - Score médio acima de 70%</li>"
    elif dados['score_geral'] >= 50:
        html += "<li>⚡ <strong>Boa qualidade dos candidatos</strong> - Há potencial para melhorar os requisitos das vagas</li>"
    else:
        html += "<li>🔧 <strong>Necessária revisão dos requisitos</strong> - Score médio baixo indica desalinhamento</li>"

    if media_candidatos_por_vaga >= 5:
        html += "<li>🎯 <strong>Alto engajamento</strong> - Média excelente de candidatos por vaga</li>"
    elif media_candidatos_por_vaga >= 3:
        html += "<li>📈 <strong>Engajamento moderado</strong> - Considere estratégias para aumentar a atração</li>"
    else:
        html += "<li>📢 <strong>Baixo engajamento</strong> - Revisar estratégias de divulgação das vagas</li>"

    html += """
                    </ul>

                    <h3>🔧 Recomendações Práticas:</h3>
                    <ul>
                        <li><strong>Otimização de Requisitos:</strong> Revisar descrições das vagas com baixo score para torná-las mais atrativas</li>
                        <li><strong>Estratégia de Divulgação:</strong> Focar nos canais que trouxeram candidatos de maior qualidade</li>
                        <li><strong>Processo Seletivo:</strong> Priorizar candidatos com score acima de 70% para entrevistas</li>
                        <li><strong>Feedback Contínuo:</strong> Implementar ciclos de melhoria baseados nos dados de performance</li>
                    </ul>

                    <h3>📊 Melhorias no Funil de Contratação:</h3>
                    <ul>
                        <li><strong>Pré-triagem Automatizada:</strong> Usar o score como filtro inicial</li>
                        <li><strong>Comunicação Proativa:</strong> Manter candidatos de alto score engajados durante o processo</li>
                        <li><strong>Análise de Concorrência:</strong> Pesquisar salários e benefícios do mercado</li>
                        <li><strong>Experiência do Candidato:</strong> Simplificar o processo de candidatura</li>
                    </ul>
                </div>
            </div>

            <div class="section">
                <div class="alert alert-info">
                    <strong>📌 Lembrete Importante:</strong><br>
                    Este relatório foi gerado com base em dados reais da sua empresa. Para uma visão mais precisa e estratégica, mantenha seus registros atualizados e considere implementar métricas adicionais como tempo de preenchimento de vagas e taxa de conversão.
                </div>
            </div>

            <div class="footer">
                <p>Relatório gerado automaticamente pelo Sistema de Recrutamento</p>
                <p>Para dúvidas ou sugestões, entre em contato com o suporte técnico</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html


def gerar_dados_graficos(empresa_id, filtro_vagas=None):
    """Gera dados formatados para gráficos"""
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    # Dados para gráfico de pizza - Distribuição de candidatos por vaga
    if filtro_vagas:
        cursor.execute(
            '''
            SELECT v.titulo, COUNT(cand.id) as total
            FROM vagas v
            LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
            WHERE v.empresa_id = ? AND v.id IN ({})
            GROUP BY v.id, v.titulo
            ORDER BY total DESC
        '''.format(','.join('?' * len(filtro_vagas))),
            [empresa_id] + filtro_vagas)
    else:
        cursor.execute(
            '''
            SELECT v.titulo, COUNT(cand.id) as total
            FROM vagas v
            LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
            WHERE v.empresa_id = ?
            GROUP BY v.id, v.titulo
            ORDER BY total DESC
        ''', (empresa_id, ))

    pizza_data = cursor.fetchall()

    # Dados para gráfico de barras - Score médio por vaga
    if filtro_vagas:
        cursor.execute(
            '''
            SELECT v.titulo, AVG(cand.score) as score_medio
            FROM vagas v
            LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
            WHERE v.empresa_id = ? AND v.id IN ({}) AND cand.score IS NOT NULL
            GROUP BY v.id, v.titulo
            ORDER BY score_medio DESC
        '''.format(','.join('?' * len(filtro_vagas))),
            [empresa_id] + filtro_vagas)
    else:
        cursor.execute(
            '''
            SELECT v.titulo, AVG(cand.score) as score_medio
            FROM vagas v
            LEFT JOIN candidaturas cand ON cand.vaga_id = v.id
            WHERE v.empresa_id = ? AND cand.score IS NOT NULL
            GROUP BY v.id, v.titulo
            ORDER BY score_medio DESC
        ''', (empresa_id, ))

    barras_data = cursor.fetchall()

    # Dados para linha do tempo - Candidaturas por dia (últimos 30 dias)
    data_limite = datetime.now() - timedelta(days=30)
    cursor.execute(
        '''
        SELECT DATE(cand.data_candidatura) as data, COUNT(cand.id) as total
        FROM candidaturas cand
        JOIN vagas v ON v.id = cand.vaga_id
        WHERE v.empresa_id = ? AND cand.data_candidatura >= ?
        GROUP BY DATE(cand.data_candidatura)
        ORDER BY data ASC
    ''', (empresa_id, data_limite))

    linha_data = cursor.fetchall()

    conn.close()

    return {
        'pizza': {
            'labels': [item[0] for item in pizza_data],
            'data': [item[1] for item in pizza_data]
        },
        'barras': {
            'labels': [item[0] for item in barras_data],
            'data':
            [round(item[1], 1) if item[1] else 0 for item in barras_data]
        },
        'linha': {
            'labels': [item[0] for item in linha_data],
            'data': [item[1] for item in linha_data]
        }
    }
