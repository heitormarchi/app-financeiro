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
- [ ] **Passo 4 — Transferência real de R$ 1,00**: não existe endpoint/UI para editar `low_balance_threshold`
      (campo interno, sem tela própria) — ajuste temporariamente via SQL direto na base:
      ```sql
      UPDATE sources SET low_balance_threshold = 999999
      WHERE type = 'bb_conta' AND entity = 'pessoal';
      ```
      Em seguida rode o job de projeção manualmente (reiniciar o backend dispara na próxima 07:30, ou
      chame `run_projection_job` via um shell Python) → aguarde o push de sugestão de transferência →
      confirme a transferência de **R$ 1,00** pelo modal em Futuros (edite o valor sugerido para 1,00 antes
      de confirmar) → verifique que o Pix caiu na conta pessoal e que a sugestão ficou com status
      `executada` e um `pix_id` (e2e) registrado.
- [ ] **Passo 5 — Reverter e fechar**: reverter o `low_balance_threshold` para `0` (valor original) via o
      mesmo SQL → commitar `git commit -m "chore: aceitacao R1b concluida"`.

Estas etapas exigem: instância Evolution ativa e conectada, certificado Inter válido, e uma transferência
Pix real de baixo valor — todas ações com efeito no mundo real, portanto reservadas para execução manual
do Heitor.

## Nota sobre teste pré-existente vermelho

`tests/test_import_ofx.py::test_futuros_viram_scheduled` falha e vai continuar falhando todo dia a partir
de agora — a fixture `bb_extrato_anon.ofx` tem datas hardcoded (`20260706`) que eram "futuras" quando foi
criada; assim que o relógio real alcança essa data, a lógica `date > now` do parser deixa de classificá-las
como futuras (comportamento correto do parser, fixture desatualizada). Não é uma falha aleatória nem
relacionada ao R1b — precisa que alguém regenere a fixture com datas relativas à data de execução do teste
para voltar a ficar verde.
