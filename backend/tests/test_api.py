import io

from PIL import Image

from app import create_app, para_publico
from supabase_api import COLUNAS_ADMIN, COLUNAS_PUBLICAS


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), (20, 40, 180)).save(buf, format="PNG")
    return buf.getvalue()


def _formulario():
    return {
        "nome": "Ana Souza",
        "endereco": "Rua das Flores, 10",
        "descricao": "Cratera aberta na avenida há vários meses.",
        "foto": (io.BytesIO(_png()), "buraco.png"),
    }


def _cliente(monkeypatch, testing=True):
    monkeypatch.delenv("supabase", raising=False)
    monkeypatch.delenv("SUPABASE", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    return create_app(testing=testing).test_client()


def test_select_publico_e_nome_endereco_problema_e_foto():
    colunas = COLUNAS_PUBLICAS.split(",")
    assert colunas == COLUNAS_ADMIN.split(",")
    assert "telefone" not in colunas
    assert "endereco" in colunas
    assert "nome" in colunas
    assert "descricao" in colunas
    assert "foto_url" in colunas


def test_para_publico_esconde_contato():
    saida = para_publico(
        {
            "id": 1,
            "nome": "Ana Souza",
            "endereco": "Rua das Flores, 10",
            "descricao": "Cratera aberta na avenida há vários meses.",
            "foto_url": "https://exemplo.supabase.co/foto.jpg",
            "status": "publicada",
            "created_at": "2026-01-01T00:00:00+00:00",
            "telefone": "92988887777",
            "endereco": "Rua das Flores, 10",
            "foto_path": "noticias/segredo.jpg",
            "foto_sha256": "a" * 64,
        }
    )
    assert saida["nome"] == "Ana Souza"
    assert saida["endereco"] == "Rua das Flores, 10"
    assert "telefone" not in saida
    assert "bairro" not in saida


def test_uri_codifica_arroba_da_senha_e_tira_colchetes(monkeypatch):
    from app import _valor_supabase

    monkeypatch.setenv(
        "supabase",
        "postgresql://postgres:[abc@def]@db.exemplo.supabase.co:5432/postgres",
    )
    uri = _valor_supabase()
    assert uri == "postgresql://postgres:abc%40def@db.exemplo.supabase.co:5432/postgres"
    assert "[abc@def]" not in uri


def test_health_le_variavel_supabase_sem_vazar_senha(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv(
        "supabase",
        "postgresql://postgres:segredo@db.exemplo.supabase.co:5432/postgres",
    )
    cliente = create_app(testing=True).test_client()
    resposta = cliente.get("/health")
    texto = resposta.get_data(as_text=True)
    assert resposta.get_json()["supabase"] is True
    assert "segredo" not in texto
    assert "postgresql" not in texto

    recusado = cliente.post("/api/reclamacoes", data={"nome": "Ana"})
    assert recusado.status_code == 400


def test_variavel_supabase_invalida_nao_eco_o_valor(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("supabase", "isto-nao-e-uri")
    cliente = create_app(testing=True).test_client()
    resposta = cliente.post("/api/reclamacoes", data=_formulario())
    assert resposta.status_code == 503
    assert "postgresql://" in resposta.get_json()["erro"]
    assert "isto-nao-e-uri" not in resposta.get_data(as_text=True)


def test_health_regras_e_admin(monkeypatch):
    cliente = _cliente(monkeypatch)
    saude = cliente.get("/health")
    assert saude.status_code == 200
    assert saude.get_json()["ok"] is True
    assert saude.get_json()["supabase"] is False

    regras = cliente.get("/api/regras")
    assert regras.status_code == 200
    assert "foto" in " ".join(regras.get_json()["regras"]).lower()

    pagina = cliente.get("/admin")
    assert pagina.status_code == 200
    assert "endereço" in pagina.get_data(as_text=True)
    assert pagina.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_post_sem_foto_e_sem_multipart(monkeypatch):
    cliente = _cliente(monkeypatch)
    recusado = cliente.post("/api/reclamacoes", json={"nome": "Ana Souza"})
    assert recusado.status_code == 415

    incompleto = cliente.post("/api/reclamacoes", data={"nome": "Ana"})
    assert incompleto.status_code == 400
    assert "telefone" not in incompleto.get_json()


def test_post_valido_sem_supabase_nao_vaza_telefone(monkeypatch):
    cliente = _cliente(monkeypatch)
    resposta = cliente.post("/api/reclamacoes", data=_formulario())
    assert resposta.status_code == 503
    corpo = resposta.get_data()
    assert b"92988887777" not in corpo
    assert b"Rua das Flores" not in corpo
    assert "erro" in resposta.get_json()


def test_admin_exige_token(monkeypatch):
    cliente = _cliente(monkeypatch)
    assert cliente.get("/api/admin/reclamacoes").status_code == 503

    monkeypatch.setenv("ADMIN_TOKEN", "segredo-da-equipe")
    cliente = create_app(testing=True).test_client()
    assert cliente.get("/api/admin/reclamacoes").status_code == 401
    assert cliente.get("/api/admin/reclamacoes", headers={"X-Admin-Token": "outro"}).status_code == 401
    autorizado = cliente.get("/api/admin/reclamacoes", headers={"X-Admin-Token": "segredo-da-equipe"})
    assert autorizado.status_code == 503
    assert b"92988887777" not in autorizado.get_data()


def test_limite_de_envio(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    cliente = _cliente(monkeypatch, testing=False)
    primeiro = cliente.post("/api/reclamacoes", data=_formulario())
    segundo = cliente.post("/api/reclamacoes", data=_formulario())
    assert primeiro.status_code == 503
    assert segundo.status_code == 429
