# Ciclo de Vida da Impressão — Design

**Data:** 2026-04-10
**Projeto:** FORJA3D
**Autor:** Claude + Alex Bruno
**Status:** Aprovado para implementação

---

## 1. Contexto e motivação

O FORJA3D hoje processa pedidos até `PAGO`, mas o loop de impressão está incompleto. O `printer-agent/agent.py` atual:

- Faz polling simples do endpoint admin a cada 30s
- Baixa o GLB, "tenta" fatiar (com fallback quebrado que envia GLB direto), envia via FTP
- Marca pedido como `IMPRIMINDO` e para
- **Não usa MQTT** (apesar do CLAUDE.md mencionar `bambulabs-api` no stack)
- Não detecta conclusão, não reporta progresso, não trata erros, não tem reconciliação após crash

Resultado: o negócio não fecha o loop sem intervenção manual em cada pedido. Este design resolve a parte "máquina" do ciclo (`PAGO → IMPRESSO`), deixando o pós-impressão (embalagem, envio físico, rastreio) no fluxo manual do admin.

## 2. Escopo

### Em escopo
- Máquina de estados `PAGO → PREPARANDO → IMPRIMINDO → IMPRESSO`
- Estado `ERRO_IMPRESSAO` e requeue manual via admin
- Monitoramento MQTT em tempo real da Bambu X1 Carbon via `bambulabs-api`
- Fatiamento obrigatório com BambuStudio CLI no printer-agent
- Progresso em tempo real (percentual, camada atual, camada total) exposto ao cliente
- Refatoração do printer-agent em módulos focados
- Novos endpoints dedicados ao agent (`/api/printer/*`) com senha separada
- Migrações Alembic substituindo o `create_all` do lifespan
- Higiene de segredos (apêndice operacional)
- Notificações por email via Resend
- Real-time no frontend via Server-Sent Events (Postgres LISTEN/NOTIFY)
- Página de detalhe `/admin/pedido/[id]` com timeline e ações

### Fora de escopo (explicitamente)
- Automação de embalagem, geração de etiqueta dos Correios, rastreio `ENVIADO → ENTREGUE` — fica manual no admin
- Integração real da API dos Correios (fica com a estimativa hardcoded atual; será spec separada)
- Tabela `order_events` para histórico granular de transições — timeline derivada dos campos específicos cobre o caso de uso
- Retry automático de impressão após falha — humano decide e reenfileira
- WebSocket bidirecional — SSE é suficiente
- Webcam streaming da X1 — complexidade de segurança/banda não compensa

## 3. Decisões de design (travadas)

| # | Decisão | Escolhido | Por quê |
|---|---|---|---|
| 1 | Escopo do ciclo | Apenas máquina (`PAGO → IMPRESSO`) | Alex está no início, pouco volume, pós-impressão é humano |
| 2 | Canal com a X1 | MQTT via `bambulabs-api` | Eventos em tempo real, X1 tem MQTT nativo, SDK já abstrai |
| 3 | Tratamento de falhas | `ERRO_IMPRESSAO` simples + requeue manual | Sem retry automático — humano diagnostica |
| 4 | Fatiamento | No agent, BambuStudio CLI obrigatório, estimativa do backend mantida | Railway não roda BambuStudio; estimativa atual já cobre preview |
| 5 | Progresso visível ao cliente | Sim, percentual + camada atual/total | Diferencial de UX, custo baixo |
| 6 | Granularidade de estados intermediários | Um estado único `PREPARANDO` | Feedback sem explodir state machine |
| 7 | Crash recovery | Stateless — reconcilia via backend + MQTT | Uma impressora, backend é fonte da verdade |
| 8 | Arquitetura do agent | Modular (backend_client, printer_client, slicer, job_runner) | Right-size, testável, alinhado com convenção do projeto |

## 4. Máquina de estados

```
AGUARDANDO_PAGAMENTO  (webhook MP confirma)
        ↓
       PAGO  ← requeue manual (admin) volta pra cá
        ↓   (agent.claim_next_job)
   PREPARANDO  ─── erro ──→  ERRO_IMPRESSAO
        ↓                         ↑
    IMPRIMINDO  ─── erro ─────────┘
   (progresso %)
        ↓   (MQTT: print_finished)
     IMPRESSO
        ↓   (admin marca manualmente — fora de escopo)
    EMBALANDO → ENVIADO → ENTREGUE
```

**Regras de transição:**
- Somente o **agent** (via endpoints `/api/printer/*`) pode transicionar `PAGO → PREPARANDO → IMPRIMINDO → IMPRESSO` e `* → ERRO_IMPRESSAO`
- Somente o **admin** pode transicionar `ERRO_IMPRESSAO → PAGO` (via endpoint `POST /api/admin/orders/{id}/requeue`)
- Admin tem override de emergência via endpoint genérico já existente (`POST /api/admin/orders/{id}`) — mantido como válvula de escape

**Validação:**
O backend rejeita transições ilegais com HTTP 400 e mensagem explicativa. A lista de transições permitidas é definida como constante em `backend/models/state_machine.py` (novo módulo).

## 5. Mudanças no banco de dados

### 5.1 Novos estados no enum

`backend/models/schemas.py` — adicionar em `StatusPedido`:
```python
PREPARANDO = "PREPARANDO"
IMPRESSO = "IMPRESSO"
ERRO_IMPRESSAO = "ERRO_IMPRESSAO"
```

### 5.2 Novas colunas em `Order` (`backend/models/tables.py`)

```python
# Progresso em tempo real (preenchido enquanto IMPRIMINDO)
progresso_percentual: Mapped[int | None] = mapped_column(Integer, nullable=True)
camada_atual: Mapped[int | None] = mapped_column(Integer, nullable=True)
camada_total: Mapped[int | None] = mapped_column(Integer, nullable=True)

# Erro (preenchido quando ERRO_IMPRESSAO)
erro_mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
erro_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

# Rastreabilidade da impressão
impressao_iniciada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
impressao_concluida_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
arquivo_3mf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### 5.3 Migrações com Alembic

O projeto usa Postgres (local via docker-compose na porta 5433, produção no Railway). O `Base.metadata.create_all` no lifespan de `main.py` é insuficiente — só cria tabelas novas, nunca altera colunas.

**Setup:**
1. Adicionar `alembic` ao `backend/requirements.txt`
2. `cd backend && alembic init alembic`
3. Configurar `alembic/env.py`:
   - Importar `Base` de `database.py`
   - `target_metadata = Base.metadata`
   - Ler `DATABASE_URL` do env
4. Remover `Base.metadata.create_all(...)` do `lifespan` em `backend/main.py`

**Migrations a criar:**
- `001_baseline.py` — `alembic revision --autogenerate -m "baseline"` captura schema atual
- `002_printer_lifecycle_fields.py` — adiciona as 8 colunas novas acima
- `003_sse_notify_trigger.py` — cria função e trigger PL/pgSQL pro LISTEN/NOTIFY (ver Seção 10)

**Deploy:**
- Railway: adicionar `alembic upgrade head` no start command, antes do `uvicorn`. Exemplo `railway.toml`:
  ```toml
  [deploy]
  startCommand = "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT"
  ```
- Dev local: rodar `alembic upgrade head` manualmente ou adicionar um script `backend/scripts/migrate.sh`

**Documentação:**
Adicionar seção "Migrações" ao `CLAUDE.md` explicando comandos básicos (`alembic revision --autogenerate -m "msg"`, `alembic upgrade head`, `alembic downgrade -1`).

## 6. Contrato da API do backend

### 6.1 Novos endpoints dedicados ao agent

Criar novo arquivo `backend/routers/printer.py`, registrado em `main.py` com prefix `/api`.

Todos os endpoints exigem header/body `agent_password` validado contra nova env var `AGENT_PASSWORD`.

#### `POST /api/printer/claim`
```
Request: { agent_password: str }
Response: { success: bool, data: Order | null, error: str | null }
```
Atômico. Usa `SELECT ... FOR UPDATE SKIP LOCKED` (Postgres) pra pegar o próximo pedido `PAGO` mais antigo e marcá-lo como `PREPARANDO` na mesma transação. Também registra `impressao_iniciada_em=NOW()`. Se não houver pedido, retorna `data: null`.

**Limpeza de `PREPARANDO` órfão:** antes do SELECT principal, o mesmo endpoint verifica se há algum pedido em `PREPARANDO` com `impressao_iniciada_em` há mais de `ORPHAN_PREPARING_MINUTES` (env var do backend, default **45 minutos**). Se sim, marca como `ERRO_IMPRESSAO` com mensagem `"Preparação abandonada (timeout)"`. Isso libera o estado pra reenfileiramento.

**Por que 45 min (não 10):** modelos complexos podem levar >10 min só pra fatiar. O threshold precisa ser generoso o suficiente pra cobrir prep legítima, mas curto o suficiente pra não deixar o estado estagnado por horas se o agent morreu. 45 min é um compromisso razoável; configurável via env var se for necessário ajustar. Também mitigado pelo fato de que o agent, ao reiniciar, faz reconciliação (Seção 9.3) e pode retomar jobs que ainda estão imprimindo de fato.

#### `POST /api/printer/orders/{id}/status`
```
Request: { agent_password: str, status: "IMPRIMINDO" | "IMPRESSO" }
Response: { success, data: Order, error }
```
Transiciona o status. Valida que a transição é legal (só aceita `PREPARANDO → IMPRIMINDO` e `IMPRIMINDO → IMPRESSO`). Se `IMPRESSO`, registra `impressao_concluida_em=NOW()`.

#### `POST /api/printer/orders/{id}/progress`
```
Request: { agent_password: str, percentual: int, camada_atual: int, camada_total: int }
Response: { success, data: { updated: true }, error }
```
Atualiza apenas os campos de progresso (não muda status). Não valida transição. Throttle acontece no agent (1 update a cada 30s); o backend aceita qualquer frequência.

#### `POST /api/printer/orders/{id}/erro`
```
Request: { agent_password: str, mensagem: str }
Response: { success, data: Order, error }
```
Marca como `ERRO_IMPRESSAO`, salva `erro_mensagem`, registra `erro_em=NOW()`.

### 6.2 Novo endpoint admin de requeue

#### `POST /api/admin/orders/{id}/requeue`
```
Request: { password: str }
Response: { success, data: Order, error }
```
Só permitido se status atual é `ERRO_IMPRESSAO`. Reverte para `PAGO` e limpa `progresso_percentual`, `camada_atual`, `camada_total`, `erro_mensagem`, `erro_em`, `impressao_iniciada_em`, `impressao_concluida_em`, `arquivo_3mf_path`.

### 6.3 Endpoint SSE (ver Seção 10)

#### `GET /api/orders/{id}/stream`
Server-Sent Events stream do estado do pedido em tempo real.

### 6.4 Autenticação — variáveis de ambiente

Backend (`backend/.env`):
```
AGENT_PASSWORD=<openssl rand -hex 32>
ORPHAN_PREPARING_MINUTES=45
```
Printer-agent (`printer-agent/config.json`):
```json
{
  "agent_password": "<mesmo valor>"
}
```

**Não reutilizar `ADMIN_PASSWORD`** — segregação de responsabilidades. Vazamento de uma não compromete a outra.

## 7. Apêndice operacional: higiene de segredos

Esta seção é uma **checklist humana**, não código. Deve ser executada ao menos uma vez durante a implementação desta spec.

### 7.1 Verificação do estado atual do repo
```bash
# Confirmar que .env está ignorado
git check-ignore backend/.env && echo "OK" || echo "PERIGO: .env não está ignorado"

# Confirmar que .env nunca foi commitado
git log --all --full-history -- backend/.env
# saída deve ser vazia

# Confirmar .env.example cobre todas as chaves
diff \
  <(grep -oE '^[A-Z_]+' backend/.env | sort) \
  <(grep -oE '^[A-Z_]+' backend/.env.example | sort)
# diferenças = atualizar .env.example
```

### 7.2 Rotação das credenciais expostas na sessão de brainstorming

Durante o brainstorming, o assistente leu `backend/.env` e os valores reais passaram pelo contexto do Claude. O repo git nunca foi afetado, mas como higiene defensiva:

**Tencent Cloud** (`TENCENT_SECRET_ID`, `TENCENT_SECRET_KEY`):
1. Console → Cloud Access Management → API Keys
2. Desabilitar a chave atual
3. Criar nova API Key
4. Atualizar `backend/.env` local
5. Atualizar variáveis de ambiente no Railway (dashboard do projeto)
6. Testar `POST /api/generate` pra confirmar que a nova chave funciona

**Mercado Pago** (`MP_ACCESS_TOKEN`):
1. Dashboard → Suas integrações → FORJA3D → Credenciais
2. Regenerar Access Token de **produção**
3. Atualizar `backend/.env` local
4. Atualizar variáveis de ambiente no Railway
5. Verificar que webhook de pagamento continua recebendo notificações após rotação (fazer um pedido de teste)

**Senhas do projeto:**
```bash
openssl rand -hex 32  # novo ADMIN_PASSWORD
openssl rand -hex 32  # novo AGENT_PASSWORD
```

### 7.3 Segregação de credenciais do agent

- `printer-agent/config.json` deve estar no `.gitignore` — verificar e adicionar se faltar
- Criar `printer-agent/config.example.json` com valores placeholder (commitado)
- Template:
  ```json
  {
    "printer": {
      "ip": "192.168.x.x",
      "serial": "SERIAL_AQUI",
      "access_code": "ACCESS_CODE_AQUI"
    },
    "backend_url": "http://localhost:8000",
    "agent_password": "DEFINIR_MESMO_VALOR_DO_BACKEND_ENV",
    "poll_interval_seconds": 30,
    "bambu_studio_cli": "C:\\Program Files\\Bambu Studio\\bambu-studio.exe"
  }
  ```

### 7.4 Controle contínuo

- Adicionar uma nota na seção "Convenções" do `CLAUDE.md`: "Antes de cada commit, rodar `git diff --cached | grep -iE 'secret|token|password|api.?key'` e verificar que nenhum valor real foi staged."
- TODO futuro (fora desta spec): adicionar um pre-commit hook que bloqueia commits com strings que parecem API keys (ex: usar `detect-secrets` ou `gitleaks`).

## 8. Arquitetura do printer-agent

### 8.1 Estrutura de arquivos

```
printer-agent/
├── agent.py              # Entrypoint + loop principal (~60 linhas)
├── config.py             # Carrega e valida config.json (~30 linhas)
├── backend_client.py     # HTTP client pro FORJA3D backend (~80 linhas)
├── printer_client.py     # MQTT + FTP pra Bambu X1 Carbon (~150 linhas)
├── slicer.py             # Wrapper do BambuStudio CLI (~50 linhas)
├── job_runner.py         # Máquina de estados de um pedido (~150 linhas)
├── logging_setup.py      # Config de logging estruturado (~20 linhas)
├── config.example.json   # Template (commitado)
├── config.json           # Local, fora do git
└── requirements.txt      # httpx, bambulabs-api, python-dotenv
```

### 8.2 Responsabilidades de cada módulo

**`config.py`**
- `load_config(path="config.json") -> AgentConfig`
- Valida campos obrigatórios: `printer.ip`, `printer.serial`, `printer.access_code`, `backend_url`, `agent_password`, `bambu_studio_cli`
- Verifica que o executável do BambuStudio existe no disco — falha no startup se não (decisão fixa: fatiamento é obrigatório)
- Retorna um dataclass tipado

**`backend_client.py`**
```python
class BackendClient:
    def __init__(self, config: AgentConfig)
    async def claim_next_job(self) -> Order | None
    async def update_status(self, order_id: str, status: Literal["IMPRIMINDO", "IMPRESSO"]) -> None
    async def update_progress(self, order_id: str, percentual: int, camada_atual: int, camada_total: int) -> None
    async def report_error(self, order_id: str, mensagem: str) -> None
    async def download_model(self, modelo_url: str, dest_path: str) -> None
```
Usa `httpx.AsyncClient` persistente. Updates não-críticos (`update_progress`) logam warning em caso de falha e seguem — nunca propagam exceção. Updates críticos (`update_status`, `report_error`) propagam erro pro caller decidir.

**`slicer.py`**
```python
@dataclass
class SliceResult:
    output_path: str
    estimated_weight_g: float | None
    estimated_time_min: int | None

class SlicerError(Exception):
    pass

class Slicer:
    def __init__(self, cli_path: str)
    def slice(self, glb_path: str, material: str, output_3mf: str) -> SliceResult
```
Chama `subprocess.run` do BambuStudio CLI. Parsea stdout pra extrair peso/tempo estimados se disponível. Em caso de erro, levanta `SlicerError(stderr[:500])`.

**`printer_client.py`**
```python
class PrinterClient:
    def __init__(self, config: AgentConfig)
    async def connect(self) -> None             # MQTT connect, com retry
    async def disconnect(self) -> None
    async def upload_file(self, local_path: str) -> str   # FTP → retorna filename remoto
    async def start_print(self, remote_filename: str) -> None  # MQTT command
    async def get_current_job(self) -> CurrentJob | None  # reconciliação no startup
    def on_progress(self, callback: Callable[[ProgressEvent], None]) -> None
    def on_finished(self, callback: Callable[[], None]) -> None
    def on_error(self, callback: Callable[[str], None]) -> None
```
Usa `bambulabs-api` por baixo. Traduz eventos MQTT brutos em eventos de domínio simples. Gerencia reconexão automática com backoff exponencial.

`ProgressEvent` é um dataclass com `percentual: int`, `camada_atual: int`, `camada_total: int`.

`CurrentJob` é um dataclass com `gcode_file: str` (nome do arquivo atual na X1) e `state: Literal["idle", "printing", "paused", "error"]`.

**`job_runner.py`**
```python
@dataclass
class JobResult:
    order_id: str
    status: Literal["IMPRESSO", "ERRO_IMPRESSAO"]
    error_message: str | None

class JobRunner:
    def __init__(self, backend: BackendClient, printer: PrinterClient)
    async def run(self, order: Order) -> JobResult
```

Fluxo interno de `run()`:
1. **Download:** `backend.download_model(order.modelo_url, f"downloads/{order.id}.glb")`
2. **Slice:** `slicer.slice(glb_path, order.material, f"downloads/{order.id}.3mf")`
3. **Upload:** `printer.upload_file(slice_result.output_path)` → retorna `remote_filename`
4. **Start:** `printer.start_print(remote_filename)`
5. **Status transition:** `backend.update_status(order.id, "IMPRIMINDO")`
6. **Register listeners:**
   - `on_progress` → acumula em `self._last_progress`, chama `_maybe_flush_progress()` (throttle 30s)
   - `on_finished` → seta `self._done_event`
   - `on_error` → seta `self._error_message` e `self._done_event`
7. **Wait:** `await self._done_event.wait()` (bloqueia até conclusão ou erro)
8. **Flush final:** garante último update de progresso em 100%
9. **Finaliza:**
   - Se sucesso: `backend.update_status(order.id, "IMPRESSO")` → retorna `JobResult(status="IMPRESSO")`
   - Se erro: `backend.report_error(order.id, self._error_message)` → retorna `JobResult(status="ERRO_IMPRESSAO")`

Cada etapa (1-4) roda dentro de try/except. Falha → `backend.report_error()` com mensagem adequada → retorna `ERRO_IMPRESSAO` sem prosseguir.

Throttle de progresso:
```python
def _maybe_flush_progress(self):
    now = time.monotonic()
    if now - self._last_progress_sent_at >= 30:
        asyncio.create_task(self._flush_progress())
        self._last_progress_sent_at = now
```

**`logging_setup.py`**
- Configura logging estruturado (JSON se em prod, texto colorido em dev)
- Níveis: `INFO` por padrão, `DEBUG` se `AGENT_DEBUG=1` no env
- Formatadores alinhados pra facilitar grep no log do PC da impressora

**`agent.py`** (entrypoint)
```python
async def main():
    config = load_config()
    setup_logging()
    backend = BackendClient(config)
    printer = PrinterClient(config)

    await printer.connect()
    await reconcile_on_startup(backend, printer)

    while True:
        try:
            order = await backend.claim_next_job()
            if not order:
                await asyncio.sleep(config.poll_interval)
                continue
            runner = JobRunner(backend, printer)
            result = await runner.run(order)
            logger.info(f"Job {result.order_id} terminou: {result.status}")
        except Exception as e:
            logger.exception("Erro no loop principal")
            await asyncio.sleep(config.poll_interval)

if __name__ == "__main__":
    asyncio.run(main())
```

### 8.3 Dependências entre módulos

```
agent.py → config, backend_client, printer_client, job_runner, logging_setup
job_runner → backend_client, printer_client, slicer
printer_client → bambulabs-api
backend_client → httpx
slicer → subprocess
```
Sem ciclos. `backend_client` e `printer_client` são independentes — podem ser testados isoladamente.

### 8.4 Testabilidade

- `slicer.py`: testável com `subprocess.run` mockado (`monkeypatch`)
- `backend_client.py`: testável com `httpx.MockTransport`
- `job_runner.py`: testável com mocks de `BackendClient` e `PrinterClient` (interfaces pequenas bem definidas)
- `printer_client.py`: o mais difícil — pode ser mockado via interface `bambulabs-api`, ou testes de integração manuais com a X1 ligada

Testes ficam em `printer-agent/tests/` (nova pasta). Pytest como runner. Esta spec **não inclui a escrita dos testes** como entregáveis — fica como TODO pro plano de implementação decidir.

## 9. Fluxo completo de um pedido

### 9.1 Caminho feliz

```
[WEBHOOK MP]
  │ status = PAGO (código existente)
  ▼
[AGENT LOOP]
  │ (a cada poll_interval) POST /api/printer/claim
  ▼
[BACKEND]
  │ limpa PREPARANDO órfão (>45min)
  │ SELECT next PAGO FOR UPDATE SKIP LOCKED
  │ UPDATE → PREPARANDO, impressao_iniciada_em=NOW()
  │ retorna order
  ▼
[AGENT: JobRunner.run(order)]
  │ 1. backend.download_model() → downloads/{id}.glb
  │ 2. slicer.slice() → downloads/{id}.3mf
  │ 3. printer.upload_file() → FTP /sdcard/{id}.3mf
  │ 4. printer.start_print() → MQTT command
  │ 5. backend.update_status(IMPRIMINDO)
  ▼
[LOOP DE MONITORAMENTO]
  │ MQTT on_progress:
  │   - acumula last_progress
  │   - se ≥30s desde último flush: POST /api/printer/orders/{id}/progress
  │ MQTT on_finished:
  │   - flush final de progresso (100%)
  │   - POST /api/printer/orders/{id}/status = IMPRESSO
  │   - backend registra impressao_concluida_em
  ▼
[JobRunner retorna; agent volta ao loop de claim]
```

### 9.2 Ramos de erro

Qualquer exceção em `JobRunner.run()` (ou evento `on_error` durante impressão) converge pro mesmo caminho:

```
exceção / erro MQTT
  │
  ▼
backend.report_error(order_id, mensagem)
  │
  ▼
[BACKEND]
  UPDATE orders
  SET status='ERRO_IMPRESSAO',
      erro_mensagem=<msg>,
      erro_em=NOW()
  WHERE id=<order_id>
  ▼
(trigger NOTIFY dispara → SSE manda evento pro cliente → UI mostra estado de erro amigável)
(notifier dispara → email de erro pro cliente)
```

**Mensagens de erro por etapa:**

| Etapa | Erro possível | Mensagem salva |
|---|---|---|
| Download GLB | 404, timeout, storage inacessível | `"Falha ao baixar modelo: {detalhe}"` |
| Slice | BambuStudio CLI exit ≠0 | `"Falha no fatiamento: {stderr[:500]}"` |
| Upload FTP | X1 offline, access_code inválido | `"Falha no upload FTP: {detalhe}"` |
| Start print | MQTT timeout, X1 ocupada | `"Falha ao iniciar impressão: {detalhe}"` |
| Durante impressão | filament out, descolou, erro da X1 | `"Impressão falhou: {código MQTT}"` |

### 9.3 Reconciliação no startup

```
agent inicia
  │
  ▼
printer.connect() + printer.get_current_job()
  │
  ├── X1 ocioso
  │     └─► segue pro loop normal de claim
  │
  └── X1 imprimindo "{id}.3mf"
        │
        ├─ extrai {id} do nome do arquivo
        ├─ GET /api/orders/{id}
        │
        ├── pedido status ∈ {PREPARANDO, IMPRIMINDO}
        │     └─► registra listeners MQTT e monitora (reconciliado)
        │
        └── pedido não existe ou status incompatível
              └─► warning "X1 imprimindo job desconhecido, ignorando"
                  (não claim novo até X1 ficar livre)
```

**Nome do arquivo como chave:** o agent usa `{order_id}.3mf` como convenção. A X1 via MQTT reporta `gcode_file` — o agent parseia `os.path.basename().replace(".3mf", "")` pra extrair o UUID.

**Limpeza de `PREPARANDO` órfão:** tratada no lado do backend dentro de `POST /api/printer/claim` (ver Seção 6.1) — qualquer pedido em `PREPARANDO` com `impressao_iniciada_em` há mais de `ORPHAN_PREPARING_MINUTES` (default 45 min) vira `ERRO_IMPRESSAO` antes do agent claim um novo.

**Interação entre cleanup e reconciliação:** se o backend marcou um pedido como `ERRO_IMPRESSAO` por timeout, mas ao reiniciar o agent descobre que a X1 está de fato imprimindo esse mesmo pedido (arquivo `{id}.3mf`), o agent deve loggar warning e **tratar como job desconhecido** (não tenta retomar). Nesse cenário, humano interveem: cancela a impressão na X1 ou reenfileira manualmente o pedido no admin. Justificativa: tentar "consertar" automaticamente um estado inconsistente aumenta risco de bugs sutis. Falhar visível é mais seguro.

## 10. Real-time no frontend via SSE + Postgres LISTEN/NOTIFY

### 10.1 Por que SSE e não polling/WebSocket

- **Unidirecional (servidor → cliente):** exatamente o caso de uso; cliente só *recebe* updates
- **HTTP puro:** passa por proxies, firewalls e CDNs sem configuração especial
- **Reconexão automática:** `EventSource` faz nativo
- **Suporte FastAPI:** `StreamingResponse` com media type `text/event-stream`
- WebSocket seria overkill; polling tem latência inerente e gera mais carga

### 10.2 Endpoint SSE

```
GET /api/orders/{id}/stream
```

**Comportamento:**
1. Envia evento `snapshot` com o estado completo do pedido (mesmo formato do `GET /api/orders/{id}`)
2. Abre conexão `LISTEN order_{id}` no Postgres via asyncpg
3. A cada `NOTIFY`, envia evento `update` com os campos mudados
4. Se `status ∈ {IMPRESSO, ERRO_IMPRESSAO, ENVIADO, ENTREGUE}` → envia evento `closed` e encerra conexão
5. Heartbeat: envia comentário SSE vazio (`:\n\n`) a cada 30s pra manter proxies vivos
6. Cleanup: `finally` chama `connection.remove_listener` e fecha a conexão asyncpg

**Formato SSE:**
```
event: snapshot
data: {"id": "...", "status": "IMPRIMINDO", ...}

event: update
data: {"progresso_percentual": 45, "camada_atual": 102}

: heartbeat

event: closed
data: {"reason": "terminal_state"}
```

### 10.3 Trigger PL/pgSQL

Migration `003_sse_notify_trigger.py`:

```sql
CREATE OR REPLACE FUNCTION notify_order_update() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('order_' || NEW.id, row_to_json(NEW)::text);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER order_update_notify
  AFTER UPDATE ON orders
  FOR EACH ROW EXECUTE FUNCTION notify_order_update();
```

**Por que LISTEN/NOTIFY em vez de pub/sub in-memory:**
- Funciona com múltiplas instâncias do backend (Railway pode escalar horizontalmente)
- Zero dependência extra (Postgres já está lá)
- asyncpg suporta nativo via `connection.add_listener(channel, callback)`
- Latência < 10ms

### 10.4 Frontend

**Novo hook** `frontend/src/lib/hooks/useOrderStream.ts`:
```ts
export function useOrderStream(orderId: string): {
  order: Order | null
  connected: boolean
  error: Error | null
}
```
Usa `EventSource` internamente. Se `EventSource` não existir ou falhar consecutivamente N vezes, faz fallback pra polling (`setInterval` chamando `getOrder`).

**Refatoração do `OrderTracker.tsx`:**
- Recebe `orderId: string` como prop (em vez de `order: Order`)
- Usa `useOrderStream` internamente
- Renderiza baseado no status atual

## 11. Notificações por email via Resend

### 11.1 Stack

- SDK: `resend` (Python)
- Free tier: 100 emails/dia, 3000/mês — suficiente pro começo
- SPF/DKIM/DMARC: configurar no DNS do domínio forja3d.com.br
- Endereço de envio: `pedidos@forja3d.com.br` (precisa estar verificado no Resend)

### 11.2 Eventos e templates

| Trigger (transição) | Assunto | Template |
|---|---|---|
| `AGUARDANDO_PAGAMENTO → PAGO` | "Recebemos seu pagamento — FORJA3D" | `payment_received.html` |
| `PREPARANDO → IMPRIMINDO` | "Sua peça entrou na impressora" | `print_started.html` |
| `IMPRIMINDO → IMPRESSO` | "Sua peça está pronta!" | `print_finished.html` |
| `EMBALANDO → ENVIADO` (com código) | "Seu pedido foi postado" | `shipped.html` |
| `* → ERRO_IMPRESSAO` | "Tivemos um contratempo com sua peça" | `print_error.html` |

### 11.3 Serviço notifier

Novo arquivo `backend/services/notifier.py`:
```python
class Notifier:
    def __init__(self)  # lê RESEND_API_KEY e EMAIL_FROM do env
    async def send_payment_received(self, order: Order) -> None
    async def send_print_started(self, order: Order) -> None
    async def send_print_finished(self, order: Order) -> None
    async def send_shipped(self, order: Order) -> None
    async def send_print_error(self, order: Order) -> None

notifier = Notifier()  # singleton módulo
```

Cada método:
1. Renderiza template Jinja2 de `backend/templates/emails/*.html`
2. Chama `resend.Emails.send(...)`
3. Em caso de exceção, loga warning e segue — **nunca propaga**
4. Email é best-effort: falha de envio **não bloqueia** a transição de status

### 11.4 Onde chamar cada método

- `send_payment_received` → `routers/payment.py`, após `status=PAGO` no webhook
- `send_print_started` → `routers/printer.py`, no endpoint `/status` quando recebe `IMPRIMINDO`
- `send_print_finished` → `routers/printer.py`, no endpoint `/status` quando recebe `IMPRESSO`
- `send_print_error` → `routers/printer.py`, no endpoint `/erro`
- `send_shipped` → `routers/admin.py`, no endpoint `POST /admin/orders/{id}` quando detecta transição para `ENVIADO` com `codigo_rastreio` novo

### 11.5 Templates HTML

Visual alinhado com o design system do frontend:
- Fundo `#0a0a0a`, tipografia DM Sans, `Space Mono` pra números
- Cabeçalho com logo/texto "FORJA3D" em teal
- Conteúdo em card com borda sutil `rgba(255,255,255,0.08)`, border-radius 16px
- Botão CTA com gradiente teal linkando pro `/pedido/{id}` (URL do frontend)
- Rodapé com contato e aviso de não responder

### 11.6 Novas env vars

Backend (`backend/.env` e Railway):
```
RESEND_API_KEY=<key do resend>
EMAIL_FROM="FORJA3D <pedidos@forja3d.com.br>"
FRONTEND_URL=https://forja3d.com.br  # já existe no .env atual
```

### 11.7 TODOs operacionais (não código)

- Registrar domínio forja3d.com.br no Resend
- Configurar registros DNS: SPF, DKIM (DKIM1 e DKIM2 do Resend), DMARC
- Criar conta de email `pedidos@forja3d.com.br` (ou alias) no provedor de DNS/email

## 12. Mudanças no frontend

### 12.1 Página `/pedido/[id]` (cliente)

**Estados visuais (mutuamente exclusivos):**

**`PREPARANDO`:**
- Label: "Preparando impressão..."
- Spinner sutil (animação suave)
- Texto auxiliar: "Baixando modelo e enviando para a impressora"

**`IMPRIMINDO`:**
- Label: "Imprimindo"
- Barra de progresso (0-100%) com fill em gradiente teal
- `{percentual}%` em destaque (Space Mono, grande)
- `camada {camada_atual} / {camada_total}`
- ETA calculado: `tempo_impressao_horas * (1 - percentual/100)` formatado como "~X h Y min" ou "~X min"

**`IMPRESSO`:**
- Label: "Impresso — preparando envio"
- Texto: "Sua peça está pronta! Vamos embalar e enviar em breve."

**`ERRO_IMPRESSAO`:**
- Label em tom de alerta âmbar (não vermelho berrante)
- Mensagem amigável: "Tivemos um problema com a impressão. Nossa equipe já foi notificada e vamos reimprimir sua peça sem custo adicional."
- **Não expõe `erro_mensagem` crua** (é texto técnico interno)
- Botão "Falar com suporte" (WhatsApp link — URL específica fica como TODO)

**Conexão:**
- Usa `useOrderStream(id)` (SSE, ver Seção 10)
- Fallback automático pra polling se SSE falhar

### 12.2 Página `/admin`

**Tabela atualizada:**
- Nova coluna "Progresso": mostra `{percentual}%` se `IMPRIMINDO`, senão `—`
- Nova coluna "Última atualização": `updated_at` formatado relativo ("há 2 min")
- Linhas em `ERRO_IMPRESSAO` destacadas com borda/fundo âmbar sutil

**Filtros:**
- Barra de botões no topo: Todos / Pago / Preparando / Imprimindo / Impresso / Embalando / Enviado / Entregue / Erro
- Clique filtra a tabela (client-side)

**Cada linha clicável:** abre `/admin/pedido/{id}` (ver Seção 12.3)

**Persistência da senha:** admin login continua igual; senha salva em `sessionStorage` pra navegação entre admin pages sem re-prompt.

### 12.3 Nova página `/admin/pedido/[id]`

Rota: `frontend/src/app/admin/pedido/[id]/page.tsx`

**Header:**
- Nome e email do cliente
- ID do pedido (Space Mono, copiável com botão)
- Badge de status em destaque (teal/âmbar)
- Timestamp de criação (absoluto e relativo)

**Timeline de eventos (derivada dos campos):**
Linha do tempo vertical, eventos mostrados somente se o campo correspondente existe:
- Criado → `created_at`
- Pago → `updated_at` da transição (aproximado) + `mp_payment_id`
- Preparando → aproximado de `impressao_iniciada_em` ou transição
- Imprimindo → `impressao_iniciada_em`
- Impresso → `impressao_concluida_em`
- Embalando / Enviado / Entregue → `updated_at` da transição + `codigo_rastreio`
- (se houver) Erro → `erro_em` + `erro_mensagem` em bloco `<code>` técnico

**Visualização do modelo:**
- `<model-viewer>` renderizando `modelo_url`

**Grid de detalhes técnicos:**
- Material, escala, peso (g), volume (cm³), tempo estimado (h)
- Preço detalhado: material + energia + API + embalagem + margem
- Frete: UF, cidade, preço, prazo
- CEP destino
- `arquivo_3mf_path` (se existir)

**Progresso em tempo real (se `IMPRIMINDO`):**
- Reusa `OrderTracker.tsx` com SSE

**Ações (botões no fim):**
- "Reenfileirar" (só se `ERRO_IMPRESSAO`) → `POST /api/admin/orders/{id}/requeue`
- "Marcar como Embalado" (se `IMPRESSO`) → `POST /api/admin/orders/{id}` com `status=EMBALANDO`
- "Marcar como Enviado" (se `EMBALANDO`) → modal com input de código, depois POST com `status=ENVIADO, codigo_rastreio=<valor>`
- "Abrir no Mercado Pago" (link externo baseado em `mp_payment_id`)
- "Forçar status..." (dropdown de emergência com confirmação dupla — transição manual arbitrária)

### 12.4 `lib/api.ts` atualizado

Funções novas:
```ts
getOrder(id: string): Promise<Order>
streamOrder(id: string): EventSource
adminRequeueOrder(id: string, password: string): Promise<Order>
adminUpdateOrder(id: string, password: string, updates: { status?: string; codigo_rastreio?: string }): Promise<Order>
```

Interface `Order` atualizada:
```ts
interface Order {
  id: string
  nome: string
  email: string
  status: "AGUARDANDO_PAGAMENTO" | "PAGO" | "PREPARANDO" | "IMPRIMINDO" | "IMPRESSO" | "ERRO_IMPRESSAO" | "EMBALANDO" | "ENVIADO" | "ENTREGUE"
  material: "PLA" | "PETG" | "TPU"
  escala: number
  peso_gramas: number
  volume_cm3: number
  tempo_impressao_horas: number
  preco_centavos: number
  frete_centavos: number
  total_centavos: number
  cep_destino: string
  prazo_dias: number
  codigo_rastreio: string | null
  mp_payment_id: string | null
  mp_preference_id: string | null
  progresso_percentual: number | null
  camada_atual: number | null
  camada_total: number | null
  erro_mensagem: string | null
  erro_em: string | null
  impressao_iniciada_em: string | null
  impressao_concluida_em: string | null
  arquivo_3mf_path: string | null
  created_at: string
  updated_at: string
}
```

## 13. Checklist de implementação (resumo)

Esta seção serve só como índice do que o plano de implementação (spec seguinte via `writing-plans`) deve cobrir. Não é um plano de execução.

**Backend:**
- [ ] Adicionar Alembic ao projeto; criar migrations baseline, lifecycle fields, trigger NOTIFY
- [ ] Adicionar estados `PREPARANDO`, `IMPRESSO`, `ERRO_IMPRESSAO` no enum
- [ ] Adicionar colunas novas em `Order`
- [ ] Criar `backend/models/state_machine.py` com regras de transição
- [ ] Criar `backend/routers/printer.py` com endpoints `/claim`, `/status`, `/progress`, `/erro`
- [ ] Adicionar `POST /api/admin/orders/{id}/requeue`
- [ ] Adicionar `GET /api/orders/{id}/stream` (SSE)
- [ ] Criar `backend/services/notifier.py` + templates em `backend/templates/emails/`
- [ ] Integrar notifier nas transições relevantes
- [ ] Adicionar env vars: `AGENT_PASSWORD`, `RESEND_API_KEY`, `EMAIL_FROM`
- [ ] Configurar Railway start command com `alembic upgrade head`

**Printer-agent:**
- [ ] Refatorar em módulos (`config`, `backend_client`, `printer_client`, `slicer`, `job_runner`, `logging_setup`, `agent`)
- [ ] Adicionar `bambulabs-api` ao `requirements.txt`
- [ ] Implementar MQTT connection com reconexão
- [ ] Implementar reconciliação no startup
- [ ] Implementar throttle de progress updates
- [ ] Criar `config.example.json`, adicionar `config.json` ao `.gitignore`

**Frontend:**
- [ ] Atualizar `Order` interface em `lib/api.ts`
- [ ] Criar `useOrderStream` hook
- [ ] Refatorar `OrderTracker.tsx` com os novos estados e SSE
- [ ] Atualizar `/pedido/[id]` pra usar `OrderTracker` refatorado
- [ ] Atualizar `/admin` com nova coluna de progresso, filtros, linhas clicáveis
- [ ] Criar `/admin/pedido/[id]` com timeline, model-viewer, ações

**Operacional (humano):**
- [ ] Rotacionar credenciais Tencent e Mercado Pago
- [ ] Gerar novos `ADMIN_PASSWORD` e `AGENT_PASSWORD`
- [ ] Atualizar `.env.example` com todas as chaves
- [ ] Registrar domínio no Resend e configurar DNS
- [ ] Atualizar CLAUDE.md com seção de migrações e nota sobre pre-commit de segredos
- [ ] Atualizar CLAUDE.md pra refletir Postgres (hoje ainda menciona SQLite)

**Testes (fora desta spec — TODO do plano de implementação):**
- [ ] Testes unitários do `slicer`, `backend_client`, `job_runner`
- [ ] Testes de integração do `printer_client` com X1 real (manuais)
- [ ] Teste end-to-end: gerar pedido → pagar (sandbox MP) → agent processa → ver progresso no frontend

## 14. Anexo: riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| `bambulabs-api` não expor todos os eventos que precisamos | Média | Alto | Pesquisar docs/fonte antes de implementar `printer_client`; ter plano B de polling direto na API REST da X1 |
| BambuStudio CLI quebrar em update silencioso | Baixa | Médio | Fixar versão via config, documentar path esperado, falhar loud no startup |
| SSE travar atrás de proxy do Vercel/Railway | Baixa | Médio | Testar em staging antes do go-live; fallback de polling já previsto |
| Resend recusar domínio sem verificação DNS completa | Alta | Baixo | TODO operacional explícito; sem DNS configurado, emails simplesmente não enviam (best-effort) |
| Race condition em `claim` com múltiplos agents | Baixa | Alto | `FOR UPDATE SKIP LOCKED` resolve; documentar que backend **exige** Postgres (não é mais opcional) |
| Migração Alembic baseline detectar drift vs. estado atual | Alta | Baixo | Rodar `alembic revision --autogenerate` num DB limpo e comparar; ajustar baseline manualmente se necessário |
