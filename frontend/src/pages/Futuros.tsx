import { useEffect, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, Legend, ReferenceLine,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import { api } from "../api";
import { useDark, chartTheme, tooltipProps, brlCompacto, mesCurto, MESES_LONGOS } from "../theme";

type Scheduled = {
  id: string; due_date: string; description: string; amount: number; origin: string;
  status: string; recurring_rule_id: string | null;
};
type Source = { id: string; bank_name: string | null; type: string };
type ProjectionPoint = { date: string; saldo_projetado: number; saldo_base_desconhecido?: boolean };
type Projection = Record<string, ProjectionPoint[]>;
type Suggestion = { id: string; amount: number; reason: string; status: string; pix_id: string | null; suggested_at: string };
type Evolucao = { month: string; total: number };
type ParcelaFutura = {
  descricao: string; entity: string; installment_no_atual: number; installment_total: number;
  valor_parcela: number; parcelas_restantes: { competencia: string; numero: number; valor: number }[];
};
type CashflowPoint = { month: string; total: number };
type RecurringRule = {
  id: string; description: string; amount: number; entity: string; source_id: string | null;
  frequency: "mensal" | "anual"; day: number; month: number | null;
};

const ORIGEM_LABEL: Record<string, string> = {
  ofx_futuro: "Extrato",
  print_vision: "Print",
  inter_agendado: "Inter",
  fatura_a_vencer: "Fatura",
  manual: "Recorrente",
};

function mesAtual(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

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
  const [historico, setHistorico] = useState<Evolucao[]>([]);
  const [parcelas, setParcelas] = useState<ParcelaFutura[]>([]);
  const [cashflow, setCashflow] = useState<CashflowPoint[]>([]);
  const [recorrentes, setRecorrentes] = useState<RecurringRule[]>([]);
  const [novoAberto, setNovoAberto] = useState(false);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const dark = useDark();
  const tema = chartTheme(dark);

  function carregar() {
    setLoading(true);
    setErro(null);
    Promise.all([
      api<Scheduled[]>("/scheduled?status=previsto"),
      api<Source[]>("/sources"),
      api<Projection>("/scheduled/projection?days=30"),
      api<Suggestion[]>("/transfers?status=sugerida"),
      api<{ evolucao: Evolucao[] }>(`/dashboard/summary?month=${mesAtual()}&months=12`),
      api<ParcelaFutura[]>("/scheduled/parcelas-futuras"),
      api<CashflowPoint[]>("/scheduled/cashflow?months=6"),
      api<RecurringRule[]>("/recurring"),
    ])
      .then(([sched, srcs, proj, sug, dash, parc, fluxo, rec]) => {
        setItens(sched);
        setSources(srcs);
        setProjection(proj);
        setSugestoes(sug);
        setValores(Object.fromEntries(sug.map((s) => [s.id, s.amount.toFixed(2)])));
        setHistorico(dash.evolucao);
        setParcelas(parc);
        setCashflow(fluxo);
        setRecorrentes(rec);
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

  async function excluirRecorrente(id: string) {
    await api(`/recurring/${id}`, { method: "DELETE" });
    carregar();
  }

  function descricaoRecorrencia(r: RecurringRule): string {
    if (r.frequency === "anual" && r.month) {
      return `Anual — dia ${r.day} de ${MESES_LONGOS[r.month - 1]}`;
    }
    return `Mensal — todo dia ${r.day}`;
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1 className="page-title">Fluxo de Caixa</h1>
        <p className="page-sub">histórico, parcelas e projeção</p>
      </header>

      {loading && (
        <>
          <div className="skeleton" style={{ height: 230 }} />
          <div className="skeleton" style={{ height: 190 }} />
          <div className="skeleton" style={{ height: 120 }} />
        </>
      )}
      {erro && <p className="erro">{erro}</p>}

      {!loading && !erro && Object.keys(projection).length > 0 && (
        <section className="card">
          <span className="card-label">Saldo projetado — 30 dias</span>
          <div style={{ width: "100%", height: 210 }}>
            <ResponsiveContainer>
              <LineChart data={chartData} margin={{ top: 4, right: 6, left: -10, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={tema.grid} />
                <XAxis dataKey="date" tickLine={false} axisLine={{ stroke: tema.grid }}
                       tick={{ fontSize: 11, fill: tema.axis }} minTickGap={24} />
                <YAxis tickFormatter={brlCompacto} tickLine={false} axisLine={false}
                       tick={{ fontSize: 11, fill: tema.axis }} width={46} />
                <Tooltip formatter={(v) => formatBRL(Number(v ?? 0))} {...tooltipProps(dark)} />
                <Legend formatter={(id) => nomeFonte(String(id))}
                        wrapperStyle={{ fontSize: 12 }} iconType="plainline" />
                <ReferenceLine y={0} stroke={tema.negative} strokeDasharray="4 4" />
                {Object.keys(projection).map((sourceId, i) => (
                  <Line key={sourceId} type="monotone" dataKey={sourceId}
                        stroke={tema.series[i % tema.series.length]} strokeWidth={2}
                        dot={false} activeDot={{ r: 4 }} name={sourceId} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {!loading && !erro && historico.length > 0 && (
        <section className="card">
          <span className="card-label">Histórico — últimos 12 meses</span>
          <div style={{ width: "100%", height: 190 }}>
            <ResponsiveContainer>
              <BarChart data={historico} margin={{ top: 4, right: 4, left: -14, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={tema.grid} />
                <XAxis dataKey="month" tickFormatter={mesCurto} tickLine={false}
                       axisLine={{ stroke: tema.grid }} tick={{ fontSize: 11, fill: tema.axis }} />
                <YAxis tickFormatter={brlCompacto} tickLine={false} axisLine={false}
                       tick={{ fontSize: 11, fill: tema.axis }} width={46} />
                <Tooltip formatter={(v) => formatBRL(Number(v ?? 0))}
                         labelFormatter={(m) => mesCurto(String(m))}
                         cursor={{ fill: "rgba(137,135,129,0.08)" }} {...tooltipProps(dark)} />
                <Bar dataKey="total" fill={tema.accent} radius={[4, 4, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {!loading && !erro && parcelas.length > 0 && (
        <section className="card">
          <span className="card-label">Parcelas em aberto</span>
          <ul className="tx-list">
            {parcelas.map((p, i) => (
              <li key={i} className="tx-item">
                <div className="tx-row" style={{ cursor: "default" }}>
                  <div className="tx-info">
                    <span className="tx-desc">{p.descricao}</span>
                    <span className="tx-data">
                      parcela {p.installment_no_atual}/{p.installment_total} — termina em{" "}
                      {mesCurto(p.parcelas_restantes[p.parcelas_restantes.length - 1].competencia)}
                    </span>
                  </div>
                  <span className="valor-negativo">{formatBRL(p.valor_parcela)}/mês</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!loading && !erro && cashflow.length > 0 && (
        <section className="card">
          <span className="card-label">Fluxo de caixa projetado — próximos meses</span>
          <div style={{ width: "100%", height: 190 }}>
            <ResponsiveContainer>
              <BarChart data={cashflow} margin={{ top: 4, right: 4, left: -14, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={tema.grid} />
                <XAxis dataKey="month" tickFormatter={mesCurto} tickLine={false}
                       axisLine={{ stroke: tema.grid }} tick={{ fontSize: 11, fill: tema.axis }} />
                <YAxis tickFormatter={brlCompacto} tickLine={false} axisLine={false}
                       tick={{ fontSize: 11, fill: tema.axis }} width={46} />
                <Tooltip formatter={(v) => formatBRL(Number(v ?? 0))}
                         labelFormatter={(m) => mesCurto(String(m))}
                         cursor={{ fill: "rgba(137,135,129,0.08)" }} {...tooltipProps(dark)} />
                <ReferenceLine y={0} stroke={tema.grid} />
                <Bar dataKey="total" radius={[3, 3, 3, 3]} maxBarSize={28}>
                  {cashflow.map((c, i) => (
                    <Cell key={i} fill={c.total < 0 ? tema.negative : tema.positive} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {sugestoes.length > 0 && (
        <section>
          {sucessoConfirm && <p className="ok">{sucessoConfirm}</p>}
          {sugestoes.map((s) => (
            <div key={s.id} className="card insight">
              <span className="card-label">Sugestão de transferência</span>
              <p className="insight-texto">{s.reason}</p>
              <div className="editor-categoria">
                <input type="number" step="0.01" value={valores[s.id] ?? ""}
                      onChange={(e) => setValores((v) => ({ ...v, [s.id]: e.target.value }))} />
                <div className="linha-acoes">
                  <button className="btn-primary"
                          onClick={() => { setConfirmando(s); setErroConfirm(null); }}>
                    Confirmar Pix
                  </button>
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
            <p>
              Valor: <strong>{formatBRL(Number(valores[confirmando.id] ?? confirmando.amount))}</strong>
            </p>
            <p className="hint">Destino: sua conta pessoal (chave Pix configurada em Config)</p>
            {erroConfirm && <p className="erro">{erroConfirm}</p>}
            <div className="modal-acoes">
              <button className="btn-primary" onClick={() => confirmarPix(confirmando)}>
                Confirmar e enviar
              </button>
              <button onClick={() => setConfirmando(null)}>Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {!loading && !erro && (
        <section className="card">
          <div className="spread">
            <span className="card-label" style={{ marginBottom: 0 }}>Lançamentos recorrentes</span>
            <button className="btn-primary" onClick={() => setNovoAberto(true)}>
              + Novo lançamento
            </button>
          </div>
          {recorrentes.length === 0 && (
            <p className="hint">
              Nenhum lançamento recorrente cadastrado. Use para coisas como aluguel mensal ou IPVA anual.
            </p>
          )}
          <ul className="tx-list">
            {recorrentes.map((r) => (
              <li key={r.id} className="tx-item">
                <div className="tx-row" style={{ cursor: "default" }}>
                  <div className="tx-info">
                    <span className="tx-desc">{r.description}</span>
                    <span className="tx-data">{descricaoRecorrencia(r)}</span>
                  </div>
                  <div className="linha-acoes" style={{ alignItems: "center" }}>
                    <span className={r.amount < 0 ? "valor-negativo" : "valor-positivo"}>
                      {r.amount < 0 ? "−" : "+"}{formatBRL(r.amount)}
                    </span>
                    <button onClick={() => excluirRecorrente(r.id)}>Excluir</button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {novoAberto && (
        <NovoLancamento
          sources={sources}
          onFechar={() => setNovoAberto(false)}
          onCriado={() => { setNovoAberto(false); carregar(); }}
        />
      )}

      {!loading && !erro && (
        <section className="card">
          <span className="card-label">Lançamentos futuros</span>
          {itens.length === 0 && <p className="hint">Nenhum lançamento futuro previsto.</p>}
          <ul className="tx-list">
            {itens.map((i) => (
              <li key={i.id} className="tx-item">
                <div className="tx-row" style={{ cursor: "default" }}>
                  <div className="tx-info">
                    <span className="tx-data">{i.due_date}</span>
                    <span className="tx-desc">{i.description}</span>
                    <span className="tx-badges">
                      <span className="badge">{ORIGEM_LABEL[i.origin] ?? i.origin}</span>
                    </span>
                  </div>
                  <span className={i.amount < 0 ? "valor-negativo" : "valor-positivo"}>
                    {i.amount < 0 ? "−" : "+"}{formatBRL(i.amount)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function NovoLancamento({ sources, onFechar, onCriado }: {
  sources: Source[]; onFechar: () => void; onCriado: () => void;
}) {
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState("");
  const [tipo, setTipo] = useState<"despesa" | "receita">("despesa");
  const [frequencia, setFrequencia] = useState<"mensal" | "anual">("mensal");
  const [dia, setDia] = useState("5");
  const [mes, setMes] = useState("1");
  const [entidade, setEntidade] = useState("pessoal");
  const [sourceId, setSourceId] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function salvar() {
    setErro(null);
    if (!descricao.trim() || !valor) {
      setErro("Preencha descrição e valor.");
      return;
    }
    setEnviando(true);
    try {
      const amount = tipo === "despesa" ? -Math.abs(Number(valor)) : Math.abs(Number(valor));
      await api("/recurring", {
        method: "POST",
        body: JSON.stringify({
          description: descricao, amount, entity: entidade,
          source_id: sourceId || null, frequency: frequencia,
          day: Number(dia), month: frequencia === "anual" ? Number(mes) : null,
        }),
      });
      onCriado();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onFechar}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <h3>Novo lançamento recorrente</h3>
        <div className="editor-categoria">
          <input placeholder="Descrição (ex: Aluguel, IPVA)" value={descricao}
                 onChange={(e) => setDescricao(e.target.value)} />
          <div className="linha-acoes">
            <input type="number" step="0.01" placeholder="Valor" value={valor}
                   onChange={(e) => setValor(e.target.value)} style={{ flex: 1 }} />
            <select value={tipo} onChange={(e) => setTipo(e.target.value as "despesa" | "receita")}>
              <option value="despesa">Despesa</option>
              <option value="receita">Receita</option>
            </select>
          </div>
          <div className="linha-acoes">
            <select value={frequencia}
                    onChange={(e) => setFrequencia(e.target.value as "mensal" | "anual")}
                    style={{ flex: 1 }}>
              <option value="mensal">Mensal</option>
              <option value="anual">Anual</option>
            </select>
            <select value={dia} onChange={(e) => setDia(e.target.value)}>
              {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>dia {d}</option>
              ))}
            </select>
            {frequencia === "anual" && (
              <select value={mes} onChange={(e) => setMes(e.target.value)}>
                {MESES_LONGOS.map((nome, i) => (
                  <option key={nome} value={i + 1}>{nome}</option>
                ))}
              </select>
            )}
          </div>
          <div className="linha-acoes">
            <select value={entidade} onChange={(e) => setEntidade(e.target.value)} style={{ flex: 1 }}>
              <option value="pessoal">Pessoal</option>
              <option value="empresa">Empresa</option>
            </select>
            <select value={sourceId} onChange={(e) => setSourceId(e.target.value)} style={{ flex: 1 }}>
              <option value="">Sem fonte associada</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>{s.bank_name}</option>
              ))}
            </select>
          </div>
        </div>
        {erro && <p className="erro">{erro}</p>}
        <div className="modal-acoes">
          <button className="btn-primary" onClick={salvar} disabled={enviando}>
            {enviando ? "Salvando..." : "Salvar"}
          </button>
          <button onClick={onFechar}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}
