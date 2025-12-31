import mysql.connector

print("--- TESTE DE CONEXÃO ---")
print("Tentando conectar ao XAMPP...")

try:
    # 1. Tenta conectar sem especificar banco (apenas login)
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password=''  # Senha vazia do XAMPP
    )
    print("✅ Conexão com o XAMPP: SUCESSO!")
    
    cursor = conn.cursor()
    
    # 2. Tenta encontrar o banco
    try:
        cursor.execute("USE sistema_rifa")
        print("✅ Banco 'sistema_rifa': ENCONTRADO!")
    except mysql.connector.Error as err:
        print(f"❌ Banco 'sistema_rifa': NÃO ENCONTRADO. (Erro: {err})")
        print("Dica: Crie manualmente no phpMyAdmin ou verifique o nome.")

    conn.close()

except mysql.connector.Error as err:
    print("\n❌ ERRO FATAL DE CONEXÃO:")
    print(err)
    print("\nCAUSAS PROVÁVEIS:")
    print("1. O XAMPP (MySQL) não está rodando (Start no painel).")
    print("2. A porta 3306 está bloqueada.")
    print("3. A senha não é vazia (talvez você tenha alterado?).")

input("\n\nPressione ENTER para fechar...")