import { useEffect, useState } from "react";
import { api, getApiKey } from "../api";
import QrScanner from "../components/QrScanner";

type Source = { id: string; type: string; entity: string; bank_name: string | null };

type ImportReport = { novas: number; duplicadas: number; rejeitadas: number; futuros: number };

export default function Adicionar() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [resultado, setResultado] = useState<ImportReport | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [mostrarScanner, setMostrarScanner] = useState(false);

  useEffect(() => {
    api<Source[]>("/sources").then((s) => {
      setSources(s);
      if (s.length > 0) setSourceId(s[0].id);
    }).catch(() => {});
  }, []);

  async function enviar() {
    if (!file || !sourceId) return;
    setEnviando(true);
    setErro(null);
    setResultado(null);
    try {
      const ext = file.name.split(".").pop()?.toLowerCase();
      const endpoint = ext === "pdf" ? "/imports/fatura" : "/imports/ofx";
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`/api/v1${endpoint}?source_id=${sourceId}`, {
        method: "POST",
        headers: { "X-API-Key": getApiKey() },
        body: form,
      });
      if (!res.ok) throw new Error(`Erro ${res.status}: ${await res.text()}`);
      setResultado(await res.json());
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1 className="page-title">Adicionar</h1>
      </header>

      <section className="card">
        <span className="card-label">Importar extrato ou fatura</span>
        <div className="form-import">
          <select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>{s.bank_name ?? s.type} ({s.entity})</option>
            ))}
          </select>
          <label className={file ? "file-drop tem-arquivo" : "file-drop"}>
            <input type="file" accept=".ofx,.pdf"
                   onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            {file ? file.name : "Toque para escolher um arquivo .ofx ou .pdf"}
          </label>
          <button className="btn-primary" disabled={!file || !sourceId || enviando} onClick={enviar}>
            {enviando ? "Enviando..." : "Importar"}
          </button>
        </div>

        {erro && <p className="erro">{erro}</p>}
        {resultado && (
          <p className="resultado-import">
            {resultado.novas} novas, {resultado.duplicadas} duplicadas,{" "}
            {resultado.rejeitadas} rejeitadas, {resultado.futuros} futuros
          </p>
        )}
      </section>

      <section className="card">
        <span className="card-label">Escanear cupom fiscal</span>
        {!mostrarScanner && (
          <>
            <p className="hint" style={{ marginBottom: 12 }}>
              Aponte a câmera para o QR code do cupom — os itens da compra entram
              categorizados automaticamente.
            </p>
            <button className="btn-primary" onClick={() => setMostrarScanner(true)}>
              Abrir câmera
            </button>
          </>
        )}
        {mostrarScanner && <QrScanner onFechar={() => setMostrarScanner(false)} />}
      </section>
    </div>
  );
}
