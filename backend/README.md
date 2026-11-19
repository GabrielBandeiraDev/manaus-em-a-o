# API · Problemas de Manaus

Recebe a reclamação com nome, endereço, problema e foto. Publica a notícia no mural.

## 1. Supabase

1. Cria um projeto em [supabase.com](https://supabase.com).
2. Abre **SQL Editor** e cola o arquivo `sql/schema.sql`. Roda.
3. Em **Connect**, copia a URI do banco (começa com `postgresql://`) para a variável `supabase`.

A URI fica só no Render ou em `backend/.env`. Não vai para o site nem para o Git.

## 2. GitHub e Render

O repositório já aponta para `https://github.com/GabrielBandeiraDev/manaus-em-a-o`. Sobe a pasta inteira, com `backend/` e o `render.yaml` da raiz.

No Render, cria um **Blueprint** (não um Web Service comum). O serviço comum vê o `package.json` e sobe o site em Node. O Blueprint lê o `render.yaml` e sobe só `backend/`.

Na tela do Blueprint, preenche a variável `supabase` com a URI do banco.

O `ADMIN_TOKEN` o Render gera. Copia esse valor: é a senha do `/admin`.

Variáveis:

| Variável | Valor |
| --- | --- |
| `supabase` | `postgresql://postgres:...@db.xxxx.supabase.co:5432/postgres` |
| `ADMIN_TOKEN` | o Render gera. Copia e guarda. |
| `CORS_ORIGINS` | `*` ou a URL do site |
| `PUBLICAR_AUTOMATICO` | `true` |

Sobe. `GET /health` tem que responder `{"ok": true, "supabase": true}`.

## 3. Site

No front, `VITE_API_URL` é a URL do Render, sem barra no fim.

Local:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
.venv\Scripts\python -m flask --app app run --port 5000
```

## O que a API faz

- `POST /api/reclamacoes` — formulário com `nome`, `endereco`, `descricao` e o arquivo `foto`.
- `GET /api/noticias` — mural com nome, endereço, problema e foto.
- `GET /api/regras` — regras da comunidade.
- `GET /admin` — as mesmas notícias, para marcar resolvida ou tirar do ar. Header `X-Admin-Token`.

Exemplo:

```bash
curl -F "nome=Ana Souza" -F "endereco=Rua das Flores, 10" -F "descricao=Cratera aberta na avenida há vários meses." -F "foto=@buraco.jpg" https://SEU-APP.onrender.com/api/reclamacoes
```
