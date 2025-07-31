
import sqlite3

def atualizar_banco():
    """Atualiza o banco de dados existente com as novas colunas"""
    conn = sqlite3.connect('recrutamento.db')
    cursor = conn.cursor()
    
    # Adicionar colunas na tabela vagas se não existirem
    try:
        cursor.execute('ALTER TABLE vagas ADD COLUMN tipo_vaga TEXT DEFAULT "Presencial"')
        print("Coluna tipo_vaga adicionada")
    except sqlite3.OperationalError:
        print("Coluna tipo_vaga já existe")
    
    try:
        cursor.execute('ALTER TABLE vagas ADD COLUMN endereco_vaga TEXT')
        print("Coluna endereco_vaga adicionada")
    except sqlite3.OperationalError:
        print("Coluna endereco_vaga já existe")
    
    try:
        cursor.execute('ALTER TABLE vagas ADD COLUMN status TEXT DEFAULT "Ativa"')
        print("Coluna status adicionada")
    except sqlite3.OperationalError:
        print("Coluna status já existe")
    
    try:
        cursor.execute('ALTER TABLE vagas ADD COLUMN candidato_selecionado_id INTEGER')
        print("Coluna candidato_selecionado_id adicionada")
    except sqlite3.OperationalError:
        print("Coluna candidato_selecionado_id já existe")
    
    # Adicionar coluna na tabela candidatos se não existir
    try:
        cursor.execute('ALTER TABLE candidatos ADD COLUMN endereco_completo TEXT')
        print("Coluna endereco_completo adicionada")
    except sqlite3.OperationalError:
        print("Coluna endereco_completo já existe")
    
    conn.commit()
    conn.close()
    print("Banco de dados atualizado com sucesso!")

if __name__ == '__main__':
    atualizar_banco()
