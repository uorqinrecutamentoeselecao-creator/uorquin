import streamlit as st
import gspread
import requests
import re
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from user_agents import parse
import requests

st.set_page_config(page_title="Uorquin", layout="centered")

st.image("logo.png", width=220)
st.markdown("<h3 style='text-align:center'>Crie seu currículo profissional em poucos minutos</h3>", unsafe_allow_html=True)

# =========================
# LISTAS
# =========================
estados = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS",
"MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]

# =========================
# IBGE
# =========================
@st.cache_data
def buscar_cidades(uf):
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
    r = requests.get(url)
    if r.status_code == 200:
        return sorted([c["nome"] for c in r.json()])
    return []

# =========================
# FORMATADORES
# =========================
def formatar_cpf(cpf):
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) >= 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:11]}"
    return cpf

def validar_cpf_simples(cpf):
    return len(re.sub(r'\D', '', cpf)) == 11

def validar_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def formatar_telefone(tel):
    tel = re.sub(r'\D', '', tel)
    if len(tel) >= 11:
        return f"({tel[:2]}) {tel[2:7]}-{tel[7:11]}"
    return tel

def formatar_cep(cep):
    cep = re.sub(r'\D', '', cep)
    if len(cep) >= 8:
        return f"{cep[:5]}-{cep[5:8]}"
    return cep

# =========================
# FUNIL (TRACKING)
# =========================
def registrar_evento(etapa):

    agora = datetime.now()

    # 🔥 garante que lista existe
    if "eventos" not in st.session_state:
        st.session_state.eventos = []

    # 🔥 garante que existe início da etapa
    if "etapa_atual_inicio" not in st.session_state:
        st.session_state.etapa_atual_inicio = agora

    inicio = st.session_state.etapa_atual_inicio

    # 🔥 calcula duração sem microsegundos
    duracao = ""
    if inicio:
        duracao_timedelta = agora - inicio
        duracao = str(duracao_timedelta).split(".")[0]

    # 🔥 evita duplicidade da mesma etapa
    etapas_registradas = [e["etapa"] for e in st.session_state.eventos]

    if etapa not in etapas_registradas:

        st.session_state.eventos.append({
            "etapa": etapa,
            "inicio": inicio.strftime("%d/%m/%Y %H:%M:%S"),
            "fim": agora.strftime("%d/%m/%Y %H:%M:%S"),
            "duracao": duracao
        })

    # 🔥 reinicia contador da próxima etapa
    st.session_state.etapa_atual_inicio = agora

# =========================
# CAPTURA USUÁRIO
# =========================
def capturar_info_usuario():
    try:
        headers = st.context.headers

        # 🔥 evita erro se não vier header
        user_agent_str = headers.get("user-agent", "")

        from user_agents import parse
        ua = parse(user_agent_str)

        dispositivo = "Mobile" if ua.is_mobile else "Desktop"
        navegador = ua.browser.family
        sistema = ua.os.family

        ip_info = requests.get("https://ipinfo.io/json").json()

        return {
            "ip": ip_info.get("ip"),
            "cidade_ip": ip_info.get("city"),
            "estado_ip": ip_info.get("region"),
            "pais_ip": ip_info.get("country"),
            "loc": ip_info.get("loc"),
            "dispositivo": dispositivo,
            "navegador": navegador,
            "sistema": sistema
        }

    except:
        return {}
# =========================
# GOOGLE
# =========================
def conectar_planilha():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]

    # ESTA É A PARTE QUE CORRIGE O ERRO:
    # Em vez de ler um arquivo, lemos o dicionário que você colou nos Secrets
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    client = gspread.authorize(creds)
    return client.open("Banco_Uorquin").sheet1


def salvar_dados(dados):
    planilha = conectar_planilha()
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # 👉 cria cabeçalho automático (só uma vez)
    if not planilha.row_values(1):

        cabecalho = [
            "Data_Cadastro",
            "Nome","CPF","Email","Telefone","Idade",
            "Endereço","Cidade","Estado","CEP",
            "Sexo","Estado Civil","Disponibilidade",
            "Tipo Emprego","Salário","Área"
        ]

        # EXPERIÊNCIAS
        for i in range(1,5):
            cabecalho += [
                f"Empresa_{i}", f"Funcao_{i}",
                f"Inicio_{i}", f"Fim_{i}", f"Cidade_{i}"
            ]

        # ESCOLARIDADE
        for i in range(1,5):
            cabecalho += [
                f"Instituicao_{i}", f"Curso_{i}", f"Conclusao_{i}"
            ]

        # CURSOS
        for i in range(1,5):
            cabecalho += [
                f"CursoInst_{i}", f"CursoNome_{i}",
                f"Nivel_{i}", f"CursoConclusao_{i}"
            ]

        # OBJETIVO
        cabecalho.append("Objetivo")

        # 🔥 TEMPO
        cabecalho += [
            "Inicio_Preenchimento","Fim_Preenchimento","Tempo_Total"
        ]

        # 🔥 FUNIL  EM COLUNAS
        cabecalho += [
            "Tempo_Step_1",
            "Tempo_Step_2",
            "Tempo_Step_3",
            "Tempo_Step_4",
            "Tempo_Conversao"
        ]

        # 🔥 METADATA
        cabecalho += [
            "IP","Cidade_IP","Estado_IP","Pais_IP","Localizacao",
            "Dispositivo","Navegador","Sistema"
        ]

        planilha.append_row(cabecalho)

    p = dados["pessoais"]

    linha = [
        data_hora,
        p["nome"], p["cpf"], p["email"], p["telefone"], p["idade"],
        p["endereco"], p["cidade"], p["estado"], p["cep"],
        p["sexo"], p["estado_civil"], p["viagens"],
        p["tipo"], p["salario"], p["area"]
    ]

    # EXPERIÊNCIAS
    for i in range(4):
        if i < len(dados.get("experiencias", [])):
            exp = dados["experiencias"][i]
            linha += [exp["empresa"], exp["funcao"], exp["inicio"], exp["fim"], exp["cidade"]]
        else:
            linha += ["", "", "", "", ""]

    # ESCOLARIDADE
    for i in range(4):
        if i < len(dados.get("escolaridade", [])):
            esc = dados["escolaridade"][i]
            linha += [esc["instituicao"], esc["curso"], esc["conclusao"]]
        else:
            linha += ["", "", ""]

    # CURSOS
    for i in range(4):
        if i < len(dados.get("cursos", [])):
            c = dados["cursos"][i]
            linha += [c["instituicao"], c["curso"], c["nivel"], c["conclusao"]]
        else:
            linha += ["", "", "", ""]

    # OBJETIVO
    linha.append(dados.get("objetivo", ""))

    # =========================
    # 🔥 TEMPO TOTAL
    # =========================
    tempo = dados.get("tempo", {})

    linha += [
        tempo.get("inicio"),
        tempo.get("fim"),
        tempo.get("duracao")
    ]

        # =========================
    # 🔥 FUNIL EM COLUNAS
    # =========================
    eventos = dados.get("eventos", [])

    mapa_tempos = {
        "step_1": "",
        "step_2": "",
        "step_3": "",
        "step_4": "",
        "conversao": ""
    }

    for e in eventos:
        etapa = e.get("etapa")
        if etapa in mapa_tempos:
            mapa_tempos[etapa] = e.get("duracao")

    linha += [
        mapa_tempos["step_1"],
        mapa_tempos["step_2"],
        mapa_tempos["step_3"],
        mapa_tempos["step_4"],
        mapa_tempos["conversao"]
    ]

    # =========================
    # 🔥 METADATA
    # =========================
    meta = dados.get("metadata", {})

    linha += [
        meta.get("ip"),
        meta.get("cidade_ip"),
        meta.get("estado_ip"),
        meta.get("pais_ip"),
        meta.get("loc"),
        meta.get("dispositivo"),
        meta.get("navegador"),
        meta.get("sistema")
    ]

    planilha.append_row(linha)
def gerar_pdf(dados):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    file_name = "curriculo.pdf"

    doc = SimpleDocTemplate(
        file_name,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # 🎨 ESTILOS PERSONALIZADOS
    nome_style = ParagraphStyle(
        "Nome",
        parent=styles["Title"],
        fontSize=20,
        textColor=colors.HexColor("#1f4e79"),
        spaceAfter=6
    )

    titulo_style = ParagraphStyle(
        "Titulo",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1f4e79"),
        spaceBefore=10,
        spaceAfter=5
    )

    normal_style = styles["Normal"]

    elementos = []

    p = dados.get("pessoais", {})

    # =========================
    # HEADER
    # =========================
    elementos.append(Paragraph(p.get("nome", "").upper(), nome_style))
    elementos.append(Paragraph(p.get("area", ""), styles["Normal"]))
    elementos.append(Spacer(1, 10))

    contato = f"""
    {p.get('cidade','')} - {p.get('estado','')} | 
    Tel: {p.get('telefone','')} | 
    Email: {p.get('email','')}
    """
    elementos.append(Paragraph(contato, styles["Normal"]))

    elementos.append(Spacer(1, 15))

    # =========================
    # OBJETIVO
    # =========================
    objetivo = dados.get("objetivo", "")
    if objetivo:
        elementos.append(Paragraph("OBJETIVO PROFISSIONAL", titulo_style))
        elementos.append(Paragraph(objetivo, normal_style))

    # =========================
    # EXPERIÊNCIAS
    # =========================
    experiencias = dados.get("experiencias", [])
    if experiencias:
        elementos.append(Paragraph("EXPERIÊNCIA PROFISSIONAL", titulo_style))

        for exp in experiencias:
            linha = f"<b>{exp.get('funcao','')}</b> - {exp.get('empresa','')}"
            periodo = f"{exp.get('inicio','')} até {exp.get('fim','')} | {exp.get('cidade','')}"

            elementos.append(Paragraph(linha, normal_style))
            elementos.append(Paragraph(periodo, styles["Italic"]))
            elementos.append(Spacer(1, 5))

    # =========================
    # ESCOLARIDADE
    # =========================
    escolaridade = dados.get("escolaridade", [])
    if escolaridade:
        elementos.append(Paragraph("FORMAÇÃO ACADÊMICA", titulo_style))

        for esc in escolaridade:
            linha = f"{esc.get('curso','')} - {esc.get('instituicao','')}"
            elementos.append(Paragraph(linha, normal_style))
            elementos.append(Paragraph(f"Conclusão: {esc.get('conclusao','')}", styles["Italic"]))
            elementos.append(Spacer(1, 5))

    # =========================
    # CURSOS
    # =========================
    cursos = dados.get("cursos", [])
    if cursos:
        elementos.append(Paragraph("CURSOS COMPLEMENTARES", titulo_style))

        for c in cursos:
            linha = f"{c.get('curso','')} - {c.get('instituicao','')} ({c.get('nivel','')})"
            elementos.append(Paragraph(linha, normal_style))
            elementos.append(Paragraph(f"Conclusão: {c.get('conclusao','')}", styles["Italic"]))
            elementos.append(Spacer(1, 5))

    # =========================
    # INFORMAÇÕES ADICIONAIS
    # =========================
    elementos.append(Paragraph("INFORMAÇÕES ADICIONAIS", titulo_style))

    info = [
        f"Estado Civil: {p.get('estado_civil','')}",
        f"Disponibilidade: {p.get('viagens','')}",
        f"Tipo de contrato: {p.get('tipo','')}",
        f"Pretensão salarial: {p.get('salario','')}"
    ]

    for i in info:
        elementos.append(Paragraph(i, normal_style))

    doc.build(elementos)

    return file_name

# =========================
# CONTROLE
# =========================
if "step" not in st.session_state:
    st.session_state.step = 1

if "dados" not in st.session_state:
    st.session_state.dados = {}

# 🔥 FUNIL - INICIALIZAÇÃO
if "eventos" not in st.session_state:
    st.session_state.eventos = []

if "etapa_atual_inicio" not in st.session_state:
    st.session_state.etapa_atual_inicio = datetime.now()

# 🔥 CONTROLE DE ETAPA (NOVO)
if "step_anterior" not in st.session_state:
    st.session_state.step_anterior = st.session_state.step

# 🔥 RESET AUTOMÁTICO DE TEMPO POR ETAPA (NOVO)
if st.session_state.step != st.session_state.step_anterior:
    st.session_state.etapa_atual_inicio = datetime.now()
    st.session_state.step_anterior = st.session_state.step

# 🔥 TEMPO TOTAL
if "inicio_preenchimento" not in st.session_state:
    st.session_state.inicio_preenchimento = datetime.now()

# CONTROLES EXISTENTES
if "qtd_exp" not in st.session_state:
    st.session_state.qtd_exp = 1

if "qtd_esc" not in st.session_state:
    st.session_state.qtd_esc = 1

if "qtd_curso" not in st.session_state:
    st.session_state.qtd_curso = 1


# =========================
# PROGRESSO (PROFISSIONAL)
# =========================
TOTAL_ETAPAS = 6

progresso = min(st.session_state.step / TOTAL_ETAPAS, 1.0)

# 🔥 BARRA
st.progress(progresso)

# 🔥 TEXTO EM %
st.markdown(
    f"""
    <div style='text-align:center; font-size:14px; margin-top:5px;'>
        Progresso: <b>{int(progresso * 100)}%</b>
    </div>
    """,
    unsafe_allow_html=True
)

# =========================
# ETAPA 1
# =========================
if st.session_state.step == 1:

    # 🔥 INICIA CONTAGEM DE TEMPO
    if "inicio_preenchimento" not in st.session_state:
        st.session_state.inicio_preenchimento = datetime.now()

    st.subheader("Dados Pessoais")

    col1, col2 = st.columns(2)

    with col1:
        nome = st.text_input("Nome Completo")
        sexo = st.selectbox("Sexo", ["Masculino", "Feminino"])
        estado_civil = st.selectbox("Estado Civil", ["Solteiro", "Casado", "Divorciado"])
        cpf = formatar_cpf(st.text_input("CPF"))
        idade = st.number_input("Idade", 0, 100)
        telefone = formatar_telefone(st.text_input("Telefone"))
        email = st.text_input("Email")

    with col2:
        endereco = st.text_input("Endereço completo")
        estado = st.selectbox("Estado", estados)
        cidade = st.selectbox("Cidade", buscar_cidades(estado))
        cep = formatar_cep(st.text_input("CEP"))
        viagens = st.selectbox("Disponibilidade para viagens", ["Sim", "Não"])
        tipo = st.selectbox("Tipo de emprego", ["CLT", "Estágio", "Jovem Aprendiz", "PJ"])
        salario = st.text_input("Pretensão salarial")
        area = st.text_input("Área de interesse")

    if st.button("Continuar ➡️"):

        if not validar_cpf_simples(cpf):
            st.error("CPF inválido")
        elif not validar_email(email):
            st.error("Email inválido")
        else:
            registrar_evento("step_1")

            st.session_state.dados["pessoais"] = {
                "nome": nome,
                "sexo": sexo,
                "estado_civil": estado_civil,
                "cpf": cpf,
                "idade": idade,
                "telefone": telefone,
                "email": email,
                "endereco": endereco,
                "cidade": cidade,
                "estado": estado,
                "cep": cep,
                "viagens": viagens,
                "tipo": tipo,
                "salario": salario,
                "area": area
            }

            st.session_state.step = 2
            st.rerun()


# =========================
# ETAPA 2
# =========================
elif st.session_state.step == 2:

    st.subheader("Experiência Profissional")

    experiencias = []

    for i in range(st.session_state.qtd_exp):
        with st.expander(f"Experiência {i+1}", expanded=(i==0)):
            empresa = st.text_input("Empresa", key=f"empresa_{i}")
            funcao = st.text_input("Função", key=f"funcao_{i}")
            inicio = st.text_input("Início (MM/AAAA)", key=f"inicio_{i}")
            fim = st.text_input("Fim (MM/AAAA)", key=f"fim_{i}")
            cidade_exp = st.selectbox(
                "Cidade",
                buscar_cidades(st.session_state.dados["pessoais"]["estado"]),
                key=f"cidade_exp_{i}"
            )

            experiencias.append({
                "empresa": empresa,
                "funcao": funcao,
                "inicio": inicio,
                "fim": fim,
                "cidade": cidade_exp
            })

    if st.session_state.qtd_exp < 4:
        if st.button("➕ Adicionar experiência"):
            st.session_state.qtd_exp += 1
            st.rerun()

    col1, col2 = st.columns(2)

    if col1.button("⬅️ Voltar"):
        st.session_state.step = 1
        st.rerun()

    if col2.button("Continuar ➡️"):
        registrar_evento("step_2")

        st.session_state.dados["experiencias"] = experiencias
        st.session_state.step = 3
        st.rerun()


# =========================
# ETAPA 3
# =========================
elif st.session_state.step == 3:

    st.subheader("Escolaridade")

    escolaridade = []

    for i in range(st.session_state.qtd_esc):
        with st.expander(f"Formação {i+1}", expanded=(i==0)):
            instituicao = st.text_input("Instituição", key=f"inst_{i}")
            curso = st.text_input("Curso", key=f"curso_{i}")
            conclusao = st.text_input("Conclusão (MM/AAAA)", key=f"conc_{i}")

            escolaridade.append({
                "instituicao": instituicao,
                "curso": curso,
                "conclusao": conclusao
            })

    if st.session_state.qtd_esc < 4:
        if st.button("➕ Adicionar formação"):
            st.session_state.qtd_esc += 1
            st.rerun()

    col1, col2 = st.columns(2)

    if col1.button("⬅️ Voltar"):
        st.session_state.step = 2
        st.rerun()

    if col2.button("Continuar ➡️"):
        registrar_evento("step_3")

        st.session_state.dados["escolaridade"] = escolaridade
        st.session_state.step = 4
        st.rerun()


# =========================
# ETAPA 4
# =========================
elif st.session_state.step == 4:

    st.subheader("Cursos de Aperfeiçoamento")

    cursos = []

    for i in range(st.session_state.qtd_curso):
        with st.expander(f"Curso {i+1}", expanded=(i==0)):
            instituicao = st.text_input("Instituição", key=f"cinst_{i}")
            curso = st.text_input("Curso", key=f"ccurso_{i}")
            nivel = st.text_input("Nível", key=f"cnivel_{i}")
            conclusao = st.text_input("Conclusão (MM/AAAA)", key=f"cconc_{i}")

            cursos.append({
                "instituicao": instituicao,
                "curso": curso,
                "nivel": nivel,
                "conclusao": conclusao
            })

    if st.session_state.qtd_curso < 4:
        if st.button("➕ Adicionar curso"):
            st.session_state.qtd_curso += 1
            st.rerun()

    col1, col2 = st.columns(2)

    if col1.button("⬅️ Voltar"):
        st.session_state.step = 3
        st.rerun()

    if col2.button("Continuar ➡️"):
        registrar_evento("step_4")

        st.session_state.dados["cursos"] = cursos
        st.session_state.step = 5
        st.rerun()


# =========================
# FINAL
# =========================
elif st.session_state.step == 5:

    objetivo = st.text_area("Objetivo profissional")

    col1, col2 = st.columns(2)

    if col1.button("⬅️ Voltar"):
        st.session_state.step = 4
        st.rerun()

    if col2.button("Finalizar"):

        # 🔥 REGISTRA CONVERSÃO
        registrar_evento("conversao")

        # 🔥 SALVA EVENTOS (ESSENCIAL)
        st.session_state.dados["eventos"] = st.session_state.eventos

        # 🔥 OBJETIVO
        st.session_state.dados["objetivo"] = objetivo

        # 🔥 TEMPO TOTAL
        fim = datetime.now()
        inicio = st.session_state.get("inicio_preenchimento")

        tempo_total = str(fim - inicio) if inicio else ""

        st.session_state.dados["tempo"] = {
            "inicio": inicio.strftime("%d/%m/%Y %H:%M") if inicio else "",
            "fim": fim.strftime("%d/%m/%Y %H:%M"),
            "duracao": tempo_total
        }

        # 🔥 METADATA
        st.session_state.dados["metadata"] = capturar_info_usuario()

        # 🔥 SALVA NO GOOGLE
        salvar_dados(st.session_state.dados)

        # 👉 VAI PRA TELA FINAL
        st.session_state.step = 6
        st.rerun()

# =========================
# SUCESSO FINAL
# =========================
elif st.session_state.step == 6:

    st.success("Cadastro realizado com sucesso! 🎉")

    nome = st.session_state.dados.get("pessoais", {}).get("nome", "candidato")
    nome_arquivo = f"curriculo_{nome.strip().replace(' ', '_').lower()}.pdf"

    pdf = gerar_pdf(st.session_state.dados)

    if pdf:
        with open(pdf, "rb") as f:
            st.download_button(
                "📄 Baixar currículo",
                f,
                file_name=nome_arquivo,
                mime="application/pdf"
            )

    if st.button("Novo cadastro"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
