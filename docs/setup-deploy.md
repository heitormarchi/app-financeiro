# Deploy na VPS (EasyPanel)

## Build da imagem

O `Dockerfile` na raiz do repo faz build multi-stage: primeiro compila o frontend
(Vite) e depois copia o `dist/` para dentro da imagem Python que roda o FastAPI.

```bash
docker build -t app-financeiro .
docker run -p 8000:8000 --env-file .env app-financeiro
```

## Passos no EasyPanel

1. Criar um novo app apontando para este repositório (ou enviar via `tar` se o
   deploy for feito sem GitHub).
2. Configurar as variáveis de ambiente do `.env` local (nunca subir o `.env` em
   si — copiar os valores manualmente na UI do EasyPanel):
   - `DATABASE_URL` (PostgreSQL da VPS)
   - `APP_API_KEY`
   - `FERNET_KEY`
   - `OPENROUTER_KEY`
   - `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_CLAIMS_EMAIL`
3. Configurar domínio com HTTPS (obrigatório para Web Push e para o service
   worker do PWA funcionar).
4. No primeiro deploy, rodar dentro do container:
   ```bash
   alembic upgrade head
   python -m scripts.seed
   ```

## Checklist de aceitação real (gate do R1a)

Estes itens dependem de dispositivo físico e dados reais — não são
verificáveis por automação, precisam ser executados manualmente pelo Heitor
após o deploy:

- [ ] PWA instalada no iPhone (Compartilhar > Tela de Início) e aberta também
      no Windows
- [ ] OFX real do BB e da Caixa importados pela UI → dashboard popula
- [ ] Senha da fatura configurada em Config → fatura.pdf real importada →
      parceladas visíveis
- [ ] Atalho iOS configurado (`docs/setup-atalho-sms.md`) → compra real do
      cartão aparece como provisória em segundos
- [ ] Cupom real de mercado escaneado → itens visíveis na transação conciliada
- [ ] `POST /push/test-weekly` → notificação chega no iPhone e no Windows
- [ ] Reimport dos mesmos arquivos → `novas: 0` (dedup funcionando)
