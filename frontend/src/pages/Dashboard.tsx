import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PieChart, Pie, Cell, Tooltip, BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../api";
import { useDark, chartTheme, tooltipProps, mesCurto, brlCompacto } from "../theme";

type CategoriaTotal = { category: string; total: number };
type Evolucao = { month: string; total: number };
type Top5Item = { descricao: string; valor: number; data: string };

type Summary = {
  total_gasto: number;
  total_por_categoria: CategoriaTotal[];
  evolucao: Evolucao[];
  top5: Top5Item[];
  resumo_semanal: string | null;
};

function mesAtual(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

const formatBRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function Dashboard() {
  const [entity, setEntity] = useState("todas");
  const [month, setMonth] = useState(mesAtual());
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const dark = useDark();
  const tema = chartTheme(dark);

  useEffect(() => {
    setLoading(true);
    setErro(null);
    api<Summary>(`/dashboard/summary?month=${month}&entity=${entity}`)
      .then(setSummary)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, [entity, month]);

  const somaCategorias = summary?.total_por_categoria.reduce((acc, c) => acc + c.total, 0) ?? 0;

  return (
    <div className="page">
      <header className="page-head">
        <h1 className="page-title">Resumo</h1>
      </header>

      <div className="filtros">
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        <select value={entity} onChange={(e) => setEntity(e.target.value)}>
          <option value="todas">Todas</option>
          <option value="pessoal">Pessoal</option>
          <option value="empresa">Empresa</option>
        </select>
      </div>

      {loading && (
        <>
          <div className="skeleton" style={{ height: 108 }} />
          <div className="skeleton" style={{ height: 260 }} />
          <div className="skeleton" style={{ height: 180 }} />
        </>
      )}
      {erro && <p className="erro">{erro}</p>}

      {!loading && !erro && summary && summary.total_gasto === 0 && (
        <div className="card empty">
          <span className="empty-titulo">Nada por aqui ainda</span>
          Sem transações neste mês. <Link to="/adicionar">Importe um extrato</Link> para
          começar a ver seus gastos.
        </div>
      )}

      {!loading && !erro && summary && summary.total_gasto > 0 && (
        <>
          <section className="card">
            <span className="card-label">Gasto no mês</span>
            <span className="hero-valor">{formatBRL(summary.total_gasto)}</span>
          </section>

          {summary.resumo_semanal && (
            <section className="card insight">
              <span className="card-label">Resumo da semana</span>
              <p className="insight-texto">{summary.resumo_semanal}</p>
            </section>
          )}

          <section className="card">
            <span className="card-label">Por categoria</span>
            <div style={{ width: "100%", height: 210 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={summary.total_por_categoria} dataKey="total" nameKey="category"
                       cx="50%" cy="50%" innerRadius={58} outerRadius={88} paddingAngle={2}
                       stroke={tema.surface} strokeWidth={2}>
                    {summary.total_por_categoria.map((_, i) => (
                      <Cell key={i} fill={tema.series[i % tema.series.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => formatBRL(Number(v ?? 0))} {...tooltipProps(dark)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="legenda">
              {summary.total_por_categoria.map((c, i) => (
                <li key={c.category}>
                  <span className="legenda-dot"
                        style={{ background: tema.series[i % tema.series.length] }} />
                  <span className="legenda-nome">{c.category}</span>
                  <span className="legenda-pct">
                    {somaCategorias > 0 ? `${Math.round((c.total / somaCategorias) * 100)}%` : ""}
                  </span>
                  <span className="legenda-valor">{formatBRL(c.total)}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <span className="card-label">Evolução — 6 meses</span>
            <div style={{ width: "100%", height: 190 }}>
              <ResponsiveContainer>
                <BarChart data={summary.evolucao} margin={{ top: 4, right: 4, left: -14, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={tema.grid} />
                  <XAxis dataKey="month" tickFormatter={mesCurto} tickLine={false}
                         axisLine={{ stroke: tema.grid }}
                         tick={{ fontSize: 11, fill: tema.axis }} />
                  <YAxis tickFormatter={brlCompacto} tickLine={false} axisLine={false}
                         tick={{ fontSize: 11, fill: tema.axis }} width={46} />
                  <Tooltip formatter={(v) => formatBRL(Number(v ?? 0))}
                           labelFormatter={(m) => mesCurto(String(m))}
                           cursor={{ fill: "rgba(137,135,129,0.08)" }} {...tooltipProps(dark)} />
                  <Bar dataKey="total" fill={tema.accent} radius={[4, 4, 0, 0]} maxBarSize={36} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="card">
            <span className="card-label">Top 5 gastos</span>
            <ul className="tx-list">
              {summary.top5.map((t, i) => (
                <li key={i} className="tx-item">
                  <div className="tx-row" style={{ cursor: "default" }}>
                    <div className="tx-info">
                      <span className="tx-data">{t.data}</span>
                      <span className="tx-desc">{t.descricao}</span>
                    </div>
                    <span className="valor-negativo">{formatBRL(t.valor)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
