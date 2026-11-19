"""Banco via a variável `supabase` (URI postgresql:// do painel do Supabase)."""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from supabase_api import SupabaseErro

_SCHEMA = (
    """
    create table if not exists public.reclamacoes (
      id bigint generated always as identity primary key,
      nome text not null,
      endereco text not null,
      descricao text not null,
      foto_path text not null,
      foto_url text not null,
      foto_sha256 text not null,
      foto_bytes bytea,
      status text not null default 'publicada',
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now()
    )
    """,
    "alter table public.reclamacoes add column if not exists foto_bytes bytea",
    "alter table public.reclamacoes drop column if exists telefone",
    "alter table public.reclamacoes drop column if exists bairro",
    "alter table public.reclamacoes drop column if exists tipo",
    """
    create index if not exists reclamacoes_created_at_idx
      on public.reclamacoes (created_at desc)
    """,
    """
    create unique index if not exists reclamacoes_foto_sha256_ativa_idx
      on public.reclamacoes (foto_sha256)
      where status <> 'rejeitada'
    """,
)


def _pronto(linha: dict) -> dict:
    saida = {}
    for chave, valor in linha.items():
        if chave == "foto_bytes":
            continue
        saida[chave] = valor.isoformat() if hasattr(valor, "isoformat") else valor
    return saida


class Postgres:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self._schema_ok = False

    def _conectar(self):
        try:
            return psycopg.connect(
                self.uri,
                sslmode="require",
                row_factory=dict_row,
                prepare_threshold=None,
                connect_timeout=15,
            )
        except psycopg.Error as exc:
            raise SupabaseErro(
                "Não conectei no Supabase. Confere a variável supabase: é a URI que começa com postgresql://.",
                503,
            ) from exc

    def _garantir(self, conn) -> None:
        if self._schema_ok:
            return
        with conn.cursor() as cur:
            for comando in _SCHEMA:
                cur.execute(comando)
        self._schema_ok = True

    def _rodar(self, sql: str, params: tuple = (), um: bool = False):
        try:
            with self._conectar() as conn:
                self._garantir(conn)
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    if um:
                        linha = cur.fetchone()
                        return _pronto(linha) if linha else None
                    return [_pronto(linha) for linha in cur.fetchall()]
        except SupabaseErro:
            raise
        except psycopg.errors.UniqueViolation as exc:
            raise SupabaseErro("Essa foto já foi enviada numa reclamação que ainda está no ar.", 409) from exc
        except psycopg.Error as exc:
            raise SupabaseErro("Não consegui gravar no Supabase agora. Tenta de novo em instantes.", 502) from exc

    def listar_publicas(self) -> list[dict]:
        return self._rodar(
            """
            select id, nome, endereco, descricao, foto_url, status, created_at
            from public.reclamacoes
            where status in ('publicada', 'resolvida')
            order by created_at desc
            limit 100
            """
        )

    def listar_admin(self) -> list[dict]:
        return self._rodar(
            """
            select id, nome, endereco, descricao, foto_url, status, created_at
            from public.reclamacoes
            order by created_at desc
            limit 200
            """
        )

    def salvar(self, campos: dict, foto: bytes, sha: str, status: str, base_url: str) -> dict:
        try:
            with self._conectar() as conn:
                self._garantir(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into public.reclamacoes
                          (nome, endereco, descricao, foto_path, foto_url, foto_sha256, foto_bytes, status)
                        values (%s, %s, %s, %s, 'pendente', %s, %s, %s)
                        returning id
                        """,
                        (
                            campos["nome"],
                            campos["endereco"],
                            campos["descricao"],
                            f"banco/{sha}.jpg",
                            sha,
                            foto,
                            status,
                        ),
                    )
                    novo = cur.fetchone()
                    if not novo:
                        raise SupabaseErro("O Supabase não devolveu a reclamação.", 502)
                    foto_url = f"{base_url}/api/fotos/{novo['id']}"
                    cur.execute(
                        """
                        update public.reclamacoes
                        set foto_url = %s, updated_at = now()
                        where id = %s
                        returning id, nome, endereco, descricao, foto_url, status, created_at
                        """,
                        (foto_url, novo["id"]),
                    )
                    linha = cur.fetchone()
        except SupabaseErro:
            raise
        except psycopg.errors.UniqueViolation as exc:
            raise SupabaseErro("Essa foto já foi enviada numa reclamação que ainda está no ar.", 409) from exc
        except psycopg.Error as exc:
            raise SupabaseErro("Não consegui gravar no Supabase agora. Tenta de novo em instantes.", 502) from exc
        if not linha:
            raise SupabaseErro("O Supabase não devolveu a reclamação.", 502)
        return _pronto(linha)

    def atualizar_status(self, item_id: int, status: str) -> dict:
        linha = self._rodar(
            """
            update public.reclamacoes
            set status = %s, updated_at = now()
            where id = %s
            returning id, nome, endereco, descricao, foto_url, status, created_at
            """,
            (status, item_id),
            um=True,
        )
        if not linha:
            raise SupabaseErro("Reclamação não encontrada.", 404)
        return linha

    def ler_foto(self, item_id: int) -> bytes | None:
        try:
            with self._conectar() as conn:
                self._garantir(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "select foto_bytes from public.reclamacoes where id = %s",
                        (item_id,),
                    )
                    linha = cur.fetchone()
        except SupabaseErro:
            raise
        except psycopg.Error as exc:
            raise SupabaseErro("Não consegui buscar a foto no Supabase.", 502) from exc
        if not linha:
            return None
        return linha["foto_bytes"]
