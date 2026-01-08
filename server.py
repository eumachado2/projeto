import os
import sys
import secrets
from flask import Flask, render_template, request, jsonify, session, redirect, send_from_directory
import mysql.connector
from flask_mail import Mail, Message
from waitress import serve
from datetime import datetime, date, timedelta

# --- CONFIGURAÇÃO DE DIRETÓRIO ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder=BASE_DIR, static_folder=BASE_DIR)
app.secret_key = 'sua_chave_secreta_aqui'
app.config['TEMPLATES_AUTO_RELOAD'] = True
os.chdir(BASE_DIR)

# --- CONFIGURAÇÃO DE E-MAIL (GMAIL) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'verificarifa@gmail.com' # TROQUE PELO SEU
app.config['MAIL_PASSWORD'] = 'brpn jbrp eacd hgnl'   # TROQUE PELA SENHA DE APP
mail = Mail(app)

# --- CONFIGURAÇÕES DO SISTEMA ---
SENHA_ADMIN = 'admsenha4321'
DB_HOST, DB_USER, DB_PASS, DB_NAME = 'localhost', 'root', '', 'sistema_rifa'
QTD_RIFAS, PRECO_RIFA = 5000, 50.00

def get_db_connection():
    try:
        return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
    except: return None

def inicializar_banco():
    print("Verificando banco de dados...")
    try:
        conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")

        # Tabela Usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                email VARCHAR(100) NOT NULL UNIQUE,
                senha VARCHAR(255) NOT NULL,
                reset_token VARCHAR(100) DEFAULT NULL,
                token_expiracao DATETIME DEFAULT NULL
            )
        """)

        # Adiciona colunas de segurança se necessário
        for col in [("reset_token", "VARCHAR(100)"), ("token_expiracao", "DATETIME")]:
            try: cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {col[0]} {col[1]} DEFAULT NULL")
            except: pass

        # Tabela Rifas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rifas (
                numero INT PRIMARY KEY,
                status ENUM('disponivel', 'pendente', 'vendido') DEFAULT 'disponivel',
                dono_id INT DEFAULT NULL,
                FOREIGN KEY (dono_id) REFERENCES usuarios(id)
            )
        """)

        # Tabela Agendamentos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agendamentos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT,
                data DATE NOT NULL,
                UNIQUE(data), 
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        """)

        # Expansão de Rifas
        cursor.execute("SELECT COUNT(*) FROM rifas")
        if cursor.fetchone()[0] < QTD_RIFAS:
            print("Gerando rifas...")
            cursor.execute("SELECT MAX(numero) FROM rifas")
            ultimo = cursor.fetchone()[0] or 0
            valores = [(i, 'disponivel') for i in range(ultimo + 1, QTD_RIFAS + 1)]
            cursor.executemany("INSERT INTO rifas (numero, status) VALUES (%s, %s)", valores)

        # Bloqueio de datas Arraial
        ano = date.today().year
        for m_i, d_i, m_f, d_f in [(1,1,1,23), (2,12,2,23)]:
            dt = date(ano, m_i, d_i)
            while dt <= date(ano, m_f, d_f):
                try: cursor.execute("INSERT IGNORE INTO agendamentos (data, usuario_id) VALUES (%s, NULL)", (dt,))
                except: pass
                dt += timedelta(days=1)
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e: print(f"Erro: {e}")

# --- ROTAS DE PÁGINAS ---
@app.route('/')
@app.route('/index.html')
def login_pg(): return render_template('index.html')
@app.route('/cadastro.html')
def cadastro_pg(): return render_template('cadastro.html')
@app.route('/esqueci.html')
def esqueci_pg(): return render_template('esqueci.html')
@app.route('/redefinir-senha/<token>')
def reset_pg(token): return render_template('novaSenha.html', token=token)
@app.route('/home.html')
def home_pg(): return render_template('home.html') if 'usuario_id' in session else redirect('/')
@app.route('/rifas.html')
def rifas_pg(): return render_template('rifas.html') if 'usuario_id' in session else redirect('/')
@app.route('/arraial.html')
def arraial_pg(): return render_template('arraial.html') if 'usuario_id' in session else redirect('/')
@app.route('/pagamento.html')
def pag_pg(): return render_template('pagamento.html') if 'usuario_id' in session else redirect('/')
@app.route('/agradecimento.html')
def agra_pg(): return render_template('agradecimento.html') if 'usuario_id' in session else redirect('/')
@app.route('/admin_login.html')
def adm_log_pg(): return redirect('/admin.html') if session.get('admin_logado') else render_template('admin_login.html')
@app.route('/admin.html')
def adm_pg(): return render_template('admin.html') if session.get('admin_logado') else redirect('/admin_login.html')
@app.route('/<path:filename>')
def static_files(filename): return send_from_directory(BASE_DIR, filename)

# --- APIs PÚBLICAS (LOGIN/CADASTRO/SENHA) ---
@app.route('/api/cadastro', methods=['POST'])
def api_cad():
    d = request.json
    c = get_db_connection()
    cur = c.cursor()
    try:
        cur.execute("INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)", (d['nome'], d['email'], d['senha']))
        c.commit()
        return jsonify({'sucesso': True})
    except: return jsonify({'sucesso': False, 'msg': 'Email já cadastrado!'})
    finally: c.close(); c.close()

@app.route('/api/login', methods=['POST'])
def api_log():
    d = request.json
    c = get_db_connection()
    cur = c.cursor(dictionary=True)
    cur.execute("SELECT * FROM usuarios WHERE email=%s AND senha=%s", (d['email'], d['senha']))
    u = cur.fetchone()
    if u: session['usuario_id'], session['nome'] = u['id'], u['nome']; return jsonify({'sucesso': True})
    return jsonify({'sucesso': False, 'msg': 'Dados incorretos.'})

@app.route('/api/forgot-password', methods=['POST'])
def api_forgot():
    email = request.json.get('email')
    c = get_db_connection(); cur = c.cursor(dictionary=True)
    cur.execute("SELECT id, nome FROM usuarios WHERE email=%s", (email,))
    u = cur.fetchone()
    if u:
        tk = secrets.token_urlsafe(32); exp = datetime.now() + timedelta(minutes=30)
        cur.execute("UPDATE usuarios SET reset_token=%s, token_expiracao=%s WHERE id=%s", (tk, exp, u['id']))
        c.commit()
        link = f"http://0.0.0.0:8080/redefinir-senha/{tk}"
        msg = Message("Recuperação - Rifa", sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f"Olá {u['nome']}, clique no link para redefinir sua senha: {link}"
        try: mail.send(msg)
        except: pass
    return jsonify({"sucesso": True, "msg": "Verifique seu e-mail."})

@app.route('/api/reset-password', methods=['POST'])
def api_reset():
    tk, ns = request.json.get('token'), request.json.get('senha')
    c = get_db_connection(); cur = c.cursor()
    cur.execute("SELECT id FROM usuarios WHERE reset_token=%s AND token_expiracao > %s", (tk, datetime.now()))
    u = cur.fetchone()
    if u:
        cur.execute("UPDATE usuarios SET senha=%s, reset_token=NULL, token_expiracao=NULL WHERE id=%s", (ns, u[0]))
        c.commit(); return jsonify({"sucesso": True})
    return jsonify({"sucesso": False, "msg": "Link expirado."})

# --- APIs DE RIFAS E CALENDÁRIO ---
@app.route('/api/status_rifas')
def api_status():
    c = get_db_connection(); cur = c.cursor(dictionary=True)
    cur.execute("SELECT numero, status FROM rifas WHERE status != 'disponivel'")
    res = {str(r['numero']): r['status'] for r in cur.fetchall()}
    return jsonify(res)

@app.route('/api/comprar_multiplos', methods=['POST'])
def api_buy():
    if 'usuario_id' not in session: return jsonify({'sucesso': False, 'msg': 'Login!'})
    nums, uid = request.json.get('numeros', []), session['usuario_id']
    c = get_db_connection(); cur = c.cursor()
    comprados = []
    try:
        c.start_transaction()
        for n in nums:
            cur.execute("SELECT status FROM rifas WHERE numero=%s FOR UPDATE", (n,))
            if cur.fetchone()[0] == 'disponivel':
                cur.execute("UPDATE rifas SET status='pendente', dono_id=%s WHERE numero=%s", (uid, n))
                comprados.append(n)
        c.commit(); return jsonify({'sucesso': True, 'comprados': comprados})
    except: c.rollback(); return jsonify({'sucesso': False})

@app.route('/api/dias_ocupados')
def api_days():
    c = get_db_connection(); cur = c.cursor()
    cur.execute("SELECT DATE_FORMAT(data, '%Y-%m-%d') FROM agendamentos")
    return jsonify([r[0] for r in cur.fetchall()])

@app.route('/api/agendar', methods=['POST'])
def api_sched():
    ds, uid = request.json.get('datas', []), session.get('usuario_id')
    c = get_db_connection(); cur = c.cursor()
    try:
        for d in ds: cur.execute("INSERT INTO agendamentos (usuario_id, data) VALUES (%s, %s)", (uid, d))
        c.commit(); return jsonify({'sucesso': True})
    except: return jsonify({'sucesso': False})

# --- APIs ADMIN (AS QUE ESTAVAM FALTANDO!) ---
@app.route('/api/admin/login', methods=['POST'])
def api_adm_log():
    if request.json.get('senha') == SENHA_ADMIN: session['admin_logado'] = True; return jsonify({'sucesso': True})
    return jsonify({'sucesso': False})

@app.route('/api/admin/logout')
def api_adm_out(): session.pop('admin_logado', None); return redirect('/admin_login.html')

@app.route('/api/admin/dados')
def api_adm_data():
    if not session.get('admin_logado'): return jsonify({'sucesso': False}), 403
    c = get_db_connection(); cur = c.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) as v FROM rifas WHERE status='vendido'")
    vend = cur.fetchone()['v']
    cur.execute("SELECT COUNT(*) as p FROM rifas WHERE status='pendente'")
    pend = cur.fetchone()['p']
    cur.execute("SELECT COUNT(*) as t FROM rifas")
    total = cur.fetchone()['t']
    
    q = """
        SELECT u.id, u.nome, u.email, u.senha,
        GROUP_CONCAT(DISTINCT CASE WHEN r.status='pendente' THEN r.numero END SEPARATOR ', ') as numeros_pendentes,
        GROUP_CONCAT(DISTINCT CASE WHEN r.status='vendido' THEN r.numero END SEPARATOR ', ') as numeros_confirmados,
        GROUP_CONCAT(DISTINCT DATE_FORMAT(a.data, '%d/%m/%Y') SEPARATOR ', ') as datas_reservadas
        FROM usuarios u 
        LEFT JOIN rifas r ON u.id = r.dono_id 
        LEFT JOIN agendamentos a ON u.id = a.usuario_id
        GROUP BY u.id ORDER BY u.id DESC
    """
    cur.execute(q)
    usrs = cur.fetchall()
    return jsonify({'sucesso': True, 'stats': {'vendidas': vend, 'pendentes': pend, 'disponiveis': total-vend-pend, 'arrecadacao_real': vend*PRECO_RIFA}, 'usuarios': usrs})

@app.route('/api/admin/aprovar_compra', methods=['POST'])
def api_adm_aprove():
    if not session.get('admin_logado'): return jsonify({'sucesso': False}), 403
    uid, nums = request.json.get('usuario_id'), request.json.get('numeros')
    if isinstance(nums, str): nums = [n.strip() for n in nums.split(',')]
    c = get_db_connection(); cur = c.cursor()
    fmt = ','.join(['%s'] * len(nums))
    cur.execute(f"UPDATE rifas SET status='vendido' WHERE dono_id=%s AND numero IN ({fmt})", (uid, *nums))
    c.commit(); return jsonify({'sucesso': True})

@app.route('/api/admin/rejeitar_compra', methods=['POST'])
def api_adm_reject():
    if not session.get('admin_logado'): return jsonify({'sucesso': False}), 403
    uid, nums = request.json.get('usuario_id'), request.json.get('numeros')
    if isinstance(nums, str): nums = [n.strip() for n in nums.split(',')]
    c = get_db_connection(); cur = c.cursor()
    fmt = ','.join(['%s'] * len(nums))
    cur.execute(f"UPDATE rifas SET status='disponivel', dono_id=NULL WHERE dono_id=%s AND numero IN ({fmt})", (uid, *nums))
    c.commit(); return jsonify({'sucesso': True})

@app.route('/api/admin/excluir_usuario', methods=['POST'])
def api_adm_del():
    if not session.get('admin_logado'): return jsonify({'sucesso': False}), 403
    uid = request.json.get('id')
    c = get_db_connection(); cur = c.cursor()
    cur.execute("UPDATE rifas SET status='disponivel', dono_id=NULL WHERE dono_id=%s", (uid,))
    cur.execute("DELETE FROM agendamentos WHERE usuario_id=%s", (uid,))
    cur.execute("DELETE FROM usuarios WHERE id=%s", (uid,))
    c.commit(); return jsonify({'sucesso': True})

@app.route('/api/admin/sortear', methods=['POST'])
def api_adm_draw():
    if not session.get('admin_logado'): return jsonify({'sucesso': False}), 403
    c = get_db_connection(); cur = c.cursor(dictionary=True)
    cur.execute("SELECT r.numero, u.nome, u.email FROM rifas r JOIN usuarios u ON r.dono_id=u.id WHERE r.status='vendido' ORDER BY RAND() LIMIT 1")
    ganhador = cur.fetchone()
    return jsonify({'sucesso': True, 'ganhador': ganhador}) if ganhador else jsonify({'sucesso': False, 'msg': 'Sem rifas vendidas!'})

@app.route('/api/admin/resetar', methods=['POST'])
def api_adm_reset():
    if not session.get('admin_logado'): return jsonify({'sucesso': False}), 403
    c = get_db_connection(); cur = c.cursor()
    cur.execute("UPDATE rifas SET status='disponivel', dono_id=NULL"); cur.execute("TRUNCATE TABLE agendamentos")
    c.commit(); return jsonify({'sucesso': True})

if __name__ == '__main__':
    inicializar_banco()
    print(f"ON: http://10.40.10.9:8080")
    serve(app, host='0.0.0.0', port=8080)