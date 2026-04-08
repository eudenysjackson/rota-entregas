# 🐾 Rota de Entregas — Guia de Instalação

## Pré-requisitos
- Python 3.9 ou superior instalado
- Conta Google com acesso às planilhas

---

## Passo 1 — Criar credenciais do Google

1. Acesse https://console.cloud.google.com
2. Crie um projeto novo (ou use um existente)
3. Ative as APIs:
   - **Google Sheets API**
   - **Google Drive API**
4. Vá em **IAM & Admin → Service Accounts → Create Service Account**
5. Dê um nome (ex: `rota-entregas`) e clique em **Create**
6. Na tela seguinte clique em **Skip** (sem papel necessário)
7. Clique no service account criado → **Keys → Add Key → JSON**
8. Baixe o arquivo e **renomeie para `credentials.json`**
9. Coloque o `credentials.json` dentro desta pasta

---

## Passo 2 — Compartilhar as planilhas

Abra cada planilha do Google Sheets e compartilhe com o e-mail do service account
(está dentro do `credentials.json` no campo `client_email`) com permissão de **Editor**.

---

## Passo 3 — Configurar o sistema

Abra o arquivo `app.py` e edite as primeiras linhas:

```python
ID_PLANILHA_ROTA  = "..."   # ID da planilha onde a rota é salva
NOME_ABA_ROTA     = "Rota"  # Nome da aba da rota
ID_PLANILHA_BASE  = "..."   # ID da planilha de clientes
NOME_ABA_BASE     = "novo"  # Nome da aba dos clientes
LINHA_INICIO_ROTA = 5       # Primeira linha de dados na planilha de rota
```

O ID da planilha está na URL:
`https://docs.google.com/spreadsheets/d/`**`SEU_ID_AQUI`**`/edit`

---

## Passo 4 — Instalar e rodar

Abra o terminal nesta pasta e execute:

```bash
# Instalar dependências (só uma vez)
pip install -r requirements.txt

# Iniciar o sistema
python app.py
```

Depois abra no navegador: **http://localhost:5000**

---

## Como usar

| Ação | Como fazer |
|---|---|
| Buscar cliente | Digite nome ou pet no campo e pressione Enter |
| Adicionar entrega | Clique em "Selecionar" e confirme o endereço e data |
| Ver rota | A tabela à direita mostra todas as entregas ordenadas por bairro |
| Reordenar | Botão "🔄 Reordenar" no canto superior direito |
| Gerar PDF | Botão "📄 PDF" abre uma janela para impressão |
| Limpar lista | Botão "🗑️ Limpar" — pede confirmação antes |

---

## Estrutura de arquivos

```
rotadeentrega/
├── app.py              ← backend (servidor Flask)
├── credentials.json    ← credenciais Google (você cria)
├── requirements.txt    ← dependências Python
├── LEIAME.md           ← este arquivo
└── templates/
    └── index.html      ← interface web
```
