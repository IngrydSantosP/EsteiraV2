import sqlite3
from datetime import datetime
import random


def inicializar_banco():
    """Inicializa o banco de dados SQLite com todas as colunas necessárias"""
    conn = sqlite3.connect("recrutamento.db")
    cursor = conn.cursor()

    # Criar tabela de candidatos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidatos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            telefone TEXT,
            linkedin TEXT,
            endereco_completo TEXT,
            pretensao_salarial REAL,
            texto_curriculo TEXT,
            caminho_curriculo TEXT,
            experiencia TEXT,
            competencias TEXT,
            resumo_profissional TEXT
        )
    ''')

    # Criar tabela de empresas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL
        )
    ''')

    # Criar tabela de vagas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            requisitos TEXT NOT NULL,
            salario_oferecido REAL NOT NULL,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tipo_vaga TEXT DEFAULT 'Presencial',
            endereco_vaga TEXT,
            status TEXT DEFAULT 'Ativa',
            candidato_selecionado_id INTEGER,
            diferenciais TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas (id),
            FOREIGN KEY (candidato_selecionado_id) REFERENCES candidatos (id)
        )
    ''')

    # Criar tabela de candidaturas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidato_id INTEGER NOT NULL,
            vaga_id INTEGER NOT NULL,
            data_candidatura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            score REAL DEFAULT 0,
            posicao INTEGER DEFAULT 0,
            FOREIGN KEY (candidato_id) REFERENCES candidatos (id),
            FOREIGN KEY (vaga_id) REFERENCES vagas (id)
        )
    ''')

    # Criar tabela de notificações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidato_id INTEGER NOT NULL,
            empresa_id INTEGER NOT NULL,
            vaga_id INTEGER NOT NULL,
            mensagem TEXT NOT NULL,
            data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lida BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (candidato_id) REFERENCES candidatos (id),
            FOREIGN KEY (empresa_id) REFERENCES empresas (id),
            FOREIGN KEY (vaga_id) REFERENCES vagas (id)
        )
    ''')

    # Tabela empresas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            senha_hash TEXT NOT NULL
        )
    """)

    # Tabela candidatos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidatos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            telefone TEXT,
            linkedin TEXT,
            endereco_completo TEXT,
            pretensao_salarial REAL,
            texto_curriculo TEXT,
            experiencia TEXT,
            competencias TEXT,
            resumo_profissional TEXT,
            caminho_curriculo TEXT
        )
    """)

    # Tabela vagas com todas as novas colunas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            requisitos TEXT NOT NULL,
            salario_oferecido REAL NOT NULL,
            tipo_vaga TEXT DEFAULT 'Presencial',
            endereco_vaga TEXT,
            status TEXT DEFAULT 'Ativa',
            candidato_selecionado_id INTEGER,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (empresa_id) REFERENCES empresas (id),
            FOREIGN KEY (candidato_selecionado_id) REFERENCES candidatos (id)
        )
    """)

    # Tabela candidaturas
    cursor.execute("""
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
    """)

    # Adicionar colunas se não existirem (para bancos existentes)
    colunas_adicionar = [('candidatos', 'endereco_completo', 'TEXT'),
                         ('candidatos', 'caminho_curriculo', 'TEXT'),
                         ('vagas', 'tipo_vaga', 'TEXT DEFAULT "Presencial"'),
                         ('vagas', 'endereco_vaga', 'TEXT'),
                         ('vagas', 'status', 'TEXT DEFAULT "Ativa"'),
                         ('vagas', 'candidato_selecionado_id', 'INTEGER')]

    for tabela, coluna, tipo in colunas_adicionar:
        try:
            cursor.execute(f'ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}')
        except sqlite3.OperationalError:
            pass  # Coluna já existe

    conn.commit()
    conn.close()


def atualizar_posicoes_candidatura(vaga_id):
    """Atualiza as posições dos candidatos para uma vaga específica"""
    conn = sqlite3.connect("recrutamento.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, score FROM candidaturas 
        WHERE vaga_id = ? 
        ORDER BY score DESC
    """, (vaga_id, ))

    candidaturas = cursor.fetchall()

    for posicao, (candidatura_id, score) in enumerate(candidaturas, 1):
        cursor.execute(
            """
            UPDATE candidaturas 
            SET posicao = ? 
            WHERE id = ?
        """, (posicao, candidatura_id))

    conn.commit()
    conn.close()


def calcular_distancia_endereco(endereco1, endereco2):
    """Calcula distância entre dois endereços (implementação simplificada)"""
    # Esta é uma implementação simplificada. Em um cenário real, seria necessário
    # integrar com uma API de geolocalização (ex: Google Maps API, OpenStreetMap Nominatim)
    # para converter endereços em coordenadas geográficas e calcular a distância real.
    # Também seria importante padronizar a entrada de endereços no cadastro.
    if endereco1 and endereco2:
        # Simula uma distância variável para demonstração
        return random.uniform(
            1.0, 50.0)  # Retorna uma distância aleatória entre 1 e 50 km
    return None


def processar_candidatura(candidato_id, vaga_id, modo_ia='local'):
    """Processa uma candidatura completa"""
    from avaliador import criar_avaliador

    mensagens = []

    conn = sqlite3.connect("recrutamento.db")
    cursor = conn.cursor()

    try:
        # Verificar se já se candidatou
        cursor.execute(
            """
            SELECT id FROM candidaturas 
            WHERE candidato_id = ? AND vaga_id = ?
        """, (candidato_id, vaga_id))

        if cursor.fetchone():
            mensagens.append({
                'texto': 'Você já se candidatou para esta vaga',
                'tipo': 'info'
            })
            return {'sucesso': False, 'mensagens': mensagens}

        # Buscar dados do candidato e da vaga
        cursor.execute(
            """
            SELECT pretensao_salarial, texto_curriculo, endereco_completo
            FROM candidatos 
            WHERE id = ?
        """, (candidato_id, ))
        candidato = cursor.fetchone()

        cursor.execute(
            """
            SELECT requisitos, salario_oferecido, tipo_vaga, endereco_vaga, diferenciais
            FROM vagas 
            WHERE id = ? AND (status IS NULL OR status = 'Ativa')
        """, (vaga_id, ))
        vaga = cursor.fetchone()

        if not vaga:
            mensagens.append({
                'texto': 'Vaga não encontrada ou não está ativa',
                'tipo': 'error'
            })
            return {'sucesso': False, 'mensagens': mensagens}

        if candidato and vaga:
            # Calcular score base com novos parâmetros
            avaliador = criar_avaliador(modo_ia)
            score = avaliador.calcular_score(
                candidato[1],  # texto_curriculo
                vaga[0],  # requisitos
                candidato[0],  # pretensao_salarial
                vaga[1],  # salario_oferecido
                vaga[4],  # diferenciais
                candidato[2],  # endereco_completo
                vaga[3],  # endereco_vaga
                vaga[2]  # tipo_vaga
            )

            # Ajustar score por proximidade geográfica (se aplicável)
            if vaga[2] in ['Presencial', 'Híbrida'
                           ] and candidato[2] and vaga[3]:
                distancia = calcular_distancia_endereco(candidato[2], vaga[3])
                if distancia:
                    # Bonus por proximidade (até 10 pontos)
                    if distancia <= 5:
                        score += 10
                    elif distancia <= 15:
                        score += 5
                    elif distancia <= 30:
                        score += 2

            # Garantir que o score não passe de 100
            score = min(score, 100)

            # Inserir candidatura
            cursor.execute(
                """
                INSERT INTO candidaturas (candidato_id, vaga_id, score)
                VALUES (?, ?, ?)
            """, (candidato_id, vaga_id, score))

            conn.commit()

            # Atualizar posições
            atualizar_posicoes_candidatura(vaga_id)

            # Buscar posição atual
            cursor.execute(
                """
                SELECT posicao FROM candidaturas 
                WHERE candidato_id = ? AND vaga_id = ?
            """, (candidato_id, vaga_id))
            posicao = cursor.fetchone()[0]

            mensagens.append({
                'texto':
                f'Candidatura realizada com sucesso! Você está na posição {posicao} com score de {score:.1f}%',
                'tipo': 'success'
            })

            return {'sucesso': True, 'mensagens': mensagens}

    except Exception as e:
        mensagens.append({
            'texto': f'Erro ao processar candidatura: {str(e)}',
            'tipo': 'error'
        })
        return {'sucesso': False, 'mensagens': mensagens}

    finally:
        conn.close()