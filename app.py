import unicodedata
import os
import secrets
import hashlib
import base64
import time
import json
from datetime import date, timedelta
from flask import Flask, jsonify, request, render_template, redirect, session, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES
# ─────────────────────────────────────────────
ID_PLANILHA_BASE    = "16aLq8UzMfWs78ewzGCmKvM_7DjL5IO7MqUce0BPb9SE"
NOME_ABA_BASE       = "novo"
CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_FILE          = "token.json"
ROTA_FILE           = "rota.json"
SCOPES              = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Railway fornece DATABASE_URL automaticamente ao adicionar PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

RANKING_BAIRROS = {
    'CENTRO': 100, 'LAPA': 100, 'GLORIA': 100,
    'TIJUCA': 90, 'VILA ISABEL': 90, 'MARACANA': 90, 'GRAJAU': 90, 'MEIER': 90,
    'FLAMENGO': 80, 'CATETE': 80, 'LARANJEIRAS': 80, 'COSME VELHO': 80, 'RIO COMPRIDO': 80,
    'BOTAFOGO': 70, 'URCA': 70, 'HUMAITA': 70,
    'LEME': 60, 'COPACABANA': 60,
    'IPANEMA': 50, 'ARPOADOR': 50,
    'LEBLON': 40, 'GAVEA': 40, 'JARDIM BOTANICO': 40, 'LAGOA': 40,
    'SAO CONRADO': 30, 'VIDIGAL': 30, 'ROCINHA': 30,
    'JOA': 20, 'ITANHANGA': 20,
    'JACAREPAGUA': 10, 'FREGUESIA': 10, 'PECHINCHA': 10, 'ANIL': 10, 'TAQUARA': 10,
    'BARRA DA TIJUCA': 0, 'BARRA': 0, 'RECREIO': 0,
    'RECREIO DOS BANDEIRANTES': 0, 'VARGEM GRANDE': 0, 'CAMORIM': 0,
}

# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

_cache_base = {"dados": [], "ts": 0}
CACHE_TTL   = 300

# ─────────────────────────────────────────────
#  BANCO DE DADOS (PostgreSQL no Railway, JSON local)
# ─────────────────────────────────────────────

def get_db_conn():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL:
        return
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rota (
                id          SERIAL PRIMARY KEY,
                tutor       TEXT,
                pet         TEXT,
                endereco    TEXT,
                numero      TEXT,
                complemento TEXT,
                bairro      TEXT,
                data        TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()

# ── Token OAuth ──

def ler_token_str():
    if DATABASE_URL:
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM config WHERE key='oauth_token'")
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read()
    return None

def salvar_token_str(token_str):
    if DATABASE_URL:
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO config (key, value) VALUES ('oauth_token', %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (token_str,))
            conn.commit()
        finally:
            conn.close()
    else:
        with open(TOKEN_FILE, "w") as f:
            f.write(token_str)

def apagar_token():
    if DATABASE_URL:
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM config WHERE key='oauth_token'")
            conn.commit()
        finally:
            conn.close()
    elif os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

# ── Rota ──

def ler_rota():
    if DATABASE_URL:
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT tutor, pet, endereco, numero, complemento, bairro, data FROM rota")
            return [
                {"tutor": r[0], "pet": r[1], "endereco": r[2],
                 "numero": r[3], "complemento": r[4] or "", "bairro": r[5], "data": r[6]}
                for r in cur.fetchall()
            ]
        finally:
            conn.close()
    if not os.path.exists(ROTA_FILE):
        return []
    with open(ROTA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_rota(rota):
    if DATABASE_URL:
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM rota")
            for item in rota:
                cur.execute(
                    "INSERT INTO rota (tutor,pet,endereco,numero,complemento,bairro,data) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (item["tutor"], item["pet"], item["endereco"], item["numero"],
                     item.get("complemento", ""), item["bairro"], item["data"])
                )
            conn.commit()
        finally:
            conn.close()
    else:
        with open(ROTA_FILE, "w", encoding="utf-8") as f:
            json.dump(rota, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
#  OAUTH
# ─────────────────────────────────────────────

def get_redirect_uri():
    base = os.environ.get("APP_URL", request.host_url.rstrip("/"))
    return base.rstrip("/") + "/callback"

def get_client_config():
    cid  = os.environ.get("GOOGLE_CLIENT_ID")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET")
    if cid and csec:
        return {
            "web": {
                "client_id": cid,
                "client_secret": csec,
                "redirect_uris": ["https://example.com/callback"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
    if os.path.exists(CLIENT_SECRETS_FILE):
        with open(CLIENT_SECRETS_FILE) as f:
            return json.load(f)
    return None

def obter_credenciais():
    token_str = ler_token_str()
    if not token_str:
        return None
    creds = Credentials.from_authorized_user_info(json.loads(token_str), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        salvar_token_str(creds.to_json())
    return creds if (creds and creds.valid) else None

def get_sheets_service():
    creds = obter_credenciais()
    if not creds:
        raise PermissionError("Não autenticado")
    return build("sheets", "v4", credentials=creds)

def _requer_auth():
    if not obter_credenciais():
        return jsonify({"erro": "nao_autenticado"}), 401
    return None

def obter_dados_base(service):
    agora = time.time()
    if agora - _cache_base["ts"] < CACHE_TTL and _cache_base["dados"]:
        return _cache_base["dados"]
    result = service.spreadsheets().values().get(
        spreadsheetId=ID_PLANILHA_BASE,
        range=f"{NOME_ABA_BASE}!A2:M"
    ).execute()
    linhas = result.get("values", [])
    _cache_base["dados"] = linhas
    _cache_base["ts"]    = agora
    return linhas

# ─────────────────────────────────────────────
#  UTILITÁRIOS
# ─────────────────────────────────────────────

def normalizar(texto):
    if not texto:
        return ""
    s = str(texto).upper().strip()
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")

def nome_curto(nome):
    partes = normalizar(nome).split()
    return (partes[0] + " " + partes[-1]) if len(partes) > 1 else normalizar(nome)

def levenshtein(a, b):
    if not a: return len(b) if b else 0
    if not b: return len(a)
    m = [[0] * (len(a) + 1) for _ in range(len(b) + 1)]
    for i in range(len(b) + 1): m[i][0] = i
    for j in range(len(a) + 1): m[0][j] = j
    for i in range(1, len(b) + 1):
        for j in range(1, len(a) + 1):
            m[i][j] = m[i-1][j-1] if b[i-1] == a[j-1] else 1 + min(m[i-1][j-1], m[i][j-1], m[i-1][j])
    return m[len(b)][len(a)]

def proxima_quinta():
    hoje = date.today()
    return hoje + timedelta(days=(3 - hoje.weekday() + 7) % 7)

def score_bairro(bairro):
    return RANKING_BAIRROS.get(normalizar(bairro), 50)

def ordenar(rota):
    return sorted(rota, key=lambda x: -score_bairro(x.get("bairro", "")))

# ─────────────────────────────────────────────
#  ROTAS: AUTENTICAÇÃO
# ─────────────────────────────────────────────

@app.route("/login")
def login():
    config = get_client_config()
    if not config:
        return ("<html><body style='font-family:Arial;padding:40px'>"
                "<h2>⚠️ Credenciais Google não encontradas</h2>"
                "<p>Coloque o <b>client_secret.json</b> na pasta ou configure as variáveis de ambiente.</p>"
                "<a href='/login'>Tentar novamente</a></body></html>"), 400

    code_verifier  = secrets.token_urlsafe(96)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    flow = Flow.from_client_config(
        config, scopes=SCOPES,
        redirect_uri=get_redirect_uri(),
    )
    auth_url, state = flow.authorization_url(
        access_type="offline", prompt="consent",
        code_challenge=code_challenge, code_challenge_method="S256",
    )
    session["oauth_state"]   = state
    session["code_verifier"] = code_verifier
    return redirect(auth_url)

@app.route("/callback")
def callback():
    config = get_client_config()
    flow = Flow.from_client_config(
        config, scopes=SCOPES,
        state=session.get("oauth_state"),
        redirect_uri=get_redirect_uri(),
    )
    flow.code_verifier = session.get("code_verifier")
    flow.fetch_token(authorization_response=request.url)
    salvar_token_str(flow.credentials.to_json())
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    apagar_token()
    return redirect(url_for("index"))

# ─────────────────────────────────────────────
#  ROTAS: PÁGINAS
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", autenticado=obter_credenciais() is not None)

# ─────────────────────────────────────────────
#  ROTAS: API
# ─────────────────────────────────────────────

@app.route("/api/buscar")
def api_buscar():
    err = _requer_auth()
    if err: return err
    termo = request.args.get("q", "").strip()
    if len(termo) < 2:
        return jsonify([])

    service    = get_sheets_service()
    linhas     = obter_dados_base(service)
    termo_norm = normalizar(termo)
    resultados = []

    for i, linha in enumerate(linhas):
        while len(linha) < 13: linha.append("")
        tutor, pet = linha[0], linha[1]
        if not tutor and not pet: continue
        tutor_n, pet_n = normalizar(tutor), normalizar(pet)
        score = 0
        if termo_norm in tutor_n or termo_norm in pet_n:
            score = 100
        elif levenshtein(termo_norm, tutor_n) <= 2 or levenshtein(termo_norm, pet_n) <= 2:
            score = 80
        if score > 0:
            resultados.append({"id": i, "tutor": nome_curto(tutor), "pet": pet, "score": score})

    resultados.sort(key=lambda x: -x["score"])
    return jsonify(resultados[:10])


@app.route("/api/selecionar")
def api_selecionar():
    err = _requer_auth()
    if err: return err
    idx     = int(request.args.get("id", 0))
    service = get_sheets_service()
    linhas  = obter_dados_base(service)

    while len(linhas[idx]) < 13: linhas[idx].append("")
    tutor_chave = normalizar(linhas[idx][0])
    pets_lista, enderecos_vistos = [], {}

    for linha in linhas:
        while len(linha) < 13: linha.append("")
        if normalizar(linha[0]) == tutor_chave:
            pet = normalizar(linha[1])
            if pet and pet not in pets_lista: pets_lista.append(pet)
            end, num, comp, bai = normalizar(linha[9]), normalizar(linha[10]), str(linha[11]).strip(), normalizar(linha[12])
            chave = f"{end}|{num}|{comp}|{bai}"
            if chave not in enderecos_vistos:
                enderecos_vistos[chave] = {"endereco": end, "numero": num, "complemento": comp, "bairro": bai}

    return jsonify({"tutor": nome_curto(linhas[idx][0]), "pets": ", ".join(pets_lista), "enderecos": list(enderecos_vistos.values())})


@app.route("/api/salvar", methods=["POST"])
def api_salvar():
    err = _requer_auth()
    if err: return err
    dados  = request.json
    p      = dados["data"].split("-")
    data_br = f"{p[2]}/{p[1]}/{p[0]}"
    rota   = ler_rota()
    rota.append({"tutor": dados["tutor"], "pet": dados["pets"],
                 "endereco": dados["endereco"], "numero": dados["numero"],
                 "complemento": dados.get("complemento", ""),
                 "bairro": dados["bairro"], "data": data_br})
    salvar_rota(ordenar(rota))
    return jsonify({"ok": True, "msg": f"{dados['tutor']} agendado para {data_br}"})


@app.route("/api/rota")
def api_rota():
    return jsonify(ordenar(ler_rota()))


@app.route("/api/reordenar", methods=["POST"])
def api_reordenar():
    salvar_rota(ordenar(ler_rota()))
    return jsonify({"ok": True})


@app.route("/api/limpar", methods=["POST"])
def api_limpar():
    salvar_rota([])
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
#  INICIALIZAÇÃO
# ─────────────────────────────────────────────
try:
    init_db()
except Exception:
    pass

if __name__ == "__main__":
    app.run(debug=True, port=5000)
