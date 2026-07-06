# Setup WhatsApp via Evolution API (R1b)

Passos para habilitar o WhatsApp como canal universal de ingestão (extrato OFX, fatura PDF, prints de futuros, cupom fiscal):

1. **Instância Evolution API**: já rodando (própria VPS ou serviço gerenciado) com uma instância conectada ao número que vai receber os documentos.
2. **Preencher o `.env`**:
   ```
   EVOLUTION_BASE_URL=https://sua-evolution.exemplo.com
   EVOLUTION_API_KEY=<apikey da instância>
   EVOLUTION_INSTANCE=<nome da instância>
   EVOLUTION_WEBHOOK_TOKEN=<token secreto aleatório — gerar com python -c "import secrets; print(secrets.token_urlsafe(32))">
   WHATSAPP_ALLOWED_JID=<seu número no formato 5511999999999@s.whatsapp.net>
   ```
3. **Configurar o webhook na Evolution**: apontar o evento `messages.upsert` para
   `https://seu-dominio/api/v1/webhooks/whatsapp/{EVOLUTION_WEBHOOK_TOKEN}` (o token na URL substitui o valor real configurado no `.env`).
4. **Segurança**: qualquer mensagem de um JID fora de `WHATSAPP_ALLOWED_JID` recebe uma resposta HTTP 200 silenciosa (sem processar, sem vazar existência do endpoint) e fica registrada no log do backend.
5. **Testar**: envie um extrato OFX (documento) para o número conectado — a resposta com a contagem de novas/duplicadas/futuros deve chegar no próprio chat em segundos. Também é possível enviar um print da tela de lançamentos futuros do banco (imagem) ou uma foto de cupom fiscal com QR code (NFC-e).
6. **Erros**: arquivos não reconhecidos ou falhas de leitura sempre geram uma resposta em português explicando o que não foi possível processar, e nunca derrubam o backend.
