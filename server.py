import os
import sys
import webbrowser
from flask import Flask, render_template, request, jsonify, session, redirect, send_from_directory
import mysql.connector

# --- CONFIGURAÇÃO ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder=BASE_DIR, static_folder=BASE_DIR)
app.secret_key = 'sua_chave_secreta_aqui'
app.config['TEMPLATES_AUTO_RELOAD'] = True
os.chdir(BASE_DIR)

# --- BANCO DE DADOS ---
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = 'root'       # Sua senha aqui
DB_NAME = 'sistema_rifa'
QTD_RIFAS = 5000   # <--- ALTERADO PARA 5000

def get_db_connection():
    try:
        return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
    except mysql.connector.Error as err:
        return None

def inicializar_banco():
    """Cria banco, tabelas e COMPLETA as rifas que faltam."""
    print("Verificando banco de dados...")
    try:
        conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")

        # Cria tabelas se não existirem
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                email VARCHAR(100) NOT NULL UNIQUE,
                senha VARCHAR(255) NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rifas (
                numero INT PRIMARY KEY,
                status ENUM('disponivel', 'vendido') DEFAULT 'disponivel',
                dono_id INT DEFAULT NULL,
                FOREIGN KEY (dono_id) REFERENCES usuarios(id)
            )
        """)

        # --- LÓGICA INTELIGENTE DE ATUALIZAÇÃO ---
        cursor.execute("SELECT COUNT(*) FROM rifas")
        qtd_atual = cursor.fetchone()[0]

        if qtd_atual < QTD_RIFAS:
            print(f"Expandindo rifas de {qtd_atual} para {QTD_RIFAS}...")
            # Gera apenas os números que faltam (ex: 1001 até 5000)
            valores = [(i, 'disponivel') for i in range(qtd_atual + 1, QTD_RIFAS + 1)]
            
            # Insere em lotes para ser mais rápido
            cursor.executemany("INSERT INTO rifas (numero, status) VALUES (%s, %s)", valores)
            conn.commit()
            print("Novas rifas adicionadas com sucesso!")
        
        cursor.close()
        conn.close()
        print("Banco de dados pronto e atualizado!")

    except mysql.connector.Error as err:
        print(f"ERRO AO INICIAR: {err}")

# --- ROTAS ---
@app.route('/')
@app.route('/index.html')
def pagina_login(): return render_template('index.html')

@app.route('/cadastro.html')
def pagina_cadastro(): return render_template('cadastro.html')

@app.route('/esqueci.html')
def pagina_esqueci(): return render_template('esqueci.html')

@app.route('/novaSenha.html')
def pagina_novasenha(): return render_template('novaSenha.html')

@app.route('/home.html')
def pagina_home():
    if 'usuario_id' not in session: return redirect('/')
    return render_template('home.html')

@app.route('/rifas.html')
def pagina_rifas():
    if 'usuario_id' not in session: return redirect('/')
    return render_template('rifas.html')

@app.route('/arraial.html')
def pagina_arraial():
    if 'usuario_id' not in session: return redirect('/')
    return render_template('arraial.html')

@app.route('/pagamento.html')
def pagina_pagamento():
    if 'usuario_id' not in session: return redirect('/')
    return render_template('pagamento.html')

@app.route('/agradecimento.html')
def pagina_agradecimento():
    if 'usuario_id' not in session: return redirect('/')
    return render_template('agradecimento.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(BASE_DIR, filename)

# --- API ---
@app.route('/api/cadastro', methods=['POST'])
def api_cadastro():
    dados = request.json
    conn = get_db_connection()
    if not conn: return jsonify({'sucesso': False, 'msg': 'Erro DB'})
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM usuarios WHERE email = %s", (dados['email'],))
        if cursor.fetchone(): return jsonify({'sucesso': False, 'msg': 'Email já existe!'})
        cursor.execute("INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)", 
                       (dados['nome'], dados['email'], dados['senha']))
        conn.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/login', methods=['POST'])
def api_login():
    dados = request.json
    conn = get_db_connection()
    if not conn: return jsonify({'sucesso': False, 'msg': 'Erro DB'})
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE email = %s AND senha = %s", (dados['email'], dados['senha']))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()

    if usuario:
        session['usuario_id'] = usuario['id']
        session['nome'] = usuario['nome']
        return jsonify({'sucesso': True})
    return jsonify({'sucesso': False, 'msg': 'Dados incorretos.'})

@app.route('/api/status_rifas')
def status_rifas():
    conn = get_db_connection()
    if not conn: return jsonify({})
    cursor = conn.cursor(dictionary=True)
    # Busca apenas as vendidas para otimizar (não trafegar 5000 itens se não precisar)
    cursor.execute("SELECT numero FROM rifas WHERE status = 'vendido'")
    vendidas = {str(row['numero']): 'vendido' for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return jsonify(vendidas)

@app.route('/api/comprar_multiplos', methods=['POST'])
def comprar_multiplos():
    if 'usuario_id' not in session: return jsonify({'sucesso': False, 'msg': 'Login necessário'})
    
    conn = get_db_connection()
    if not conn: return jsonify({'sucesso': False, 'msg': 'Erro DB'})
    cursor = conn.cursor()
    numeros = request.json.get('numeros', [])
    usuario_id = session['usuario_id']
    
    comprados, falharam = [], []

    try:
        conn.start_transaction()
        for num in numeros:
            cursor.execute("SELECT status FROM rifas WHERE numero = %s FOR UPDATE", (num,))
            row = cursor.fetchone()
            if row and row[0] == 'disponivel':
                cursor.execute("UPDATE rifas SET status='vendido', dono_id=%s WHERE numero=%s", (usuario_id, num))
                comprados.append(num)
            else:
                falharam.append(num)
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'sucesso': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()

    if comprados:
        return jsonify({'sucesso': True, 'comprados': comprados, 'falharam': falharam})
    return jsonify({'sucesso': False, 'msg': 'Rifas indisponíveis.'})

if __name__ == '__main__':
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        inicializar_banco()
        webbrowser.open("http://localhost:8000")
    app.run(port=8000, debug=True)