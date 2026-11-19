import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Problemas de Manaus — Buraco, esgoto, luz" },
      { name: "description", content: "Comunidade que mostra os problemas dos bairros de Manaus e cobra a solução." },
      { property: "og:title", content: "Problemas de Manaus" },
      { property: "og:description", content: "Mostro o problema e cobro a solução. Buraco, esgoto, luz nos bairros de Manaus." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

type Item = { id: number; bairro: string; tipo: string; desc: string; resolvido: boolean };
const INICIAL: Item[] = [
  { id: 1, bairro: "Cidade Nova", tipo: "Buraco", desc: "Cratera na avenida principal há meses.", resolvido: false },
  { id: 2, bairro: "Compensa", tipo: "Esgoto", desc: "Esgoto a céu aberto na frente das casas.", resolvido: false },
  { id: 3, bairro: "Jorge Teixeira", tipo: "Luz", desc: "Rua inteira sem iluminação à noite.", resolvido: false },
  { id: 4, bairro: "Centro", tipo: "Buraco", desc: "Buraco tapado depois da cobrança.", resolvido: true },
];
const TIPOS = ["Buraco", "Esgoto", "Luz", "Lixo", "Alagamento", "Outro"];
const BANDEIRA = "https://commons.wikimedia.org/wiki/Special:FilePath/Bandeira_de_Manaus.svg";

function Index() {
  const [itens, setItens] = useState<Item[]>(INICIAL);
  const [bairro, setBairro] = useState("");
  const [tipo, setTipo] = useState(TIPOS[0]);
  const [desc, setDesc] = useState("");

  useEffect(() => {
    const s = localStorage.getItem("manaus-problemas");
    if (s) setItens(JSON.parse(s));
  }, []);
  const salvar = (n: Item[]) => { setItens(n); localStorage.setItem("manaus-problemas", JSON.stringify(n)); };

  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    if (!bairro.trim() || !desc.trim()) return;
    salvar([{ id: Date.now(), bairro, tipo, desc, resolvido: false }, ...itens]);
    setBairro(""); setDesc("");
  };

  const abertos = itens.filter((i) => !i.resolvido);
  const resolvidos = itens.filter((i) => i.resolvido);

  const Card = ({ i }: { i: Item }) => (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="rounded bg-primary px-2 py-0.5 text-xs font-bold text-primary-foreground">{i.tipo}</span>
        <span className="text-sm text-muted-foreground">{i.bairro}</span>
      </div>
      <p className="mt-2">{i.desc}</p>
      <button
        onClick={() => salvar(itens.map((x) => (x.id === i.id ? { ...x, resolvido: !x.resolvido } : x)))}
        className="mt-3 text-sm font-semibold text-accent-foreground underline"
      >
        {i.resolvido ? "Voltar pra sem solução" : "Marcar como resolvido"}
      </button>
    </div>
  );

  return (
    <div className="min-h-screen">
      <header className="bg-primary text-primary-foreground">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 px-4 py-10 text-center">
          <img src={BANDEIRA} alt="Bandeira de Manaus" className="h-20 rounded shadow-lg" />
          <h1 className="text-4xl font-black uppercase md:text-5xl">Problemas de Manaus</h1>
          <p className="text-lg">Buraco, esgoto, luz. Mostro o problema e cobro a solução.</p>
          <a href="https://instagram.com/bandeiraa.g" target="_blank" rel="noreferrer"
            className="rounded-full bg-secondary px-5 py-2 font-bold text-secondary-foreground">
            Siga @bandeiraa.g no Instagram
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-10 px-4 py-10">
        <div className="grid grid-cols-2 gap-4 text-center">
          <div className="rounded-lg bg-destructive p-6 text-destructive-foreground">
            <div className="text-4xl font-black">{abertos.length}</div><div className="font-semibold">Sem solução</div>
          </div>
          <div className="rounded-lg bg-accent p-6 text-accent-foreground">
            <div className="text-4xl font-black">{resolvidos.length}</div><div className="font-semibold">Resolvidos</div>
          </div>
        </div>

        <form onSubmit={enviar} className="space-y-3 rounded-lg border bg-card p-5">
          <h2 className="text-xl font-bold">Faça sua reclamação</h2>
          <input value={bairro} onChange={(e) => setBairro(e.target.value)} placeholder="Seu bairro"
            className="w-full rounded border bg-background px-3 py-2" />
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="w-full rounded border bg-background px-3 py-2">
            {TIPOS.map((t) => <option key={t}>{t}</option>)}
          </select>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Descreva o problema" rows={3}
            className="w-full rounded border bg-background px-3 py-2" />
          <button className="w-full rounded bg-primary py-2 font-bold text-primary-foreground">Enviar reclamação</button>
        </form>

        <section>
          <h2 className="mb-3 text-2xl font-black">Sem solução</h2>
          <div className="grid gap-3 md:grid-cols-2">{abertos.map((i) => <Card key={i.id} i={i} />)}</div>
        </section>
        <section>
          <h2 className="mb-3 text-2xl font-black">Resolvidos</h2>
          <div className="grid gap-3 md:grid-cols-2">{resolvidos.map((i) => <Card key={i.id} i={i} />)}</div>
        </section>
      </main>

      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        Comunidade Problemas de Manaus · <a className="underline" href="https://instagram.com/bandeiraa.g">@bandeiraa.g</a>
      </footer>
    </div>
  );
}
