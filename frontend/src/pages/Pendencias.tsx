import { useEffect, useState } from "react";
import { api } from "../api";

type Pendencia = {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  resolved: boolean;
  created_at: string;
};

const TIPO_LABEL: Record<string, string> = {
  parse_failed: "Falha ao processar",
  item_generico: "Item genérico do cupom",
  sms_sem_fatura: "SMS sem fatura correspondente",
  descrever_lancamento: "Descrever lançamento",
};

export default function Pendencias() {
  const [itens, setItens] = useState<Pendencia[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  function carregar() {
    setLoading(true);
    api<Pendencia[]>("/pendencias?resolved=false")
      .then(setItens)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(carregar, []);

  async function reprocessar(id: string) {
    try {
      await api(`/pendencias/${id}/reprocess`, { method: "POST" });
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    }
  }

  async function resolver(id: string, body: { descricao?: string; category?: string }) {
    try {
      await api(`/pendencias/${id}/resolve`, { method: "POST", body: JSON.stringify(body) });
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="page">
      <h2>Pendências</h2>
      {loading && <p>Carregando...</p>}
      {erro && <p className="erro">{erro}</p>}
      {!loading && !erro && itens.length === 0 && <p>Nenhuma pendência 🎉</p>}

      <ul className="tx-list">
        {itens.map((p) => (
          <li key={p.id} className="tx-item">
            <div className="tx-detalhe">
              <strong>{TIPO_LABEL[p.type] ?? p.type}</strong>
              <p className="pendencia-payload">
                {String(p.payload.descricao ?? p.payload.erro ?? p.payload.merchant ?? "")}
              </p>

              {p.type === "parse_failed" && p.payload.canal === "sms" && (
                <button onClick={() => reprocessar(p.id)}>Reprocessar</button>
              )}

              {p.type === "descrever_lancamento" && (
                <DescreverForm onSalvar={(descricao) => resolver(p.id, { descricao })} />
              )}

              {p.type === "item_generico" && (
                <DescreverForm placeholder="categoria" onSalvar={(category) => resolver(p.id, { category })} />
              )}

              {p.type === "sms_sem_fatura" && (
                <button onClick={() => resolver(p.id, {})}>Marcar como resolvido</button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DescreverForm({ placeholder = "descrição", onSalvar }: {
  placeholder?: string;
  onSalvar: (valor: string) => void;
}) {
  const [valor, setValor] = useState("");
  return (
    <div className="editor-categoria">
      <input placeholder={placeholder} value={valor} onChange={(e) => setValor(e.target.value)} />
      <button disabled={!valor} onClick={() => onSalvar(valor)}>Salvar</button>
    </div>
  );
}
