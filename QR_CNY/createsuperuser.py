import sqlite3
import getpass

def crear_superusuario():
    print("=== CREAR SUPERUSUARIO (ESTILO DJANGO) ===")
    
    # Pedir datos por consola
    usuario = input("Usuario (ej. admin): ").strip()
    nombres = input("Nombres completos: ").strip()
    password = getpass.getpass("Contraseña: ").strip()
    
    if not usuario or not password or not nombres:
        print("❌ Error: Todos los campos son obligatorios.")
        return

    # Conectar a tu base de datos local
    db_path = "asistencia_enterprise.db"  # Cambia esto si tu archivo .db se llama diferente
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Asegurarse de que la tabla exista
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                usuario TEXT PRIMARY KEY,
                password TEXT,
                rol TEXT,
                nombres_completos TEXT
            )
        """)
        
        # Insertar el superusuario
        cursor.execute(
            "INSERT OR REPLACE INTO usuarios (usuario, password, rol, nombres_completos) VALUES (?, ?, ?, ?)",
            (usuario, password, "Directivo", nombres)
        )
        conn.commit()
        conn.close()
        print(f"\n✅ ¡Superusuario '{usuario}' creado/actualizado con éxito en tu base de datos local!")
        print("Ahora haz un 'git add', 'git commit' y 'git push' para subir tu archivo .db actualizado a GitHub.")
        
    except Exception as e:
        print(f"❌ Error al guardar en la base de datos: {e}")

if __name__ == "__main__":
    crear_superusuario()
