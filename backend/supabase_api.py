"""Acesso ao Supabase só com a service_role, no servidor."""

from __future__ import annotations

from datetime import datetime, timezone

import requests

COLUNAS_PUBLICAS = "id,nome,endereco,descricao,foto_url,status,created_at"
COLUNAS_ADMIN = COLUNAS_PUBLICAS
BUCKET = "reclamacoes-fotos"


class SupabaseErro(Exception):
    def __init__(self, mensagem: str, status: int = 502) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


class Supabase:
    def __init__(self, url: str, chave: str) -> None:
        self.url = url.rstrip("/")
        self.chave = chave

    def _enviar(self, metodo, url: str, **kwargs) -> requests.Response:
        try:
            return metodo(url, **kwargs)
        except requests.RequestException as exc:
            raise SupabaseErro("Não consegui alcançar o Supabase agora.", 503) from exc

    def _rest(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.chave}",
            "apikey": self.chave,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }

    def _erro(self, resposta: requests.Response, armazenamento: bool = False) -> None:
        codigo = ""
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = {}
        if isinstance(corpo, dict):
            codigo = str(corpo.get("code", ""))
        if codigo == "23505":
            raise SupabaseErro("Essa foto já foi enviada numa reclamação que ainda está no ar.", 409)
        if resposta.status_code in (401, 403):
            raise SupabaseErro(
                "A chave do Supabase foi recusada. No Render, usa a service_role. Nunca a anon.",
                503,
            )
        if armazenamento and resposta.status_code == 404:
            raise SupabaseErro(
                "O bucket reclamacoes-fotos não existe. Roda o SQL em backend/sql/schema.sql no Supabase.",
                503,
            )
        raise SupabaseErro("Não consegui gravar no Supabase agora. Tenta de novo em instantes.", 502)

    def _linhas(self, resposta: requests.Response) -> list[dict]:
        if resposta.status_code >= 400:
            self._erro(resposta)
        if not resposta.content:
            return []
        dados = resposta.json()
        if isinstance(dados, list):
            return dados
        if isinstance(dados, dict):
            return [dados]
        return []

    def subir_foto(self, path: str, conteudo: bytes, content_type: str) -> str:
        resposta = self._enviar(
            requests.post,
            f"{self.url}/storage/v1/object/{BUCKET}/{path}",
            headers={
                "Authorization": f"Bearer {self.chave}",
                "apikey": self.chave,
                "Content-Type": content_type,
                "x-upsert": "false",
            },
            data=conteudo,
            timeout=(5, 90),
        )
        if resposta.status_code >= 400:
            self._erro(resposta, armazenamento=True)
        return f"{self.url}/storage/v1/object/public/{BUCKET}/{path}"

    def apagar_foto(self, path: str) -> None:
        try:
            requests.delete(
                f"{self.url}/storage/v1/object/{BUCKET}/{path}",
                headers={
                    "Authorization": f"Bearer {self.chave}",
                    "apikey": self.chave,
                },
                timeout=(5, 20),
            )
        except requests.RequestException:
            return

    def inserir(self, dados: dict) -> dict:
        resposta = self._enviar(
            requests.post,
            f"{self.url}/rest/v1/reclamacoes",
            headers=self._rest(),
            params={"select": COLUNAS_PUBLICAS},
            json=dados,
            timeout=(5, 20),
        )
        linhas = self._linhas(resposta)
        if not linhas:
            raise SupabaseErro("O Supabase não devolveu a reclamação.", 502)
        return linhas[0]

    def listar_publicas(self) -> list[dict]:
        resposta = self._enviar(
            requests.get,
            f"{self.url}/rest/v1/reclamacoes",
            headers=self._rest(),
            params={
                "select": COLUNAS_PUBLICAS,
                "status": "in.(publicada,resolvida)",
                "order": "created_at.desc",
                "limit": "100",
            },
            timeout=(5, 20),
        )
        return self._linhas(resposta)

    def listar_admin(self) -> list[dict]:
        resposta = self._enviar(
            requests.get,
            f"{self.url}/rest/v1/reclamacoes",
            headers=self._rest(),
            params={
                "select": COLUNAS_ADMIN,
                "order": "created_at.desc",
                "limit": "200",
            },
            timeout=(5, 20),
        )
        return self._linhas(resposta)

    def atualizar_status(self, item_id: int, status: str) -> dict:
        resposta = self._enviar(
            requests.patch,
            f"{self.url}/rest/v1/reclamacoes",
            headers=self._rest(),
            params={"id": f"eq.{item_id}", "select": COLUNAS_ADMIN},
            json={
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            timeout=(5, 20),
        )
        linhas = self._linhas(resposta)
        if not linhas:
            raise SupabaseErro("Reclamação não encontrada.", 404)
        return linhas[0]
