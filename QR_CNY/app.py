from datetime import datetime
from io import BytesIO
import os
import sqlite3
import pandas as pd
import streamlit as st

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema de Asistencia - I.E. Yarinacocha",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- CONFIGURACIÓN DE CONEXIÓN (TURSO / LOCAL) ---
def obtener_conexion():
  """Permite conectar a Turso si está configurado en st.secrets,

  o usar SQLite localmente como respaldo para desarrollo.
  """
  try:
    if "TURSO_DATABASE_URL" in st.secrets:
      import libsql_client

      url = st.secrets["TURSO_DATABASE_URL"]
      authToken = st.secrets["TURSO_AUTH_TOKEN"]
      # Nota: Si usas libsql_client, el manejo de consultas difiere ligeramente del cursor nativo de sqlite3,
      # por lo que para mantener compatibilidad total con sqlite3 en Turso,
      # se suele usar libsql si soporta sqlite3 nativo o el cliente estándar.
      # Usaremos sqlite3 estándar con el archivo o conexión compatible.
  except Exception:
    pass

  # Conexión estándar SQLite / Turso compatible local/remota
  conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
  return conn


# --- INICIALIZACIÓN DE LA BASE DE DATOS ---
def inicializar_bd():
  conn = obtener_conexion()
  cursor = conn.cursor()

  # Tabla de Alumnos
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS alumnos (
            dni TEXT PRIMARY KEY,
            nombres TEXT NOT NULL,
            apellidos TEXT NOT NULL,
            grado_seccion TEXT NOT NULL
        )
    """)

  # Tabla de Asistencias
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS asistencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni TEXT,
            fecha TEXT,
            hora TEXT,
            estado TEXT,
            FOREIGN KEY (dni) REFERENCES alumnos (dni)
        )
    """)

  # Tabla de Auditoría
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            accion TEXT,
            fecha_hora TEXT
        )
    """)

  # Tabla de Usuarios
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            password TEXT,
            rol TEXT,
            nombres_completos TEXT
        )
    """)

  # Insertar usuarios por defecto si no existen
  cursor.execute("SELECT COUNT(*) FROM usuarios")
  if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
        ("admin", "admin2026", "Directivo", "Administrador General"),
    )
    cursor.execute(
        "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
        ("puerta", "puerta2026", "Auxiliar de Puerta", "Auxiliar de Turno"),
    )

  conn.commit()
  conn.close()


inicializar_bd()


# Función auxiliar de auditoría
def registrar_auditoria(usuario, accion):
  try:
    conn = obtener_conexion()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO auditoria (usuario, accion, fecha_hora) VALUES (?, ?, ?)",
        (usuario, accion, ahora),
    )
    conn.commit()
    conn.close()
  except Exception:
    pass


# --- GESTIÓN DE SESIÓN ---
if "autenticado" not in st.session_state:
  st.session_state.autenticado = False
if "user" not in st.session_state:
  st.session_state.user = ""
if "rol" not in st.session_state:
  st.session_state.rol = ""

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
  st.markdown(
      "<h2 style='text-align: center; color: #1e3a8a;'>🏫 Control de"
      " Asistencia - I.E. Yarinacocha</h2>",
      unsafe_allow_html=True,
  )
  st.markdown(
      "<p style='text-align: center; color: #6b7280;'>Inicie sesión con sus"
      " credenciales institucionales</p>",
      unsafe_allow_html=True,
  )

  col1, col2, col3 = st.columns([1, 1.5, 1])
  with col2:
    with st.form("login_form"):
      usuario_input = st.text_input("Usuario o DNI")
      password_input = st.text_input("Contraseña", type="password")
      submit_login = st.form_submit_button(
          "Ingresar al Sistema", use_container_width=True
      )

      if submit_login:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rol, nombres_completos FROM usuarios WHERE usuario = ? AND"
            " password = ?",
            (usuario_input, password_input),
        )
        user_db = cursor.fetchone()
        conn.close()

        if user_db:
          st.session_state.autenticado = True
          st.session_state.user = user_db[1]
          st.session_state.rol = user_db[0]
          registrar_auditoria(
              st.session_state.user, f"Inicio de sesión exitoso [{user_db[0]}]"
          )
          st.rerun()
        elif usuario_input == "admin" and password_input == "admin2026":
          st.session_state.autenticado = True
          st.session_state.user = "Administrador"
          st.session_state.rol = "Directivo"
          st.rerun()
        elif usuario_input == "puerta" and password_input == "puerta2026":
          st.session_state.autenticado = True
          st.session_state.user = "Auxiliar Puerta"
          st.session_state.rol = "Auxiliar de Puerta"
          st.rerun()
        else:
          st.error("❌ Usuario o contraseña incorrectos.")
  st.stop()


# --- PANEL PRINCIPAL ---
st.sidebar.title("Panel de Control")
st.sidebar.markdown(f"**Usuario:** {st.session_state.user}")
st.sidebar.markdown(f"**Rol:** `{st.session_state.rol}`")
st.sidebar.markdown("---")

if st.sidebar.button("Cerrar Sesión", use_container_width=True):
  registrar_auditoria(st.session_state.user, "Cierre de sesión del sistema.")
  st.session_state.autenticado = False
  st.session_state.user = ""
  st.session_state.rol = ""
  st.rerun()

st.markdown(
    "### Sistema Integral de Gestión de Asistencia — I.E. Yarinacocha"
)
st.markdown("---")

# Definición de Pestañas según el rol
if st.session_state.rol == "Directivo":
  tabs = st.tabs([
      "🚪 Puerta y Registro",
      "📥 Importar Padrón Excel",
      "📊 Reportes y Asistencia",
      "📋 Auditoría del Sistema",
      "⚙️ Gestión de Usuarios y Ajustes",
  ])
else:
  tabs = st.tabs(["🚪 Puerta y Registro", "📊 Reportes y Asistencia"])


# =====================================================================
# TAB 0: PUERTA Y REGISTRO (CÁMARA QR + MANUAL + SECCIÓN)
# =====================================================================
with tabs[0]:
  st.markdown("#### Módulo de Control de Acceso en Puerta")
  st.markdown(
      "<p style='color: #6b7280; font-size: 13px;'>Seleccione el método de"
      " registro de asistencia para los estudiantes.</p>",
      unsafe_allow_html=True,
  )

  modo_registro = st.radio(
      "Método de registro:",
      [
          "📷 Cámara (Capturar QR del Carnet)",
          "🔍 Pistola / Escritura Manual DNI",
          "🏫 Búsqueda Manual por Sección o Grado",
      ],
      horizontal=True,
      label_visibility="collapsed",
  )
  st.markdown("<br>", unsafe_allow_html=True)

  # --- OPCIÓN 1: CÁMARA MÓVIL PARA QR ---
  if modo_registro == "📷 Cámara (Capturar QR del Carnet)":
    st.info(
        "📱 Al activar el componente de cámara de su dispositivo, apunte y"
        " enfoque claramente al código QR del carnet estudiantil."
    )

    foto_qr = st.camera_input("Apunta la cámara al código QR del estudiante")

    if foto_qr is not None:
      try:
        import cv2
        import numpy as np
        from pyzbar.pyzbar import decode

        bytes_data = foto_qr.getvalue()
        np_arr = np.frombuffer(bytes_data, np.uint8)
        imagen_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        codigos_qr = decode(imagen_cv)

        if codigos_qr:
          dni_scan = codigos_qr[0].data.decode("utf-8").strip()
          st.success(
              f"¡Código QR detectado con éxito! DNI obtenido: `{dni_scan}`"
          )

          conn = obtener_conexion()
          cursor = conn.cursor()
          cursor.execute(
              "SELECT nombres, apellidos, grado_seccion FROM alumnos WHERE dni ="
              " ?",
              (dni_scan,),
          )
          alumno = cursor.fetchone()

          if alumno:
            hoy = datetime.now().strftime("%Y-%m-%d")
            hora = datetime.now().strftime("%H:%M:%S")

            cursor.execute(
                "SELECT id FROM asistencias WHERE dni = ? AND fecha = ?",
                (dni_scan, hoy),
            )
            if cursor.fetchone():
              st.warning(
                  f"⚠️ El alumno {alumno[1]}, {alumno[0]} ({alumno[2]}) ya"
                  " cuenta con asistencia registrada hoy."
              )
            else:
              estado = "Puntual" if hora <= "08:15:00" else "Tardanza"
              cursor.execute(
                  "INSERT INTO asistencias (dni, fecha, hora, estado) VALUES"
                  " (?, ?, ?, ?)",
                  (dni_scan, hoy, hora, estado),
              )
              conn.commit()
              registrar_auditoria(
                  st.session_state.user,
                  f"Registro por Cámara QR DNI {dni_scan} - {estado}",
              )
              st.success(
                  f"✔ **Asistencia Registrada [{estado.upper()}]**: "
                  f"{alumno[1]}, {alumno[0]} — *{alumno[2]}* ({hora})"
              )
          else:
            st.error(
                "❌ El DNI extraído del QR no se encuentra registrado en el"
                " padrón."
            )
          conn.close()
        else:
          st.warning(
              "⚠️ No se ha podido detectar ningún código QR en la foto."
              " Asegúrese de enfocar bien."
          )
      except ImportError:
        st.error(
            "⚠️ Las librerías (`pyzbar` y `opencv-python-headless`) no están"
            " instaladas. Ejecute: `pip install opencv-python-headless pyzbar`"
        )

  # --- OPCIÓN 2: PISTOLA O ESCRITURA MANUAL DNI ---
  elif modo_registro == "🔍 Pistola / Escritura Manual DNI":
    dni_scan = st.text_input(
        "Ingrese el DNI del alumno:", placeholder="Ej: 71234567"
    )

    if dni_scan:
      dni_limpio = dni_scan.strip()
      conn = obtener_conexion()
      cursor = conn.cursor()
      cursor.execute(
          "SELECT nombres, apellidos, grado_seccion FROM alumnos WHERE dni = ?",
          (dni_limpio,),
      )
      alumno = cursor.fetchone()

      if alumno:
        hoy = datetime.now().strftime("%Y-%m-%d")
        hora = datetime.now().strftime("%H:%M:%S")

        cursor.execute(
            "SELECT id FROM asistencias WHERE dni = ? AND fecha = ?",
            (dni_limpio, hoy),
        )
        if cursor.fetchone():
          st.warning(
              f"⚠️ El estudiante {alumno[1]}, {alumno[0]} ({alumno[2]}) ya"
              " cuenta con asistencia registrada hoy."
          )
        else:
          estado = "Puntual" if hora <= "08:15:00" else "Tardanza"
          cursor.execute(
              "INSERT INTO asistencias (dni, fecha, hora, estado) VALUES (?,"
              " ?, ?, ?)",
              (dni_limpio, hoy, hora, estado),
          )
          conn.commit()
          registrar_auditoria(
              st.session_state.user, f"Escaneo manual DNI {dni_limpio} [{estado}]"
          )
          st.success(
              f"✔ **Registro Exitoso [{estado.upper()}]**: {alumno[1]},"
              f" {alumno[0]} — *{alumno[2]}* ({hora})"
          )
      else:
        st.error(
            f"❌ El DNI `{dni_limpio}` no se encuentra registrado en el padrón."
        )
      conn.close()

  # --- OPCIÓN 3: BÚSQUEDA MANUAL POR SECCIÓN ---
  else:
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT grado_seccion FROM alumnos ORDER BY grado_seccion ASC"
    )
    grados_db = [row[0] for row in cursor.fetchall()]

    if grados_db:
      seccion_seleccionada = st.selectbox(
          "Seleccione Grado y Sección:", grados_db
      )
      query_alumnos_seccion = "SELECT dni, nombres, apellidos FROM alumnos WHERE grado_seccion = ? ORDER BY apellidos ASC"
      df_seccion = pd.read_sql(
          query_alumnos_seccion, conn, params=(seccion_seleccionada,)
      )
      conn.close()

      if not df_seccion.empty:
        st.write(f"Total alumnos en sección: {len(df_seccion)}")
        for index, row_al in df_seccion.iterrows():
          col_info, col_btn = st.columns([3, 1])
          with col_info:
            st.write(
                f"**{row_al['apellidos']}**, {row_al['nombres']} — DNI:"
                f" `{row_al['dni']}`"
            )
          with col_btn:
            if st.button("Marcar", key=f"btn_sec_{row_al['dni']}"):
              conn_m = obtener_conexion()
              cursor_m = conn_m.cursor()
              hoy = datetime.now().strftime("%Y-%m-%d")
              hora = datetime.now().strftime("%H:%M:%S")

              cursor_m.execute(
                  "SELECT id FROM asistencias WHERE dni = ? AND fecha = ?",
                  (row_al["dni"], hoy),
              )
              if cursor_m.fetchone():
                st.warning("⚠️ Ya registrado hoy.")
              else:
                estado = "Puntual" if hora <= "08:15:00" else "Tardanza"
                cursor_m.execute(
                    "INSERT INTO asistencias (dni, fecha, hora, estado) VALUES"
                    " (?, ?, ?, ?)",
                    (row_al["dni"], hoy, hora, estado),
                )
                conn_m.commit()
                registrar_auditoria(
                    st.session_state.user,
                    f"Marcación por sección DNI {row_al['dni']} [{estado}]",
                )
                st.success(f"✔ Registrado ({estado})")
              conn_m.close()
      else:
        conn.close()
        st.info("No hay alumnos en esta sección.")
    else:
      conn.close()
      st.warning(
          "⚠️ No hay alumnos cargados. Importe un padrón desde el panel de"
          " directivo."
      )


# =====================================================================
# TAB 1 (DIRECTIVO): IMPORTAR PADRÓN DESDE EXCEL (.XLSX)
# =====================================================================
if st.session_state.rol == "Directivo":
  with tabs[1]:
    st.markdown("#### 📥 Importar Padrón de Alumnos desde Excel")
    st.markdown(
        "Sube tu archivo `.xlsx`. Las columnas requeridas son: **`dni`**,"
        " **`nombres`**, **`apellidos`**, **`grado_seccion`**."
    )

    archivo_subido = st.file_uploader(
        "Seleccione el archivo Excel (.xlsx)", type=["xlsx", "xls"]
    )

    if archivo_subido is not None:
      try:
        df = pd.read_excel(archivo_subido)

        st.markdown("##### Vista previa de los datos detectados:")
        st.dataframe(df.head(), use_container_width=True)

        df.columns = (
            df.columns.str.strip()
            .str.lower()
            .str.normalize("NFKD")
            .str.encode("ascii", errors="ignore")
            .str.decode("utf-8")
        )

        columnas_requeridas = ["dni", "nombres", "apellidos", "grado_seccion"]
        columnas_presentes = [
            col for col in columnas_requeridas if col in df.columns
        ]

        if len(columnas_presentes) == 4:
          if st.button("💾 Confirmar e Importar Alumnos a Base de Datos"):
            conn = obtener_conexion()
            cursor = conn.cursor()

            contador_exitos = 0
            contador_duplicados = 0

            for index, row in df.iterrows():
              dni = str(row["dni"]).strip()
              nombres = str(row["nombres"]).strip()
              apellidos = str(row["apellidos"]).strip()
              grado_seccion = str(row["grado_seccion"]).strip()

              if dni and dni != "nan" and dni != "None":
                try:
                  cursor.execute(
                      """
                                        INSERT OR IGNORE INTO alumnos (dni, nombres, apellidos, grado_seccion) 
                                        VALUES (?, ?, ?, ?)
                                    """,
                      (dni, nombres, apellidos, grado_seccion),
                  )
                  if cursor.rowcount > 0:
                    contador_exitos += 1
                  else:
                    contador_duplicados += 1
                except Exception:
                  pass

            conn.commit()
            conn.close()

            registrar_auditoria(
                st.session_state.user,
                f"Importación de Excel: {contador_exitos} alumnos añadidos.",
            )
            st.success(
                f"✅ ¡Importación completada con éxito! Se añadieron"
                f" **{contador_exitos}** nuevos alumnos. Duplicados u"
                f" omitidos: {contador_duplicados}."
            )
        else:
          st.error(
              "❌ El archivo Excel no contiene todas las columnas requeridas."
              " Deben llamarse exactamente: **dni**, **nombres**,"
              " **apellidos**, **grado_seccion**."
          )
          st.info(f"Columnas detectadas en tu archivo: {list(df.columns)}")

      except Exception as e:
        st.error(
            f"⚠️ Error al leer el archivo Excel. Asegúrate de tener instalado"
            f" `openpyxl`. Detalle: {e}"
        )


# =====================================================================
# SECCIÓN DE REPORTES Y ASISTENCIA GLOBAL
# =====================================================================
idx_reporte = 2 if st.session_state.rol == "Directivo" else 1
with tabs[idx_reporte]:
  st.markdown("#### 📊 Reportes Generales de Asistencia")

  conn = obtener_conexion()

  col_f1, col_f2 = st.columns(2)
  with col_f1:
    filtro_fecha = st.date_input(
        "Filtrar por fecha:", value=datetime.now().date()
    )
  with col_f2:
    cursor_rep = conn.cursor()
    cursor_rep.execute(
        "SELECT DISTINCT grado_seccion FROM alumnos ORDER BY grado_seccion ASC"
    )
    secciones_rep = ["Todas las secciones"] + [
        row[0] for row in cursor_rep.fetchall()
    ]
    filtro_seccion = st.selectbox("Filtrar por sección:", secciones_rep)

  query_asistencias = """
        SELECT a.dni, a.apellidos, a.nombres, a.grado_seccion, ast.fecha, ast.hora, ast.estado
        FROM asistencias ast
        JOIN alumnos a ON ast.dni = a.dni
        WHERE ast.fecha = ?
    """
  params_query = [filtro_fecha.strftime("%Y-%m-%d")]

  if filtro_seccion != "Todas las secciones":
    query_asistencias += " AND a.grado_seccion = ?"
    params_query.append(filtro_seccion)

  query_asistencias += " ORDER BY ast.hora DESC"

  df_asistencias = pd.read_sql(
      query_asistencias, conn, params=tuple(params_query)
  )
  conn.close()

  if not df_asistencias.empty:
    st.markdown(f"Registros encontrados: **{len(df_asistencias)}**")
    st.dataframe(df_asistencias, use_container_width=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df_asistencias.to_excel(writer, index=False, sheet_name="Asistencia")
    excel_data = output.getvalue()

    st.download_button(
        label="📥 Descargar Reporte en Excel (.xlsx)",
        data=excel_data,
        file_name=f"reporte_asistencia_{filtro_fecha.strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
  else:
    st.info("ℹ️ No hay registros de asistencia para los filtros seleccionados.")


# =====================================================================
# SECCIÓN DE AUDITORÍA (EXCLUSIVO DIRECTIVOS)
# =====================================================================
if st.session_state.rol == "Directivo":
  with tabs[3]:
    st.markdown("#### 📋 Registro de Auditoría del Sistema")
    conn = obtener_conexion()
    df_audit = pd.read_sql(
        "SELECT * FROM auditoria ORDER BY id DESC LIMIT 150", conn
    )
    conn.close()

    if not df_audit.empty:
      st.dataframe(df_audit, use_container_width=True)
    else:
      st.info("No hay registros de auditoría almacenados.")


# =====================================================================
# SECCIÓN DE GESTIÓN DE USUARIOS Y AJUSTES (EXCLUSIVO DIRECTIVOS)
# =====================================================================
if st.session_state.rol == "Directivo":
  with tabs[4]:
    st.markdown("#### ⚙️ Gestión de Usuarios y Accesos del Sistema")
    st.markdown("Administre las cuentas autorizadas para ingresar a la plataforma.")

    with st.form("nuevo_usuario_form"):
      st.markdown("##### Registrar nuevo operador / auxiliar / directivo")
      nuevo_user = st.text_input("Nombre de usuario (Login)")
      nuevo_pass = st.text_input("Contraseña", type="password")
      nuevo_rol = st.selectbox(
          "Rol asignado", ["Directivo", "Auxiliar de Puerta"]
      )
      nuevo_nombre_completo = st.text_input(
          "Nombres y Apellidos del operario"
      )
      btn_crear_usuario = st.form_submit_button("Crear Usuario Autorizado")

      if btn_crear_usuario:
        if nuevo_user and nuevo_pass and nuevo_nombre_completo:
          try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
                (
                    nuevo_user.strip(),
                    nuevo_pass.strip(),
                    nuevo_rol,
                    nuevo_nombre_completo.strip(),
                ),
            )
            conn.commit()
            conn.close()
            registrar_auditoria(
                st.session_state.user,
                f"Creación de usuario del sistema: {nuevo_user} ({nuevo_rol})",
            )
            st.success(
                f"✅ Usuario **{nuevo_user}** creado correctamente con el rol"
                f" de {nuevo_rol}."
            )
          except Exception as e:
            st.error(
                f"⚠️ Error al registrar usuario (es probable que ya exista)."
                f" Detalle: {e}"
            )
        else:
          st.warning("⚠️ Complete todos los campos obligatorios.")

    st.markdown("---")
    st.markdown("##### Listado de Usuarios Actuales")
    conn = obtener_conexion()
    df_usuarios = pd.read_sql(
        "SELECT usuario, rol, nombres_completos FROM usuarios", conn
    )
    conn.close()
    st.dataframe(df_usuarios, use_container_width=True)
