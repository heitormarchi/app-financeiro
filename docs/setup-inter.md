# Setup Inter Empresas (R1b)

Passos para habilitar a sincronização real com o Banco Inter (conta PJ):

1. **Gerar certificado mTLS**: acessar o [portal Inter Empresas](https://developers.bancointer.com.br/) → Aplicações → criar aplicação com escopos `extrato.read`, `pagamento-pix.write`, `pagamento-pix.read` → gerar/baixar o certificado (`.crt`) e a chave privada (`.key`).
2. **Enviar para a VPS**: colocar os arquivos em um volume persistente, ex. `/etc/secrets/inter/inter.crt` e `/etc/secrets/inter/inter.key` (fora do diretório de build da imagem — nunca commitar no repo).
3. **Preencher o `.env`**:
   ```
   INTER_CLIENT_ID=...
   INTER_CLIENT_SECRET=...
   INTER_CERT_PATH=/etc/secrets/inter/inter.crt
   INTER_KEY_PATH=/etc/secrets/inter/inter.key
   INTER_PIX_DEST_KEY=<chave Pix pessoal de destino>
   ```
4. **Cadastrar a fonte**: rodar `scripts/seed.py` (já inclui `inter_pj`/`empresa`) ou criar manualmente via banco caso o seed já tenha rodado antes.
5. **Sync manual**: com o backend no ar, `POST /api/v1/inter/sync` (autenticado com `X-API-Key`) dispara `sync_inter` imediatamente — útil para validar credenciais e certificado antes de esperar o job diário das 07:00.
6. **Monitorar expiração do certificado**: `GET /api/v1/sources` expõe `cert_days_left` para a fonte `inter_pj` — a tela Config exibe esse valor.
