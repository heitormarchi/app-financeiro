import { useEffect, useRef, useState } from "react";
import jsQR from "jsqr";
import { api } from "../api";

type NfceResult = { itens?: number; conciliada?: boolean; parsed?: boolean; erro?: string; [k: string]: unknown };

declare global {
  interface Window {
    BarcodeDetector?: new (opts: { formats: string[] }) => {
      detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>;
    };
  }
}

export default function QrScanner({ onFechar }: { onFechar: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<NfceResult | null>(null);
  const [urlManual, setUrlManual] = useState("");
  const [processando, setProcessando] = useState(false);

  function pararCamera() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  useEffect(() => {
    let stream: MediaStream | null = null;
    let rafId: number;
    let ativo = true;

    async function iniciar() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        const detector = window.BarcodeDetector
          ? new window.BarcodeDetector({ formats: ["qr_code"] })
          : null;

        const loop = async () => {
          if (!ativo || !videoRef.current || resultado) return;
          try {
            let url: string | null = null;
            if (detector) {
              const codes = await detector.detect(videoRef.current);
              if (codes.length > 0) url = codes[0].rawValue;
            } else if (canvasRef.current) {
              const canvas = canvasRef.current;
              const ctx = canvas.getContext("2d");
              canvas.width = videoRef.current.videoWidth;
              canvas.height = videoRef.current.videoHeight;
              if (ctx && canvas.width > 0) {
                ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imageData.data, imageData.width, imageData.height);
                if (code) url = code.data;
              }
            }
            if (url && url.includes("sat.sef.sc.gov.br")) {
              pararCamera();
              await processar(url);
              return;
            }
          } catch {
            // ignora erro de leitura de um frame e tenta o próximo
          }
          rafId = requestAnimationFrame(loop);
        };
        rafId = requestAnimationFrame(loop);
      } catch {
        setErro("Não foi possível acessar a câmera. Cole a URL manualmente abaixo.");
      }
    }

    iniciar();

    return () => {
      ativo = false;
      if (rafId) cancelAnimationFrame(rafId);
      stream?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function processar(qrUrl: string) {
    pararCamera();
    setProcessando(true);
    setErro(null);
    try {
      const res = await api<NfceResult>("/nfce/scan", {
        method: "POST",
        body: JSON.stringify({ qr_url: qrUrl }),
      });
      setResultado(res);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setProcessando(false);
    }
  }

  return (
    <div className="qr-scanner">
      {!resultado && (
        <>
          <video ref={videoRef} className="qr-video" muted playsInline />
          <canvas ref={canvasRef} style={{ display: "none" }} />
          {processando && <p>Processando cupom...</p>}
          {erro && <p className="erro">{erro}</p>}
          <div className="qr-manual">
            <input placeholder="Colar URL do QR manualmente" value={urlManual}
                   onChange={(e) => setUrlManual(e.target.value)} />
            <button className="btn-primary" onClick={() => urlManual && processar(urlManual)}>Enviar</button>
          </div>
        </>
      )}
      {resultado && resultado.parsed === false && (
        <p className="erro">
          Não foi possível ler o cupom{resultado.erro ? `: ${resultado.erro}` : ""}. Uma pendência
          foi registrada para revisão manual.
        </p>
      )}
      {resultado && resultado.parsed !== false && (
        <p className="resultado-import">
          {resultado.itens ?? "?"} itens importados
          {resultado.conciliada ? ", conciliado com a compra ✓" : ""}
        </p>
      )}
      <button onClick={onFechar}>Fechar</button>
    </div>
  );
}
