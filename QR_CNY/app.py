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


# =====================================================================
# CAPA DE CONEXIÓN A BASE DE DATOS (CENTRALIZADA)
# =====================================================================
def obtener_conexion():
    """Conecta a la base de datos remota (Turso) si las credenciales están

    configuradas en st.secrets, o utiliza SQLite local como respaldo.
    """
    try:
        if "TURSO_DATABASE_URL" in st.secrets and "TURSO_AUTH_TOKEN" in st.secrets:
            import libsql_client
            url = st.secrets["TURSO_DATABASE_URL"]
            auth_token = st.secrets["TURSO_AUTH_TOKEN"]
            # Si usas el cliente libsql de Turso:
            conn = libsql_client.connect(url=url, auth_token=auth_token)
            return conn
    except Exception:
        pass

    # Respaldo local SQLite
    db_path = st.secrets.get("DB_PATH", "asistencia_enterprise.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return conn


# =====================================================================
# INICIALIZACIÓN DE LA BASE DE DATOS Y TABLAS
# =====================================================================
def inicializar_bd():
    conn = obtener_conexion()
    cursor = conn.cursor()

    tablas = [
        """
        CREATE TABLE IF NOT EXISTS alumnos (
            dni TEXT PRIMARY KEY,
            nombres TEXT NOT NULL,
            apellidos TEXT NOT NULL,
            grado_seccion TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS asistencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni TEXT,
            fecha TEXT,
            hora TEXT,
            estado TEXT,
            FOREIGN KEY (dni) REFERENCES alumnos (dni)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            accion TEXT,
            fecha_hora TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            password TEXT,
            rol TEXT,
            nombres_completos TEXT
        )
        """,
    ]

    for tabla_sql in tablas:
        try:
            cursor.execute(tabla_sql)
        except Exception:
            pass

    # Crear usuarios por defecto si la tabla está vacía
    try:
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        res = cursor.fetchone()
        count = res[0] if res else 0
        if count == 0:
            cursor.executemany(
                "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
                [
                    ("admin", "admin2026", "Directivo", "Administrador General"),
                    ("puerta", "puerta2026", "Auxiliar de Puerta", "Auxiliar de Turno"),
                ],
            )
            try:
                conn.commit()
            except Exception:
                pass
    except Exception:
        pass

    try:
        conn.close()
    except Exception:
        pass


inicializar_bd()


# =====================================================================
# FUNCIONES AUXILIARES Y DE NEGOCIO
# =====================================================================
def registrar_auditoria(usuario, accion):
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO auditoria (usuario, accion, fecha_hora) VALUES (?, ?, ?)",
            (usuario, accion, ahora),
        )
        try:
            conn.commit()
        except Exception:
            pass
        conn.close()
    except Exception:
        pass


def procesar_registro_asistencia(dni_limpio, origen_accion):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT nombres, apellidos, grado_seccion FROM alumnos WHERE dni = ?",
        (dni_limpio,),
    )
    alumno = cursor.fetchone()

    if not alumno:
        conn.close()
        return (
            False,
            f"❌ El DNI `{dni_limpio}` no está registrado en el padrón institucional.",
        )

    hoy = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M:%S")

    # Validación anti-duplicados en el día
    cursor.execute(
        "SELECT hora, estado FROM asistencias WHERE dni = ? AND fecha = ?",
        (dni_limpio, hoy),
    )
    existente = cursor.fetchone()

    if existente:
        conn.close()
        return (
            False,
            f"⚠️ El alumno **{alumno[1]}, {alumno[0]}** ({alumno[2]}) **ya marcó asistencia hoy** a las `{existente[0]}` [{existente[1]}].",
        )

    estado = "Puntual" if hora <= "08:15:00" else "Tardanza"
    cursor.execute(
        "INSERT INTO asistencias (dni, fecha, hora, estado) VALUES (?, ?, ?, ?)",
        (dni_limpio, hoy, hora, estado),
    )
    try:
        conn.commit()
    except Exception:
        pass
    conn.close()

    registrar_auditoria(
        st.session_state.user, f"{origen_accion} DNI {dni_limpio} [{estado}]"
    )
    return (
        True,
        f"✔ **Asistencia Registrada [{estado.upper()}]**: {alumno[1]}, {alumno[0]} — *{alumno[2]}* ({hora})",
    )


# --- GENERADOR DE PDF: REPORTE DIARIO DE ASISTENCIA ---
def generar_pdf_reporte_diario(df_datos, fecha_str):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elementos = []
        estilos = getSampleStyleSheet()

        elementos.append(Paragraph("<b>INSTITUCIÓN EDUCATIVA YARINACOCHA</b>", estilos["Heading1"]))
        elementos.append(Paragraph(f"<b>Reporte Consolidado de Asistencia - Fecha: {fecha_str}</b>", estilos["Normal"]))
        elementos.append(Spacer(1, 15))

        if not df_datos.empty:
            data = [["DNI", "Apellidos", "Nombres", "Grado/Secc", "Fecha", "Hora", "Estado"]]
            for _, row in df_datos.iterrows():
                data.append([str(row["dni"]), str(row["apellidos"]), str(row["nombres"]), str(row["grado_seccion"]), str(row["fecha"]), str(row["hora"]), str(row["estado"])])

            t = Table(data, colWidths=[65, 110, 110, 80, 70, 60, 65])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ]))
            elementos.append(t)
        else:
            elementos.append(Paragraph("No hay registros de asistencia para la fecha seleccionada.", estilos["Normal"]))

        doc.build(elementos)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error al generar PDF: {e}")
        return None


# --- GENERADOR DE PDF: CARNETS ESCOLARES POR SECCIÓN ---
def generar_pdf_carnets_seccion(df_alumnos_seccion, seccion):
    try:
        import qrcode
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
        elementos = []
        estilos = getSampleStyleSheet()

        elementos.append(Paragraph(f"<b>Carnets Escolares - Sección: {seccion}</b>", estilos["Heading2"]))
        elementos.append(Spacer(1, 10))

        tabla_carnets = []
        fila_actual = []

        for _, alumno in df_alumnos_seccion.iterrows():
            dni = str(alumno["dni"])
            nombres = str(alumno["nombres"])
            apellidos = str(alumno["apellidos"])
            gr_sec = str(alumno["grado_seccion"])

            qr = qrcode.QRCode(version=1, box_size=3, border=1)
            qr.add_data(dni)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white")
            qr_io = BytesIO()
            img_qr.save(qr_io, format="PNG")
            qr_io.seek(0)

            qr_img_rl = RLImage(qr_io, width=70, height=70)

            contenido_carnet = [
                Paragraph("<b>I.E. YARINACOCHA</b>", ParagraphStyle('C1', parent=estilos['Normal'], fontSize=8, alignment=1, textColor=colors.HexColor('#1e3a8a'))),
                Paragraph("Control de Asistencia", ParagraphStyle('C2', parent=estilos['Normal'], fontSize=6, alignment=1, textColor=colors.gray)),
                Spacer(1, 4),
                qr_img_rl,
                Spacer(1, 4),
                Paragraph(f"<b>{apellidos}</b>", ParagraphStyle('C3', parent=estilos['Normal'], fontSize=8, alignment=1)),
                Paragraph(f"{nombres}", ParagraphStyle('C4', parent=estilos['Normal'], fontSize=7, alignment=1)),
                Paragraph(f"<b>DNI:</b> {dni} | <b>{gr_sec}</b>", ParagraphStyle('C5', parent=estilos['Normal'], fontSize=6, alignment=1, textColor=colors.darkblue)),
            ]

            t_card = Table([[contenido_carnet]], colWidths=[160], rowHeights=[135])
            t_card.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e3a8a")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))

            fila_actual.append(t_card)
            if len(fila_actual) == 3:
                tabla_carnets.append(fila_actual)
                fila_actual = []

        if fila_actual:
            while len(fila_actual) < 3:
                fila_actual.append("")
            tabla_carnets.append(fila_actual)

        if tabla_carnets:
            t_grid = Table(tabla_carnets, colWidths=[180, 180, 180])
            t_grid.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            elementos.append(t_grid)

        doc.build(elementos)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error al generar carnets en PDF: {e}")
        return None


# =====================================================================
# GESTIÓN DE SESIÓN
# =====================================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "user" not in st.session_state:
    st.session_state.user = ""
if "rol" not in st.session_state:
    st.session_state.rol = ""

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center; color: #1e3a8a;'>🏫 Control de Asistencia - I.E. Yarinacocha</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6b7280;'>Inicie sesión con sus credenciales institucionales</p>", unsafe_allow_html=True)

    _, col_centro, _ = st.columns([1, 1.5, 1])
    with col_centro:
        with st.form("login_form"):
            usuario_input = st.text_input("Usuario o DNI")
            password_input = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Ingresar al Sistema", use_container_width=True)

            if submit_login:
                conn = obtener_conexion()
                cursor = conn.cursor()
                
                # AQUÍ ESTÁ EL CAMBIO: Usamos 'username' en lugar de 'usuario' 
                # porque así se llama la columna en tu base de datos de Turso
                cursor.execute(
                    "SELECT rol, username FROM usuarios WHERE username = ? AND password = ?",
                    (usuario_input, password_input)
                )
                user_db = cursor.fetchone()
                
                try:
                    conn.close()
                except Exception:
                    pass

                if user_db:
                    st.session_state.autenticado = True
                    st.session_state.user = user_db[1]  # Guarda el username
                    st.session_state.rol = user_db[0]   # Guarda el rol
                    registrar_auditoria(st.session_state.user, f"Inicio de sesión exitoso [{user_db[0]}]")
                    st.rerun()
                elif usuario_input == "admin" and password_input == "admin2026":
                    st.session_state.autenticado = True
                    st.session_state.user = "Administrador General"
                    st.session_state.rol = "Directivo"
                    st.rerun()
                elif usuario_input == "puerta" and password_input == "puerta2026":
                    st.session_state.autenticado = True
                    st.session_state.user = "Auxiliar de Turno"
                    st.session_state.rol = "Auxiliar de Puerta"
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
    st.stop()


# --- PANEL PRINCIPAL Y MENÚ LATERAL ---
st.sidebar.title("Panel de Control")
st.sidebar.markdown(f"**Usuario:** {st.session_state.user}")
st.sidebar.markdown(f"**Rol:** `{st.session_state.rol}`")
st.sidebar.markdown("---")

if st.sidebar.button("Cerrar Sesión", use_container_width=True):
    registrar_auditoria(st.session_state.user, "Cierre de sesión.")
    st.session_state.autenticado = False
    st.session_state.user = ""
    st.session_state.rol = ""
    st.rerun()

st.markdown("### Sistema Integral de Gestión de Asistencia — I.E. Yarinacocha")
st.markdown("---")

# Definición de Pestañas según el Rol
if st.session_state.rol == "Directivo":
    tabs = st.tabs([
        "🚪 Puerta y Registro",
        "📥 Importar Padrón",
        "📊 Reportes y Semáforo",
        "🪪 Carnets Escolares",
        "📋 Auditoría y Usuarios"
    ])
else:
    tabs = st.tabs(["🚪 Puerta y Registro", "📊 Reportes y Semáforo"])


# =====================================================================
# TAB 0: PUERTA Y REGISTRO (CÁMARA QR / MANUAL / SECCIÓN)
# =====================================================================
with tabs[0]:
    st.markdown("#### Módulo de Control de Acceso en Puerta")
    modo_registro = st.radio(
        "Método de registro:",
        ["📷 Cámara (QR)", "🔍 Pistola / DNI Manual", "🏫 Búsqueda por Sección"],
        horizontal=True,
        label_visibility="collapsed"
    )
    st.markdown("<br>", unsafe_allow_html=True)

    if modo_registro == "📷 Cámara (QR)":
        st.info("📱 Apunte con la cámara al código QR del carnet escolar.")
        foto_qr = st.camera_input("Apunta la cámara al QR")

        if foto_qr is not None:
            try:
                import cv2
                import numpy as np
                from pyzbar.pyzbar import decode

                np_arr = np.frombuffer(foto_qr.getvalue(), np.uint8)
                imagen_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                codigos_qr = decode(imagen_cv)

                if codigos_qr:
                    dni_scan = codigos_qr[0].data.decode("utf-8").strip()
                    exito, mensaje = procesar_registro_asistencia(dni_scan, "Cámara QR")
                    st.success(mensaje) if exito else st.warning(mensaje)
                else:
                    st.warning("⚠️ No se detectó ningún código QR nítido.")
            except ImportError:
                st.error("⚠️ Faltan librerías: instale `pip install opencv-python-headless pyzbar`")

    elif modo_registro == "🔍 Pistola / DNI Manual":
        dni_scan = st.text_input("Ingrese o pistolee el DNI:", placeholder="Ej: 71234567")
        if dni_scan:
            exito, mensaje = procesar_registro_asistencia(dni_scan.strip(), "Manual DNI")
            st.success(mensaje) if exito else st.warning(mensaje)

    else:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT grado_seccion FROM alumnos ORDER BY grado_seccion ASC")
        grados_db = [row[0] for row in cursor.fetchall()]
        try:
            conn.close()
        except Exception:
            pass

        if grados_db:
            seccion_sel = st.selectbox("Seleccione Grado y Sección:", grados_db)
            conn = obtener_conexion()
            df_sec = pd.read_sql("SELECT dni, nombres, apellidos FROM alumnos WHERE grado_seccion = ? ORDER BY apellidos ASC", conn, params=(seccion_sel,))
            try:
                conn.close()
            except Exception:
                pass

            if not df_sec.empty:
                for _, row in df_sec.iterrows():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.write(f"**{row['apellidos']}**, {row['nombres']} — `{row['dni']}`")
                    with c2:
                        if st.button("Marcar Asistencia", key=f"m_{row['dni']}", use_container_width=True):
                            exito, mensaje = procesar_registro_asistencia(row["dni"], "Marcación por sección")
                            st.success(mensaje) if exito else st.warning(mensaje)
                            if exito: st.rerun()
            else:
                st.info("No hay alumnos en esta sección.")
        else:
            st.warning("⚠️ Padrón vacío. Importe alumnos primero.")


# =====================================================================
# TAB 1 (DIRECTIVO): IMPORTAR PADRÓN DESDE EXCEL Y ELIMINAR ALUMNOS
# =====================================================================
if st.session_state.rol == "Directivo":
    with tabs[1]:
        st.markdown("#### 📥 Importar Padrón de Alumnos (.xlsx)")
        archivo_subido = st.file_uploader("Seleccione el Excel oficial", type=["xlsx", "xls"])

        if archivo_subido is not None:
            try:
                df = pd.read_excel(archivo_subido)
                st.dataframe(df.head(3), use_container_width=True)

                df.columns = df.columns.str.strip().str.lower().str.normalize("NFKD").str.encode("ascii", errors="ignore").str.decode("utf-8")
                req = ["dni", "nombres", "apellidos", "grado_seccion"]

                if all(col in df.columns for col in req):
                    if st.button("💾 Guardar en Base de Datos"):
                        conn = obtener_conexion()
                        cursor = conn.cursor()
                        exitos, duplicados = 0, 0

                        for _, row in df.iterrows():
                            dni = str(row["dni"]).strip()
                            if dni and dni != "nan":
                                try:
                                    cursor.execute("INSERT OR IGNORE INTO alumnos (dni, nombres, apellidos, grado_seccion) VALUES (?, ?, ?, ?)",
                                                   (dni, str(row["nombres"]).strip(), str(row["apellidos"]).strip(), str(row["grado_seccion"]).strip()))
                                    if cursor.rowcount > 0: exitos += 1
                                    else: duplicados += 1
                                except Exception: pass
                        try:
                            conn.commit()
                        except Exception:
                            pass
                        try:
                            conn.close()
                        except Exception:
                            pass

                        registrar_auditoria(st.session_state.user, f"Importación de padrón: {exitos} alumnos.")
                        st.success(f"✅ Importación exitosa. Nuevos: {exitos} | Duplicados omitidos: {duplicados}")
                else:
                    st.error("❌ El Excel debe contener: dni, nombres, apellidos, grado_seccion")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

        st.markdown("---")
        st.markdown("#### 🗑️ Gestión y Eliminación de Alumnos del Padrón")
        conn = obtener_conexion()
        df_alumnos_todos = pd.read_sql("SELECT dni, nombres, apellidos, grado_seccion FROM alumnos ORDER BY grado_seccion, apellidos ASC", conn)
        try:
            conn.close()
        except Exception:
            pass

        if not df_alumnos_todos.empty:
            busqueda_alumno = st.text_input("🔍 Buscar alumno por DNI o Apellidos para eliminar:", placeholder="Escriba para filtrar...")
            if busqueda_alumno:
                df_filtrado = df_alumnos_todos[
                    df_alumnos_todos['dni'].str.contains(busqueda_alumno, case=False, na=False) |
                    df_alumnos_todos['apellidos'].str.contains(busqueda_alumno, case=False, na=False)
                ]
            else:
                df_filtrado = df_alumnos_todos.head(10) # Mostrar los primeros 10 por rendimiento

            st.write(f"Mostrando {len(df_filtrado)} alumnos:")
            for _, al_row in df_filtrado.iterrows():
                col_a1, col_a2 = st.columns([3, 1])
                with col_a1:
                    st.write(f"**{al_row['apellidos']}**, {al_row['nombres']} — DNI: `{al_row['dni']}` | Sección: *{al_row['grado_seccion']}*")
                with col_a2:
                    if st.button("🗑️ Eliminar Alumno", key=f"del_al_{al_row['dni']}"):
                        conn = obtener_conexion()
                        cur = conn.cursor()
                        # Borrar asistencias asociadas primero para evitar conflictos de llave foránea
                        cur.execute("DELETE FROM asistencias WHERE dni = ?", (al_row['dni'],))
                        cur.execute("DELETE FROM alumnos WHERE dni = ?", (al_row['dni'],))
                        try:
                            conn.commit()
                        except Exception:
                            pass
                        try:
                            conn.close()
                        except Exception:
                            pass
                        registrar_auditoria(st.session_state.user, f"Eliminó al alumno DNI: {al_row['dni']}")
                        st.success(f"Alumno con DNI {al_row['dni']} eliminado correctamente.")
                        st.rerun()
        else:
            st.info("No hay alumnos registrados en el padrón.")


# =====================================================================
# SECCIÓN DE REPORTES, SEMÁFORO Y ELIMINACIÓN DE ASISTENCIAS
# =====================================================================
idx_rep = 2
with tabs[idx_rep]:
    st.markdown("#### 📊 Reportes de Asistencia, Semáforo y Control de Registros")

    f_fecha = st.date_input("Seleccione fecha de consulta:", value=datetime.now().date())
    f_str = f_fecha.strftime("%Y-%m-%d")

    conn = obtener_conexion()
    query = """
        SELECT ast.id, a.dni, a.apellidos, a.nombres, a.grado_seccion, ast.fecha, ast.hora, ast.estado
        FROM asistencias ast
        JOIN alumnos a ON ast.dni = a.dni
        WHERE ast.fecha = ?
        ORDER BY ast.hora DESC
    """
    df_rep = pd.read_sql(query, conn, params=(f_str,))
    try:
        conn.close()
    except Exception:
        pass

    # --- SEMÁFORO DE AULAS ---
    st.markdown("##### 🚦 Semáforo de Asistencia por Aulas (Hoy)")
    conn = obtener_conexion()
    query_semaforo = """
        SELECT 
            al.grado_seccion,
            COUNT(DISTINCT al.dni) as total_alumnos,
            SUM(CASE WHEN ast.id IS NOT NULL THEN 1 ELSE 0 END) as asistentes
        FROM alumnos al
        LEFT JOIN asistencias ast ON al.dni = ast.dni AND ast.fecha = ?
        GROUP BY al.grado_seccion
        ORDER BY al.grado_seccion ASC
    """
    df_sem = pd.read_sql(query_semaforo, conn, params=(f_str,))
    try:
        conn.close()
    except Exception:
        pass

    if not df_sem.empty:
        cols = st.columns(min(len(df_sem), 4))
        for i, row in df_sem.iterrows():
            total = row["total_alumnos"]
            asistentes = row["asistentes"]
            pct = (asistentes / total * 100) if total > 0 else 0

            color_bg = "#dcfce7" if pct >= 80 else ("#fef9c3" if pct >= 50 else "#fee2e2")
            borde_color = "#16a34a" if pct >= 80 else ("#ca8a04" if pct >= 50 else "#dc2626")

            with cols[i % len(cols)]:
                st.markdown(f"""
                    <div style="padding: 12px; border-radius: 8px; background-color: {color_bg}; border-left: 5px solid {borde_color}; margin-bottom: 10px;">
                        <b style="font-size: 15px;">{row['grado_seccion']}</b><br>
                        <span>Asistencia: <b>{asistentes}/{total}</b></span><br>
                        <span style="font-size: 12px; color: #374151;">({pct:.1f}%)</span>
                    </div>
                """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 📄 Exportar Reporte Diario y Gestión de Asistencias")
    
    if not df_rep.empty:
        st.dataframe(df_rep, use_container_width=True)

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_rep.to_excel(writer, index=False, sheet_name="Asistencia")
            st.download_button("📥 Descargar Excel", data=output.getvalue(), file_name=f"asistencia_{f_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        with col_b2:
            pdf_bytes = generar_pdf_reporte_diario(df_rep, f_str)
            if pdf_bytes:
                st.download_button("📥 Descargar Reporte en PDF", data=pdf_bytes, file_name=f"reporte_asistencia_{f_str}.pdf", mime="application/pdf", use_container_width=True)

        # ELIMINAR REGISTROS DE ASISTENCIA ERRÓNEOS (Solo Directivo)
        if st.session_state.rol == "Directivo":
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("🗑️ Eliminar un registro de asistencia específico (Corrección)"):
                asistencia_a_borrar = st.selectbox(
                    "Seleccione el registro de asistencia a eliminar:",
                    options=df_rep['id'].tolist(),
                    format_func=lambda x: f"ID: {x} - {df_rep[df_rep['id']==x]['apellidos'].values[0]}, {df_rep[df_rep['id']==x]['nombres'].values[0]} ({df_rep[df_rep['id']==x]['hora'].values[0]})"
                )
                if st.button("Eliminar Registro Seleccionado"):
                    conn = obtener_conexion()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM asistencias WHERE id = ?", (asistencia_a_borrar,))
                    try:
                        conn.commit()
                    except Exception:
                        pass
                    try:
                        conn.close()
                    except Exception:
                        pass
                    registrar_auditoria(st.session_state.user, f"Eliminó el registro de asistencia ID: {asistencia_a_borrar}")
                    st.success("✅ Registro de asistencia eliminado correctamente.")
                    st.rerun()
    else:
        st.info("ℹ️ No hay registros para la fecha seleccionada.")


# =====================================================================
# TAB 3 (DIRECTIVO): EXPORTAR CARNETS POR SECCIÓN
# =====================================================================
if st.session_state.rol == "Directivo":
    with tabs[3]:
        st.markdown("#### 🪪 Impresión Masiva de Carnets con QR")
        st.markdown("Seleccione una sección para generar el documento PDF con todos los carnets de los estudiantes listos para recortar.")

        conn = obtener_conexion()
        cur_c = conn.cursor()
        cur_c.execute("SELECT DISTINCT grado_seccion FROM alumnos ORDER BY grado_seccion ASC")
        secciones_c = [r[0] for r in cur_c.fetchall()]
        try:
            conn.close()
        except Exception:
            pass

        if secciones_c:
            secc_elegida = st.selectbox("Seleccione la Sección para Carnets:", secciones_c, key="sel_sec_carnets")
            
            conn = obtener_conexion()
            df_carnets = pd.read_sql("SELECT dni, nombres, apellidos, grado_seccion FROM alumnos WHERE grado_seccion = ? ORDER BY apellidos ASC", conn, params=(secc_elegida,))
            try:
                conn.close()
            except Exception:
                pass

            st.write(f"Estudiantes en la sección **{secc_elegida}**: {len(df_carnets)}")

            if not df_carnets.empty:
                if st.button("📄 Generar PDF de Carnets de la Sección", type="primary"):
                    with st.spinner("Generando códigos QR y armando diseño PDF..."):
                        pdf_carnets = generar_pdf_carnets_seccion(df_carnets, secc_elegida)
                        if pdf_carnets:
                            st.success("✅ ¡Carnets generados con éxito!")
                            st.download_button(
                                label="📥 Descargar Carnets en PDF",
                                data=pdf_carnets,
                                file_name=f"carnets_{secc_elegida.replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
            else:
                st.info("No hay alumnos en esta sección.")
        else:
            st.warning("No hay secciones registradas en el sistema.")


# =====================================================================
# TAB 4 / ÚLTIMA (DIRECTIVO): AUDITORÍA Y GESTIÓN DE USUARIOS
# =====================================================================
if st.session_state.rol == "Directivo":
    with tabs[4]:
        st.markdown("#### ⚙️ Gestión de Usuarios y Accesos")
        
        with st.form("nuevo_usuario_form"):
            st.markdown("##### Registrar nuevo operador")
            n_user = st.text_input("Usuario (Login)")
            n_pass = st.text_input("Contraseña", type="password")
            n_rol = st.selectbox("Rol", ["Directivo", "Auxiliar de Puerta"])
            n_nombre = st.text_input("Nombres y Apellidos completos")
            
            if st.form_submit_button("Crear Usuario"):
                if n_user and n_pass and n_nombre:
                    try:
                        conn = obtener_conexion()
                        cur = conn.cursor()
                        cur.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?)", (n_user.strip(), n_pass.strip(), n_rol, n_nombre.strip()))
                        try:
                            conn.commit()
                        except Exception:
                            pass
                        try:
                            conn.close()
                        except Exception:
                            pass
                        registrar_auditoria(st.session_state.user, f"Creó usuario: {n_user}")
                        st.success(f"✅ Usuario {n_user} creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error (quizás el usuario ya existe): {e}")
                else:
                    st.warning("Complete todos los campos.")

        st.markdown("---")
        st.markdown("##### Usuarios Actuales / Eliminar Usuario")
        conn = obtener_conexion()
        df_usr = pd.read_sql("SELECT usuario, rol, nombres_completos FROM usuarios", conn)
        try:
            conn.close()
        except Exception:
            pass

        for _, u_row in df_usr.iterrows():
            c_u1, c_u2 = st.columns([3, 1])
            with c_u1:
                st.write(f"👤 **{u_row['nombres_completos']}** (`{u_row['usuario']}`) — Rol: *{u_row['rol']}*")
            with c_u2:
                if u_row['usuario'] != "admin":
                    if st.button("🗑️ Eliminar Usuario", key=f"del_u_{u_row['usuario']}"):
                        conn = obtener_conexion()
                        cur = conn.cursor()
                        cur.execute("DELETE FROM usuarios WHERE usuario = ?", (u_row['usuario'],))
                        try:
                            conn.commit()
                        except Exception:
                            pass
                        try:
                            conn.close()
                        except Exception:
                            pass
                        registrar_auditoria(st.session_state.user, f"Eliminó al usuario: {u_row['usuario']}")
                        st.success(f"Usuario {u_row['usuario']} eliminado.")
                        st.rerun()

        st.markdown("---")
        st.markdown("#### 📋 Auditoría del Sistema")
        conn = obtener_conexion()
        df_audit = pd.read_sql("SELECT * FROM auditoria ORDER BY id DESC LIMIT 100", conn)
        try:
            conn.close()
        except Exception:
            pass
        st.dataframe(df_audit, use_container_width=True)
