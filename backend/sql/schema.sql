-- Problemas de Manaus
-- Rode este arquivo inteiro no SQL Editor do Supabase (uma vez).
-- A API Flask usa a chave service_role. O navegador não acessa esta tabela.
-- A notícia pública leva nome, endereço, problema e foto.

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
  updated_at timestamptz not null default now(),
  constraint reclamacoes_nome_chk check (
    char_length(btrim(nome)) between 3 and 80
    and btrim(nome) ~ '[[:alpha:]]'
    and btrim(nome) !~ '[0-9]'
  ),
  constraint reclamacoes_endereco_chk check (char_length(btrim(endereco)) between 8 and 180),
  constraint reclamacoes_descricao_chk check (char_length(btrim(descricao)) between 20 and 800),
  constraint reclamacoes_status_chk check (
    status in ('recebida', 'publicada', 'resolvida', 'rejeitada')
  ),
  constraint reclamacoes_foto_chk check (
    foto_path <> ''
    and foto_url <> ''
    and foto_sha256 ~ '^[a-f0-9]{64}$'
  )
);

comment on table public.reclamacoes is
  'Reclamacoes com nome, endereco, problema e foto.';

comment on column public.reclamacoes.endereco is
  'Endereco do problema. Aparece na noticia.';

alter table public.reclamacoes drop constraint if exists reclamacoes_telefone_chk;
alter table public.reclamacoes drop constraint if exists reclamacoes_bairro_chk;
alter table public.reclamacoes drop constraint if exists reclamacoes_tipo_chk;
alter table public.reclamacoes drop column if exists telefone;
alter table public.reclamacoes drop column if exists bairro;
alter table public.reclamacoes drop column if exists tipo;
alter table public.reclamacoes add column if not exists foto_bytes bytea;

create index if not exists reclamacoes_created_at_idx
  on public.reclamacoes (created_at desc);

create index if not exists reclamacoes_feed_idx
  on public.reclamacoes (created_at desc)
  where status in ('publicada', 'resolvida');

create unique index if not exists reclamacoes_foto_sha256_ativa_idx
  on public.reclamacoes (foto_sha256)
  where status <> 'rejeitada';

alter table public.reclamacoes enable row level security;
alter table public.reclamacoes force row level security;

revoke all on table public.reclamacoes from public;
revoke all on table public.reclamacoes from anon;
revoke all on table public.reclamacoes from authenticated;
grant all on table public.reclamacoes to service_role;

do $$
declare
  seq text;
begin
  seq := pg_get_serial_sequence('public.reclamacoes', 'id');
  if seq is not null then
    execute format('grant usage, select on sequence %s to service_role', seq);
  end if;
end $$;

-- Fotos da noticia. Publicas para o mural carregar a imagem.
-- Upload só com service_role (a API). Sem policy de insert para anon.
do $$
begin
  insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
  values (
    'reclamacoes-fotos',
    'reclamacoes-fotos',
    true,
    5242880,
    array['image/jpeg', 'image/png', 'image/webp']
  )
  on conflict (id) do update
  set
    public = true,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
exception
  when undefined_column then
    insert into storage.buckets (id, name, public)
    values ('reclamacoes-fotos', 'reclamacoes-fotos', true)
    on conflict (id) do update set public = true;
end $$;
