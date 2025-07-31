
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash
import PyPDF2
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'chave-secreta-mvp-recrutamento'

# Configurações do ambiente
MODO_IA = os.getenv('MODO_IA', 'local')
TOP_JOBS = int(os.getenv('TOP_JOBS', '3'))
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

# Criar pasta de uploads se não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def inicializar_banco():
    """Inicializa o banco de dados SQLite"""
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    
    # Tabela empresas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            senha_hash TEXT NOT NULL
        )
    ''')
    
    # Tabela candidatos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidatos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            telefone TEXT,
            linkedin TEXT,
            pretensao_salarial REAL,
            texto_curriculo TEXT,
            experiencia TEXT,
            competencias TEXT,
            resumo_profissional TEXT
        )
    ''')
    
    # Tabela vagas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            requisitos TEXT NOT NULL,
            salario_oferecido REAL NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (empresa_id) REFERENCES empresas (id)
        )
    ''')
    
    # Tabela candidaturas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidato_id INTEGER NOT NULL,
            vaga_id INTEGER NOT NULL,
            score REAL NOT NULL,
            posicao INTEGER,
            data_candidatura DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (candidato_id) REFERENCES candidatos (id),
            FOREIGN KEY (vaga_id) REFERENCES vagas (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def arquivo_permitido(nome_arquivo):
    """Verifica se o arquivo tem extensão permitida"""
    return '.' in nome_arquivo and nome_arquivo.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extrair_texto_pdf(caminho_arquivo):
    """Extrai texto do PDF usando PyPDF2"""
    try:
        with open(caminho_arquivo, 'rb') as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            texto = ""
            for pagina in leitor.pages:
                texto += pagina.extract_text() + "\n"
        return texto
    except Exception as e:
        print(f"Erro ao extrair texto do PDF: {e}")
        return ""

def processar_curriculo(texto_curriculo):
    """Processa o texto do currículo para extrair informações"""
    experiencia = ""
    competencias = ""
    resumo_profissional = ""
    
    # Buscar experiência profissional
    padroes_experiencia = [
        r'experiência[^:]*:(.+?)(?=\n\n|\ncompetências|\nhabilidades|\nformação|$)',
        r'experiência profissional[^:]*:(.+?)(?=\n\n|\ncompetências|\nhabilidades|\nformação|$)',
        r'histórico profissional[^:]*:(.+?)(?=\n\n|\ncompetências|\nhabilidades|\nformação|$)'
    ]
    
    for padrao in padroes_experiencia:
        match = re.search(padrao, texto_curriculo.lower(), re.DOTALL)
        if match:
            experiencia = match.group(1).strip()
            break
    
    # Buscar competências/habilidades
    padroes_competencias = [
        r'competências[^:]*:(.+?)(?=\n\n|\nexperiência|\nformação|$)',
        r'habilidades[^:]*:(.+?)(?=\n\n|\nexperiência|\nformação|$)',
        r'conhecimentos[^:]*:(.+?)(?=\n\n|\nexperiência|\nformação|$)'
    ]
    
    for padrao in padroes_competencias:
        match = re.search(padrao, texto_curriculo.lower(), re.DOTALL)
        if match:
            competencias = match.group(1).strip()
            break
    
    # Buscar resumo profissional
    padroes_resumo = [
        r'resumo[^:]*:(.+?)(?=\n\n|\nexperiência|\ncompetências|$)',
        r'objetivo[^:]*:(.+?)(?=\n\n|\nexperiência|\ncompetências|$)',
        r'perfil[^:]*:(.+?)(?=\n\n|\nexperiência|\ncompetências|$)'
    ]
    
    for padrao in padroes_resumo:
        match = re.search(padrao, texto_curriculo.lower(), re.DOTALL)
        if match:
            resumo_profissional = match.group(1).strip()
            break
    
    return experiencia, competencias, resumo_profissional

def calcular_score_local(texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido):
    """Calcula score usando método local simples"""
    score = 0
    
    # Divide os requisitos e conta quantos aparecem no currículo
    requisitos_lista = [req.strip().lower() for req in requisitos_vaga.split(',')]
    texto_curriculo_lower = texto_curriculo.lower()
    
    requisitos_encontrados = 0
    for requisito in requisitos_lista:
        if requisito in texto_curriculo_lower:
            requisitos_encontrados += 1
    
    # Score baseado nos requisitos (70% do peso)
    if requisitos_lista:
        score += (requisitos_encontrados / len(requisitos_lista)) * 70
    
    # Score baseado na pretensão salarial (30% do peso)
    if pretensao_salarial and salario_oferecido:
        if pretensao_salarial <= salario_oferecido:
            score += 30
        elif pretensao_salarial <= salario_oferecido * 1.2:  # 20% acima
            score += 20
        elif pretensao_salarial <= salario_oferecido * 1.5:  # 50% acima
            score += 10
    
    return min(score, 100)

def calcular_score_huggingface(texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido):
    """Calcula score usando Hugging Face sentence-transformers"""
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        # Carregar modelo
        modelo = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Calcular embeddings
        embedding_curriculo = modelo.encode([texto_curriculo])
        embedding_requisitos = modelo.encode([requisitos_vaga])
        
        # Calcular similaridade
        similaridade = cosine_similarity(embedding_curriculo, embedding_requisitos)[0][0]
        
        # Score baseado na similaridade semântica (70% do peso)
        score = similaridade * 70
        
        # Score baseado na pretensão salarial (30% do peso)
        if pretensao_salarial and salario_oferecido:
            if pretensao_salarial <= salario_oferecido:
                score += 30
            elif pretensao_salarial <= salario_oferecido * 1.2:
                score += 20
            elif pretensao_salarial <= salario_oferecido * 1.5:
                score += 10
        
        return min(score, 100)
        
    except ImportError:
        print("Sentence-transformers não disponível, usando método local")
        return calcular_score_local(texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido)

def calcular_score_matching(texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido):
    """Calcula score baseado no modo de IA configurado"""
    if MODO_IA == 'huggingface':
        return calcular_score_huggingface(texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido)
    else:
        return calcular_score_local(texto_curriculo, requisitos_vaga, pretensao_salarial, salario_oferecido)

def atualizar_posicoes_candidatura(vaga_id):
    """Atualiza as posições dos candidatos para uma vaga específica"""
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, score FROM candidaturas 
        WHERE vaga_id = ? 
        ORDER BY score DESC
    ''', (vaga_id,))
    
    candidaturas = cursor.fetchall()
    
    for posicao, (candidatura_id, score) in enumerate(candidaturas, 1):
        cursor.execute('''
            UPDATE candidaturas 
            SET posicao = ? 
            WHERE id = ?
        ''', (posicao, candidatura_id))
    
    conn.commit()
    conn.close()

# Rotas da aplicação
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login_empresa', methods=['GET', 'POST'])
def login_empresa():
    if request.method == 'POST':
        cnpj = request.form['cnpj']
        senha = request.form['senha']
        
        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, senha_hash FROM empresas WHERE cnpj = ?', (cnpj,))
        empresa = cursor.fetchone()
        conn.close()
        
        if empresa and check_password_hash(empresa[1], senha):
            session['empresa_id'] = empresa[0]
            session['tipo_usuario'] = 'empresa'
            return redirect(url_for('dashboard_empresa'))
        else:
            flash('CNPJ ou senha incorretos', 'error')
    
    return render_template('login_empresa.html')

@app.route('/cadastro_empresa', methods=['GET', 'POST'])
def cadastro_empresa():
    if request.method == 'POST':
        cnpj = request.form['cnpj']
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        
        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO empresas (cnpj, nome, email, senha_hash)
                VALUES (?, ?, ?, ?)
            ''', (cnpj, nome, email, generate_password_hash(senha)))
            conn.commit()
            flash('Empresa cadastrada com sucesso!', 'success')
            return redirect(url_for('login_empresa'))
        except sqlite3.IntegrityError:
            flash('CNPJ já cadastrado', 'error')
        finally:
            conn.close()
    
    return render_template('cadastro_empresa.html')

@app.route('/login_candidato', methods=['GET', 'POST'])
def login_candidato():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, senha_hash FROM candidatos WHERE email = ?', (email,))
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
        pretensao_salarial = float(request.form['pretensao_salarial'])
        
        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO candidatos (nome, email, senha_hash, telefone, linkedin, pretensao_salarial)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome, email, generate_password_hash(senha), telefone, linkedin, pretensao_salarial))
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
    if 'empresa_id' not in session:
        return redirect(url_for('login_empresa'))
    
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM vagas WHERE empresa_id = ?', (session['empresa_id'],))
    vagas = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard_empresa.html', vagas=vagas)

@app.route('/criar_vaga', methods=['GET', 'POST'])
def criar_vaga():
    if 'empresa_id' not in session:
        return redirect(url_for('login_empresa'))
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        requisitos = request.form['requisitos']
        salario_oferecido = float(request.form['salario_oferecido'])
        
        conn = sqlite3.connect('recrutamento.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO vagas (empresa_id, titulo, descricao, requisitos, salario_oferecido)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['empresa_id'], titulo, descricao, requisitos, salario_oferecido))
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
    
    cursor.execute('''
        SELECT c.nome, c.email, c.telefone, c.linkedin, ca.score, ca.posicao
        FROM candidaturas ca
        JOIN candidatos c ON ca.candidato_id = c.id
        WHERE ca.vaga_id = ?
        ORDER BY ca.score DESC
    ''', (vaga_id,))
    
    candidatos = cursor.fetchall()
    
    cursor.execute('SELECT titulo FROM vagas WHERE id = ?', (vaga_id,))
    vaga = cursor.fetchone()
    conn.close()
    
    return render_template('candidatos_vaga.html', candidatos=candidatos, vaga_titulo=vaga[0] if vaga else '')

@app.route('/dashboard_candidato')
def dashboard_candidato():
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))
    
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    
    # Verificar se tem currículo
    cursor.execute('SELECT texto_curriculo FROM candidatos WHERE id = ?', (session['candidato_id'],))
    candidato = cursor.fetchone()
    
    if not candidato or not candidato[0]:
        conn.close()
        return redirect(url_for('upload_curriculo'))
    
    # Buscar vagas recomendadas
    cursor.execute('''
        SELECT v.id, v.titulo, v.descricao, v.requisitos, v.salario_oferecido, e.nome as empresa_nome
        FROM vagas v
        JOIN empresas e ON v.empresa_id = e.id
    ''')
    vagas = cursor.fetchall()
    
    cursor.execute('SELECT pretensao_salarial, texto_curriculo FROM candidatos WHERE id = ?', (session['candidato_id'],))
    candidato_info = cursor.fetchone()
    
    conn.close()
    
    # Calcular scores para todas as vagas
    vagas_com_score = []
    for vaga in vagas:
        score = calcular_score_matching(
            candidato_info[1], 
            vaga[3], 
            candidato_info[0], 
            vaga[4]
        )
        vagas_com_score.append(vaga + (score,))
    
    # Ordenar por score e pegar apenas as TOP_JOBS
    vagas_com_score.sort(key=lambda x: x[6], reverse=True)
    top_vagas = vagas_com_score[:TOP_JOBS]
    
    return render_template('dashboard_candidato.html', vagas=top_vagas)

@app.route('/upload_curriculo', methods=['GET', 'POST'])
def upload_curriculo():
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))
    
    if request.method == 'POST':
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)
        
        arquivo = request.files['arquivo']
        
        if arquivo.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)
        
        if arquivo and arquivo_permitido(arquivo.filename):
            nome_arquivo = secure_filename(arquivo.filename)
            caminho_arquivo = os.path.join(UPLOAD_FOLDER, f"candidato_{session['candidato_id']}_{nome_arquivo}")
            arquivo.save(caminho_arquivo)
            
            # Extrair texto do PDF
            texto_curriculo = extrair_texto_pdf(caminho_arquivo)
            
            if texto_curriculo:
                # Processar currículo
                experiencia, competencias, resumo_profissional = processar_curriculo(texto_curriculo)
                
                # Salvar no banco
                conn = sqlite3.connect('recrutamento.db')
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE candidatos 
                    SET texto_curriculo = ?, experiencia = ?, competencias = ?, resumo_profissional = ?
                    WHERE id = ?
                ''', (texto_curriculo, experiencia, competencias, resumo_profissional, session['candidato_id']))
                
                conn.commit()
                conn.close()
                
                # Remover arquivo após processar
                os.remove(caminho_arquivo)
                
                return render_template('processar_curriculo.html', 
                                     experiencia=experiencia,
                                     competencias=competencias,
                                     resumo_profissional=resumo_profissional)
            else:
                flash('Erro ao processar o PDF', 'error')
        else:
            flash('Apenas arquivos PDF são permitidos', 'error')
    
    return render_template('upload_curriculo.html')

@app.route('/finalizar_curriculo', methods=['POST'])
def finalizar_curriculo():
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))
    
    experiencia = request.form['experiencia']
    competencias = request.form['competencias']
    resumo_profissional = request.form['resumo_profissional']
    
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE candidatos 
        SET experiencia = ?, competencias = ?, resumo_profissional = ?
        WHERE id = ?
    ''', (experiencia, competencias, resumo_profissional, session['candidato_id']))
    
    conn.commit()
    conn.close()
    
    flash('Currículo processado com sucesso!', 'success')
    return redirect(url_for('dashboard_candidato'))

@app.route('/candidatar/<int:vaga_id>')
def candidatar(vaga_id):
    if 'candidato_id' not in session:
        return redirect(url_for('login_candidato'))
    
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    
    # Verificar se já se candidatou
    cursor.execute('''
        SELECT id FROM candidaturas 
        WHERE candidato_id = ? AND vaga_id = ?
    ''', (session['candidato_id'], vaga_id))
    
    if cursor.fetchone():
        flash('Você já se candidatou para esta vaga', 'info')
        return redirect(url_for('dashboard_candidato'))
    
    # Buscar dados do candidato e da vaga
    cursor.execute('''
        SELECT pretensao_salarial, texto_curriculo 
        FROM candidatos 
        WHERE id = ?
    ''', (session['candidato_id'],))
    candidato = cursor.fetchone()
    
    cursor.execute('''
        SELECT requisitos, salario_oferecido 
        FROM vagas 
        WHERE id = ?
    ''', (vaga_id,))
    vaga = cursor.fetchone()
    
    if candidato and vaga:
        # Calcular score
        score = calcular_score_matching(
            candidato[1], 
            vaga[0], 
            candidato[0], 
            vaga[1]
        )
        
        # Inserir candidatura
        cursor.execute('''
            INSERT INTO candidaturas (candidato_id, vaga_id, score)
            VALUES (?, ?, ?)
        ''', (session['candidato_id'], vaga_id, score))
        
        conn.commit()
        
        # Atualizar posições
        atualizar_posicoes_candidatura(vaga_id)
        
        # Buscar posição atual
        cursor.execute('''
            SELECT posicao FROM candidaturas 
            WHERE candidato_id = ? AND vaga_id = ?
        ''', (session['candidato_id'], vaga_id))
        posicao = cursor.fetchone()[0]
        
        flash(f'Candidatura realizada com sucesso! Você está na posição {posicao}', 'success')
    
    conn.close()
    return redirect(url_for('dashboard_candidato'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    inicializar_banco()
    app.run(host='0.0.0.0', port=5000, debug=True)
