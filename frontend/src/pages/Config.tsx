import { useEffect, useState } from "react";
import { api, getApiKey } from "../api";

type Source = {
  id: string;
  type: string;
  entity: string;
  bank_name: string | null;
  has_pdf_password: boolean;
  last_ingested_at: string | null;
};

function urlBase64ToUint8Array(base64: string): BufferSource {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const base64Safe = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64Safe);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0))).buffer;
}

function diasDesde(dataIso: string | null): number | null {
  if (!dataIso) return null;
  const dias = (Date.now() - new Date(dataIso).getTime()) / 86_400_000;
  return Math.floor(dias);
}

export default function Config() {
  const [apiKey, setApiKey] = useState(getApiKey());
  const [statusConexao, setStatusConexao] = useState<"idle" | "ok" | "erro">("idle");
  const [sources, setSources] = useState<Source[]>([]);
  const [senhas, setSenhas] = useState<Record<string, string>>({});
  const [statusPush, setStatusPush] = useState<string | null>(null);

  function carregarSources() {
    api<Source[]>("/sources").then(setSources).catch(() => {});
  }

  useEffect(carregarSources, []);

  function salvarApiKey() {
    localStorage.setItem("apiKey", apiKey);
    testarConexao();
  }

  async function testarConexao() {
    try {
      await api("/sources");
      setStatusConexao("ok");
    } catch {
      setStatusConexao("erro");
    }
  }

  async function salvarSenhaPdf(sourceId: string) {
    const senha = senhas[sourceId];
    if (!senha) return;
    await api(`/sources/${sourceId}/pdf-password`, {
      method: "PUT",
      body: JSON.stringify({ password: senha }),
    });
    setSenhas((s) => ({ ...s, [sourceId]: "" }));
    carregarSources();
  }

  async function ativarNotificacoes() {
    setStatusPush(null);
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        setStatusPush("Este navegador não suporta notificações push.");
        return;
      }
      const permissao = await Notification.requestPermission();
      if (permissao !== "granted") {
        setStatusPush("Permissão de notificação negada.");
        return;
      }
      const registration = await navigator.serviceWorker.ready;
      const { key } = await api<{ key: string }>("/push/vapid-public-key");
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      });
      await api("/push/subscriptions", {
        method: "POST",
        body: JSON.stringify(subscription.toJSON()),
      });
      setStatusPush("Notificações ativadas neste aparelho.");
    } catch (e) {
      setStatusPush(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="page">
      <h2>Config</h2>

      <section>
        <h3>API Key</h3>
        <div className="editor-categoria">
          <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          <button onClick={salvarApiKey}>Salvar e testar</button>
        </div>
        {statusConexao === "ok" && <p className="ok">Conectado ✓</p>}
        {statusConexao === "erro" && <p className="erro">Falha na conexão — verifique a chave.</p>}
      </section>

      <section>
        <h3>Senhas de fatura (PDF)</h3>
        {sources.map((s) => (
          <div key={s.id} className="editor-categoria">
            <span>{s.bank_name ?? s.type} {s.has_pdf_password ? "(senha configurada)" : "(sem senha)"}</span>
            <input type="password" placeholder="senha do PDF"
                   value={senhas[s.id] ?? ""}
                   onChange={(e) => setSenhas((v) => ({ ...v, [s.id]: e.target.value }))} />
            <button onClick={() => salvarSenhaPdf(s.id)}>Salvar</button>
          </div>
        ))}
      </section>

      <section>
        <h3>Notificações</h3>
        <button onClick={ativarNotificacoes}>Ativar notificações neste aparelho</button>
        {statusPush && <p>{statusPush}</p>}
        <p className="hint">
          No iPhone, adicione à Tela de Início primeiro (Compartilhar {'>'} Adicionar à Tela de Início).
        </p>
      </section>

      <section>
        <h3>Saúde das fontes</h3>
        <ul className="tx-list">
          {sources.map((s) => {
            const dias = diasDesde(s.last_ingested_at);
            return (
              <li key={s.id} className="tx-item">
                <div className="tx-row">
                  <span>{s.bank_name ?? s.type}</span>
                  <span className={dias !== null && dias > 30 ? "erro" : ""}>
                    {dias === null ? "nunca sincronizado" : `há ${dias} dia(s)`}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
