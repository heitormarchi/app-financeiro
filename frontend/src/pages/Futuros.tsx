import { useEffect, useState } from "react";
import { api } from "../api";

type Scheduled = { id: string; due_date: string; description: string; amount: number; origin: string; status: string };

const formatBRL = (v: number) =>
  Math.abs(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function Futuros() {
  const [itens, setItens] = useState<Scheduled[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api<Scheduled[]>("/scheduled?status=previsto")
      .then(setItens)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <h2>Futuros</h2>
      <div className="banner">Projeção de saldo e sugestões chegam na próxima fase.</div>

      {loading && <p>Carregando...</p>}
      {erro && <p className="erro">{erro}</p>}
      {!loading && !erro && itens.length === 0 && <p>Nenhum lançamento futuro previsto.</p>}

      <ul className="tx-list">
        {itens.map((i) => (
          <li key={i.id} className="tx-item">
            <div className="tx-row">
              <div className="tx-info">
                <span className="tx-data">{i.due_date}</span>
                <span className="tx-desc">{i.description}</span>
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
