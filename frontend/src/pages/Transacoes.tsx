import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

type ReceiptItem = { id: string; description: string; total_price: number; category: string | null };

type Tx = {
  id: string;
  amount: number;
  date: string;
  raw_description: string;
  merchant: string | null;
  category: string | null;
  subcategory: string | null;
  entity: string;
  status: string;
  is_invoice_payment: boolean;
  installment_no: number | null;
  installment_total: number | null;
  source_channel?: string;
  receipt_items: ReceiptItem[];
};

type Source = { id: string; type: string; entity: string; bank_name: string | null };

const formatBRL = (v: number) =>
  Math.abs(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function mesAtual(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function Transacoes() {
  const [txs, setTxs] = useState<Tx[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [month, setMonth] = useState(mesAtual());
  const [category, setCategory] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const categoriasExistentes = useMemo(
    () => Array.from(new Set(txs.map((t) => t.category).filter(Boolean))) as string[],
    [txs]
  );

  function carregar() {
    setLoading(true);
    setErro(null);
    const params = new URLSearchParams({ month });
    if (category) params.set("category", category);
    if (sourceId) params.set("source_id", sourceId);
    api<Tx[]>(`/transactions?${params.toString()}`)
      .then(setTxs)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    api<Source[]>("/sources").then(setSources).catch(() => {});
  }, []);

  useEffect(carregar, [month, category, sourceId]);

  async function salvarCategoria(id: string, novaCategoria: string, subcategoria: string) {
    await api(`/transactions/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ category: novaCategoria, subcategory: subcategoria || null }),
    });
    setEditingId(null);
    carregar();
  }

  async function salvarCategoriaItem(itemId: string, novaCategoria: string, salvarRegra: boolean) {
    await api(`/nfce/items/${itemId}/category`, {
      method: "PUT",
      body: JSON.stringify({ category: novaCategoria, salvar_regra: salvarRegra }),
    });
    carregar();
  }

  return (
    <div className="page">
      <div className="filtros">
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Todas categorias</option>
          {categoriasExistentes.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
          <option value="">Todas fontes</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>{s.bank_name ?? s.type}</option>
          ))}
        </select>
      </div>

      {loading && <p>Carregando...</p>}
      {erro && <p className="erro">{erro}</p>}
      {!loading && !erro && txs.length === 0 && (
        <p>Sem dados neste mês — importe um extrato em ➕</p>
      )}

      <ul className="tx-list">
        {txs.map((t) => (
          <li key={t.id} className="tx-item">
            <div className="tx-row" onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}>
              <div className="tx-info">
                <span className="tx-data">{t.date}</span>
                <span className="tx-desc">{t.merchant || t.raw_description}</span>
                <span className="tx-badges">
                  {t.source_channel && <span className="badge">{t.source_channel.toUpperCase()}</span>}
                  {t.status === "provisoria" && <span className="badge badge-provisoria">provisória</span>}
                </span>
              </div>
              <span className={t.amount < 0 ? "valor-negativo" : "valor-positivo"}>
                {t.amount < 0 ? "-" : "+"}{formatBRL(t.amount)}
              </span>
            </div>

            {expandedId === t.id && (
              <div className="tx-detalhe">
                <p>Categoria: {t.category ?? "sem categoria"} {t.subcategory ? `/ ${t.subcategory}` : ""}</p>
                <button onClick={() => setEditingId(editingId === t.id ? null : t.id)}>
                  Editar categoria
                </button>

                {editingId === t.id && (
                  <EditorCategoria
                    categorias={categoriasExistentes}
                    categoriaAtual={t.category ?? ""}
                    subcategoriaAtual={t.subcategory ?? ""}
                    onSalvar={(cat, sub) => salvarCategoria(t.id, cat, sub)}
                  />
                )}

                {t.receipt_items.length > 0 && (
                  <div className="receipt-items">
                    <h4>Itens do cupom</h4>
                    {t.receipt_items.map((item) => (
                      <ItemEditor key={item.id} item={item} onSalvar={salvarCategoriaItem} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function EditorCategoria({ categorias, categoriaAtual, subcategoriaAtual, onSalvar }: {
  categorias: string[];
  categoriaAtual: string;
  subcategoriaAtual: string;
  onSalvar: (categoria: string, subcategoria: string) => void;
}) {
  const [cat, setCat] = useState(categoriaAtual);
  const [livre, setLivre] = useState("");
  const [sub, setSub] = useState(subcategoriaAtual);

  return (
    <div className="editor-categoria">
      <select value={cat} onChange={(e) => setCat(e.target.value)}>
        <option value="">Selecione...</option>
        {categorias.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
      <input placeholder="ou nova categoria" value={livre} onChange={(e) => setLivre(e.target.value)} />
      <input placeholder="subcategoria (opcional)" value={sub} onChange={(e) => setSub(e.target.value)} />
      <button onClick={() => onSalvar(livre || cat, sub)}>Salvar</button>
    </div>
  );
}

function ItemEditor({ item, onSalvar }: {
  item: ReceiptItem;
  onSalvar: (itemId: string, categoria: string, salvarRegra: boolean) => void;
}) {
  const [cat, setCat] = useState(item.category ?? "");
  const [salvarRegra, setSalvarRegra] = useState(false);

  return (
    <div className="item-editor">
      <span>{item.description} — {formatBRL(item.total_price)}</span>
      <input value={cat} onChange={(e) => setCat(e.target.value)} placeholder="categoria" />
      <label>
        <input type="checkbox" checked={salvarRegra} onChange={(e) => setSalvarRegra(e.target.checked)} />
        salvar como regra
      </label>
      <button onClick={() => onSalvar(item.id, cat, salvarRegra)}>Salvar</button>
    </div>
  );
}
