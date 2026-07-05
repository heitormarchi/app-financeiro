import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from "recharts";
import { api } from "../api";

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

const CORES = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316"];

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

  useEffect(() => {
    setLoading(true);
    setErro(null);
    api<Summary>(`/dashboard/summary?month=${month}&entity=${entity}`)
      .then(setSummary)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, [entity, month]);

  return (
    <div className="page">
      <div className="filtros">
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        <select value={entity} onChange={(e) => setEntity(e.target.value)}>
          <option value="todas">Todas</option>
          <option value="pessoal">Pessoal</option>
          <option value="empresa">Empresa</option>
        </select>
      </div>

      {loading && <p>Carregando...</p>}
      {erro && <p className="erro">{erro}</p>}

      {!loading && !erro && summary && summary.total_gasto === 0 && (
        <p>Sem dados neste mês — importe um extrato em ➕</p>
      )}

      {!loading && !erro && summary && summary.total_gasto > 0 && (
        <>
          <h2>{formatBRL(summary.total_gasto)}</h2>

          <div style={{ width: "100%", height: 240 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={summary.total_por_categoria} dataKey="total" nameKey="category"
                     cx="50%" cy="50%" outerRadius={80} label={(d) => String(d.name ?? "")}>
                  {summary.total_por_categoria.map((_, i) => (
                    <Cell key={i} fill={CORES[i % CORES.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => formatBRL(Number(v ?? 0))} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <h3>Evolução (6 meses)</h3>
          <div style={{ width: "100%", height: 200 }}>
            <ResponsiveContainer>
              <BarChart data={summary.evolucao}>
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip formatter={(v) => formatBRL(Number(v ?? 0))} />
                <Bar dataKey="total" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <h3>Top 5 gastos</h3>
          <ul className="top5-list">
            {summary.top5.map((t, i) => (
              <li key={i}>
                <span>{t.descricao}</span>
                <span className="valor-negativo">{formatBRL(t.valor)}</span>
              </li>
            ))}
          </ul>

          {summary.resumo_semanal && (
            <div className="card-resumo">
              <h3>Resumo semanal</h3>
              <p>{summary.resumo_semanal}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
