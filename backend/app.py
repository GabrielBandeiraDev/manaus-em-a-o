"""API das reclamações: nome, endereço, problema e foto."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from pathlib import Path
from urllib.parse import quote, unquote
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from banco import Postgres
from regras import REGRAS, ErroReclamacao, preparar_foto, validar_campos
from supabase_api import COLUNAS_PUBLICAS, Supabase, SupabaseErro

STATUS_OK = {"recebida", "publicada", "resolvida", "rejeitada"}
RAIZ = Path(__file__).resolve().parent
log = logging.getLogger("problemas")


def _ligado(nome: str, padrao: str) -> bool:
    return os.getenv(nome, padrao).strip().lower() in {"1", "true", "sim", "yes"}


def _inteiro(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, str(padrao)))
    except ValueError:
        return padrao


def para_publico(row: dict) -> dict:
    return {chave: row.get(chave) for chave in COLUNAS_PUBLICAS.split(",")}


def para_admin(row: dict) -> dict:
    return para_publico(row)


def _ip() -> str:
    encaminhado = request.headers.get("X-Forwarded-For", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip() or "desconhecido"
    return request.remote_addr or "desconhecido"


def _limitado(app: Flask) -> bool:
    if app.config.get("TESTING"):
        return False
    agora = time.monotonic()
    janela = _inteiro("RATE_WINDOW", 3600)
    limite = _inteiro("RATE_LIMIT", 8)
    baldes: dict = app.config["RATE_BUCKETS"]
    if len(baldes) > 5000:
        baldes.clear()
    ip = _ip()
    hits = [marca for marca in baldes.get(ip, []) if agora - marca < janela]
    if len(hits) >= limite:
        baldes[ip] = hits
        return True
    hits.append(agora)
    baldes[ip] = hits
    return False


def _normalizar_uri(valor: str) -> str:
    if not _uri_banco(valor):
        return valor
    scheme, rest = valor.split("://", 1)
    if "@" not in rest or ":" not in rest.split("@", 1)[0]:
        return valor
    userinfo, host = rest.rsplit("@", 1)
    usuario, senha = userinfo.split(":", 1)
    senha = unquote(senha)
    if len(senha) >= 2 and senha.startswith("[") and senha.endswith("]"):
        senha = senha[1:-1]
    return f"{scheme}://{quote(usuario, safe='')}:{quote(senha, safe='')}@{host}"


def _valor_supabase() -> str:
    for nome in ("supabase", "SUPABASE"):
        bruto = os.environ.get(nome, "")
        if isinstance(bruto, str) and bruto.strip():
            return _normalizar_uri(bruto.strip().strip('"').strip("'"))
    return ""


def _uri_banco(valor: str) -> bool:
    return valor.startswith("postgres://") or valor.startswith("postgresql://")


def _supabase_configurado() -> bool:
    if _uri_banco(_valor_supabase()):
        return True
    url = os.getenv("SUPABASE_URL", "").strip()
    chave = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    return bool(url and chave)


def _abrir() -> Postgres | Supabase:
    valor = _valor_supabase()
    if _uri_banco(valor):
        return Postgres(valor)
    if valor.startswith("http://") or valor.startswith("https://"):
        raise SupabaseErro(
            "A variável supabase precisa da URI do banco, a que começa com postgresql://.",
            503,
        )
    url = os.getenv("SUPABASE_URL", "").strip()
    chave = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if url and chave:
        return Supabase(url, chave)
    raise SupabaseErro(
        "Supabase ainda não configurado. Coloca na variável supabase a URI do banco (postgresql://...).",
        503,
    )


def _base_publica() -> str:
    fixo = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if fixo:
        return fixo
    return request.url_root.rstrip("/")


def _admin_recusado():
    token = os.getenv("ADMIN_TOKEN", "").strip()
    if not token:
        return jsonify(erro="ADMIN_TOKEN não configurado no servidor."), 503
    recebido = request.headers.get("X-Admin-Token", "")
    if not isinstance(recebido, str) or not secrets.compare_digest(recebido, token):
        return jsonify(erro="Token de admin inválido."), 401
    return None


def create_app(testing: bool = False) -> Flask:
    if not testing:
        env_repo = RAIZ.parent / ".env"
        env_back = RAIZ / ".env"
        if env_repo.is_file():
            load_dotenv(env_repo)
        if env_back.is_file():
            load_dotenv(env_back, override=True)
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
    app.config["TESTING"] = testing
    app.config["RATE_BUCKETS"] = {}
    app.json.ensure_ascii = False

    origens = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]
    CORS(app, resources={r"/api/*": {"origins": origens or "*"}})

    @app.after_request
    def cabecalhos(resposta):
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["X-Frame-Options"] = "DENY"
        return resposta

    @app.errorhandler(413)
    def grande(_erro):
        return jsonify(erro="A foto passa de 5 MB. Tira outra mais leve."), 413

    @app.errorhandler(404)
    def nao(_erro):
        if request.path.startswith("/api/"):
            return jsonify(erro="Esse caminho não existe."), 404
        return ("Não encontrado.", 404)

    @app.get("/")
    def raiz():
        return jsonify(
            servico="Problemas de Manaus",
            saude="/health",
            noticias="/api/noticias",
            regras="/api/regras",
            admin="/admin",
        )

    @app.get("/health")
    def health():
        return jsonify(
            ok=True,
            supabase=_supabase_configurado(),
        )

    @app.get("/api/regras")
    def regras():
        return jsonify(
            regras=list(REGRAS),
            privacidade="A notícia mostra nome, endereço, problema e foto.",
        )

    @app.get("/api/noticias")
    def noticias():
        try:
            linhas = _abrir().listar_publicas()
        except SupabaseErro as exc:
            return jsonify(erro=exc.mensagem), exc.status
        resposta = jsonify(noticias=[para_publico(linha) for linha in linhas])
        resposta.headers["Cache-Control"] = "public, max-age=15"
        return resposta

    @app.post("/api/reclamacoes")
    def criar():
        if request.is_json:
            return jsonify(erro="Envia a reclamação com a foto em formulário (multipart)."), 415
        try:
            campos = validar_campos(request.form)
            arquivo = request.files.get("foto")
            if arquivo is None or not arquivo.filename:
                raise ErroReclamacao("Manda a foto do problema.")
            conteudo = arquivo.read(5 * 1024 * 1024 + 1)
            content_type, extensao, limpa = preparar_foto(conteudo)
        except ErroReclamacao as exc:
            return jsonify(erro=exc.mensagem), exc.status

        if _limitado(app):
            return jsonify(erro="Muitas reclamações deste acesso agora. Espera um pouco e tenta de novo."), 429

        try:
            cliente = _abrir()
        except SupabaseErro as exc:
            return jsonify(erro=exc.mensagem), exc.status

        status = "publicada" if _ligado("PUBLICAR_AUTOMATICO", "true") else "recebida"
        sha = hashlib.sha256(limpa).hexdigest()
        if isinstance(cliente, Postgres):
            try:
                row = cliente.salvar(campos, limpa, sha, status, _base_publica())
            except SupabaseErro as exc:
                return jsonify(erro=exc.mensagem), exc.status
        else:
            caminho = f"noticias/{uuid4().hex}.{extensao}"
            try:
                foto_url = cliente.subir_foto(caminho, limpa, content_type)
                row = cliente.inserir(
                    {
                        **campos,
                        "foto_path": caminho,
                        "foto_url": foto_url,
                        "foto_sha256": sha,
                        "status": status,
                    }
                )
            except SupabaseErro as exc:
                cliente.apagar_foto(caminho)
                return jsonify(erro=exc.mensagem), exc.status

        if status == "publicada":
            mensagem = "Reclamação publicada no mural."
        else:
            mensagem = "Reclamação recebida. Ela entra no mural quando a equipe publicar."
        resposta = jsonify(mensagem=mensagem, reclamacao=para_publico(row))
        resposta.headers["Cache-Control"] = "no-store"
        resposta.status_code = 201
        return resposta

    @app.get("/api/admin/reclamacoes")
    def admin_lista():
        recusado = _admin_recusado()
        if recusado:
            return recusado
        try:
            linhas = _abrir().listar_admin()
        except SupabaseErro as exc:
            return jsonify(erro=exc.mensagem), exc.status
        resposta = jsonify(reclamacoes=[para_admin(linha) for linha in linhas])
        resposta.headers["Cache-Control"] = "no-store"
        return resposta

    @app.patch("/api/admin/reclamacoes/<int:item_id>")
    def admin_status(item_id: int):
        recusado = _admin_recusado()
        if recusado:
            return recusado
        corpo = request.get_json(silent=True) or {}
        status = corpo.get("status") if isinstance(corpo, dict) else None
        if status not in STATUS_OK:
            return jsonify(erro="Status inválido. Usa recebida, publicada, resolvida ou rejeitada."), 400
        try:
            row = _abrir().atualizar_status(item_id, status)
        except SupabaseErro as exc:
            return jsonify(erro=exc.mensagem), exc.status
        resposta = jsonify(reclamacao=para_admin(row))
        resposta.headers["Cache-Control"] = "no-store"
        return resposta

    @app.get("/api/fotos/<int:item_id>")
    def foto(item_id: int):
        try:
            cliente = _abrir()
        except SupabaseErro as exc:
            return jsonify(erro=exc.mensagem), exc.status
        if not isinstance(cliente, Postgres):
            return jsonify(erro="Foto não encontrada."), 404
        try:
            dados = cliente.ler_foto(item_id)
        except SupabaseErro as exc:
            return jsonify(erro=exc.mensagem), exc.status
        if not dados:
            return jsonify(erro="Foto não encontrada."), 404
        return Response(dados, mimetype="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/admin")
    @app.get("/admin/")
    def admin_pagina():
        resposta = send_from_directory(RAIZ / "templates", "admin.html")
        resposta.headers["Cache-Control"] = "no-store"
        resposta.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resposta

    if not testing:
        logging.basicConfig(level=logging.INFO)
        log.info(
            "api pronta. supabase=%s",
            _supabase_configurado(),
        )

    return app


app = create_app()
