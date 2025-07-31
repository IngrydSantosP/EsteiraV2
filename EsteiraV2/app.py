import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from utils.helpers import inicializar_banco, calcular_distancia_endereco
from utils.resume_extractor import processar_upload_curriculo, finalizar_processamento_curriculo
from avaliador import criar_avaliador
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import io
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'chave-secreta-mvp-recrutamento-2024'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'

# Configurações do ambiente
MODO_IA = os.getenv('MODO_IA', 'local')
TOP_JOBS = int(os.getenv('TOP_JOBS', '3'))


def gerar_feedback_ia_vaga(total, alta_compatibilidade, media_compatibilidade,
                           baixa_compatibilidade):
    """Gera feedback inteligente sobre os candidatos da vaga"""
    if total == 0:
        return {
            'texto': 'Nenhum candidato ainda',
            'cor': 'text-gray-500',
            'icone': '📋'
        }

    if alta_compatibilidade > 0:
        percentual_alto = (alta_compatibilidade / total) * 100
        if percentual_alto >= 50:
            return {
                'texto':
                f'{alta_compatibilidade} candidato(s) com perfil excelente (80%+)',
                'cor': 'text-green-600',
                'icone': '🎯'
            }
        else:
            return {
                'texto':
                f'{alta_compatibilidade} candidato(s) muito compatível(eis)',
                'cor': 'text-green-500',
                'icone': '✅'
            }

    if media_compatibilidade > 0:
        return {
            'texto':
            f'{media_compatibilidade} candidato(s) com bom potencial (60-79%)',
            'cor': 'text-yellow-600',
            'icone': '⚡'
        }

    return {
        'texto': f'{total} candidato(s) - revisar requisitos da vaga',
        'cor': 'text-orange-500',
        'icone': '⚠️'
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login_empresa', methods=['GET', 'POST'])
def login_empresa():
    if request.method == 'POST':
        cnpj = request.form.get('cnpj', '').strip()
        senha = request.form.get('senha', '')

        if not cnpj or not senha:
            flash('Por favor, preencha todos os campos', 'error')
            return render_template('login_empresa.html')

        cnpj_limpo = ''.join(filter(str.isdigit, cnpj))

        if len(cnpj_limpo) != 14:
            flash('CNPJ deve ter exatamente 14 dígitos', 'error')
            return render_template('login_empresa.html')

        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()

        try:
            cursor.execute(
                'SELECT id, senha_hash FROM empresas WHERE cnpj = ?',
                (cnpj_limpo, ))
            empresa = cursor.fetchone()

            if empresa and check_password_hash(empresa[1], senha):
                session.clear()
                session['empresa_id'] = empresa[0]
                session['tipo_usuario'] = 'empresa'
                session.permanent = True
                return redirect(url_for('dashboard_empresa'))
            else:
                flash('CNPJ ou senha incorretos', 'error')
        except Exception as e:
            print(f"Erro no login: {e}")
            flash('Erro interno do sistema. Tente novamente.', 'error')
        finally:
            conn.close()

    return render_template('login_empresa.html')


@app.route('/cadastro_empresa', methods=['GET', 'POST'])
def cadastro_empresa():
    if request.method == 'POST':
        cnpj = request.form.get('cnpj', '').strip()
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')

        if not all([cnpj, nome, email, senha]):
            flash('Por favor, preencha todos os campos', 'error')
            return render_template('cadastro_empresa.html')

        cnpj_limpo = ''.join(filter(str.isdigit, cnpj))

        if len(cnpj_limpo) != 14:
            flash('CNPJ deve ter exatamente 14 dígitos', 'error')
            return render_template('cadastro_empresa.html')

        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres', 'error')
            return render_template('cadastro_empresa.html')

        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id FROM empresas WHERE cnpj = ?',
                           (cnpj_limpo, ))
            if cursor.fetchone():
                flash('CNPJ já está cadastrado no sistema', 'error')
                return render_template('cadastro_empresa.html')

            cursor.execute('SELECT id FROM empresas WHERE email = ?',
                           (email, ))
            if cursor.fetchone():
                flash('Email já está cadastrado no sistema', 'error')
                return render_template('cadastro_empresa.html')

            cursor.execute(
                'INSERT INTO empresas (cnpj, nome, email, senha_hash) VALUES (?, ?, ?, ?)',
                (cnpj_limpo, nome, email, generate_password_hash(senha)))
            conn.commit()
            flash('Empresa cadastrada com sucesso!', 'success')
            return redirect(url_for('login_empresa'))
        except Exception as e:
            flash('Erro ao cadastrar empresa. Verifique os dados.', 'error')
        finally:
            conn.close()

    return render_template('cadastro_empresa.html')


@app.route('/login_candidato', methods=['GET', 'POST'])
@app.route('/index.html', methods=['GET', 'POST'])
def login_candidato():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()

        cursor.execute('SELECT id, senha_hash FROM candidatos WHERE email = ?',
                       (email, ))
        candidato = cursor.fetchone()
        conn.close()

        if candidato and check_password_hash(candidato[1], senha):
            session['candidato_id'] = candidato[0]
            session['tipo_usuario'] = 'candidato'
            return redirect(url_for('dashboard_candidato'))
        else:
            flash('Email ou senha incorretos', 'error')

    return render_template('login_candidato.html')


@app.route('/cadastro_candidato', methods=['GET', 'POST'])
def cadastro_candidato():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        telefone = request.form['telefone']
        linkedin = request.form['linkedin']
        endereco_completo = request.form['endereco_completo']
        pretensao_salarial = float(request.form['pretensao_salarial'])

        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()

        try:
            cursor.execute(
                '''INSERT INTO candidatos (nome, email, senha_hash, telefone, linkedin, endereco_completo, pretensao_salarial)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (nome, email, generate_password_hash(senha), telefone,
                 linkedin, endereco_completo, pretensao_salarial))
            conn.commit()
            flash('Candidato cadastrado com sucesso!', 'success')
            return redirect(url_for('login_candidato'))
        except sqlite3.IntegrityError:
            flash('Email já cadastrado', 'error')
        finally:
            conn.close()

    return render_template('cadastro_candidato.html')


@app.route('/dashboard_empresa')
def dashboard_empresa():
    if 'empresa_id' not in session or session.get('tipo_usuario') != 'empresa':
        flash('Faça login para acessar esta página', 'error')
        return redirect(url_for('login_empresa'))

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    cursor.execute(
        '''SELECT v.*, 
               COUNT(ca.id) as total_candidatos,
               COUNT(CASE WHEN ca.score >= 80 THEN 1 END) as candidatos_80_plus,
               COUNT(CASE WHEN ca.score >= 60 AND ca.score < 80 THEN 1 END) as candidatos_60_79,
               COUNT(CASE WHEN ca.score < 60 THEN 1 END) as candidatos_abaixo_60,
               c.nome as candidato_contratado_nome,
               ca_contratado.posicao as candidato_contratado_posicao
           FROM vagas v
           LEFT JOIN candidaturas ca ON v.id = ca.vaga_id
           LEFT JOIN candidatos c ON v.candidato_selecionado_id = c.id
           LEFT JOIN candidaturas ca_contratado ON v.candidato_selecionado_id = ca_contratado.candidato_id AND v.id = ca_contratado.vaga_id
           WHERE v.empresa_id = ?
           GROUP BY v.id
           ORDER BY v.data_criacao DESC''', (session['empresa_id'], ))

    vagas_com_stats = cursor.fetchall()
    conn.close()

    vagas_processadas = []
    for vaga in vagas_com_stats:
        # Verificar se data_criacao é timestamp ou string
        if isinstance(vaga[6], str):
            # Se for string, tentar converter para datetime
            try:
                data_criacao = datetime.strptime(
                    vaga[6], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
            except:
                data_criacao = vaga[6][:10] if vaga[
                    6] else 'N/A'  # Pegar apenas a data
        else:
            # Se for timestamp
            data_criacao = datetime.utcfromtimestamp(
                vaga[6]).strftime('%d/%m/%Y') if vaga[6] else 'N/A'

        vaga_dict = {
            'id':
            vaga[0],
            'empresa_id':
            vaga[1],
            'titulo':
            vaga[2],
            'descricao':
            vaga[3],
            'requisitos':
            vaga[4],
            'salario_oferecido':
            vaga[5],
            'diferenciais':
            vaga[11] if len(vaga) > 11 and vaga[11] else '',
            'tipo_vaga':
            vaga[7] if vaga[7] else 'Presencial',
            'endereco_vaga':
            vaga[8] if vaga[8] else '',
            'status':
            vaga[9] if vaga[9] else 'Ativa',
            'candidato_selecionado_id':
            vaga[10],
            'data_criacao':
            data_criacao,
            'total_candidatos':
            vaga[12] if len(vaga) > 12 else 0,
            'candidatos_80_plus':
            vaga[13] if len(vaga) > 13 else 0,
            'candidatos_60_79':
            vaga[14] if len(vaga) > 14 else 0,
            'candidatos_abaixo_60':
            vaga[15] if len(vaga) > 15 else 0,
            'candidato_contratado': {
                'nome': vaga[16] if len(vaga) > 16 and vaga[16] else None,
                'posicao': vaga[17] if len(vaga) > 17 and vaga[17] else None
            } if vaga[9] == 'Concluída' else None,
            'data_contratacao':
            data_criacao if vaga[9] == 'Concluída' else None,
            'feedback_ia':
            gerar_feedback_ia_vaga(vaga[12] if len(vaga) > 12 else 0,
                                   vaga[13] if len(vaga) > 13 else 0,
                                   vaga[14] if len(vaga) > 14 else 0,
                                   vaga[15] if len(vaga) > 15 else 0)
        }
        vagas_processadas.append(vaga_dict)

    return render_template('dashboard_empresa.html', vagas=vagas_processadas)


@app.route('/criar_vaga', methods=['GET', 'POST'])
def criar_vaga():
    if 'empresa_id' not in session:
        return redirect(url_for('login_empresa'))

    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        requisitos = request.form['requisitos']
        diferenciais = request.form.get('diferenciais', '')
        salario_oferecido = float(request.form['salario_oferecido'])
        tipo_vaga = request.form['tipo_vaga']
        endereco_vaga = request.form.get('endereco_vaga', '')

        if tipo_vaga in ['Presencial', 'Híbrida'] and not endereco_vaga:
            flash('Endereço é obrigatório para vagas presenciais ou híbridas',
                  'error')
            return render_template('criar_vaga.html')

        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()

        cursor.execute(
            '''INSERT INTO vagas (empresa_id, titulo, descricao, requisitos, diferenciais, salario_oferecido, tipo_vaga, endereco_vaga)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (session['empresa_id'], titulo, descricao, requisitos,
             diferenciais, salario_oferecido, tipo_vaga, endereco_vaga))
        conn.commit()
        conn.close()

        flash('Vaga criada com sucesso!', 'success')
        return redirect(url_for('dashboard_empresa'))

    return render_template('criar_vaga.html')


@app.route('/candidatos_vaga/<int:vaga_id>')
def candidatos_vaga(vaga_id):
    if 'empresa_id' not in session:
        return redirect(url_for('login_empresa'))

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    cursor.execute(
        '''SELECT c.nome, c.email, c.telefone, c.linkedin, ca.score, ca.posicao, c.id, c.endereco_completo
           FROM candidaturas ca
           JOIN candidatos c ON ca.candidato_id = c.id
           WHERE ca.vaga_id = ?
           ORDER BY ca.score DESC''', (vaga_id, ))

    candidatos = cursor.fetchall()

    cursor.execute('SELECT titulo FROM vagas WHERE id = ?', (vaga_id, ))
    vaga = cursor.fetchone()
    conn.close()

    return render_template('candidatos_vaga.html',
                           candidatos=candidatos,
                           vaga_titulo=vaga[0] if vaga else '',
                           vaga_id=vaga_id)


@app.route('/dashboard_candidato')
def dashboard_candidato():
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    cursor.execute('SELECT texto_curriculo FROM candidatos WHERE id = ?',
                   (session['candidato_id'], ))
    candidato = cursor.fetchone()

    if not candidato or not candidato[0]:
        conn.close()
        return redirect(url_for('upload_curriculo'))

    cursor.execute(
        '''SELECT v.id, v.titulo, e.nome as empresa_nome, v.salario_oferecido, ca.score, ca.posicao
           FROM candidaturas ca
           JOIN vagas v ON ca.vaga_id = v.id
           JOIN empresas e ON v.empresa_id = e.id
           WHERE ca.candidato_id = ?
           ORDER BY ca.posicao ASC''', (session['candidato_id'], ))

    vagas_candidatadas_raw = cursor.fetchall()

    # Processar candidaturas garantindo tipos corretos
    vagas_candidatadas = []
    for vaga in vagas_candidatadas_raw:
        vaga_processada = (
            int(vaga[0]),  # id
            vaga[1],  # titulo
            vaga[2],  # empresa_nome
            float(vaga[3]) if vaga[3] else 0.0,  # salario_oferecido
            float(vaga[4]) if vaga[4] else 0.0,  # score
            int(vaga[5]) if vaga[5] else 0  # posicao
        )
        vagas_candidatadas.append(vaga_processada)

    cursor.execute(
        '''SELECT v.id, v.titulo, v.descricao, v.requisitos, v.salario_oferecido, e.nome as empresa_nome, v.diferenciais, v.tipo_vaga, v.endereco_vaga
           FROM vagas v
           JOIN empresas e ON v.empresa_id = e.id
           WHERE v.id NOT IN (
               SELECT vaga_id FROM candidaturas WHERE candidato_id = ?
           ) AND (v.status = 'Ativa' OR v.status IS NULL)''',
        (session['candidato_id'], ))

    vagas_disponiveis = cursor.fetchall()

    cursor.execute(
        'SELECT pretensao_salarial, texto_curriculo, endereco_completo FROM candidatos WHERE id = ?',
        (session['candidato_id'], ))
    candidato_info = cursor.fetchone()

    conn.close()

    avaliador = criar_avaliador(MODO_IA)
    vagas_com_score = []
    for vaga in vagas_disponiveis:
        score = avaliador.calcular_score(
            candidato_info[1], vaga[3], candidato_info[0], vaga[4],
            vaga[6] if vaga[6] else '',
            candidato_info[2] if len(candidato_info) > 2 else None, vaga[8],
            vaga[7])
        # Garantir que todos os valores numéricos sejam convertidos para tipos apropriados
        vaga_processada = (
            int(vaga[0]),  # id
            vaga[1],  # titulo
            vaga[2],  # descricao
            vaga[3],  # requisitos
            float(vaga[4]) if vaga[4] else 0.0,  # salario_oferecido
            vaga[5],  # empresa_nome
            vaga[6] if vaga[6] else '',  # diferenciais
            vaga[7] if vaga[7] else 'Presencial',  # tipo_vaga
            vaga[8] if vaga[8] else '',  # endereco_vaga
            float(score)  # score calculado
        )
        vagas_com_score.append(vaga_processada)

    vagas_com_score.sort(key=lambda x: x[9],
                         reverse=True)  # Ordenar pelo score (índice 9)
    top_vagas = vagas_com_score[:TOP_JOBS]

    return render_template('dashboard_candidato.html',
                           vagas_recomendadas=top_vagas,
                           vagas_candidatadas=vagas_candidatadas)


@app.route('/upload_curriculo', methods=['GET', 'POST'])
def upload_curriculo():
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))

    if request.method == 'POST':
        resultado = processar_upload_curriculo(request,
                                               session['candidato_id'])

        # Processar mensagens corretamente
        for mensagem in resultado['mensagens']:
            if isinstance(mensagem, dict) and 'texto' in mensagem:
                flash(mensagem['texto'], mensagem.get('tipo', 'info'))
            else:
                flash(str(mensagem), 'info')

        if resultado['sucesso']:
            return render_template(
                'processar_curriculo.html',
                dados_extraidos=resultado['dados_extraidos'])
        else:
            return redirect(request.url)

    return render_template('upload_curriculo.html')


@app.route('/finalizar_curriculo', methods=['POST'])
def finalizar_curriculo():
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))

    resultado = finalizar_processamento_curriculo(request,
                                                  session['candidato_id'])

    # Processar mensagens corretamente
    for mensagem in resultado['mensagens']:
        if isinstance(mensagem, dict) and 'texto' in mensagem:
            flash(mensagem['texto'], mensagem.get('tipo', 'info'))
        else:
            flash(str(mensagem), 'info')

    if resultado['sucesso']:
        return redirect(url_for('dashboard_candidato'))
    else:
        return redirect(url_for('upload_curriculo'))


@app.route('/candidatar/<int:vaga_id>')
def candidatar(vaga_id):
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))

    from utils.helpers import processar_candidatura
    resultado = processar_candidatura(session['candidato_id'], vaga_id,
                                      MODO_IA)

    # Processar mensagens para garantir que estão em formato correto
    for mensagem in resultado['mensagens']:
        if isinstance(mensagem, dict) and 'texto' in mensagem:
            flash(mensagem['texto'], mensagem.get('tipo', 'info'))
        else:
            flash(str(mensagem), 'info')

    return redirect(url_for('dashboard_candidato'))


@app.route('/api/candidatos_vaga/<int:vaga_id>')
def api_candidatos_vaga(vaga_id):
    if 'empresa_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    cursor.execute(
        '''SELECT c.id, c.nome, ca.score
           FROM candidaturas ca
           JOIN candidatos c ON ca.candidato_id = c.id
           JOIN vagas v ON ca.vaga_id = v.id
           WHERE ca.vaga_id = ? AND v.empresa_id = ?
           ORDER BY ca.score DESC''', (vaga_id, session['empresa_id']))

    candidatos = cursor.fetchall()
    conn.close()

    return jsonify([{
        'id': c[0],
        'nome': c[1],
        'score': round(c[2], 1)
    } for c in candidatos])


@app.route('/encerrar_vaga', methods=['POST'])
def encerrar_vaga():
    if 'empresa_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401

    data = request.get_json()
    vaga_id = data.get('vaga_id')
    acao = data.get('acao')
    candidato_id = data.get('candidato_id')
    mensagem_personalizada = data.get('mensagem_personalizada', '')

    if not vaga_id or not acao:
        return jsonify({'error': 'Dados incompletos'}), 400

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    # Verificar se a vaga pertence à empresa
    cursor.execute('SELECT id FROM vagas WHERE id = ? AND empresa_id = ?',
                   (vaga_id, session['empresa_id']))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Vaga não encontrada'}), 404

    try:
        if acao == 'contratar':
            if not candidato_id:
                return jsonify({'error': 'Candidato não selecionado'}), 400

            # Verificar se o candidato se candidatou à vaga
            cursor.execute(
                'SELECT id FROM candidaturas WHERE candidato_id = ? AND vaga_id = ?',
                (candidato_id, vaga_id))
            if not cursor.fetchone():
                return jsonify(
                    {'error': 'Candidato não se candidatou a esta vaga'}), 400

            # Marcar vaga como Concluída e definir candidato selecionado
            cursor.execute(
                'UPDATE vagas SET status = "Concluída", candidato_selecionado_id = ? WHERE id = ?',
                (candidato_id, vaga_id))

            # Criar notificação para o candidato
            if not mensagem_personalizada:
                mensagem_personalizada = "Parabéns! Você foi selecionado para esta vaga."

            cursor.execute(
                '''INSERT INTO notificacoes (candidato_id, empresa_id, vaga_id, mensagem)
                   VALUES (?, ?, ?, ?)''',
                (candidato_id, session['empresa_id'], vaga_id,
                 mensagem_personalizada))

            # Buscar informações para log
            cursor.execute(
                '''SELECT c.nome, c.email, v.titulo
                   FROM candidatos c, vagas v
                   WHERE c.id = ? AND v.id = ?''', (candidato_id, vaga_id))
            candidato_info = cursor.fetchone()

            if candidato_info:
                print(
                    f"Candidato contratado: {candidato_info[0]} para a vaga {candidato_info[2]}. Notificação enviada."
                )

            response = {
                'success': True,
                'message': 'Candidato contratado com sucesso!'
            }

        elif acao == 'congelar':
            cursor.execute(
                'UPDATE vagas SET status = "Congelada" WHERE id = ?',
                (vaga_id, ))
            response = {
                'success': True,
                'message': 'Vaga congelada com sucesso!'
            }

        elif acao == 'excluir':
            # Excluir candidaturas primeiro
            cursor.execute('DELETE FROM candidaturas WHERE vaga_id = ?',
                           (vaga_id, ))
            cursor.execute('DELETE FROM vagas WHERE id = ?', (vaga_id, ))
            response = {
                'success': True,
                'message': 'Vaga excluída com sucesso!'
            }

        elif acao == 'reativar':
            cursor.execute('UPDATE vagas SET status = "Ativa" WHERE id = ?',
                           (vaga_id, ))
            response = {
                'success': True,
                'message': 'Vaga reativada com sucesso!'
            }

        else:
            return jsonify({'error': 'Ação inválida'}), 400

        conn.commit()
        return jsonify(response)

    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Erro ao processar ação: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/editar_perfil_candidato', methods=['GET', 'POST'])
def editar_perfil_candidato():
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        telefone = request.form['telefone']
        linkedin = request.form['linkedin']
        pretensao_salarial = float(request.form['pretensao_salarial'])
        experiencia = request.form['experiencia']
        competencias = request.form['competencias']
        resumo_profissional = request.form['resumo_profissional']

        cursor.execute(
            '''
            UPDATE candidatos 
            SET nome = ?, telefone = ?, linkedin = ?, pretensao_salarial = ?,
                experiencia = ?, competencias = ?, resumo_profissional = ?
            WHERE id = ?
        ''', (nome, telefone, linkedin, pretensao_salarial, experiencia,
              competencias, resumo_profissional, session['candidato_id']))

        conn.commit()
        conn.close()

        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('dashboard_candidato'))

    cursor.execute(
        '''
        SELECT nome, telefone, linkedin, pretensao_salarial, 
               experiencia, competencias, resumo_profissional
        FROM candidatos WHERE id = ?
    ''', (session['candidato_id'], ))

    candidato = cursor.fetchone()
    conn.close()

    return render_template('editar_perfil_candidato.html', candidato=candidato)


@app.route('/editar_vaga/<int:vaga_id>', methods=['GET', 'POST'])
def editar_vaga(vaga_id):
    if 'empresa_id' not in session:
        return redirect(url_for('login_empresa'))

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    # Verificar se a vaga pertence à empresa
    cursor.execute('SELECT * FROM vagas WHERE id = ? AND empresa_id = ?',
                   (vaga_id, session['empresa_id']))
    vaga = cursor.fetchone()

    if not vaga:
        flash('Vaga não encontrada', 'error')
        return redirect(url_for('dashboard_empresa'))

    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        requisitos = request.form['requisitos']
        salario_oferecido = float(request.form['salario_oferecido'])
        tipo_vaga = request.form['tipo_vaga']
        endereco_vaga = request.form['endereco_vaga']

        cursor.execute(
            '''
            UPDATE vagas 
            SET titulo = ?, descricao = ?, requisitos = ?, salario_oferecido = ?, tipo_vaga = ?, endereco_vaga = ?
            WHERE id = ?
        ''', (titulo, descricao, requisitos, salario_oferecido, tipo_vaga,
              endereco_vaga, vaga_id))

        conn.commit()
        conn.close()

        flash('Vaga atualizada com sucesso!', 'success')
        return redirect(url_for('dashboard_empresa'))

    cursor.execute('SELECT * FROM vagas WHERE id = ?', (vaga_id, ))
    vaga = cursor.fetchone()
    conn.close()
    return render_template('editar_vaga.html', vaga=vaga)


@app.route('/vaga/<int:vaga_id>')
def detalhes_vaga(vaga_id):
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    # Buscar dados da vaga e empresa
    cursor.execute(
        '''
        SELECT v.*, e.nome as empresa_nome
        FROM vagas v
        JOIN empresas e ON v.empresa_id = e.id
        WHERE v.id = ? AND v.status = 'Ativa'
    ''', (vaga_id, ))

    vaga_data = cursor.fetchone()

    if not vaga_data:
        flash('Vaga não encontrada ou não está mais ativa', 'error')
        return redirect(url_for('dashboard_candidato'))

    # Verificar se já se candidatou
    cursor.execute(
        '''
        SELECT id, score FROM candidaturas 
        WHERE candidato_id = ? AND vaga_id = ?
    ''', (session['candidato_id'], vaga_id))
    candidatura = cursor.fetchone()

    # Buscar dados do candidato para calcular feedback
    cursor.execute(
        '''
        SELECT texto_curriculo, endereco_completo, pretensao_salarial
        FROM candidatos WHERE id = ?
    ''', (session['candidato_id'], ))
    candidato_data = cursor.fetchone()

    conn.close()

    # Estruturar dados da vaga
    vaga = {
        'id':
        vaga_data[0],
        'titulo':
        vaga_data[2],
        'descricao':
        vaga_data[3],
        'requisitos':
        vaga_data[4],
        'salario_oferecido':
        vaga_data[5],
        'tipo_vaga':
        vaga_data[7] or 'Presencial',
        'endereco_vaga':
        vaga_data[8],
        'diferenciais':
        vaga_data[11],
        'data_criacao':
        datetime.strptime(vaga_data[6], '%Y-%m-%d %H:%M:%S')
        if vaga_data[6] else None
    }

    empresa = {'nome': vaga_data[12]}

    # Calcular score e feedback se não candidatado ainda
    score = None
    feedback_performance = None

    if candidato_data:
        from avaliador import criar_avaliador
        avaliador = criar_avaliador(MODO_IA)

        score = candidatura[1] if candidatura else avaliador.calcular_score(
            candidato_data[0], vaga['requisitos'], candidato_data[2],
            vaga['salario_oferecido'], vaga['diferenciais'], candidato_data[1],
            vaga['endereco_vaga'], vaga['tipo_vaga'])

        # Gerar feedback de performance
        feedback_performance = {
            'requisitos_atendidos':
            len([
                r for r in avaliador._extrair_palavras_chave(
                    vaga['requisitos'].lower())
                if r in candidato_data[0].lower()
            ]),
            'total_requisitos':
            len(avaliador._extrair_palavras_chave(vaga['requisitos'].lower())),
            'diferenciais_atendidos':
            len([
                d for d in avaliador._extrair_palavras_chave(
                    vaga['diferenciais'].lower(
                    ) if vaga['diferenciais'] else '')
                if d in candidato_data[0].lower()
            ]) if vaga['diferenciais'] else 0,
            'bonus_localizacao':
            bool(vaga['tipo_vaga'] in ['Presencial', 'Híbrida']
                 and candidato_data[1] and vaga['endereco_vaga'])
        }

    return render_template('detalhes_vaga.html',
                           vaga=vaga,
                           empresa=empresa,
                           score=score,
                           feedback_performance=feedback_performance,
                           ja_candidatado=bool(candidatura))


@app.route('/minhas_candidaturas')
def minhas_candidaturas():
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    cursor.execute(
        '''
        SELECT v.id, v.titulo, e.nome as empresa_nome, v.salario_oferecido,
               ca.score, ca.posicao, ca.data_candidatura
        FROM candidaturas ca
        JOIN vagas v ON ca.vaga_id = v.id
        JOIN empresas e ON v.empresa_id = e.id
        WHERE ca.candidato_id = ?
        ORDER BY ca.data_candidatura DESC
    ''', (session['candidato_id'], ))

    candidaturas = cursor.fetchall()
    conn.close()

    return render_template('minhas_candidaturas.html',
                           candidaturas=candidaturas)


@app.route('/baixar_curriculo/<int:candidato_id>')
def baixar_curriculo(candidato_id):
    if 'empresa_id' not in session:
        return redirect(url_for('login_empresa'))

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    # Verificar se a empresa tem acesso ao candidato (através de candidatura)
    cursor.execute(
        '''
        SELECT COUNT(*) FROM candidaturas ca
        JOIN vagas v ON ca.vaga_id = v.id
        WHERE ca.candidato_id = ? AND v.empresa_id = ?
    ''', (candidato_id, session['empresa_id']))

    if cursor.fetchone()[0] == 0:
        flash('Acesso negado ao currículo', 'error')
        return redirect(url_for('dashboard_empresa'))

    # Buscar dados do candidato
    cursor.execute(
        '''
        SELECT nome, caminho_curriculo
        FROM candidatos WHERE id = ?
    ''', (candidato_id, ))

    candidato = cursor.fetchone()
    conn.close()

    if not candidato:
        flash('Candidato não encontrado', 'error')
        return redirect(url_for('dashboard_empresa'))

    # Verificar se o arquivo do currículo existe
    if not candidato[1]:
        flash('Currículo não disponível para download', 'error')
        return redirect(url_for('dashboard_empresa'))

    caminho_curriculo = os.path.join('uploads', candidato[1])

    if not os.path.exists(caminho_curriculo):
        flash('Arquivo do currículo não encontrado', 'error')
        return redirect(url_for('dashboard_empresa'))

    nome_download = f"curriculo_{candidato[0].replace(' ', '_')}.pdf"

    return send_file(caminho_curriculo,
                     as_attachment=True,
                     download_name=nome_download,
                     mimetype='application/pdf')


@app.route('/empresa/relatorio')
def relatorio_empresa():
    if 'empresa_id' not in session:
        flash('Faça login para acessar essa página', 'error')
        return redirect(url_for('login_empresa'))

    empresa_id = session['empresa_id']

    # Buscar vagas da empresa para o filtro
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, titulo FROM vagas WHERE empresa_id = ? ORDER BY titulo',
        (empresa_id, ))
    vagas_disponiveis = cursor.fetchall()
    conn.close()

    from utils.relatorio_generator import gerar_dados_graficos
    dados_graficos = gerar_dados_graficos(empresa_id)

    return render_template('relatorio_empresa.html',
                           vagas_disponiveis=vagas_disponiveis,
                           dados_graficos=json.dumps(dados_graficos))


@app.route('/empresa/relatorio/completo')
def relatorio_completo():
    if 'empresa_id' not in session:
        return redirect(url_for('login_empresa'))

    empresa_id = session['empresa_id']
    filtro_vagas = request.args.getlist('vagas')

    # Se foi especificado filtro, converter para inteiros
    if filtro_vagas:
        try:
            filtro_vagas = [int(v) for v in filtro_vagas]
        except ValueError:
            filtro_vagas = None
    else:
        filtro_vagas = None

    from utils.relatorio_generator import gerar_relatorio_completo, gerar_html_relatorio

    try:
        dados = gerar_relatorio_completo(empresa_id, filtro_vagas)
        html_relatorio = gerar_html_relatorio(dados)

        return html_relatorio

    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'error')
        return redirect(url_for('relatorio_empresa'))


@app.route('/api/relatorio/graficos')
def api_relatorio_graficos():
    if 'empresa_id' not in session:
        return {'error': 'Não autorizado'}, 401

    empresa_id = session['empresa_id']
    filtro_vagas = request.args.getlist('vagas')

    if filtro_vagas:
        try:
            filtro_vagas = [int(v) for v in filtro_vagas]
        except ValueError:
            filtro_vagas = None
    else:
        filtro_vagas = None

    from utils.relatorio_generator import gerar_dados_graficos

    try:
        dados = gerar_dados_graficos(empresa_id, filtro_vagas)
        return dados
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/cancelar_candidatura', methods=['POST'])
def cancelar_candidatura():
    if 'candidato_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401

    data = request.get_json()
    vaga_id = data.get('vaga_id')

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    # Verificar se a candidatura existe
    cursor.execute(
        'SELECT id FROM candidaturas WHERE candidato_id = ? AND vaga_id = ?',
        (session['candidato_id'], vaga_id))
    candidatura = cursor.fetchone()

    if not candidatura:
        conn.close()
        return {'error': 'Candidatura não encontrada'}, 404

    # Remover candidatura
    cursor.execute(
        'DELETE FROM candidaturas WHERE candidato_id = ? AND vaga_id = ?',
        (session['candidato_id'], vaga_id))

    # Recalcular posições dos candidatos restantes
    cursor.execute(
        '''
        UPDATE candidaturas
        SET posicao = (
            SELECT COUNT(*) + 1
            FROM candidaturas c2
            WHERE c2.vaga_id = candidaturas.vaga_id 
            AND c2.score > candidaturas.score
        )
        WHERE vaga_id = ?
    ''', (vaga_id, ))

    conn.commit()
    conn.close()

    return {'success': True}


@app.route("/reativar_vaga/<int:vaga_id>", methods=["POST"])
def reativar_vaga_route(vaga_id):
    if 'empresa_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE vagas SET status = "Ativa" WHERE id = ?',
                   (vaga_id, ))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard_empresa'))


@app.route('/api/notificacoes')
def api_notificacoes():
    if 'candidato_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    cursor.execute(
        '''
        SELECT n.id, n.mensagem, n.data_envio, n.lida,
               v.titulo as vaga_titulo,
               e.nome as empresa_nome
        FROM notificacoes n
        JOIN vagas v ON n.vaga_id = v.id
        JOIN empresas e ON n.empresa_id = e.id
        WHERE n.candidato_id = ?
        ORDER BY n.data_envio DESC
    ''', (session['candidato_id'], ))

    notificacoes = cursor.fetchall()
    conn.close()

    return jsonify([{
        'id': n[0],
        'mensagem': n[1],
        'data_envio': n[2],
        'lida': bool(n[3]),
        'vaga_titulo': n[4],
        'empresa_nome': n[5]
    } for n in notificacoes])


@app.route('/api/notificacoes/marcar-lida', methods=['POST'])
def marcar_notificacao_lida():
    if 'candidato_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401

    data = request.get_json()
    notificacao_id = data.get('id')

    if not notificacao_id:
        return jsonify({'error': 'ID da notificação é obrigatório'}), 400

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE notificacoes 
        SET lida = 1 
        WHERE id = ? AND candidato_id = ?
    ''', (notificacao_id, session['candidato_id']))

    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/notificacoes/marcar-todas-lidas', methods=['POST'])
def marcar_todas_notificacoes_lidas():
    if 'candidato_id' not in session:
        return jsonify({'error': 'Não autorizado'}), 401

    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE notificacoes 
        SET lida = 1 
        WHERE candidato_id = ?
    ''', (session['candidato_id'], ))

    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    inicializar_banco()
    app.run(host='0.0.0.0', port=5001, debug=True)
