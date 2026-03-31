# Briefing Diário do Rodolfo

## Comando para usar a cada manhã

Cole o texto abaixo em uma nova sessão do Claude Code:

---

```
Gere o briefing diário do Rodolfo. Execute de forma autônoma, sem fazer perguntas.

## Objetivo
Montar o briefing do dia com previsão do tempo, agenda de hoje e eventos dos próximos 7 dias, e salvar como rascunho no Gmail de rodolfo.tocastro@gmail.com.

## Passo 1 — Buscar previsão do tempo
Use `WebSearch` com a query: "previsão do tempo Campinas hoje amanhã [DATA_HOJE] [DATA_AMANHA] temperatura chuva"
Extraia: condição do dia, temperatura mínima e máxima, chance de chuva, e resumo para hoje e amanhã.

## Passo 2 — Buscar eventos de hoje
Use `gcal_list_events` nos calendários abaixo em paralelo, com `timeMin` = hoje às 00:00:00 e `timeMax` = hoje às 23:59:59 (timezone: America/Sao_Paulo):
- `rodolfo.tocastro@gmail.com`
- `dg93sv9kfu3h6spuqgdo887932qo44eh@import.calendar.google.com` (calendário do trabalho/Teams)
- `family13773359058415049452@group.calendar.google.com` (Family)
- `pt-br.brazilian#holiday@group.v.calendar.google.com` (Feriados)

## Passo 3 — Buscar eventos dos próximos 7 dias
Use `gcal_list_events` nos mesmos 4 calendários em paralelo, com `timeMin` = amanhã às 00:00:00 e `timeMax` = daqui 7 dias às 23:59:59 (timezone: America/Sao_Paulo).

## Passo 4 — Montar o HTML e criar rascunho no Gmail
Monte o HTML completo em memória (não salvar em disco) com as seguintes seções:

### Seção 0: Previsão do Tempo
Cards lado a lado para hoje e amanhã, cada um com:
- Ícone emoji do clima (☀️ 🌤️ ⛅ 🌧️ ⛈️ etc.)
- Temperatura mín / máx
- Descrição da condição (ex: "Sol entre nuvens", "Chuviscos pela manhã")
- Chance de chuva em %
- Barra visual de probabilidade de chuva
Usar fundo azul-acinzentado suave (#e8f0f8), texto escuro.

### Seção 1: Agenda do Dia
Liste todos os eventos em ordem cronológica (horário · nome · local/obs).
Inclua eventos de dia inteiro e eventos com horário.
Eventos com "teams.microsoft.com" na descrição/localização → badge azul "Teams".
Eventos com endereço físico → badge vermelho "Presencial".
Última ocorrência de série recorrente → texto vermelho + badge âmbar "⚠ Última ocorrência".

### Seção 2: Próximos Dias
Agrupe os eventos dos próximos 7 dias por dia da semana (ex: "Terça, 24/mar").
- Dias com 3+ compromissos: indicação "· Dia cheio"
- Eventos com endereço físico: badge vermelho "Presencial"
- Última ocorrência de série recorrente: texto vermelho
- Aniversários: badge roxo "🎂 Aniversário"
- Omitir eventos rotineiros de ≤15 min (ex: "Aplicação / Resgate")

## Estilo visual
- Header verde escuro (#1a3a2a) com texto creme
- Fundo geral off-white (#f4f1ec)
- Cards de clima com fundo azul suave (#e8f0f8)
- Eventos: horário à esquerda (72px, cinza), nome/detalhes à direita
- Badges: Teams=azul, Presencial=vermelho, Aniversário=roxo, Última=âmbar
- Rodapé com data/hora de geração

## Passo 5 — Criar rascunho no Gmail
Use `create_gmail_draft` com:
- `user_google_email`: rodolfo.tocastro@gmail.com
- `to`: rodolfo.tocastro@gmail.com
- `subject`: `🌿 Briefing do Dia — {dia da semana abreviado, DD/mês abreviado/AAAA — ex: "Seg, 23/mar/2026"}`
- `body_format`: html
- `body`: o HTML completo gerado no Passo 4

## Critério de sucesso
O rascunho foi criado com sucesso no Gmail com HTML formatado contendo previsão do tempo, agenda de hoje e próximos 7 dias.
```

---

## Calendários configurados

| ID | Nome |
|----|------|
| `rodolfo.tocastro@gmail.com` | Calendário principal |
| `dg93sv9kfu3h6spuqgdo887932qo44eh@import.calendar.google.com` | Trabalho (Teams/Outlook) |
| `family13773359058415049452@group.calendar.google.com` | Family |
| `pt-br.brazilian#holiday@group.v.calendar.google.com` | Feriados no Brasil |

## Pré-requisito

O MCP do **Gmail** precisa estar conectado **antes** de iniciar a sessão.
Verificar em: Claude.ai → Settings → Integrations → Gmail ✓

## Observações sobre os eventos

- Eventos com `teams.microsoft.com` na descrição = reunião Teams
- Eventos com endereço de rua na localização = presencial
- Campo `recurringEventId` presente + data final = verificar última ocorrência
- Eventos "Aplicação / Resgate" (15 min, recorrente) = rotineiro, omitir de próximos dias
- Calendário de trabalho vem do Outlook via importação `.ics`
