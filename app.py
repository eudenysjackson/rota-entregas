import unicodedata
import os
import json
import time
from datetime import date, timedelta
from flask import Flask, jsonify, request, render_template
from googleapiclient.discovery import build

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES
# ─────────────────────────────────────────────
ID_PLANILHA_BASE = os.environ.get("ID_PLANILHA_BASE", "16aLq8UzMfWs78ewzGCmKvM_7DjL5IO7MqUce0BPb9SE")
NOME_ABA_BASE    = os.environ.get("NOME_ABA_BASE", "novo")
GOOGLE_API_KEY   = os.environ.get("GOOGLE_API_KEY", "")
ROTA_FILE        = "rota.json"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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

_cache_base = {"dados": [], "ts": 0}
CACHE_TTL   = 300

# ─────────────────────────────────────────────
#  BANCO DE DADOS
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
#  GOOGLE SHEETS (leitura pública via API key)
# ─────────────────────────────────────────────

def get_sheets_service():
    return build("sheets", "v4", developerKey=GOOGLE_API_KEY)

def obter_dados_base():
    agora = time.time()
    if agora - _cache_base["ts"] < CACHE_TTL and _cache_base["dados"]:
        return _cache_base["dados"]
    service = get_sheets_service()
    result  = service.spreadsheets().values().get(
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

def score_bairro(bairro):
    return RANKING_BAIRROS.get(normalizar(bairro), 50)

def ordenar(rota):
    return sorted(rota, key=lambda x: -score_bairro(x.get("bairro", "")))

# ─────────────────────────────────────────────
#  ROTAS
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/buscar")
def api_buscar():
    termo = request.args.get("q", "").strip()
    if len(termo) < 2:
        return jsonify([])
    linhas     = obter_dados_base()
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
    idx    = int(request.args.get("id", 0))
    linhas = obter_dados_base()
    while len(linhas[idx]) < 13: linhas[idx].append("")
    tutor_chave = normalizar(linhas[idx][0])
    pets_lista, enderecos_vistos = [], {}
    for linha in linhas:
        while len(linha) < 13: linha.append("")
        if normalizar(linha[0]) == tutor_chave:
            pet = normalizar(linha[1])
            if pet and pet not in pets_lista: pets_lista.append(pet)
            end  = normalizar(linha[9])
            num  = normalizar(linha[10])
            comp = str(linha[11]).strip()
            bai  = normalizar(linha[12])
            chave = f"{end}|{num}|{comp}|{bai}"
            if chave not in enderecos_vistos:
                enderecos_vistos[chave] = {"endereco": end, "numero": num, "complemento": comp, "bairro": bai}
    return jsonify({"tutor": nome_curto(linhas[idx][0]), "pets": ", ".join(pets_lista), "enderecos": list(enderecos_vistos.values())})

@app.route("/api/salvar", methods=["POST"])
def api_salvar():
    dados   = request.json
    p       = dados["data"].split("-")
    data_br = f"{p[2]}/{p[1]}/{p[0]}"
    rota    = ler_rota()
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
try:
    init_db()
except Exception:
    pass

if __name__ == "__main__":
    app.run(debug=True, port=5000)
