import os
import sys
import webbrowser
from flask import Flask, render_template, request, jsonify, session, redirect, send_from_directory
import mysql.connector
from waitress import serve # <--- IMPORTANTE PARA ACESSO EXTERNO

# --- CONFIGURAÇÃO ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder=BASE_DIR, static_folder=BASE_DIR)
app.secret_key = 'sua_chave_secreta_aqui'
app.config['TEMPLATES_AUTO_RELOAD'] = True
os.chdir(BASE_DIR)

# --- CONFIGURAÇÕES DO ADMIN ---
SENHA_ADMIN = 'admsenha4321'

# --- BANCO DE DADOS ---
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = ''       
DB_NAME = 'sistema_rifa'
QTD_RIFAS = 5000   
PRECO_RIFA = 50.00 

def get_db_connection():
    try:
        return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
    except mysql.connector.Error as err:
        return None

def inicializar_banco():
    print("Verificando banco de dados...")
    try:
        conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")

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
                status ENUM('disponivel', 'pendente', 'vendido') DEFAULT 'disponivel',
                dono_id INT DEFAULT NULL,
                FOREIGN KEY (dono_id) REFERENCES usuarios(id)
            )
        """)

        try:
            cursor.execute("ALTER TABLE rifas MODIFY COLUMN status ENUM('disponivel', 'pendente', 'vendido') DEFAULT 'disponivel'")
            conn.commit()
        except: pass

        cursor.execute("SELECT COUNT(*) FROM rifas")
        qtd_atual = cursor.fetchone()[0]

        if qtd_atual < QTD_RIFAS:
            print(f"Expandindo rifas de {qtd_atual} para {QTD_RIFAS}...")
            valores = [(i, 'disponivel') for i in range(qtd_atual + 1, QTD_RIFAS + 1)]
            cursor.executemany("INSERT INTO rifas (numero, status) VALUES (%s, %s)", valores)
            conn.commit()
            print("Novas rifas adicionadas com sucesso!")
        
        cursor.close()
        conn.close()
        print("Banco de dados pronto e atualizado!")

    except mysql.connector.Error as err:
        print(f"ERRO AO INICIAR: {err}")

# --- ROTAS DE PÁGINAS ---
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

# --- ROTAS ADMIN (PROTEGIDAS) ---
@app.route('/admin_login.html')
def pagina_admin_login():
    if session.get('admin_logado'): return redirect('/admin.html')
    return render_template('admin_login.html')

@app.route('/admin.html')
def pagina_admin():
    if not session.get('admin_logado'): return redirect('/admin_login.html')
    return render_template('admin.html')

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
    cursor.execute("SELECT numero, status FROM rifas WHERE status IN ('vendido', 'pendente')")
    ocupadas = {str(row['numero']): row['status'] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return jsonify(ocupadas)

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
                cursor.execute("UPDATE rifas SET status='pendente', dono_id=%s WHERE numero=%s", (usuario_id, num))
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

# --- APIS DO ADMIN (COM PROTEÇÃO) ---

@app.route('/api/admin/login', methods=['POST'])
def admin_login_api():
    dados = request.json
    if dados.get('senha') == SENHA_ADMIN:
        session['admin_logado'] = True
        return jsonify({'sucesso': True})
    return jsonify({'sucesso': False, 'msg': 'Senha incorreta'})

@app.route('/api/admin/logout')
def admin_logout():
    session.pop('admin_logado', None)
    return redirect('/admin_login.html')

# Middleware simples para verificar sessão nas rotas abaixo
def check_admin():
    return session.get('admin_logado')

@app.route('/api/admin/dados')
def admin_dados():
    if not check_admin(): return jsonify({'sucesso': False, 'msg': 'Acesso negado'}), 403
    
    conn = get_db_connection()
    if not conn: return jsonify({'sucesso': False})
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as total FROM rifas")
    total_rifas = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as vendidas FROM rifas WHERE status='vendido'")
    qtd_vendidas = cursor.fetchone()['vendidas']

    cursor.execute("SELECT COUNT(*) as pendentes FROM rifas WHERE status='pendente'")
    qtd_pendentes = cursor.fetchone()['pendentes']

    query_usuarios = """
        SELECT 
            u.id, 
            u.nome, 
            u.email, 
            u.senha,
            GROUP_CONCAT(CASE WHEN r.status = 'pendente' THEN r.numero END ORDER BY r.numero SEPARATOR ', ') as numeros_pendentes,
            GROUP_CONCAT(CASE WHEN r.status = 'vendido' THEN r.numero END ORDER BY r.numero SEPARATOR ', ') as numeros_confirmados
        FROM usuarios u 
        LEFT JOIN rifas r ON u.id = r.dono_id 
        GROUP BY u.id
        HAVING numeros_pendentes IS NOT NULL OR numeros_confirmados IS NOT NULL
    """
    cursor.execute(query_usuarios)
    usuarios = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        'sucesso': True,
        'stats': {
            'total': total_rifas,
            'vendidas': qtd_vendidas,
            'pendentes': qtd_pendentes,
            'disponiveis': total_rifas - qtd_vendidas - qtd_pendentes,
            'arrecadacao_real': qtd_vendidas * PRECO_RIFA,
            'arrecadacao_pendente': qtd_pendentes * PRECO_RIFA
        },
        'usuarios': usuarios
    })

@app.route('/api/admin/aprovar_compra', methods=['POST'])
def admin_aprovar():
    if not check_admin(): return jsonify({'sucesso': False}), 403
    dados = request.json
    usuario_id = dados.get('usuario_id')
    numeros = dados.get('numeros')

    if isinstance(numeros, str): numeros = [n.strip() for n in numeros.split(',')]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        format_strings = ','.join(['%s'] * len(numeros))
        cursor.execute(f"UPDATE rifas SET status='vendido' WHERE dono_id=%s AND status='pendente' AND numero IN ({format_strings})", 
                       (usuario_id, *numeros))
        conn.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/rejeitar_compra', methods=['POST'])
def admin_rejeitar():
    if not check_admin(): return jsonify({'sucesso': False}), 403
    dados = request.json
    usuario_id = dados.get('usuario_id')
    numeros = dados.get('numeros') 

    if isinstance(numeros, str): numeros = [n.strip() for n in numeros.split(',')]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        format_strings = ','.join(['%s'] * len(numeros))
        cursor.execute(f"UPDATE rifas SET status='disponivel', dono_id=NULL WHERE dono_id=%s AND status='pendente' AND numero IN ({format_strings})", 
                       (usuario_id, *numeros))
        conn.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/atualizar_usuario', methods=['POST'])
def admin_atualizar_usuario():
    if not check_admin(): return jsonify({'sucesso': False}), 403
    dados = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE usuarios SET nome=%s, email=%s, senha=%s WHERE id=%s", 
                       (dados['nome'], dados['email'], dados['senha'], dados['id']))
        conn.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/resetar', methods=['POST'])
def admin_resetar():
    if not check_admin(): return jsonify({'sucesso': False}), 403
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE rifas SET status='disponivel', dono_id=NULL")
        conn.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()

# --- INICIALIZAÇÃO CORRETA PARA REDE (WAITRESS) ---
if __name__ == '__main__':
    # Inicializa o banco apenas uma vez (se não for o reloader)
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        inicializar_banco()
    
    print("\n-----------------------------------------------------------")
    print(" SERVIDOR RODANDO COM WAITRESS (PROFISSIONAL)")
    print(f" > Para acessar neste PC: http://localhost:8080")
    print(f" > Para acessar de OUTROS PCs: http://SEU_IP_DO_PC:8080")
    print("-----------------------------------------------------------\n")
    
    # host='0.0.0.0' libera para a rede inteira
    serve(app, host='0.0.0.0', port=8080)