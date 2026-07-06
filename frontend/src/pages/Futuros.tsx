import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ReferenceLine, ResponsiveContainer,
} from "recharts";
import { api } from "../api";

type Scheduled = { id: string; due_date: string; description: string; amount: number; origin: string; status: string };
type Source = { id: string; bank_name: string | null; type: string };
type ProjectionPoint = { date: string; saldo_projetado: number; saldo_base_desconhecido?: boolean };
type Projection = Record<string, ProjectionPoint[]>;
type Suggestion = { id: string; amount: number; reason: string; status: string; pix_id: string | null; suggested_at: string };

const ORIGEM_LABEL: Record<string, string> = {
  ofx_futuro: "Extrato",
  print_vision: "Print",
  inter_agendado: "Inter",
  fatura_a_vencer: "Fatura",
};

const CORES = ["#2563eb", "#f59e0b", "#10b981", "#8b5cf6"];

const formatBRL = (v: number) =>
  Math.abs(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function Futuros() {
  const [itens, setItens] = useState<Scheduled[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [projection, setProjection] = useState<Projection>({});
  const [sugestoes, setSugestoes] = useState<Suggestion[]>([]);
  const [valores, setValores] = useState<Record<string, string>>({});
  const [confirmando, setConfirmando] = useState<Suggestion | null>(null);
  const [erroConfirm, setErroConfirm] = useState<string | null>(null);
  const [sucessoConfirm, setSucessoConfirm] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  function carregar() {
    setLoading(true);
    setErro(null);
    Promise.all([
      api<Scheduled[]>("/scheduled?status=previsto"),
      api<Source[]>("/sources"),
      api<Projection>("/scheduled/projection?days=30"),
      api<Suggestion[]>("/transfers?status=sugerida"),
    ])
      .then(([sched, srcs, proj, sug]) => {
        setItens(sched);
        setSources(srcs);
        setProjection(proj);
        setSugestoes(sug);
        setValores(Object.fromEntries(sug.map((s) => [s.id, s.amount.toFixed(2)])));
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(carregar, []);

  const nomeFonte = (id: string) => sources.find((s) => s.id === id)?.bank_name ?? id.slice(0, 8);

  const datas = Array.from(
    new Set(Object.values(projection).flatMap((serie) => serie.map((p) => p.date)))
  ).sort();
  const chartData = datas.map((d) => {
    const row: Record<string, number | string> = { date: d.slice(5) };
    for (const [sourceId, serie] of Object.entries(projection)) {
      const ponto = serie.find((p) => p.date === d);
      if (ponto) row[sourceId] = ponto.saldo_projetado;
    }
    return row;
  });

  async function confirmarPix(s: Suggestion) {
    setErroConfirm(null);
    setSucessoConfirm(null);
    try {
      const amount = valores[s.id] ?? s.amount.toFixed(2);
      const r = await api<{ ok: boolean; pix_id: string }>(`/transfers/${s.id}/confirm`, {
        method: "POST",
        body: JSON.stringify({ amount }),
      });
      setSucessoConfirm(`Pix enviado — id ${r.pix_id}`);
      setConfirmando(null);
      carregar();
    } catch (e) {
      setErroConfirm(e instanceof Error ? e.message : String(e));
    }
  }

  async function dispensar(s: Suggestion) {
    await api(`/transfers/${s.id}/dismiss`, { method: "POST" });
    carregar();
  }

  return (
    <div className="page">
      <h2>Futuros</h2>

      {loading && <p>Carregando...</p>}
      {erro && <p className="erro">{erro}</p>}

      {!loading && !erro && Object.keys(projection).length > 0 && (
        <div style={{ width: "100%", height: 220 }}>
          <ResponsiveContainer>
            <LineChart data={chartData}>
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip formatter={(v) => formatBRL(Number(v ?? 0))} />
              <Legend formatter={(id) => nomeFonte(id)} />
              <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 4" />
              {Object.keys(projection).map((sourceId, i) => (
                <Line key={sourceId} type="monotone" dataKey={sourceId}
                     stroke={CORES[i % CORES.length]} dot={false} name={sourceId} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {sugestoes.length > 0 && (
        <section>
          <h3>Sugestões de transferência</h3>
          {sucessoConfirm && <p className="ok">{sucessoConfirm}</p>}
          {sugestoes.map((s) => (
            <div key={s.id} className="card-resumo">
              <p>{s.reason}</p>
              <div className="editor-categoria">
                <input type="number" step="0.01" value={valores[s.id] ?? ""}
                      onChange={(e) => setValores((v) => ({ ...v, [s.id]: e.target.value }))} />
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => { setConfirmando(s); setErroConfirm(null); }}>Confirmar Pix</button>
                  <button onClick={() => dispensar(s)}>Dispensar</button>
                </div>
              </div>
            </div>
          ))}
        </section>
      )}

      {confirmando && (
        <div className="modal-overlay" onClick={() => setConfirmando(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h3>Confirmar transferência Pix</h3>
            <p>Valor: {formatBRL(Number(valores[confirmando.id] ?? confirmando.amount))}</p>
            <p>Destino: sua conta pessoal (chave Pix configurada em Config)</p>
            {erroConfirm && <p className="erro">{erroConfirm}</p>}
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => confirmarPix(confirmando)}>Confirmar e enviar</button>
              <button onClick={() => setConfirmando(null)}>Cancelar</button>
            </div>
          </div>
        </div>
      )}

      <h3>Lançamentos futuros</h3>
      {!loading && !erro && itens.length === 0 && <p>Nenhum lançamento futuro previsto.</p>}

      <ul className="tx-list">
        {itens.map((i) => (
          <li key={i.id} className="tx-item">
            <div className="tx-row">
              <div className="tx-info">
                <span className="tx-data">{i.due_date}</span>
                <span className="tx-desc">{i.description}</span>
                <span className="tx-badges"><span className="badge">{ORIGEM_LABEL[i.origin] ?? i.origin}</span></span>
              </div>
              <span className={i.amount < 0 ? "valor-negativo" : "valor-positivo"}>
                {i.amount < 0 ? "-" : "+"}{formatBRL(i.amount)}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
