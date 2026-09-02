import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import hashlib
import qrcode
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Gestión de Asistencia Escolar",
    page_icon="escudo.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS PROFESIONALES (DISEÑO LIMPIO Y CORPORATIVO) ---
st.markdown("""
    <style>
        /* Tipografía general y colores base */
        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        
        /* Contenedor principal y animaciones suaves */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(2px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .stApp {
            animation: fadeIn 0.25s ease-out;
        }

        /* Botones principales con estilo profesional */
        .stButton button {
            border-radius: 6px;
            font-weight: 500;
            border: 1px solid #d1d5db;
            background-color: #ffffff;
            color: #374151;
            padding: 0.45rem 1rem;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }
        .stButton button:hover {
            background-color: #f9fafb;
            border-color: #9ca3af;
            color: #111827;
        }
        .stButton button:active {
            transform: scale(0.98);
        }

        /* Botones de formulario destacados */
        [data-testid="stFormSubmitButton"] button {
            background-color: #2563eb !important;
            color: white !important;
            border: none !important;
        }
        [data-testid="stFormSubmitButton"] button:hover {
            background-color: #1d4ed8 !important;
        }

        /* Tarjetas de métricas estilizadas */
        [data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            padding: 14px 18px;
            border-radius: 8px;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        }

        /* Campos de entrada */
        input, select {
            border-radius: 6px !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- BASE DE DATOS Y OPTIMIZACIÓN DE ÍNDICES ---
def init_db():
    conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT,
            rol TEXT,
            seccion_asignada TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alumnos (
            dni TEXT PRIMARY KEY,
            nombres TEXT,
            apellidos TEXT,
            grado_seccion TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asistencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni TEXT,
            fecha TEXT,
            hora TEXT,
            estado TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS justificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni TEXT,
            fecha TEXT,
            motivo TEXT,
            registrado_por TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            accion TEXT,
            timestamp TEXT
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alumnos_dni ON alumnos(dni);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alumnos_seccion ON alumnos(grado_seccion);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_asistencias_dni_fecha ON asistencias(dni, fecha);")
    
    # Usuarios base predeterminados si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        usuarios_base = [
            ("directivo1", hashlib.sha256("dir123".encode()).hexdigest(), "Directivo", "TODAS"),
            ("auxiliar1", hashlib.sha256("aux123".encode()).hexdigest(), "Auxiliar de Puerta", "TODAS"),
            ("docente_1a", hashlib.sha256("doc123".encode()).hexdigest(), "Docente", "1°A")
        ]
        for u, p, r, s in usuarios_base:
            cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol, seccion_asignada) VALUES (?, ?, ?, ?)", (u, p, r, s))
        
    conn.commit()
    conn.close()

init_db()

def registrar_auditoria(usuario, accion):
    conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO auditoria (usuario, accion, timestamp) VALUES (?, ?, ?)",
                   (usuario, accion, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# --- CONTROL DE SESIÓN Y LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.rol = None
    st.session_state.seccion = None

if not st.session_state.logged_in:
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #111827; font-weight: 600;'>Control de Asistencia</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #6b7280; font-size: 14px;'>Ingrese sus credenciales institucionales</p>", unsafe_allow_html=True)
        
        with st.form("login_form_secure"):
            username_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")
            login_btn = st.form_submit_button("Acceder al Sistema", use_container_width=True)
            
            if login_btn:
                conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
                cursor = conn.cursor()
                cursor.execute("SELECT rol, seccion_asignada FROM usuarios WHERE username = ? AND password = ?", 
                               (username_input.strip(), hashlib.sha256(password_input.encode()).hexdigest()))
                res = cursor.fetchone()
                conn.close()
                
                if res:
                    st.session_state.logged_in = True
                    st.session_state.user = username_input.strip()
                    st.session_state.rol = res[0]
                    st.session_state.seccion = res[1]
                    registrar_auditoria(st.session_state.user, "Inicio de sesión correcto")
                    st.rerun()
                else:
                    st.error("Credenciales inválidas. Verifique sus datos.")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.markdown("### 🏫 Panel Institucional")
st.sidebar.markdown(f"**Usuario:** `{st.session_state.user}`")
st.sidebar.markdown(f"**Rol:** {st.session_state.rol}")
st.sidebar.divider()

if st.sidebar.button("Cerrar Sesión", use_container_width=True):
    registrar_auditoria(st.session_state.user, "Cierre de sesión")
    st.session_state.logged_in = False
    st.rerun()

st.markdown("<h2 style='color: #111827; font-weight: 600; margin-bottom: 0px;'>Módulo de Asistencia Escolar</h2>", unsafe_allow_html=True)
st.markdown("<p style='color: #6b7280; font-size: 14px;'>Sistema de control diario, reportes y gestión administrativa</p>", unsafe_allow_html=True)
st.divider()

# --- MÉTRICAS GENERALES ---
conn_m = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
total_alumnos_db = pd.read_sql("SELECT COUNT(*) as c FROM alumnos", conn_m)['c'][0]
total_asistencias_db = pd.read_sql("SELECT COUNT(*) as c FROM asistencias", conn_m)['c'][0]
conn_m.close()

col_m1, col_m2 = st.columns(2)
col_m1.metric("Alumnos Registrados en Padrón", total_alumnos_db)
col_m2.metric("Asistencias Históricas Acumuladas", total_asistencias_db)
st.markdown("<br>", unsafe_allow_html=True)

# --- DEFINICIÓN DE PESTAÑAS SEGÚN ROL ---
if st.session_state.rol in ["Directivo", "Auxiliar de Puerta"]:
    tabs = st.tabs(["🚪 Control en Puerta", "📋 Semáforo de Aulas", "📊 Reporte Diario", "📝 Permisos y Justif.", "🖨️ Carnets QR", "⚙️ Administración"])
else:
    tabs = st.tabs(["📋 Mi Aula Asignada", "📊 Reporte Diario", "📝 Permisos y Justif."])

# --- TAB 1: PUERTA Y REGISTRO ---
if st.session_state.rol in ["Directivo", "Auxiliar de Puerta"]:
    with tabs[0]:
        st.markdown("#### Registro de Acceso en Puerta")
        st.markdown("<p style='color: #6b7280; font-size: 13px;'>Utilice el lector de código de barras/QR o realice la búsqueda manual.</p>", unsafe_allow_html=True)
        
        modo_registro = st.radio("Método de registro:", ["🔍 Escáner (Pistola QR / DNI)", "🏫 Búsqueda Manual por Sección"], horizontal=True, label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if modo_registro == "🔍 Escáner (Pistola QR / DNI)":
            dni_scan = st.text_input("Ingrese o escanee el DNI del alumno:", placeholder="Ej: 71234567")
            
            if dni_scan:
                conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
                cursor = conn.cursor()
                cursor.execute("SELECT nombres, apellidos, grado_seccion FROM alumnos WHERE dni = ?", (dni_scan.strip(),))
                alumno = cursor.fetchone()
                
                if alumno:
                    hoy = datetime.now().strftime("%Y-%m-%d")
                    hora = datetime.now().strftime("%H:%M:%S")
                    
                    cursor.execute("SELECT id FROM asistencias WHERE dni = ? AND fecha = ?", (dni_scan.strip(), hoy))
                    if cursor.fetchone():
                        st.warning(f"⚠️ **Aviso:** El alumno {alumno[1]}, {alumno[0]} ({alumno[2]}) ya cuenta con asistencia registrada el día de hoy.")
                    else:
                        estado = "Puntual" if hora <= "08:15:00" else "Tardanza"
                        cursor.execute("INSERT INTO asistencias (dni, fecha, hora, estado) VALUES (?, ?, ?, ?)", 
                                       (dni_scan.strip(), hoy, hora, estado))
                        conn.commit()
                        registrar_auditoria(st.session_state.user, f"Escaneo QR/DNI {dni_scan} - {estado}")
                        st.success(f"✔ **Registro exitoso [{estado.upper()}]**: {alumno[1]}, {alumno[0]} — *{alumno[2]}* ({hora})")
                else:
                    st.error("❌ El DNI ingresado no se encuentra registrado en el padrón.")
                conn.close()
                
        else:
            conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
            df_sec = pd.read_sql("SELECT DISTINCT grado_seccion FROM alumnos ORDER BY grado_seccion", conn)
            
            if not df_sec.empty:
                seccion_elegida = st.selectbox("Seleccione Grado y Sección:", df_sec["grado_seccion"].tolist())
                df_alumnos_sec = pd.read_sql("SELECT dni, nombres, apellidos FROM alumnos WHERE grado_seccion = ? ORDER BY apellidos ASC", conn, params=(seccion_elegida,))
                
                if not df_alumnos_sec.empty:
                    df_alumnos_sec["nombre_completo"] = df_alumnos_sec["apellidos"] + ", " + df_alumnos_sec["nombres"] + " (DNI: " + df_alumnos_sec["dni"] + ")"
                    alumno_seleccionado = st.selectbox("Seleccione al Alumno:", df_alumnos_sec["nombre_completo"].tolist())
                    
                    if alumno_seleccionado:
                        dni_encontrado = alumno_seleccionado.split("(DNI: ")[-1].replace(")", "").strip()
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        hoy = datetime.now().strftime("%Y-%m-%d")
                        hora = datetime.now().strftime("%H:%M:%S")
                        
                        cursor = conn.cursor()
                        cursor.execute("SELECT estado FROM asistencias WHERE dni = ? AND fecha = ?", (dni_encontrado, hoy))
                        ya_registrado = cursor.fetchone()
                        
                        if ya_registrado:
                            st.info(f"ℹ️ El alumno ya cuenta con asistencia registrada hoy: **{ya_registrado[0]}**")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("Registrar Asistencia (Puntual/Tardanza)", use_container_width=True):
                                estado = "Puntual" if hora <= "08:15:00" else "Tardanza"
                                cursor.execute("INSERT INTO asistencias (dni, fecha, hora, estado) VALUES (?, ?, ?, ?)", (dni_encontrado, hoy, hora, estado))
                                conn.commit()
                                registrar_auditoria(st.session_state.user, f"Registro manual DNI {dni_encontrado} - {estado}")
                                st.success(f"✔ Registrado correctamente como **{estado}**")
                                st.rerun()
                        with b2:
                            if st.button("Registrar Falta", use_container_width=True):
                                cursor.execute("INSERT INTO asistencias (dni, fecha, hora, estado) VALUES (?, ?, ?, 'Falta')", (dni_encontrado, hoy, hora))
                                conn.commit()
                                registrar_auditoria(st.session_state.user, f"Registro manual falta DNI {dni_encontrado}")
                                st.error("❌ Registrado como **Falta**")
                                st.rerun()
                else:
                    st.info("No hay alumnos registrados en esta sección.")
            else:
                st.warning("⚠️ No hay alumnos cargados en la base de datos.")
            conn.close()

# --- TAB: SEMÁFORO DE AULA ---
idx_ctrl = 1 if st.session_state.rol in ["Directivo", "Auxiliar de Puerta"] else 0
with tabs[idx_ctrl]:
    st.markdown("#### Semáforo y Consolidado de Asistencias")
    st.markdown("<p style='color: #6b7280; font-size: 13px;'>Monitoreo de incidencias, tardanzas y faltas acumuladas por estudiante.</p>", unsafe_allow_html=True)
    
    conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
    
    if st.session_state.rol == "Docente":
        secciones_disponibles = [st.session_state.seccion]
    else:
        df_grados = pd.read_sql("SELECT DISTINCT grado_seccion FROM alumnos", conn)
        secciones_disponibles = df_grados["grado_seccion"].tolist() if not df_grados.empty else []
        
    if secciones_disponibles:
        seccion_sel = st.selectbox("Seleccione Aula a Consultar:", secciones_disponibles)
        alumnos_aula = pd.read_sql("SELECT dni, nombres, apellidos FROM alumnos WHERE grado_seccion = ? ORDER BY apellidos ASC", conn, params=(seccion_sel,))
        
        if not alumnos_aula.empty:
            data_tabla = []
            for _, r in alumnos_aula.iterrows():
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM asistencias WHERE dni = ? AND estado IN ('Puntual', 'Tardanza')", (r['dni'],))
                asistidos = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM asistencias WHERE dni = ? AND estado = 'Tardanza'", (r['dni'],))
                tardanzas = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM asistencias WHERE dni = ? AND estado = 'Falta'", (r['dni'],))
                faltas = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM justificaciones WHERE dni = ?", (r['dni'],))
                justs = cursor.fetchone()[0]
                
                efectivas = max(0, faltas - justs)
                semaforo = "🟢 Normal" if efectivas == 0 else ("🟡 Alerta (1)" if efectivas == 1 else ("🟠 Riesgo (2)" if efectivas == 2 else "🔴 Peligro (3+)"))
                
                data_tabla.append({
                    "Apellidos y Nombres": f"{r['apellidos']}, {r['nombres']}",
                    "Asistencias": asistidos,
                    "Tardanzas": tardanzas,
                    "Faltas Totales": faltas,
                    "Permisos / Justif.": justs,
                    "Faltas Efectivas": efectivas,
                    "Estado": semaforo
                })
            
            df_resumen = pd.DataFrame(data_tabla)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(df_resumen, use_container_width=True)
        else:
            st.info("No se encontraron alumnos en esta sección.")
    else:
        st.warning("⚠️ No hay secciones disponibles.")
    conn.close()

# --- TAB: REPORTE DIARIO ---
idx_rep = 2 if st.session_state.rol in ["Directivo", "Auxiliar de Puerta"] else 1
with tabs[idx_rep]:
    st.markdown("#### Reporte Diario de Asistencia")
    st.markdown("<p style='color: #6b7280; font-size: 13px;'>Consulta de registros filtrados por fecha y sección específica.</p>", unsafe_allow_html=True)
    
    conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_reporte = st.date_input("Fecha de Consulta", value=datetime.now())
    fecha_str = fecha_reporte.strftime("%Y-%m-%d")
    
    df_sec_rep = pd.read_sql("SELECT DISTINCT grado_seccion FROM alumnos ORDER BY grado_seccion", conn)
    lista_secciones_rep = ["TODAS LAS SECCIONES"] + (df_sec_rep["grado_seccion"].tolist() if not df_sec_rep.empty else [])
    
    with col_f2:
        seccion_filtro_rep = st.selectbox("Sección", lista_secciones_rep)
    
    if seccion_filtro_rep == "TODAS LAS SECCIONES":
        query_reporte = """
            SELECT a.dni, al.nombres, al.apellidos, al.grado_seccion, a.hora, a.estado 
            FROM asistencias a 
            JOIN alumnos al ON a.dni = al.dni 
            WHERE a.fecha = ?
            ORDER BY a.hora DESC
        """
        df_asistentes = pd.read_sql(query_reporte, conn, params=(fecha_str,))
    else:
        query_reporte = """
            SELECT a.dni, al.nombres, al.apellidos, al.grado_seccion, a.hora, a.estado 
            FROM asistencias a 
            JOIN alumnos al ON a.dni = al.dni 
            WHERE a.fecha = ? AND al.grado_seccion = ?
            ORDER BY a.hora DESC
        """
        df_asistentes = pd.read_sql(query_reporte, conn, params=(fecha_str, seccion_filtro_rep))
        
    conn.close()
    
    st.markdown("<br>", unsafe_allow_html=True)
    if not df_asistentes.empty:
        st.markdown(f"**Total de registros encontrados:** {len(df_asistentes)}")
        st.dataframe(df_asistentes, use_container_width=True)
    else:
        st.info(f"ℹ️ No se registraron asistencias para la fecha {fecha_str} con el filtro seleccionado.")

# --- TAB: PERMISOS Y JUSTIFICACIONES ---
idx_just = 3 if st.session_state.rol in ["Directivo", "Auxiliar de Puerta"] else 2
with tabs[idx_just]:
    st.markdown("#### Registro de Permisos y Justificaciones")
    st.markdown("<p style='color: #6b7280; font-size: 13px;'>Justifique inasistencias o permisos formales de los estudiantes.</p>", unsafe_allow_html=True)
    
    conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
    df_all = pd.read_sql("SELECT dni, nombres, apellidos, grado_seccion FROM alumnos ORDER BY apellidos ASC", conn)
    
    if not df_all.empty:
        with st.form("form_justif"):
             df_all["nombre_completo"] = df_all["apellidos"] + ", " + df_all["nombres"] + " (" + df_all["grado_seccion"] + " - DNI: " + df_all["dni"] + ")"
             alumno_elegido = st.selectbox("Estudiante:", df_all["nombre_completo"].tolist())
             fecha_j = st.date_input("Fecha a Justificar")
             motivo_j = st.text_input("Motivo del Permiso / Justificación", placeholder="Ej: Cita médica documentada, permiso institucional...")
             
             st.markdown("<br>", unsafe_allow_html=True)
             btn_j = st.form_submit_button("Guardar Justificación", use_container_width=True)
             
             if btn_j:
                 dni_extraido = alumno_elegido.split("DNI: ")[-1].replace(")", "").strip()
                 cursor = conn.cursor()
                 cursor.execute("INSERT INTO justificaciones (dni, fecha, motivo, registrado_por) VALUES (?, ?, ?, ?)",
                                (dni_extraido, str(fecha_j), motivo_j, st.session_state.user))
                 conn.commit()
                 registrar_auditoria(st.session_state.user, f"Registró permiso/justificación DNI {dni_extraido}")
                 st.success("¡Justificación registrada y aplicada correctamente en el sistema!")
                 st.rerun()
                 
        # --- NUEVA SECCIÓN: HISTORIAL DETALLADO DE JUSTIFICACIONES ---
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 📄 Historial Detallado de Permisos Registrados")
        st.markdown("<p style='color: #6b7280; font-size: 13px;'>Listado completo de todas las justificaciones con sus respectivos motivos.</p>", unsafe_allow_html=True)
        
        df_historial_j = pd.read_sql("""
            SELECT j.fecha AS 'Fecha Permiso', 
                   a.apellidos AS 'Apellidos', 
                   a.nombres AS 'Nombres', 
                   a.grado_seccion AS 'Sección', 
                   j.motivo AS 'Motivo / Detalle', 
                   j.registrado_por AS 'Registrado Por'
            FROM justificaciones j 
            JOIN alumnos a ON j.dni = a.dni 
            ORDER BY j.id DESC
        """, conn)
        
        if not df_historial_j.empty:
            st.dataframe(df_historial_j, use_container_width=True)
        else:
            st.info("No hay permisos o justificaciones registradas en el sistema.")
    else:
        st.warning("⚠️ No hay alumnos cargados en la base de datos.")
    conn.close()

# --- TAB: CARNETS Y CÓDIGOS QR ---
if st.session_state.rol in ["Directivo", "Auxiliar de Puerta"]:
    with tabs[4]:
        st.markdown("#### Generador de Carnets Escolares (QR)")
        st.markdown("<p style='color: #6b7280; font-size: 13px;'>Visualice y descargue los códigos QR individuales por sección.</p>", unsafe_allow_html=True)
        
        conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
        df_sec_qr = pd.read_sql("SELECT DISTINCT grado_seccion FROM alumnos ORDER BY grado_seccion", conn)
        
        if not df_sec_qr.empty:
            seccion_qr = st.selectbox("Seleccione Sección para Carnets:", df_sec_qr["grado_seccion"].tolist())
            alumnos_qr = pd.read_sql("SELECT dni, nombres, apellidos, grado_seccion FROM alumnos WHERE grado_seccion = ? ORDER BY apellidos ASC", conn, params=(seccion_qr,))
            
            if not alumnos_qr.empty:
                st.markdown(f"<br>Mostrando {len(alumnos_qr)} carnets para la sección **{seccion_qr}**:", unsafe_allow_html=True)
                st.divider()
                
                for _, row in alumnos_qr.iterrows():
                    with st.container():
                        qr = qrcode.QRCode(version=1, box_size=4, border=2)
                        qr.add_data(row['dni'])
                        qr.make(fit=True)
                        img_qr = qr.make_image(fill_color="black", back_color="white")
                        
                        buffered = BytesIO()
                        img_qr.save(buffered, format="PNG")
                        
                        col_img, col_info = st.columns([1, 3])
                        col_img.image(buffered.getvalue(), width=110)
                        col_info.markdown(f"**{row['apellidos']}, {row['nombres']}**")
                        col_info.markdown(f"DNI: `{row['dni']}` | Sección: `{row['grado_seccion']}`")
                        st.divider()
            else:
                st.info("No hay alumnos en esta sección.")
        else:
            st.warning("⚠️ No hay padrón cargado en el sistema.")
        conn.close()

# --- TAB: ADMINISTRACIÓN Y GESTIÓN DE USUARIOS ---
if st.session_state.rol == "Directivo":
    with tabs[5]:
        st.markdown("#### Panel de Administración y Seguridad")
        st.markdown("<p style='color: #6b7280; font-size: 13px;'>Gestión de accesos, credenciales de usuarios, padrón de alumnos y auditoría.</p>", unsafe_allow_html=True)
        st.divider()
        
        # --- SUBSECCIÓN 1: CREAR NUEVO USUARIO ---
        st.markdown("##### 👤 Crear Nuevo Usuario")
        with st.form("form_crear_usuario"):
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                nuevo_user = st.text_input("Nombre de Usuario (Login)").strip()
                nuevo_rol = st.selectbox("Rol Institucional", ["Directivo", "Auxiliar de Puerta", "Docente"])
            with col_u2:
                nuevo_pass = st.text_input("Contraseña Temporal", type="password")
                
                conn_u = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
                df_sec_u = pd.read_sql("SELECT DISTINCT grado_seccion FROM alumnos", conn_u)
                conn_u.close()
                lista_secs = ["TODAS"] + (df_sec_u["grado_seccion"].tolist() if not df_sec_u.empty else [])
                nueva_seccion = st.selectbox("Sección Asignada (Usar 'TODAS' para Directivos/Auxiliares)", lista_secs)
            
            st.markdown("<br>", unsafe_allow_html=True)
            btn_crear_user = st.form_submit_button("Registrar Usuario en el Sistema", use_container_width=True)
            
            if btn_crear_user:
                if not nuevo_user or not nuevo_pass:
                    st.error("❌ El nombre de usuario y la contraseña no pueden estar vacíos.")
                else:
                    pass_cifrada = hashlib.sha256(nuevo_pass.encode()).hexdigest()
                    try:
                        conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO usuarios (username, password, rol, seccion_asignada) VALUES (?, ?, ?, ?)",
                                       (nuevo_user, pass_cifrada, nuevo_rol, nueva_seccion))
                        conn.commit()
                        conn.close()
                        registrar_auditoria(st.session_state.user, f"Creó usuario: {nuevo_user} (Rol: {nuevo_rol})")
                        st.success(f"✔ Usuario **{nuevo_user}** registrado de forma exitosa.")
                    except sqlite3.IntegrityError:
                        st.error(f"❌ El usuario **{nuevo_user}** ya se encuentra registrado.")
        
        st.divider()
        
        # --- SUBSECCIÓN 2: CAMBIAR CONTRASEÑA ---
        st.markdown("##### 🔑 Actualizar Contraseña de Usuario")
        with st.form("form_cambiar_pass"):
            conn_pass = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
            df_users = pd.read_sql("SELECT username FROM usuarios", conn_pass)
            conn_pass.close()
            
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                user_a_cambiar = st.selectbox("Seleccionar Usuario", df_users["username"].tolist())
            with col_p2:
                nueva_pass_text = st.text_input("Nueva Contraseña", type="password")
                
            st.markdown("<br>", unsafe_allow_html=True)
            btn_cambiar = st.form_submit_button("Actualizar Credenciales", use_container_width=True)
            
            if btn_cambiar:
                if not nueva_pass_text:
                    st.error("❌ La nueva contraseña no puede estar vacía.")
                else:
                    pass_nueva_cifrada = hashlib.sha256(nueva_pass_text.encode()).hexdigest()
                    conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE usuarios SET password = ? WHERE username = ?", (pass_nueva_cifrada, user_a_cambiar))
                    conn.commit()
                    conn.close()
                    registrar_auditoria(st.session_state.user, f"Actualizó contraseña del usuario: {user_a_cambiar}")
                    st.success(f"✔ Contraseña del usuario **{user_a_cambiar}** actualizada correctamente.")

        st.divider()
        
        # --- SUBSECCIÓN 3: LISTADO DE USUARIOS Y CARGA DE PADRÓN ---
        st.markdown("##### 👥 Usuarios Activos")
        conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
        df_usuarios = pd.read_sql("SELECT username, rol, seccion_asignada FROM usuarios", conn)
        st.dataframe(df_usuarios, use_container_width=True)
        conn.close()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 📥 Importación del Padrón de Alumnos (Excel)")
        archivo_excel = st.file_uploader("Sube el archivo Excel (.xlsx) con columnas exactas: dni, nombres, apellidos, grado_seccion", type=["xlsx"])
        if archivo_excel:
            try:
                df_subido = pd.read_excel(archivo_excel)
                conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
                df_subido.to_sql("alumnos", conn, if_exists="append", index=False)
                
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM alumnos")
                total = cursor.fetchone()[0]
                conn.close()
                
                registrar_auditoria(st.session_state.user, f"Importó padrón. Total: {total} alumnos")
                st.success(f"✔ Padrón importado con éxito. Total actual de alumnos: **{total}**.")
            except Exception as e:
                st.error(f"Error al procesar el archivo. Verifique que las columnas sean: dni, nombres, apellidos, grado_seccion. Detalle técnico: {e}")
                
        st.divider()
        st.markdown("##### 📊 Registro de Auditoría del Sistema")
        conn = sqlite3.connect("asistencia_enterprise.db", check_same_thread=False)
        df_audit = pd.read_sql("SELECT * FROM auditoria ORDER BY id DESC LIMIT 25", conn)
        st.dataframe(df_audit, use_container_width=True)
        conn.close()
