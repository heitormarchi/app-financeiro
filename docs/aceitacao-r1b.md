# Checklist de aceitação real — R1b (Automação e Empresa)

Todo o código de R1b (Tasks 1-7) está implementado, testado (TDD) e commitado. Esta Task 8 exige
credenciais e serviços reais que só o Heitor pode configurar — não pode ser automatizada por código.
Setup de referência: [setup-whatsapp.md](setup-whatsapp.md) e [setup-inter.md](setup-inter.md).

- [ ] **Passo 1 — WhatsApp real**: configurar o webhook na Evolution API real (ver setup-whatsapp.md)
      → enviar um extrato OFX real pelo WhatsApp → a resposta com as contagens (novas/duplicadas/futuros)
      deve chegar no próprio chat.
- [ ] **Passo 2 — Visão computacional real**: enviar um print real da tela "Futuros" do app do BB pelo
      WhatsApp → os lançamentos devem aparecer na tela Futuros do PWA.
- [ ] **Passo 3 — Inter real**: gerar o certificado mTLS real (ver setup-inter.md), rodar o sync
      (`POST /api/v1/inter/sync` ou botão "Sincronizar agora" em Config) → transações da empresa devem
      aparecer no Dashboard filtrando por entidade "Empresa", com saldo visível em Config.
- [ ] **Passo 4 — Transferência real de R$ 1,00**: forçar um cenário de saldo baixo (subir temporariamente
      `low_balance_threshold` da conta pessoal) → aguardar o push de sugestão de transferência (ou rodar o
      job manualmente) → confirmar a transferência de **R$ 1,00** pelo modal em Futuros → verificar que o
      Pix caiu na conta pessoal e que a sugestão ficou com status `executada` e um `pix_id` (e2e) registrado.
- [ ] **Passo 5 — Reverter e fechar**: reverter o `low_balance_threshold` para o valor original → commitar
      `git commit -m "chore: aceitacao R1b concluida"`.

Estas etapas exigem: instância Evolution ativa e conectada, certificado Inter válido, e uma transferência
Pix real de baixo valor — todas ações com efeito no mundo real, portanto reservadas para execução manual
do Heitor.
