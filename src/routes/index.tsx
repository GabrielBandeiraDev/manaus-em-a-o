import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState, type FormEvent } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Problemas de Manaus — Buraco, esgoto, luz" },
      {
        name: "description",
        content: "Manda seu nome, o endereço, o problema e a foto. A notícia entra no mural.",
      },
      { property: "og:title", content: "Problemas de Manaus" },
      {
        property: "og:description",
        content: "Mostro o problema e cobro a solução. Buraco, esgoto, luz nos bairros de Manaus.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

type Noticia = {
  id: number;
  nome: string;
  endereco: string;
  descricao: string;
  foto_url: string;
  status: string;
  created_at: string;
};

const CAMPO =
  "w-full rounded-lg border border-border bg-white px-3 py-2.5 text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/30";
const BANDEIRA = "https://commons.wikimedia.org/wiki/Special:FilePath/Bandeira_de_Manaus.svg";
const REGRAS = [
  "Diz seu nome. Ele sai na notícia.",
  "Endereço com rua e número, do lugar do problema. Ele sai na notícia.",
  "Descreve o problema com clareza, em pelo menos uma frase.",
  "A foto é obrigatória, do problema no local, nítida, sem montagem e sem ofensa. Até 5 MB, JPG, PNG ou WEBP.",
];

function apiBase(): string {
  const bruto = import.meta.env["VITE_API_URL"];
  if (typeof bruto === "string" && bruto.trim() !== "") return bruto.replace(/\/$/, "");
  if (import.meta.env["DEV"]) return "http://127.0.0.1:5000";
  return "";
}

function campo(valor: unknown): string | null {
  return typeof valor === "string" ? valor : null;
}

function lerNoticia(valor: unknown): Noticia | null {
  if (!valor || typeof valor !== "object") return null;
  const item = valor as Record<string, unknown>;
  const idBruto = item["id"];
  const id =
    typeof idBruto === "number" ? idBruto : typeof idBruto === "string" ? Number(idBruto) : NaN;
  const nome = campo(item["nome"]);
  const endereco = campo(item["endereco"]);
  const descricao = campo(item["descricao"]);
  const fotoUrl = campo(item["foto_url"]);
  const status = campo(item["status"]);
  const createdAt = campo(item["created_at"]);
  if (
    !Number.isFinite(id) ||
    !nome ||
    !endereco ||
    !descricao ||
    !fotoUrl ||
    !status ||
    !createdAt
  ) {
    return null;
  }
  return { id, nome, endereco, descricao, foto_url: fotoUrl, status, created_at: createdAt };
}

function mensagemErro(valor: unknown): string | null {
  if (!valor || typeof valor !== "object" || !("erro" in valor)) return null;
  const erro = (valor as { erro?: unknown }).erro;
  return typeof erro === "string" ? erro : null;
}

function quando(iso: string): string {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "";
  return data.toLocaleDateString("pt-BR");
}

function Index() {
  const [itens, setItens] = useState<Noticia[]>([]);
  const [erroMural, setErroMural] = useState("");
  const [nome, setNome] = useState("");
  const [endereco, setEndereco] = useState("");
  const [desc, setDesc] = useState("");
  const [foto, setFoto] = useState<File | null>(null);
  const fotoRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState("");
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    if (!foto) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(foto);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [foto]);

  useEffect(() => {
    let vivo = true;
    const carregar = async () => {
      try {
        const res = await fetch(`${apiBase()}/api/noticias`);
        const data: unknown = await res.json();
        if (!vivo) return;
        if (!res.ok) {
          setErroMural(mensagemErro(data) ?? "O mural não respondeu.");
          return;
        }
        if (
          !data ||
          typeof data !== "object" ||
          !("noticias" in data) ||
          !Array.isArray(data.noticias)
        ) {
          setErroMural("O mural veio num formato inesperado.");
          return;
        }
        setItens(data.noticias.map(lerNoticia).filter((item): item is Noticia => item !== null));
        setErroMural("");
      } catch {
        if (vivo) setErroMural("Sem ligação com o servidor das reclamações.");
      }
    };
    void carregar();
    return () => {
      vivo = false;
    };
  }, [versao]);

  const abertos = itens.filter((item) => item.status === "publicada");
  const resolvidos = itens.filter((item) => item.status === "resolvida");

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (nome.trim().length < 3) {
      setAviso("Diz seu nome. Sem número.");
      return;
    }
    if (endereco.trim().length < 8) {
      setAviso("Endereço com rua e número.");
      return;
    }
    if (desc.trim().length < 20) {
      setAviso("Descreve o problema numa frase. Mínimo de 20 caracteres, máximo de 800.");
      return;
    }
    if (!foto) {
      setAviso("Manda a foto do problema.");
      return;
    }

    const corpo = new FormData();
    corpo.set("nome", nome.trim());
    corpo.set("endereco", endereco.trim());
    corpo.set("descricao", desc.trim());
    corpo.set("foto", foto);

    setEnviando(true);
    setAviso("");
    try {
      const res = await fetch(`${apiBase()}/api/reclamacoes`, { method: "POST", body: corpo });
      const data: unknown = await res.json();
      if (!res.ok) {
        setAviso(mensagemErro(data) ?? "Não consegui enviar. Tenta de novo.");
        return;
      }
      const mensagem =
        data && typeof data === "object" && "mensagem" in data ? data.mensagem : null;
      setAviso(typeof mensagem === "string" ? mensagem : "Reclamação publicada.");
      setNome("");
      setEndereco("");
      setDesc("");
      setFoto(null);
      if (fotoRef.current) fotoRef.current.value = "";
      setVersao((atual) => atual + 1);
    } catch {
      setAviso("Sem ligação com o servidor. Confere se a API está no ar.");
    } finally {
      setEnviando(false);
    }
  };

  const Card = ({ item }: { item: Noticia }) => (
    <article className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      {item.foto_url.startsWith("http://") || item.foto_url.startsWith("https://") ? (
        <img
          src={item.foto_url}
          alt={`Problema em ${item.endereco}`}
          className="h-48 w-full object-cover"
        />
      ) : null}
      <div className="space-y-2 p-4">
        <p className="font-bold text-primary">{item.endereco}</p>
        <p className="whitespace-pre-wrap">{item.descricao}</p>
        <p className="text-sm text-muted-foreground">
          {item.nome} · {quando(item.created_at)}
        </p>
      </div>
    </article>
  );

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-primary text-primary-foreground">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-5 px-4 py-8 text-center md:flex-row md:text-left">
          <img
            src={BANDEIRA}
            alt="Bandeira de Manaus"
            className="h-16 rounded-md shadow-md ring-2 ring-white/40"
          />
          <div className="flex-1">
            <p className="text-sm font-bold tracking-[0.18em] uppercase">Manaus</p>
            <h1 className="text-3xl font-black md:text-4xl">Problemas de Manaus</h1>
            <p className="mt-1 text-base text-white/90">
              Buraco, esgoto, luz. Mostro o problema e cobro a solução.
            </p>
          </div>
          <a
            href="https://instagram.com/bandeiraa.g"
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-secondary px-5 py-2.5 font-bold text-secondary-foreground shadow-sm"
          >
            @bandeiraa.g
          </a>
        </div>
      </header>

      <section className="bg-accent text-accent-foreground">
        <div className="mx-auto max-w-4xl px-4 py-8">
          <h2 className="mb-4 text-center text-2xl font-black md:text-left">O mural</h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-secondary p-5 text-center text-secondary-foreground shadow-md">
              <div className="text-4xl font-black">{abertos.length}</div>
              <div className="font-bold">Sem solução</div>
            </div>
            <div className="rounded-xl bg-white p-5 text-center text-primary shadow-md">
              <div className="text-4xl font-black">{resolvidos.length}</div>
              <div className="font-bold">Resolvidos</div>
            </div>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-4xl space-y-8 px-4 py-8">
        <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <h2 className="text-xl font-black text-primary">Regras</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed">
            {REGRAS.map((regra) => (
              <li key={regra}>{regra}</li>
            ))}
          </ol>
        </section>

        <form
          onSubmit={enviar}
          className="space-y-3 rounded-2xl border border-border bg-card p-5 shadow-sm"
        >
          <h2 className="text-xl font-black text-primary">Faça sua reclamação</h2>
          <p className="text-sm text-muted-foreground">
            Nome, endereço, o problema e a foto. Isso entra no mural.
          </p>
          <input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Seu nome"
            aria-label="Nome"
            className={CAMPO}
          />
          <input
            value={endereco}
            onChange={(e) => setEndereco(e.target.value)}
            placeholder="Rua, número, ponto de referência"
            aria-label="Endereço"
            className={CAMPO}
          />
          <textarea
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="Descreva o problema"
            aria-label="Descrição"
            rows={3}
            maxLength={800}
            className={CAMPO}
          />
          <label className="flex cursor-pointer items-center justify-center rounded-lg border border-primary bg-white px-3 py-3 text-sm font-bold text-primary">
            <span className="truncate">{foto ? foto.name : "Escolher foto do problema"}</span>
            <input
              ref={fotoRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              aria-label="Foto do problema"
              onChange={(e) => setFoto(e.target.files?.[0] ?? null)}
              className="sr-only"
            />
          </label>
          {preview ? (
            <img
              src={preview}
              alt="Prévia da foto"
              className="h-48 w-full rounded-xl object-cover"
            />
          ) : null}
          {aviso ? (
            <p className="rounded-lg bg-muted px-3 py-2 text-sm font-semibold text-foreground">
              {aviso}
            </p>
          ) : null}
          <button
            disabled={enviando}
            className="w-full rounded-lg bg-secondary py-3 font-black text-secondary-foreground shadow-sm disabled:opacity-60"
          >
            {enviando ? "Enviando..." : "Enviar reclamação"}
          </button>
        </form>

        {erroMural ? (
          <p className="rounded-lg bg-muted px-3 py-2 text-sm font-semibold">{erroMural}</p>
        ) : null}

        <section>
          <h2 className="mb-3 text-2xl font-black text-primary">Sem solução</h2>
          {abertos.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma reclamação publicada ainda.</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {abertos.map((item) => (
                <Card key={item.id} item={item} />
              ))}
            </div>
          )}
        </section>
        <section>
          <h2 className="mb-3 text-2xl font-black text-primary">Resolvidos</h2>
          {resolvidos.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum problema marcado como resolvido.</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {resolvidos.map((item) => (
                <Card key={item.id} item={item} />
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="bg-primary py-6 text-center text-sm text-primary-foreground">
        Comunidade Problemas de Manaus ·{" "}
        <a className="font-bold underline" href="https://instagram.com/bandeiraa.g">
          @bandeiraa.g
        </a>
        {" · "}
        <a className="underline" href={`${apiBase()}/admin`}>
          Equipe
        </a>
      </footer>
    </div>
  );
}
