# Printer Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete printer lifecycle (`PAGO → PREPARANDO → IMPRIMINDO → IMPRESSO`) with MQTT monitoring, real-time progress via SSE, email notifications, and an admin detail page for order management.

**Architecture:** Backend gets new state machine, dedicated `/api/printer/*` endpoints for the agent (separate from admin auth), SSE via Postgres LISTEN/NOTIFY, Resend-based email notifier, and Alembic for migrations. The printer-agent is refactored into focused modules (`config`, `backend_client`, `printer_client`, `slicer`, `job_runner`) with MQTT via `bambulabs-api`. Frontend gets real-time order updates via SSE hook, new state rendering, and a detailed admin page at `/admin/pedido/[id]`.

**Tech Stack:**
- Backend: Python 3.12, FastAPI, SQLAlchemy async, asyncpg, Alembic, Resend SDK, Jinja2 (já no FastAPI starlette), pytest + pytest-asyncio
- Agent: Python 3.12, httpx, bambulabs-api, pytest
- Frontend: Next.js 15, TypeScript, EventSource API (nativo)
- DB: PostgreSQL 15+ (local docker-compose, Railway em produção)

**Spec:** `docs/superpowers/specs/2026-04-10-printer-lifecycle-design.md`

---

## Phase 0 — Setup de infra (Alembic, pytest)

### Task 0.1: Adicionar Alembic e pytest ao backend

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Adicionar dependências ao requirements**

Edit `backend/requirements.txt` para acrescentar no fim:
```
alembic>=1.13.0
resend>=2.5.0
jinja2>=3.1.0
pytest>=8.3.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 2: Instalar no venv local**

Run:
```bash
cd backend && .venv/Scripts/pip install -r requirements.txt
```
Expected: instala alembic, resend, jinja2, pytest, pytest-asyncio sem erro.

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(backend): adiciona alembic, resend, pytest"
```

### Task 0.2: Inicializar Alembic

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/` (pasta vazia inicialmente)

- [ ] **Step 1: Rodar alembic init**

Run:
```bash
cd backend && .venv/Scripts/alembic init alembic
```
Expected: cria `backend/alembic/` e `backend/alembic.ini`.

- [ ] **Step 2: Configurar `alembic/env.py` pra async + import do Base**

Replace the content of `backend/alembic/env.py` with:
```python
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Carrega .env
from dotenv import load_dotenv
load_dotenv()

# Importa Base e models para que o autogenerate os detecte
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Base  # noqa: E402
from models import tables  # noqa: E402, F401

config = context.config

# Injeta DATABASE_URL do .env no alembic
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/forja3d")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Verificar que alembic consegue conectar**

Run (com Postgres rodando):
```bash
cd backend && .venv/Scripts/alembic current
```
Expected: não retorna erro (saída vazia = nenhuma migration aplicada ainda).

- [ ] **Step 4: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat(backend): inicializa alembic com suporte a async"
```

### Task 0.3: Setup do pytest pra backend

**Files:**
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Criar `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 2: Criar `backend/tests/__init__.py`**

Arquivo vazio.

- [ ] **Step 3: Criar `backend/tests/conftest.py` com fixtures async**

```python
import asyncio
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Usa um DB de teste separado
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/forja3d_test")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin")
os.environ.setdefault("AGENT_PASSWORD", "test_agent")
os.environ.setdefault("ORPHAN_PREPARING_MINUTES", "45")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Cria schema no DB de teste e devolve uma sessão limpa por teste."""
    from database import Base

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncClient:
    from main import app
    from database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 4: Criar DB de teste no Postgres local**

Run:
```bash
docker exec -it $(docker ps -q --filter ancestor=postgres) psql -U postgres -c "CREATE DATABASE forja3d_test;" 2>/dev/null || echo "DB já existe ou comando diferente — criar manualmente no seu docker-compose"
```
Expected: `CREATE DATABASE` ou aviso que já existe. Se não funcionar, criar manualmente via `docker-compose exec db psql -U postgres -c "CREATE DATABASE forja3d_test;"`.

- [ ] **Step 5: Sanity check do pytest**

Criar `backend/tests/test_sanity.py`:
```python
def test_sanity():
    assert 1 + 1 == 2
```

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_sanity.py -v
```
Expected: PASS.

- [ ] **Step 6: Remover o sanity test e commitar setup**

```bash
rm backend/tests/test_sanity.py
git add backend/pytest.ini backend/tests/
git commit -m "test(backend): setup pytest com fixtures async e DB de teste"
```

---

## Phase 1 — State machine e migrations

### Task 1.1: Adicionar novos estados ao enum

**Files:**
- Modify: `backend/models/schemas.py`

- [ ] **Step 1: Editar `backend/models/schemas.py`**

Substituir a classe `StatusPedido` por:
```python
class StatusPedido(str, Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    PAGO = "PAGO"
    PREPARANDO = "PREPARANDO"
    IMPRIMINDO = "IMPRIMINDO"
    IMPRESSO = "IMPRESSO"
    ERRO_IMPRESSAO = "ERRO_IMPRESSAO"
    EMBALANDO = "EMBALANDO"
    ENVIADO = "ENVIADO"
    ENTREGUE = "ENTREGUE"
```

- [ ] **Step 2: Commit**

```bash
git add backend/models/schemas.py
git commit -m "feat(backend): adiciona estados PREPARANDO, IMPRESSO, ERRO_IMPRESSAO"
```

### Task 1.2: Adicionar colunas novas ao model `Order`

**Files:**
- Modify: `backend/models/tables.py`

- [ ] **Step 1: Adicionar novos campos na classe `Order`**

Em `backend/models/tables.py`, adicionar logo após o campo `mp_preference_id` (antes dos timestamps):
```python
    # Progresso em tempo real
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

- [ ] **Step 2: Commit**

```bash
git add backend/models/tables.py
git commit -m "feat(backend): adiciona colunas de progresso e erro no Order"
```

### Task 1.3: Criar módulo de state machine (com tests)

**Files:**
- Create: `backend/models/state_machine.py`
- Create: `backend/tests/test_state_machine.py`

- [ ] **Step 1: Escrever os testes primeiro**

Criar `backend/tests/test_state_machine.py`:
```python
import pytest

from models.state_machine import (
    ALLOWED_TRANSITIONS,
    TransitionError,
    assert_allowed,
)


def test_pago_to_preparando_is_allowed():
    assert_allowed("PAGO", "PREPARANDO")


def test_preparando_to_imprimindo_is_allowed():
    assert_allowed("PREPARANDO", "IMPRIMINDO")


def test_imprimindo_to_impresso_is_allowed():
    assert_allowed("IMPRIMINDO", "IMPRESSO")


def test_preparando_to_erro_is_allowed():
    assert_allowed("PREPARANDO", "ERRO_IMPRESSAO")


def test_imprimindo_to_erro_is_allowed():
    assert_allowed("IMPRIMINDO", "ERRO_IMPRESSAO")


def test_erro_to_pago_is_allowed():
    """Requeue path."""
    assert_allowed("ERRO_IMPRESSAO", "PAGO")


def test_pago_to_imprimindo_is_not_allowed():
    with pytest.raises(TransitionError):
        assert_allowed("PAGO", "IMPRIMINDO")


def test_impresso_to_imprimindo_is_not_allowed():
    with pytest.raises(TransitionError):
        assert_allowed("IMPRESSO", "IMPRIMINDO")


def test_any_to_entregue_not_in_agent_machine():
    with pytest.raises(TransitionError):
        assert_allowed("IMPRESSO", "ENTREGUE")  # só via admin manual


def test_transitions_dict_contains_entry_for_each_active_state():
    for state in ["PAGO", "PREPARANDO", "IMPRIMINDO", "ERRO_IMPRESSAO"]:
        assert state in ALLOWED_TRANSITIONS
```

- [ ] **Step 2: Rodar os testes e ver que falham**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_state_machine.py -v
```
Expected: FAIL com `ModuleNotFoundError: No module named 'models.state_machine'`.

- [ ] **Step 3: Implementar `backend/models/state_machine.py`**

```python
"""Regras de transição de estado para pedidos.

Só valida as transições automáticas (agent + requeue).
Admin tem override manual via endpoint genérico que não passa por aqui.
"""


class TransitionError(Exception):
    """Transição não permitida."""


# key = estado atual, value = set de estados destino permitidos
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "PAGO": {"PREPARANDO"},
    "PREPARANDO": {"IMPRIMINDO", "ERRO_IMPRESSAO"},
    "IMPRIMINDO": {"IMPRESSO", "ERRO_IMPRESSAO"},
    "ERRO_IMPRESSAO": {"PAGO"},  # só via requeue admin
}


def assert_allowed(from_status: str, to_status: str) -> None:
    """Levanta TransitionError se a transição não for permitida."""
    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise TransitionError(
            f"Transição ilegal: {from_status} → {to_status}. "
            f"Permitido de {from_status}: {sorted(allowed) or 'nenhum'}"
        )
```

- [ ] **Step 4: Rodar os testes e ver que passam**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_state_machine.py -v
```
Expected: todos os 10 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/models/state_machine.py backend/tests/test_state_machine.py
git commit -m "feat(backend): state machine de transições com testes"
```

### Task 1.4: Migration baseline

**Files:**
- Create: `backend/alembic/versions/001_baseline.py` (via autogenerate)

- [ ] **Step 1: Drop-recreate o DB local antes do baseline**

Com Postgres rodando via docker-compose:
```bash
docker-compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS forja3d;"
docker-compose exec db psql -U postgres -c "CREATE DATABASE forja3d;"
```
Expected: commands OK. (Você perde dados do DB de dev — já combinamos na spec.)

- [ ] **Step 2: Autogenerate baseline a partir do model atual**

Run:
```bash
cd backend && .venv/Scripts/alembic revision --autogenerate -m "baseline"
```
Expected: cria `backend/alembic/versions/<hash>_baseline.py` com `op.create_table("orders", ...)` e `op.create_table("generations", ...)` cobrindo todos os campos — **incluindo os novos campos adicionados em 1.2**.

- [ ] **Step 3: Renomear o arquivo pra ficar ordenado**

Run:
```bash
cd backend/alembic/versions && mv *_baseline.py 001_baseline.py
```
Dentro do arquivo, alterar `revision = "<hash>"` para `revision = "001_baseline"` e `down_revision = None` (deve já estar).

- [ ] **Step 4: Aplicar a migration**

Run:
```bash
cd backend && .venv/Scripts/alembic upgrade head
```
Expected: cria as tabelas `orders`, `generations`, `alembic_version` no DB `forja3d`.

- [ ] **Step 5: Verificar schema**

Run:
```bash
docker-compose exec db psql -U postgres -d forja3d -c "\d orders"
```
Expected: tabela com todas as colunas, incluindo `progresso_percentual`, `camada_atual`, etc.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/001_baseline.py
git commit -m "feat(backend): migration baseline com campos de lifecycle"
```

### Task 1.5: Remover `create_all` do lifespan

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Editar `backend/main.py`**

Substituir a função `lifespan` por:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations são aplicadas via `alembic upgrade head` no start command.
    # Não chamamos Base.metadata.create_all aqui.
    yield
    await engine.dispose()
```

E remover o import `from models.tables import Order, Generation` que estava dentro do lifespan (agora inútil).

- [ ] **Step 2: Verificar que o backend ainda sobe**

Run:
```bash
cd backend && .venv/Scripts/python -c "from main import app; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "refactor(backend): remove create_all do lifespan (migrations via alembic)"
```

---

## Phase 2 — Endpoints `/api/printer/*`

### Task 2.1: Router skeleton + autenticação de agent

**Files:**
- Create: `backend/routers/printer.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Criar `backend/routers/printer.py`**

```python
import os

from fastapi import APIRouter, Header, HTTPException, status

router = APIRouter(tags=["printer"], prefix="/printer")

AGENT_PASSWORD = os.getenv("AGENT_PASSWORD", "dev_agent_password")


def verify_agent(agent_password: str) -> None:
    """Valida senha do agent; levanta HTTP 401 se inválida."""
    if agent_password != AGENT_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autorizado (agent)",
        )
```

- [ ] **Step 2: Registrar router em `main.py`**

Em `backend/main.py`, adicionar no import:
```python
from routers import generate, orders, payment, shipping, admin, price, printer
```
E adicionar após os outros `include_router`:
```python
app.include_router(printer.router, prefix="/api")
```

- [ ] **Step 3: Sanity check**

Run:
```bash
cd backend && .venv/Scripts/python -c "from main import app; print([r.path for r in app.routes if '/printer' in str(r.path)])"
```
Expected: lista vazia (endpoints ainda não criados) mas sem erro de import.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/printer.py backend/main.py
git commit -m "feat(backend): skeleton do router /api/printer com auth de agent"
```

### Task 2.2: Endpoint `/printer/claim` com orphan cleanup

**Files:**
- Modify: `backend/routers/printer.py`
- Create: `backend/tests/test_printer_claim.py`

- [ ] **Step 1: Escrever os testes**

Criar `backend/tests/test_printer_claim.py`:
```python
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from models.tables import Order


def _make_order(**overrides) -> Order:
    base = dict(
        nome="Teste",
        email="t@t.com",
        status="PAGO",
        modelo_url="/uploads/fake.glb",
        material="PLA",
        escala=1.0,
        peso_gramas=50.0,
        volume_cm3=30.0,
        tempo_impressao_horas=2.0,
        preco_centavos=5000,
        frete_centavos=2000,
        cep_destino="28035030",
        prazo_dias=5,
    )
    base.update(overrides)
    return Order(**base)


@pytest.mark.asyncio
async def test_claim_returns_null_when_no_pago_orders(client, db_session):
    resp = await client.post("/api/printer/claim", json={"agent_password": "test_agent"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] is None


@pytest.mark.asyncio
async def test_claim_picks_oldest_pago_and_marks_preparando(client, db_session):
    old = _make_order()
    new = _make_order()
    db_session.add_all([old, new])
    await db_session.commit()

    resp = await client.post("/api/printer/claim", json={"agent_password": "test_agent"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] is not None
    assert body["data"]["id"] == old.id
    assert body["data"]["status"] == "PREPARANDO"

    await db_session.refresh(old)
    assert old.status == "PREPARANDO"
    assert old.impressao_iniciada_em is not None


@pytest.mark.asyncio
async def test_claim_rejects_wrong_password(client):
    resp = await client.post("/api/printer/claim", json={"agent_password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_claim_cleans_orphan_preparando_older_than_threshold(client, db_session):
    orphan = _make_order(
        status="PREPARANDO",
        impressao_iniciada_em=datetime.utcnow() - timedelta(minutes=60),
    )
    fresh_pago = _make_order()
    db_session.add_all([orphan, fresh_pago])
    await db_session.commit()

    resp = await client.post("/api/printer/claim", json={"agent_password": "test_agent"})
    body = resp.json()
    # cleanup happened, then fresh_pago was claimed
    assert body["data"]["id"] == fresh_pago.id

    await db_session.refresh(orphan)
    assert orphan.status == "ERRO_IMPRESSAO"
    assert "abandonada" in (orphan.erro_mensagem or "").lower()
```

- [ ] **Step 2: Rodar os testes e ver que falham**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_printer_claim.py -v
```
Expected: 4 testes FALHAM com 404 (endpoint não existe).

- [ ] **Step 3: Implementar o endpoint**

Adicionar em `backend/routers/printer.py`:
```python
from datetime import datetime, timedelta

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.tables import Order

ORPHAN_PREPARING_MINUTES = int(os.getenv("ORPHAN_PREPARING_MINUTES", "45"))


class AgentRequest(BaseModel):
    agent_password: str


def _order_to_dict(o: Order) -> dict:
    return {
        "id": o.id,
        "nome": o.nome,
        "email": o.email,
        "status": o.status,
        "modelo_url": o.modelo_url,
        "modelo_path": o.modelo_path,
        "material": o.material,
        "escala": o.escala,
        "peso_gramas": o.peso_gramas,
        "volume_cm3": o.volume_cm3,
        "tempo_impressao_horas": o.tempo_impressao_horas,
        "preco_centavos": o.preco_centavos,
        "frete_centavos": o.frete_centavos,
        "cep_destino": o.cep_destino,
        "prazo_dias": o.prazo_dias,
        "codigo_rastreio": o.codigo_rastreio,
        "progresso_percentual": o.progresso_percentual,
        "camada_atual": o.camada_atual,
        "camada_total": o.camada_total,
        "erro_mensagem": o.erro_mensagem,
        "impressao_iniciada_em": o.impressao_iniciada_em.isoformat() if o.impressao_iniciada_em else None,
        "impressao_concluida_em": o.impressao_concluida_em.isoformat() if o.impressao_concluida_em else None,
        "arquivo_3mf_path": o.arquivo_3mf_path,
    }


@router.post("/claim")
async def claim_next_job(
    req: AgentRequest,
    db: AsyncSession = Depends(get_db),
):
    verify_agent(req.agent_password)

    # 1. Cleanup de PREPARANDO órfão
    threshold = datetime.utcnow() - timedelta(minutes=ORPHAN_PREPARING_MINUTES)
    orphans_stmt = select(Order).where(
        Order.status == "PREPARANDO",
        Order.impressao_iniciada_em < threshold,
    )
    orphans = (await db.execute(orphans_stmt)).scalars().all()
    for o in orphans:
        o.status = "ERRO_IMPRESSAO"
        o.erro_mensagem = "Preparação abandonada (timeout)"
        o.erro_em = datetime.utcnow()

    # 2. Claim próximo PAGO com SKIP LOCKED
    claim_stmt = (
        select(Order)
        .where(Order.status == "PAGO")
        .order_by(Order.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(claim_stmt)
    order = result.scalar_one_or_none()

    if order is None:
        await db.commit()  # flush do cleanup acima
        return {"success": True, "data": None, "error": None}

    order.status = "PREPARANDO"
    order.impressao_iniciada_em = datetime.utcnow()
    await db.commit()
    await db.refresh(order)

    return {"success": True, "data": _order_to_dict(order), "error": None}
```

- [ ] **Step 4: Rodar os testes de novo**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_printer_claim.py -v
```
Expected: 4 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/printer.py backend/tests/test_printer_claim.py
git commit -m "feat(backend): POST /api/printer/claim com orphan cleanup"
```

### Task 2.3: Endpoint `/printer/orders/{id}/status`

**Files:**
- Modify: `backend/routers/printer.py`
- Create: `backend/tests/test_printer_status.py`

- [ ] **Step 1: Escrever os testes**

Criar `backend/tests/test_printer_status.py`:
```python
import pytest

from models.tables import Order
from tests.test_printer_claim import _make_order


@pytest.mark.asyncio
async def test_status_preparando_to_imprimindo(client, db_session):
    o = _make_order(status="PREPARANDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/status",
        json={"agent_password": "test_agent", "status": "IMPRIMINDO"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "IMPRIMINDO"

    await db_session.refresh(o)
    assert o.status == "IMPRIMINDO"


@pytest.mark.asyncio
async def test_status_imprimindo_to_impresso_sets_concluded_at(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/status",
        json={"agent_password": "test_agent", "status": "IMPRESSO"},
    )
    assert resp.status_code == 200

    await db_session.refresh(o)
    assert o.status == "IMPRESSO"
    assert o.impressao_concluida_em is not None


@pytest.mark.asyncio
async def test_status_rejects_illegal_transition(client, db_session):
    o = _make_order(status="PAGO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/status",
        json={"agent_password": "test_agent", "status": "IMPRIMINDO"},
    )
    assert resp.status_code == 400
    assert "ilegal" in resp.json()["detail"].lower() or "illegal" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_returns_404_for_missing_order(client):
    resp = await client.post(
        "/api/printer/orders/nope/status",
        json={"agent_password": "test_agent", "status": "IMPRIMINDO"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Rodar testes e ver falhar**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_printer_status.py -v
```
Expected: 4 FAIL com 404 ou similar.

- [ ] **Step 3: Implementar o endpoint**

Adicionar em `backend/routers/printer.py`:
```python
from typing import Literal

from fastapi import HTTPException
from models.state_machine import TransitionError, assert_allowed


class StatusUpdateRequest(BaseModel):
    agent_password: str
    status: Literal["IMPRIMINDO", "IMPRESSO"]


@router.post("/orders/{order_id}/status")
async def update_status(
    order_id: str,
    req: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    verify_agent(req.agent_password)

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    try:
        assert_allowed(order.status, req.status)
    except TransitionError as e:
        raise HTTPException(status_code=400, detail=f"Transição ilegal: {e}")

    order.status = req.status
    if req.status == "IMPRESSO":
        order.impressao_concluida_em = datetime.utcnow()

    await db.commit()
    await db.refresh(order)
    return {"success": True, "data": _order_to_dict(order), "error": None}
```

- [ ] **Step 4: Rodar testes**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_printer_status.py -v
```
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/printer.py backend/tests/test_printer_status.py
git commit -m "feat(backend): POST /api/printer/orders/{id}/status com validação de transição"
```

### Task 2.4: Endpoint `/printer/orders/{id}/progress`

**Files:**
- Modify: `backend/routers/printer.py`
- Create: `backend/tests/test_printer_progress.py`

- [ ] **Step 1: Escrever os testes**

Criar `backend/tests/test_printer_progress.py`:
```python
import pytest

from tests.test_printer_claim import _make_order


@pytest.mark.asyncio
async def test_progress_updates_fields(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/progress",
        json={
            "agent_password": "test_agent",
            "percentual": 42,
            "camada_atual": 85,
            "camada_total": 200,
        },
    )
    assert resp.status_code == 200
    await db_session.refresh(o)
    assert o.progresso_percentual == 42
    assert o.camada_atual == 85
    assert o.camada_total == 200


@pytest.mark.asyncio
async def test_progress_accepts_multiple_updates(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    for pct, lyr in [(10, 20), (50, 100), (90, 180)]:
        resp = await client.post(
            f"/api/printer/orders/{o.id}/progress",
            json={
                "agent_password": "test_agent",
                "percentual": pct,
                "camada_atual": lyr,
                "camada_total": 200,
            },
        )
        assert resp.status_code == 200

    await db_session.refresh(o)
    assert o.progresso_percentual == 90
```

- [ ] **Step 2: Implementar o endpoint**

Adicionar em `backend/routers/printer.py`:
```python
class ProgressUpdateRequest(BaseModel):
    agent_password: str
    percentual: int
    camada_atual: int
    camada_total: int


@router.post("/orders/{order_id}/progress")
async def update_progress(
    order_id: str,
    req: ProgressUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    verify_agent(req.agent_password)

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    order.progresso_percentual = req.percentual
    order.camada_atual = req.camada_atual
    order.camada_total = req.camada_total

    await db.commit()
    return {"success": True, "data": {"updated": True}, "error": None}
```

- [ ] **Step 3: Rodar testes**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_printer_progress.py -v
```
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/printer.py backend/tests/test_printer_progress.py
git commit -m "feat(backend): POST /api/printer/orders/{id}/progress"
```

### Task 2.5: Endpoint `/printer/orders/{id}/erro`

**Files:**
- Modify: `backend/routers/printer.py`
- Create: `backend/tests/test_printer_erro.py`

- [ ] **Step 1: Escrever os testes**

Criar `backend/tests/test_printer_erro.py`:
```python
import pytest

from tests.test_printer_claim import _make_order


@pytest.mark.asyncio
async def test_erro_marks_order_and_saves_message(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/erro",
        json={"agent_password": "test_agent", "mensagem": "filament out"},
    )
    assert resp.status_code == 200
    await db_session.refresh(o)
    assert o.status == "ERRO_IMPRESSAO"
    assert o.erro_mensagem == "filament out"
    assert o.erro_em is not None


@pytest.mark.asyncio
async def test_erro_from_preparando_also_works(client, db_session):
    o = _make_order(status="PREPARANDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/printer/orders/{o.id}/erro",
        json={"agent_password": "test_agent", "mensagem": "slice failed"},
    )
    assert resp.status_code == 200
    await db_session.refresh(o)
    assert o.status == "ERRO_IMPRESSAO"
```

- [ ] **Step 2: Implementar o endpoint**

Adicionar em `backend/routers/printer.py`:
```python
class ErroRequest(BaseModel):
    agent_password: str
    mensagem: str


@router.post("/orders/{order_id}/erro")
async def report_error(
    order_id: str,
    req: ErroRequest,
    db: AsyncSession = Depends(get_db),
):
    verify_agent(req.agent_password)

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    order.status = "ERRO_IMPRESSAO"
    order.erro_mensagem = req.mensagem[:2000]  # trunca
    order.erro_em = datetime.utcnow()
    await db.commit()
    await db.refresh(order)

    return {"success": True, "data": _order_to_dict(order), "error": None}
```

- [ ] **Step 3: Rodar testes**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_printer_erro.py -v
```
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/printer.py backend/tests/test_printer_erro.py
git commit -m "feat(backend): POST /api/printer/orders/{id}/erro"
```

### Task 2.6: Endpoint `/admin/orders/{id}/requeue`

**Files:**
- Modify: `backend/routers/admin.py`
- Create: `backend/tests/test_admin_requeue.py`

- [ ] **Step 1: Escrever os testes**

Criar `backend/tests/test_admin_requeue.py`:
```python
from datetime import datetime

import pytest

from tests.test_printer_claim import _make_order


@pytest.mark.asyncio
async def test_requeue_erro_back_to_pago(client, db_session):
    o = _make_order(
        status="ERRO_IMPRESSAO",
        erro_mensagem="deu ruim",
        erro_em=datetime.utcnow(),
        progresso_percentual=50,
    )
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/admin/orders/{o.id}/requeue",
        json={"password": "test_admin"},
    )
    assert resp.status_code == 200
    await db_session.refresh(o)
    assert o.status == "PAGO"
    assert o.erro_mensagem is None
    assert o.erro_em is None
    assert o.progresso_percentual is None


@pytest.mark.asyncio
async def test_requeue_non_erro_is_rejected(client, db_session):
    o = _make_order(status="IMPRIMINDO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/admin/orders/{o.id}/requeue",
        json={"password": "test_admin"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_requeue_rejects_wrong_password(client, db_session):
    o = _make_order(status="ERRO_IMPRESSAO")
    db_session.add(o)
    await db_session.commit()

    resp = await client.post(
        f"/api/admin/orders/{o.id}/requeue",
        json={"password": "wrong"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
```

- [ ] **Step 2: Implementar endpoint**

Adicionar em `backend/routers/admin.py`:
```python
from fastapi import HTTPException


class RequeueRequest(BaseModel):
    password: str


@router.post("/admin/orders/{order_id}/requeue")
async def admin_requeue_order(
    order_id: str,
    request: RequeueRequest,
    db: AsyncSession = Depends(get_db),
):
    if not verify_admin(request.password):
        return {"success": False, "data": None, "error": "Não autorizado."}

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if order.status != "ERRO_IMPRESSAO":
        raise HTTPException(
            status_code=400,
            detail=f"Só é possível reenfileirar pedidos em ERRO_IMPRESSAO (status atual: {order.status})",
        )

    order.status = "PAGO"
    order.progresso_percentual = None
    order.camada_atual = None
    order.camada_total = None
    order.erro_mensagem = None
    order.erro_em = None
    order.impressao_iniciada_em = None
    order.impressao_concluida_em = None
    order.arquivo_3mf_path = None

    await db.commit()
    await db.refresh(order)
    return {
        "success": True,
        "data": {"id": order.id, "status": order.status},
        "error": None,
    }
```

- [ ] **Step 3: Rodar testes**

Run:
```bash
cd backend && .venv/Scripts/pytest tests/test_admin_requeue.py -v
```
Expected: 3 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/admin.py backend/tests/test_admin_requeue.py
git commit -m "feat(backend): POST /api/admin/orders/{id}/requeue"
```

---

## Phase 3 — SSE e LISTEN/NOTIFY

### Task 3.1: Migration do trigger NOTIFY

**Files:**
- Create: `backend/alembic/versions/002_sse_notify_trigger.py`

- [ ] **Step 1: Criar migration manual (não autogenerate, é SQL raw)**

Criar `backend/alembic/versions/002_sse_notify_trigger.py`:
```python
"""sse notify trigger

Revision ID: 002_sse_notify_trigger
Revises: 001_baseline
Create Date: 2026-04-10
"""
from alembic import op


revision = "002_sse_notify_trigger"
down_revision = "001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_order_update() RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify('order_' || NEW.id, row_to_json(NEW)::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER order_update_notify
            AFTER UPDATE ON orders
            FOR EACH ROW EXECUTE FUNCTION notify_order_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS order_update_notify ON orders;")
    op.execute("DROP FUNCTION IF EXISTS notify_order_update();")
```

- [ ] **Step 2: Aplicar a migration**

Run:
```bash
cd backend && .venv/Scripts/alembic upgrade head
```
Expected: aplica 002, cria função e trigger.

- [ ] **Step 3: Verificar no Postgres**

Run:
```bash
docker-compose exec db psql -U postgres -d forja3d -c "\df notify_order_update"
```
Expected: mostra a função.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/002_sse_notify_trigger.py
git commit -m "feat(backend): trigger pg_notify para SSE"
```

### Task 3.2: Endpoint SSE `/orders/{id}/stream`

**Files:**
- Modify: `backend/routers/orders.py`

- [ ] **Step 1: Adicionar o endpoint no router de orders**

Adicionar em `backend/routers/orders.py`:
```python
import asyncio
import json

import asyncpg
from fastapi.responses import StreamingResponse


@router.get("/orders/{order_id}/stream")
async def stream_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Server-Sent Events: snapshot + updates em tempo real."""
    # Primeiro busca o snapshot atual
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return {"success": False, "data": None, "error": "Pedido não encontrado."}

    # Serializa snapshot usando a mesma função do endpoint GET
    snapshot = {
        "id": order.id,
        "nome": order.nome,
        "status": order.status,
        "material": order.material,
        "escala": order.escala,
        "peso_gramas": order.peso_gramas,
        "preco_centavos": order.preco_centavos,
        "frete_centavos": order.frete_centavos,
        "total_centavos": order.preco_centavos + order.frete_centavos,
        "prazo_dias": order.prazo_dias,
        "codigo_rastreio": order.codigo_rastreio,
        "progresso_percentual": order.progresso_percentual,
        "camada_atual": order.camada_atual,
        "camada_total": order.camada_total,
        "erro_mensagem": None,  # não expor erro bruto pro cliente
        "impressao_iniciada_em": order.impressao_iniciada_em.isoformat() if order.impressao_iniciada_em else None,
        "impressao_concluida_em": order.impressao_concluida_em.isoformat() if order.impressao_concluida_em else None,
        "tempo_impressao_horas": order.tempo_impressao_horas,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }

    terminal_states = {"IMPRESSO", "ERRO_IMPRESSAO", "ENVIADO", "ENTREGUE"}
    is_admin = False  # TODO futuro: rota admin separada com erro cru

    async def event_generator():
        # Snapshot inicial
        yield f"event: snapshot\ndata: {json.dumps(snapshot)}\n\n"

        if snapshot["status"] in terminal_states:
            yield f'event: closed\ndata: {{"reason": "terminal_state"}}\n\n'
            return

        # Conecta direto ao Postgres (fora do SQLAlchemy) pra usar LISTEN
        raw_dsn = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(raw_dsn)
        queue: asyncio.Queue = asyncio.Queue()

        def _listener(_conn, _pid, _channel, payload):
            queue.put_nowait(payload)

        channel = f"order_{order_id}"
        await conn.add_listener(channel, _listener)

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                data = json.loads(payload)
                # Remove campos sensíveis
                data.pop("erro_mensagem", None)
                yield f"event: update\ndata: {json.dumps(data)}\n\n"

                if data.get("status") in terminal_states:
                    yield f'event: closed\ndata: {{"reason": "terminal_state"}}\n\n'
                    return
        finally:
            await conn.remove_listener(channel, _listener)
            await conn.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- [ ] **Step 2: Teste manual com curl**

Com o backend rodando (`uvicorn main:app --reload`) e um pedido existente, em outro terminal:
```bash
curl -N "http://localhost:8000/api/orders/<ID_DE_UM_PEDIDO>/stream"
```
Expected: recebe `event: snapshot` imediatamente, depois `: heartbeat` a cada 30s.

Em outro terminal, edite o pedido no DB pra disparar NOTIFY:
```bash
docker-compose exec db psql -U postgres -d forja3d -c "UPDATE orders SET progresso_percentual = 42 WHERE id = '<ID>';"
```
Expected: o curl do SSE recebe um `event: update` com os dados novos.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/orders.py
git commit -m "feat(backend): SSE /api/orders/{id}/stream via LISTEN/NOTIFY"
```

---

## Phase 4 — Email notifier (Resend)

### Task 4.1: Serviço notifier

**Files:**
- Create: `backend/services/notifier.py`
- Create: `backend/templates/emails/` (pasta)

- [ ] **Step 1: Criar `backend/services/notifier.py`**

```python
"""Envio de emails transacionais via Resend.

Best-effort: falhas não bloqueiam as transições de estado.
"""
import logging
import os
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "emails"


class Notifier:
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY", "")
        self.from_address = os.getenv("EMAIL_FROM", "FORJA3D <no-reply@forja3d.com.br>")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        self.enabled = bool(self.api_key)
        if self.enabled:
            resend.api_key = self.api_key

        self.jinja = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def _render(self, template_name: str, **ctx) -> str:
        tmpl = self.jinja.get_template(template_name)
        return tmpl.render(frontend_url=self.frontend_url, **ctx)

    async def _send(self, to: str, subject: str, html: str) -> None:
        if not self.enabled:
            logger.warning("Resend não configurado; email '%s' não enviado", subject)
            return
        try:
            resend.Emails.send({
                "from": self.from_address,
                "to": to,
                "subject": subject,
                "html": html,
            })
        except Exception as e:
            logger.warning("Falha ao enviar email '%s': %s", subject, e)

    async def send_payment_received(self, order) -> None:
        html = self._render("payment_received.html", order=order)
        await self._send(order.email, "Recebemos seu pagamento — FORJA3D", html)

    async def send_print_started(self, order) -> None:
        html = self._render("print_started.html", order=order)
        await self._send(order.email, "Sua peça entrou na impressora", html)

    async def send_print_finished(self, order) -> None:
        html = self._render("print_finished.html", order=order)
        await self._send(order.email, "Sua peça está pronta!", html)

    async def send_shipped(self, order) -> None:
        html = self._render("shipped.html", order=order)
        await self._send(order.email, "Seu pedido foi postado", html)

    async def send_print_error(self, order) -> None:
        html = self._render("print_error.html", order=order)
        await self._send(order.email, "Tivemos um contratempo com sua peça", html)


notifier = Notifier()
```

- [ ] **Step 2: Commit (templates vêm na próxima task)**

```bash
git add backend/services/notifier.py
git commit -m "feat(backend): notifier service (Resend) — best-effort"
```

### Task 4.2: Templates HTML de email

**Files:**
- Create: `backend/templates/emails/base.html`
- Create: `backend/templates/emails/payment_received.html`
- Create: `backend/templates/emails/print_started.html`
- Create: `backend/templates/emails/print_finished.html`
- Create: `backend/templates/emails/shipped.html`
- Create: `backend/templates/emails/print_error.html`

- [ ] **Step 1: Criar `base.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{% block title %}FORJA3D{% endblock %}</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'DM Sans',Arial,sans-serif;color:#ffffff;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;">
  <tr><td align="center" style="padding:40px 20px;">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#111;border:1px solid rgba(255,255,255,0.08);border-radius:16px;">
      <tr><td style="padding:32px;">
        <div style="font-size:22px;font-weight:700;color:#4ECDC4;margin-bottom:24px;">FORJA3D</div>
        {% block content %}{% endblock %}
        <div style="margin-top:32px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08);font-size:12px;color:#888;">
          Este é um email automático, por favor não responda.
        </div>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>
```

- [ ] **Step 2: Criar `payment_received.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 style="font-size:24px;margin:0 0 16px;">Recebemos seu pagamento!</h1>
<p>Oi {{ order.nome }}, confirmamos o pagamento do seu pedido na FORJA3D.</p>
<p>Assim que a impressão começar, você vai receber outro email.</p>
<p style="margin-top:24px;">
  <a href="{{ frontend_url }}/pedido/{{ order.id }}" style="display:inline-block;padding:12px 24px;background:linear-gradient(90deg,#4ECDC4,#44B09E);color:#000;font-weight:700;border-radius:12px;text-decoration:none;">
    Acompanhar pedido
  </a>
</p>
{% endblock %}
```

- [ ] **Step 3: Criar `print_started.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 style="font-size:24px;margin:0 0 16px;">Sua peça entrou na impressora</h1>
<p>Oi {{ order.nome }}, a impressão da sua peça começou agora.</p>
<p>Você pode acompanhar o progresso em tempo real na página do pedido.</p>
<p>Tempo estimado: <strong>{{ "%.1f"|format(order.tempo_impressao_horas) }}h</strong></p>
<p style="margin-top:24px;">
  <a href="{{ frontend_url }}/pedido/{{ order.id }}" style="display:inline-block;padding:12px 24px;background:linear-gradient(90deg,#4ECDC4,#44B09E);color:#000;font-weight:700;border-radius:12px;text-decoration:none;">
    Ver progresso
  </a>
</p>
{% endblock %}
```

- [ ] **Step 4: Criar `print_finished.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 style="font-size:24px;margin:0 0 16px;">Sua peça está pronta!</h1>
<p>Oi {{ order.nome }}, terminamos de imprimir sua peça.</p>
<p>Agora vamos embalar e enviar pelos Correios. Você receberá o código de rastreio assim que postarmos.</p>
<p style="margin-top:24px;">
  <a href="{{ frontend_url }}/pedido/{{ order.id }}" style="display:inline-block;padding:12px 24px;background:linear-gradient(90deg,#4ECDC4,#44B09E);color:#000;font-weight:700;border-radius:12px;text-decoration:none;">
    Ver pedido
  </a>
</p>
{% endblock %}
```

- [ ] **Step 5: Criar `shipped.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 style="font-size:24px;margin:0 0 16px;">Seu pedido foi postado</h1>
<p>Oi {{ order.nome }}, acabamos de postar sua peça nos Correios.</p>
<p>Código de rastreio: <strong style="font-family:'Space Mono',monospace;color:#4ECDC4;">{{ order.codigo_rastreio }}</strong></p>
<p>Prazo estimado: <strong>{{ order.prazo_dias }} dias úteis</strong></p>
<p style="margin-top:24px;">
  <a href="https://rastreamento.correios.com.br/app/index.php?objeto={{ order.codigo_rastreio }}" style="display:inline-block;padding:12px 24px;background:linear-gradient(90deg,#4ECDC4,#44B09E);color:#000;font-weight:700;border-radius:12px;text-decoration:none;">
    Rastrear nos Correios
  </a>
</p>
{% endblock %}
```

- [ ] **Step 6: Criar `print_error.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 style="font-size:24px;margin:0 0 16px;">Tivemos um contratempo</h1>
<p>Oi {{ order.nome }},</p>
<p>Tivemos um problema com a impressão da sua peça. Nossa equipe já foi notificada e vamos reimprimir sua peça sem nenhum custo adicional.</p>
<p>Em breve você receberá outro email quando a reimpressão começar.</p>
<p style="margin-top:24px;">
  <a href="{{ frontend_url }}/pedido/{{ order.id }}" style="display:inline-block;padding:12px 24px;background:linear-gradient(90deg,#4ECDC4,#44B09E);color:#000;font-weight:700;border-radius:12px;text-decoration:none;">
    Ver pedido
  </a>
</p>
{% endblock %}
```

- [ ] **Step 7: Commit**

```bash
git add backend/templates/
git commit -m "feat(backend): templates HTML de email"
```

### Task 4.3: Integrar notifier nas transições

**Files:**
- Modify: `backend/routers/payment.py`
- Modify: `backend/routers/printer.py`
- Modify: `backend/routers/admin.py`

- [ ] **Step 1: Payment webhook — `send_payment_received`**

Em `backend/routers/payment.py`, dentro do `if payment_info["status"] == "approved"`, depois de `await db.commit()`:
```python
from services.notifier import notifier
# ...
                    await db.commit()
                    await db.refresh(order)
                    await notifier.send_payment_received(order)
```

- [ ] **Step 2: Printer /status — `send_print_started` e `send_print_finished`**

Em `backend/routers/printer.py`, no endpoint `update_status`, depois do refresh:
```python
from services.notifier import notifier
# ...
    await db.commit()
    await db.refresh(order)

    if req.status == "IMPRIMINDO":
        await notifier.send_print_started(order)
    elif req.status == "IMPRESSO":
        await notifier.send_print_finished(order)

    return {"success": True, "data": _order_to_dict(order), "error": None}
```

- [ ] **Step 3: Printer /erro — `send_print_error`**

Em `backend/routers/printer.py`, no endpoint `report_error`, depois do refresh:
```python
    await db.commit()
    await db.refresh(order)
    await notifier.send_print_error(order)
    return {"success": True, "data": _order_to_dict(order), "error": None}
```

- [ ] **Step 4: Admin update — `send_shipped` quando transição pra ENVIADO**

Em `backend/routers/admin.py`, adicionar o import no topo:
```python
from services.notifier import notifier
```

Substituir o corpo do endpoint `admin_update_order` (que hoje é):
```python
    if request.status:
        order.status = request.status
    if request.codigo_rastreio is not None:
        order.codigo_rastreio = request.codigo_rastreio

    await db.commit()

    return {
        "success": True,
        "data": {"id": order.id, "status": order.status, "codigo_rastreio": order.codigo_rastreio},
        "error": None,
    }
```

Por:
```python
    old_status = order.status
    if request.status:
        order.status = request.status
    if request.codigo_rastreio is not None:
        order.codigo_rastreio = request.codigo_rastreio

    await db.commit()
    await db.refresh(order)

    if old_status != "ENVIADO" and order.status == "ENVIADO" and order.codigo_rastreio:
        await notifier.send_shipped(order)

    return {
        "success": True,
        "data": {"id": order.id, "status": order.status, "codigo_rastreio": order.codigo_rastreio},
        "error": None,
    }
```

- [ ] **Step 5: Rodar os testes existentes e ver que nenhum quebrou**

Run:
```bash
cd backend && .venv/Scripts/pytest -v
```
Expected: todos PASS. (Notifier não enviará emails reais porque `RESEND_API_KEY` não está no .env de teste — fica em `enabled=False` e só loga warning.)

- [ ] **Step 6: Commit**

```bash
git add backend/routers/
git commit -m "feat(backend): integra notifier nas transições de estado"
```

### Task 4.4: Adicionar env vars documentadas

**Files:**
- Modify: `backend/.env.example`

- [ ] **Step 1: Adicionar chaves novas ao `.env.example`**

Adicionar no fim do `backend/.env.example`:
```
# Agent lifecycle
AGENT_PASSWORD=
ORPHAN_PREPARING_MINUTES=45

# Email (Resend)
RESEND_API_KEY=
EMAIL_FROM="FORJA3D <pedidos@forja3d.com.br>"
```

- [ ] **Step 2: Commit**

```bash
git add backend/.env.example
git commit -m "docs(backend): .env.example com as novas variáveis"
```

---

## Phase 5 — Refatoração do printer-agent

### Task 5.1: Dependências do agent + requirements

**Files:**
- Modify: `printer-agent/requirements.txt`

- [ ] **Step 1: Adicionar dependências**

Substituir o conteúdo de `printer-agent/requirements.txt` por:
```
httpx>=0.28.0
bambulabs-api>=2.6.0
python-dotenv>=1.0.1
pytest>=8.3.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 2: Commit**

```bash
git add printer-agent/requirements.txt
git commit -m "chore(agent): adiciona bambulabs-api, pytest"
```

### Task 5.2: `config.py` — carregamento e validação

**Files:**
- Create: `printer-agent/config.py`
- Create: `printer-agent/config.example.json`
- Modify: `printer-agent/.gitignore` (ou raiz `.gitignore`)

- [ ] **Step 1: Verificar `.gitignore` do projeto**

Verificar que a raiz `.gitignore` já cobre `config.json`:
```bash
grep -n "config.json" .gitignore
```
Se não cobrir, adicionar uma linha:
```
printer-agent/config.json
```
(Vou assumir aqui que não cobre e que vou adicionar.)

- [ ] **Step 2: Criar `printer-agent/config.example.json`**

```json
{
  "printer": {
    "ip": "192.168.1.100",
    "serial": "SERIAL_DA_IMPRESSORA",
    "access_code": "ACCESS_CODE_AQUI"
  },
  "backend_url": "http://localhost:8000",
  "agent_password": "DEFINIR_IGUAL_AO_BACKEND_ENV",
  "poll_interval_seconds": 30,
  "bambu_studio_cli": "C:\\Program Files\\Bambu Studio\\bambu-studio.exe"
}
```

- [ ] **Step 3: Criar `printer-agent/config.py`**

```python
"""Carrega e valida config.json do printer-agent."""
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PrinterConfig:
    ip: str
    serial: str
    access_code: str


@dataclass
class AgentConfig:
    printer: PrinterConfig
    backend_url: str
    agent_password: str
    poll_interval: int
    bambu_studio_cli: str
    download_dir: Path


def load_config(path: str | None = None) -> AgentConfig:
    path = path or os.path.join(os.path.dirname(__file__), "config.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    required_top = ["printer", "backend_url", "agent_password", "bambu_studio_cli"]
    for k in required_top:
        if not raw.get(k):
            raise ValueError(f"config.json: campo obrigatório ausente: {k}")

    required_printer = ["ip", "serial", "access_code"]
    for k in required_printer:
        if not raw["printer"].get(k):
            raise ValueError(f"config.json: printer.{k} obrigatório")

    cli = raw["bambu_studio_cli"]
    if not os.path.isfile(cli):
        raise FileNotFoundError(
            f"BambuStudio CLI não encontrado em: {cli}. "
            f"Configure o caminho correto em config.json ou instale o Bambu Studio."
        )

    download_dir = Path(os.path.dirname(__file__)) / "downloads"
    download_dir.mkdir(exist_ok=True)

    return AgentConfig(
        printer=PrinterConfig(**raw["printer"]),
        backend_url=raw["backend_url"].rstrip("/"),
        agent_password=raw["agent_password"],
        poll_interval=int(raw.get("poll_interval_seconds", 30)),
        bambu_studio_cli=cli,
        download_dir=download_dir,
    )
```

- [ ] **Step 4: Commit**

```bash
git add printer-agent/config.py printer-agent/config.example.json .gitignore
git commit -m "feat(agent): módulo config com validação + config.example.json"
```

### Task 5.3: `backend_client.py`

**Files:**
- Create: `printer-agent/backend_client.py`

- [ ] **Step 1: Criar `printer-agent/backend_client.py`**

```python
"""Cliente HTTP assíncrono para o backend FORJA3D."""
import logging
from dataclasses import dataclass
from typing import Literal

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Order:
    id: str
    nome: str
    email: str
    status: str
    modelo_url: str
    material: str
    escala: float
    peso_gramas: float
    tempo_impressao_horas: float

    @classmethod
    def from_dict(cls, d: dict) -> "Order":
        return cls(
            id=d["id"],
            nome=d["nome"],
            email=d.get("email", ""),
            status=d["status"],
            modelo_url=d["modelo_url"],
            material=d["material"],
            escala=d.get("escala", 1.0),
            peso_gramas=d.get("peso_gramas", 0.0),
            tempo_impressao_horas=d.get("tempo_impressao_horas", 0.0),
        )


class BackendClient:
    def __init__(self, backend_url: str, agent_password: str):
        self.base = backend_url
        self.password = agent_password
        self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def claim_next_job(self) -> Order | None:
        try:
            r = await self._client.post(
                f"{self.base}/api/printer/claim",
                json={"agent_password": self.password},
            )
            r.raise_for_status()
            body = r.json()
            if not body.get("success") or body.get("data") is None:
                return None
            return Order.from_dict(body["data"])
        except Exception as e:
            logger.warning("claim_next_job falhou: %s", e)
            return None

    async def update_status(self, order_id: str, status: Literal["IMPRIMINDO", "IMPRESSO"]) -> None:
        r = await self._client.post(
            f"{self.base}/api/printer/orders/{order_id}/status",
            json={"agent_password": self.password, "status": status},
        )
        r.raise_for_status()

    async def update_progress(self, order_id: str, percentual: int, camada_atual: int, camada_total: int) -> None:
        try:
            r = await self._client.post(
                f"{self.base}/api/printer/orders/{order_id}/progress",
                json={
                    "agent_password": self.password,
                    "percentual": percentual,
                    "camada_atual": camada_atual,
                    "camada_total": camada_total,
                },
            )
            r.raise_for_status()
        except Exception as e:
            logger.warning("update_progress falhou: %s", e)

    async def report_error(self, order_id: str, mensagem: str) -> None:
        try:
            r = await self._client.post(
                f"{self.base}/api/printer/orders/{order_id}/erro",
                json={"agent_password": self.password, "mensagem": mensagem},
            )
            r.raise_for_status()
        except Exception as e:
            logger.error("report_error falhou: %s (mensagem original: %s)", e, mensagem)

    async def download_model(self, modelo_url: str, dest_path: str) -> None:
        url = modelo_url if modelo_url.startswith("http") else f"{self.base}{modelo_url}"
        async with self._client.stream("GET", url) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in r.aiter_bytes():
                    f.write(chunk)
```

- [ ] **Step 2: Commit**

```bash
git add printer-agent/backend_client.py
git commit -m "feat(agent): backend_client com httpx assíncrono"
```

### Task 5.4: `slicer.py` — wrapper do BambuStudio CLI

**Files:**
- Create: `printer-agent/slicer.py`

- [ ] **Step 1: Criar `printer-agent/slicer.py`**

```python
"""Wrapper do BambuStudio CLI para fatiar GLB → 3MF."""
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SlicerError(Exception):
    pass


@dataclass
class SliceResult:
    output_path: str
    estimated_weight_g: float | None = None
    estimated_time_min: int | None = None


class Slicer:
    def __init__(self, cli_path: str):
        self.cli = cli_path

    def slice(self, glb_path: str, material: str, output_3mf: str) -> SliceResult:
        """Fatia um GLB em 3MF usando BambuStudio CLI.

        Material esperado: "PLA", "PETG" ou "TPU".
        """
        cmd = [
            self.cli,
            "--export-3mf", output_3mf,
            "--load-filament", material,
            glb_path,
        ]
        logger.info("Slicing: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 min
            )
        except subprocess.CalledProcessError as e:
            raise SlicerError(f"BambuStudio CLI falhou (exit {e.returncode}): {e.stderr[:500]}")
        except subprocess.TimeoutExpired:
            raise SlicerError("BambuStudio CLI passou de 30 min (timeout)")
        except FileNotFoundError:
            raise SlicerError(f"BambuStudio CLI não encontrado: {self.cli}")

        # Parse best-effort de peso/tempo do stdout (formato varia)
        weight = None
        time_min = None
        for line in proc.stdout.splitlines():
            lower = line.lower()
            if "filament used" in lower and "g" in lower:
                try:
                    weight = float(line.split()[-1].rstrip("gG"))
                except (ValueError, IndexError):
                    pass
            if "total time" in lower or "print time" in lower:
                try:
                    time_min = int(line.split()[-1])
                except (ValueError, IndexError):
                    pass

        return SliceResult(
            output_path=output_3mf,
            estimated_weight_g=weight,
            estimated_time_min=time_min,
        )
```

- [ ] **Step 2: Commit**

```bash
git add printer-agent/slicer.py
git commit -m "feat(agent): slicer wrapper do BambuStudio CLI"
```

### Task 5.5: `printer_client.py` — MQTT + FTP via bambulabs-api

**Files:**
- Create: `printer-agent/printer_client.py`

- [ ] **Step 1: Criar `printer-agent/printer_client.py`**

Nota: a biblioteca `bambulabs-api` tem sua própria API. Esta implementação assume a interface principal (classe `Printer` com métodos `connect`, `disconnect`, `mqtt_client`, métodos de upload/start, e callbacks para eventos). **Verificar a documentação da biblioteca e ajustar nomes de métodos se necessário** durante a implementação. O contrato externo (métodos públicos abaixo) deve ser mantido — só a implementação interna pode precisar de tweaks.

```python
"""Cliente da Bambu X1 Carbon via bambulabs-api (MQTT + FTP)."""
import asyncio
import ftplib
import logging
import os
from dataclasses import dataclass
from typing import Callable

import bambulabs_api as bl

logger = logging.getLogger(__name__)


@dataclass
class ProgressEvent:
    percentual: int
    camada_atual: int
    camada_total: int


@dataclass
class CurrentJob:
    gcode_file: str
    state: str  # "idle" | "printing" | "paused" | "error"


class PrinterClient:
    def __init__(self, ip: str, serial: str, access_code: str):
        self.ip = ip
        self.serial = serial
        self.access_code = access_code
        self._printer: bl.Printer | None = None
        self._progress_cb: Callable[[ProgressEvent], None] | None = None
        self._finished_cb: Callable[[], None] | None = None
        self._error_cb: Callable[[str], None] | None = None

    async def connect(self) -> None:
        """Conecta MQTT à impressora."""
        loop = asyncio.get_event_loop()
        self._printer = bl.Printer(self.ip, self.access_code, self.serial)
        # bambulabs-api costuma ser síncrono; roda em thread
        await loop.run_in_executor(None, self._printer.connect)
        logger.info("Conectado à X1 %s", self.ip)
        self._wire_callbacks()

    def _wire_callbacks(self) -> None:
        """Liga callbacks de eventos MQTT aos callbacks registrados."""
        p = self._printer
        if p is None:
            return

        # A API do bambulabs-api expõe um método mqtt_client com subscribes.
        # Aqui fazemos polling leve a cada 2s dos getters in-memory dele,
        # que internamente são populados pelos eventos MQTT.
        async def _poll_loop():
            last_pct = -1
            last_state = None
            while self._printer is not None:
                try:
                    pct = int(p.get_percentage() or 0)
                    layer = int(p.current_layer_num() or 0)
                    total = int(p.total_layer_num() or 0)
                    state = str(p.get_state() or "idle").lower()

                    if pct != last_pct and self._progress_cb:
                        self._progress_cb(ProgressEvent(pct, layer, total))
                        last_pct = pct

                    if last_state != "finish" and state == "finish" and self._finished_cb:
                        self._finished_cb()
                    if last_state != "failed" and state == "failed" and self._error_cb:
                        self._error_cb(p.get_print_error() or "Impressão falhou")
                    last_state = state
                except Exception as e:
                    logger.debug("Erro polling MQTT state: %s", e)
                await asyncio.sleep(2)

        asyncio.create_task(_poll_loop())

    async def disconnect(self) -> None:
        if self._printer is not None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._printer.disconnect)
            self._printer = None

    async def upload_file(self, local_path: str) -> str:
        """Upload via FTP (passive, porta 990 TLS)."""
        filename = os.path.basename(local_path)
        loop = asyncio.get_event_loop()

        def _ftp():
            ftp = ftplib.FTP_TLS()
            ftp.connect(self.ip, 990, timeout=60)
            ftp.login("bblp", self.access_code)
            ftp.prot_p()
            ftp.set_pasv(True)
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR /sdcard/{filename}", f)
            ftp.quit()

        await loop.run_in_executor(None, _ftp)
        logger.info("Uploaded %s", filename)
        return filename

    async def start_print(self, remote_filename: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._printer.start_print,
            f"/sdcard/{remote_filename}",
        )
        logger.info("Comando de start_print enviado pra %s", remote_filename)

    async def get_current_job(self) -> CurrentJob | None:
        if self._printer is None:
            return None
        try:
            loop = asyncio.get_event_loop()
            state = await loop.run_in_executor(None, self._printer.get_state) or "idle"
            gcode_file = await loop.run_in_executor(None, self._printer.get_file_name) or ""
            return CurrentJob(gcode_file=gcode_file, state=str(state).lower())
        except Exception as e:
            logger.warning("get_current_job falhou: %s", e)
            return None

    def on_progress(self, cb: Callable[[ProgressEvent], None]) -> None:
        self._progress_cb = cb

    def on_finished(self, cb: Callable[[], None]) -> None:
        self._finished_cb = cb

    def on_error(self, cb: Callable[[str], None]) -> None:
        self._error_cb = cb
```

- [ ] **Step 2: Commit**

```bash
git add printer-agent/printer_client.py
git commit -m "feat(agent): printer_client com MQTT via bambulabs-api + FTP upload"
```

### Task 5.6: `job_runner.py` — orquestração

**Files:**
- Create: `printer-agent/job_runner.py`

- [ ] **Step 1: Criar `printer-agent/job_runner.py`**

```python
"""Orquestra um pedido do download ao IMPRESSO / ERRO_IMPRESSAO."""
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from backend_client import BackendClient, Order
from printer_client import PrinterClient, ProgressEvent
from slicer import Slicer, SlicerError

logger = logging.getLogger(__name__)

PROGRESS_THROTTLE_SECONDS = 30


@dataclass
class JobResult:
    order_id: str
    status: Literal["IMPRESSO", "ERRO_IMPRESSAO"]
    error_message: str | None = None


class JobRunner:
    def __init__(
        self,
        backend: BackendClient,
        printer: PrinterClient,
        slicer: Slicer,
        download_dir: Path,
    ):
        self.backend = backend
        self.printer = printer
        self.slicer = slicer
        self.download_dir = download_dir
        self._last_progress: ProgressEvent | None = None
        self._last_flush_at: float = 0.0
        self._done = asyncio.Event()
        self._error_msg: str | None = None

    async def run(self, order: Order) -> JobResult:
        logger.info("Processando pedido %s", order.id)

        glb_path = self.download_dir / f"{order.id}.glb"
        mf_path = self.download_dir / f"{order.id}.3mf"

        # 1. Download
        try:
            await self.backend.download_model(order.modelo_url, str(glb_path))
        except Exception as e:
            return await self._fail(order.id, f"Falha ao baixar modelo: {e}")

        # 2. Slice
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self.slicer.slice, str(glb_path), order.material, str(mf_path)
            )
        except SlicerError as e:
            return await self._fail(order.id, f"Falha no fatiamento: {e}")
        except Exception as e:
            return await self._fail(order.id, f"Erro inesperado no slicer: {e}")

        # 3. Upload
        try:
            remote = await self.printer.upload_file(str(mf_path))
        except Exception as e:
            return await self._fail(order.id, f"Falha no upload FTP: {e}")

        # 4. Register callbacks
        self._order_id = order.id
        self.printer.on_progress(self._on_progress)
        self.printer.on_finished(self._on_finished)
        self.printer.on_error(self._on_printer_error)

        # 5. Start print
        try:
            await self.printer.start_print(remote)
        except Exception as e:
            return await self._fail(order.id, f"Falha ao iniciar impressão: {e}")

        # 6. Status → IMPRIMINDO
        try:
            await self.backend.update_status(order.id, "IMPRIMINDO")
        except Exception as e:
            return await self._fail(order.id, f"Falha ao atualizar status: {e}")

        # 7. Wait for completion or error
        await self._done.wait()

        if self._error_msg:
            return await self._fail(order.id, self._error_msg)

        # Final progress flush (100%)
        if self._last_progress is not None:
            try:
                await self.backend.update_progress(
                    order.id,
                    100,
                    self._last_progress.camada_total or self._last_progress.camada_atual,
                    self._last_progress.camada_total,
                )
            except Exception as e:
                logger.warning("Flush final de progresso falhou: %s", e)

        # 8. Status → IMPRESSO
        try:
            await self.backend.update_status(order.id, "IMPRESSO")
        except Exception as e:
            return await self._fail(order.id, f"Falha ao marcar IMPRESSO: {e}")

        return JobResult(order_id=order.id, status="IMPRESSO")

    def _on_progress(self, ev: ProgressEvent) -> None:
        self._last_progress = ev
        now = time.monotonic()
        if now - self._last_flush_at >= PROGRESS_THROTTLE_SECONDS:
            self._last_flush_at = now
            asyncio.create_task(self._flush_progress())

    async def _flush_progress(self) -> None:
        if self._last_progress is None:
            return
        p = self._last_progress
        await self.backend.update_progress(
            self._order_id, p.percentual, p.camada_atual, p.camada_total
        )

    def _on_finished(self) -> None:
        self._done.set()

    def _on_printer_error(self, msg: str) -> None:
        self._error_msg = msg
        self._done.set()

    async def _fail(self, order_id: str, msg: str) -> JobResult:
        logger.error("Job %s falhou: %s", order_id, msg)
        await self.backend.report_error(order_id, msg)
        return JobResult(order_id=order_id, status="ERRO_IMPRESSAO", error_message=msg)
```

- [ ] **Step 2: Commit**

```bash
git add printer-agent/job_runner.py
git commit -m "feat(agent): job_runner com máquina de estados por pedido"
```

### Task 5.7: Reescrever `agent.py` (entrypoint) + logging_setup

**Files:**
- Create: `printer-agent/logging_setup.py`
- Modify: `printer-agent/agent.py`

- [ ] **Step 1: Criar `printer-agent/logging_setup.py`**

```python
import logging
import os
import sys


def setup_logging() -> None:
    level = logging.DEBUG if os.getenv("AGENT_DEBUG") == "1" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
```

- [ ] **Step 2: Reescrever `printer-agent/agent.py`**

Substituir o arquivo inteiro por:
```python
"""FORJA3D Printer Agent — entrypoint.

Loop: claim → download → slice → upload → start → monitor → (IMPRESSO | ERRO).
"""
import asyncio
import logging

from backend_client import BackendClient
from config import load_config
from job_runner import JobRunner
from logging_setup import setup_logging
from printer_client import PrinterClient
from slicer import Slicer

logger = logging.getLogger(__name__)


async def reconcile_on_startup(backend: BackendClient, printer: PrinterClient) -> None:
    """Se a X1 está imprimindo, tenta casar com um pedido do backend.
    Se não casar, loga warning e deixa o humano resolver.
    """
    job = await printer.get_current_job()
    if job is None or job.state != "printing":
        logger.info("X1 ociosa ou state desconhecido, seguindo loop normal.")
        return

    # Extrai order_id do nome do arquivo
    basename = job.gcode_file.split("/")[-1]
    order_id = basename.replace(".3mf", "").replace(".gcode.3mf", "")
    logger.info("X1 imprimindo arquivo %s → order_id=%s", basename, order_id)
    # Nota: por simplicidade, o agent só loga e segue. O pedido provavelmente
    # já está em IMPRIMINDO ou PREPARANDO no backend e vai receber update final
    # quando a impressão acabar naturalmente.
    logger.warning(
        "Reconciliação não-retomável nesta versão: X1 continuará imprimindo %s, "
        "mas o agent não vai reportar progresso. Aguarde conclusão e verifique "
        "manualmente se o status no admin bate.",
        order_id,
    )


async def main() -> None:
    setup_logging()
    config = load_config()
    logger.info("=" * 50)
    logger.info("FORJA3D Printer Agent")
    logger.info("Backend: %s", config.backend_url)
    logger.info("Impressora: %s", config.printer.ip)
    logger.info("Intervalo de poll: %ss", config.poll_interval)
    logger.info("=" * 50)

    backend = BackendClient(config.backend_url, config.agent_password)
    printer = PrinterClient(
        config.printer.ip, config.printer.serial, config.printer.access_code
    )
    slicer = Slicer(config.bambu_studio_cli)

    try:
        await printer.connect()
        await reconcile_on_startup(backend, printer)

        while True:
            try:
                order = await backend.claim_next_job()
                if order is None:
                    await asyncio.sleep(config.poll_interval)
                    continue

                runner = JobRunner(backend, printer, slicer, config.download_dir)
                result = await runner.run(order)
                logger.info("Job %s terminou: %s", result.order_id, result.status)
            except KeyboardInterrupt:
                logger.info("Agent encerrado pelo usuário.")
                break
            except Exception:
                logger.exception("Erro no loop principal")
                await asyncio.sleep(config.poll_interval)
    finally:
        await printer.disconnect()
        await backend.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Commit**

```bash
git add printer-agent/agent.py printer-agent/logging_setup.py
git commit -m "refactor(agent): reescreve agent.py com módulos + reconciliação"
```

### Task 5.8: Atualizar `config.json` local e testar import

**Files:**
- Modify: `printer-agent/config.json` (manualmente)

- [ ] **Step 1: Garantir que `config.json` do dev tem `agent_password` e `bambu_studio_cli`**

Editar `printer-agent/config.json` (local, não commitado) adicionando as chaves novas:
```json
{
  "printer": {
    "ip": "192.168.1.100",
    "serial": "SERIAL_DA_IMPRESSORA",
    "access_code": "ACCESS_CODE_AQUI"
  },
  "backend_url": "http://localhost:8000",
  "agent_password": "<MESMO VALOR DO BACKEND .env>",
  "poll_interval_seconds": 30,
  "bambu_studio_cli": "C:\\Program Files\\Bambu Studio\\bambu-studio.exe"
}
```

- [ ] **Step 2: Testar imports do agent**

Run (com os módulos instalados):
```bash
cd printer-agent && python -c "from agent import main; print('imports ok')"
```
Expected: `imports ok` (ou erro se `bambulabs_api` não estiver instalado — nesse caso instalar com `pip install bambulabs-api`).

Se `bambulabs-api` não existir com esse nome de pacote, pesquise o nome correto no PyPI e ajuste o import em `printer_client.py`.

- [ ] **Step 3: Sem commit (config.json não entra no git)**

---

## Phase 6 — Frontend

### Task 6.1: Atualizar tipos e API em `lib/api.ts`

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Adicionar a interface `Order` e funções de conveniência**

Adicionar ao fim de `frontend/src/lib/api.ts`:
```ts
export type OrderStatus =
  | "AGUARDANDO_PAGAMENTO"
  | "PAGO"
  | "PREPARANDO"
  | "IMPRIMINDO"
  | "IMPRESSO"
  | "ERRO_IMPRESSAO"
  | "EMBALANDO"
  | "ENVIADO"
  | "ENTREGUE";

export interface Order {
  id: string;
  nome: string;
  email?: string;
  status: OrderStatus;
  material: "PLA" | "PETG" | "TPU";
  escala: number;
  peso_gramas: number;
  preco_centavos: number;
  frete_centavos: number;
  total_centavos: number;
  prazo_dias: number;
  codigo_rastreio: string | null;
  progresso_percentual: number | null;
  camada_atual: number | null;
  camada_total: number | null;
  erro_mensagem: string | null;
  impressao_iniciada_em: string | null;
  impressao_concluida_em: string | null;
  tempo_impressao_horas: number;
  created_at: string;
}

export async function getOrder(id: string): Promise<ApiResponse<Order>> {
  return apiGet<Order>(`/api/orders/${id}`);
}

export async function adminRequeueOrder(
  id: string,
  password: string
): Promise<ApiResponse<{ id: string; status: OrderStatus }>> {
  return apiPost(`/api/admin/orders/${id}/requeue`, { password });
}

export async function adminUpdateOrder(
  id: string,
  password: string,
  updates: { status?: OrderStatus; codigo_rastreio?: string }
): Promise<ApiResponse<unknown>> {
  return apiPost(`/api/admin/orders/${id}`, { password, ...updates });
}

export function orderStreamUrl(id: string): string {
  return `${API_URL}/api/orders/${id}/stream`;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(frontend): tipos Order e funções de API para lifecycle"
```

### Task 6.2: Hook `useOrderStream`

**Files:**
- Create: `frontend/src/lib/hooks/useOrderStream.ts`

- [ ] **Step 1: Criar o hook**

```ts
"use client";

import { useEffect, useRef, useState } from "react";

import { Order, getOrder, orderStreamUrl } from "../api";

const POLL_FALLBACK_MS = 5000;

export function useOrderStream(id: string | null) {
  const [order, setOrder] = useState<Order | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (!id) return;

    const startPolling = () => {
      const poll = async () => {
        const res = await getOrder(id);
        if (res.success && res.data) {
          setOrder((prev) => ({ ...prev, ...res.data }) as Order);
        }
      };
      poll();
      pollRef.current = window.setInterval(poll, POLL_FALLBACK_MS);
    };

    // Try SSE
    try {
      const es = new EventSource(orderStreamUrl(id));
      esRef.current = es;

      es.addEventListener("snapshot", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setOrder(data);
        setConnected(true);
      });

      es.addEventListener("update", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setOrder((prev) => (prev ? { ...prev, ...data } : data));
      });

      es.addEventListener("closed", () => {
        es.close();
        esRef.current = null;
      });

      es.onerror = () => {
        setConnected(false);
        if (esRef.current) {
          esRef.current.close();
          esRef.current = null;
        }
        startPolling();
      };
    } catch (err) {
      setError(err as Error);
      startPolling();
    }

    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [id]);

  return { order, connected, error };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/hooks/useOrderStream.ts
git commit -m "feat(frontend): useOrderStream hook com SSE + polling fallback"
```

### Task 6.3: Refatorar `OrderTracker.tsx`

**Files:**
- Modify: `frontend/src/components/OrderTracker.tsx`

- [ ] **Step 1: Reescrever o componente**

Substituir `frontend/src/components/OrderTracker.tsx` por:
```tsx
"use client";

import { Order, OrderStatus } from "../lib/api";

interface OrderTrackerProps {
  order: Order;
}

const LABELS: Record<OrderStatus, string> = {
  AGUARDANDO_PAGAMENTO: "Aguardando pagamento",
  PAGO: "Pago",
  PREPARANDO: "Preparando impressão",
  IMPRIMINDO: "Imprimindo",
  IMPRESSO: "Impresso — preparando envio",
  ERRO_IMPRESSAO: "Tivemos um problema",
  EMBALANDO: "Embalando",
  ENVIADO: "Enviado",
  ENTREGUE: "Entregue",
};

function formatETA(totalHours: number, percent: number): string {
  const remainingH = totalHours * (1 - percent / 100);
  if (remainingH <= 0) return "finalizando";
  if (remainingH < 1) return `~${Math.round(remainingH * 60)} min`;
  const h = Math.floor(remainingH);
  const m = Math.round((remainingH - h) * 60);
  return m > 0 ? `~${h}h ${m}min` : `~${h}h`;
}

export default function OrderTracker({ order }: OrderTrackerProps) {
  const status = order.status;
  const pct = order.progresso_percentual ?? 0;

  return (
    <div className="p-6 rounded-2xl border border-white/[0.08] bg-white/[0.02]">
      <div className="text-xs uppercase tracking-wider text-gray-400 mb-2">Status</div>
      <div className={`text-xl font-semibold mb-4 ${status === "ERRO_IMPRESSAO" ? "text-amber-400" : "text-white"}`}>
        {LABELS[status]}
      </div>

      {status === "PREPARANDO" && (
        <p className="text-sm text-gray-400">
          Baixando modelo e enviando para a impressora…
        </p>
      )}

      {status === "IMPRIMINDO" && (
        <div className="space-y-3">
          <div className="h-3 w-full bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-[#4ECDC4] to-[#44B09E] transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex items-baseline justify-between">
            <div className="font-mono text-3xl text-[#4ECDC4]">{pct}%</div>
            <div className="text-sm text-gray-400">
              {order.camada_atual && order.camada_total
                ? `camada ${order.camada_atual} / ${order.camada_total}`
                : null}
            </div>
          </div>
          <div className="text-sm text-gray-400">
            Tempo restante: {formatETA(order.tempo_impressao_horas, pct)}
          </div>
        </div>
      )}

      {status === "IMPRESSO" && (
        <p className="text-sm text-gray-400">
          Sua peça está pronta! Vamos embalar e enviar em breve.
        </p>
      )}

      {status === "ERRO_IMPRESSAO" && (
        <p className="text-sm text-amber-200/80">
          Tivemos um problema com a impressão. Nossa equipe já foi notificada e vamos
          reimprimir sua peça sem custo adicional.
        </p>
      )}

      {(status === "ENVIADO" || status === "ENTREGUE") && order.codigo_rastreio && (
        <p className="text-sm text-gray-400">
          Rastreio:{" "}
          <a
            href={`https://rastreamento.correios.com.br/app/index.php?objeto=${order.codigo_rastreio}`}
            className="font-mono text-[#4ECDC4] hover:underline"
            target="_blank"
            rel="noreferrer"
          >
            {order.codigo_rastreio}
          </a>
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/OrderTracker.tsx
git commit -m "refactor(frontend): OrderTracker com estados novos e progresso"
```

### Task 6.4: Atualizar `/pedido/[id]/page.tsx`

**Files:**
- Modify: `frontend/src/app/pedido/[id]/page.tsx`

- [ ] **Step 1: Ler o arquivo atual**

Ler `frontend/src/app/pedido/[id]/page.tsx` pra entender o layout existente (onde plugar o `OrderTracker`).

- [ ] **Step 2: Substituir o fetch manual pelo hook**

Editar `frontend/src/app/pedido/[id]/page.tsx` pra usar `useOrderStream(id)` em vez do fetch que existe hoje, e passar o `order` pro `<OrderTracker order={order} />`.

Estrutura esperada do componente (adaptar ao layout atual):
```tsx
"use client";

import { useParams } from "next/navigation";

import OrderTracker from "@/components/OrderTracker";
import { useOrderStream } from "@/lib/hooks/useOrderStream";

export default function PedidoPage() {
  const params = useParams<{ id: string }>();
  const { order } = useOrderStream(params.id ?? null);

  if (!order) {
    return <div className="p-8">Carregando pedido…</div>;
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-2">Pedido #{order.id.slice(0, 8)}</h1>
      <p className="text-gray-400 mb-8">{order.nome}</p>

      <OrderTracker order={order} />

      {/* ... resto do conteúdo existente: detalhes do pedido, preço, etc ... */}
    </div>
  );
}
```

Preservar blocos de informação não-relacionados ao status (detalhes do pedido, preços, etc) que já estavam na página.

- [ ] **Step 3: Testar manualmente no browser**

Rodar `npm run dev` no frontend, `uvicorn main:app --reload` no backend, e abrir `http://localhost:3002/pedido/<id>`. Verificar que o status aparece e que ao rodar `UPDATE orders SET progresso_percentual = 75 WHERE id = '...'` no DB, a barra atualiza automaticamente.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pedido/[id]/page.tsx
git commit -m "feat(frontend): /pedido/[id] consome SSE via useOrderStream"
```

### Task 6.5: Atualizar `/admin/page.tsx`

**Files:**
- Modify: `frontend/src/app/admin/page.tsx`

- [ ] **Step 1: Ler o arquivo atual**

Ler `frontend/src/app/admin/page.tsx` pra entender a estrutura atual (tabela de pedidos, filtros, ações).

- [ ] **Step 2: Adicionar coluna de progresso**

Na tabela de pedidos, adicionar uma coluna "Progresso" que mostra:
- `{order.progresso_percentual}%` se `status === "IMPRIMINDO"`
- `—` caso contrário

- [ ] **Step 3: Adicionar filtro por status**

Antes da tabela, adicionar uma barra de botões:
```tsx
const STATUS_FILTERS: (OrderStatus | "TODOS")[] = [
  "TODOS",
  "PAGO",
  "PREPARANDO",
  "IMPRIMINDO",
  "IMPRESSO",
  "EMBALANDO",
  "ENVIADO",
  "ENTREGUE",
  "ERRO_IMPRESSAO",
];

const [statusFilter, setStatusFilter] = useState<OrderStatus | "TODOS">("TODOS");
const filtered = orders.filter((o) => statusFilter === "TODOS" || o.status === statusFilter);
```

Renderizar a barra:
```tsx
<div className="flex flex-wrap gap-2 mb-6">
  {STATUS_FILTERS.map((s) => (
    <button
      key={s}
      onClick={() => setStatusFilter(s)}
      className={`px-3 py-1.5 rounded-lg text-sm ${
        statusFilter === s ? "bg-[#4ECDC4] text-black" : "bg-white/5 text-gray-300 hover:bg-white/10"
      }`}
    >
      {s.replace(/_/g, " ")}
    </button>
  ))}
</div>
```

- [ ] **Step 4: Linhas clicáveis → `/admin/pedido/[id]`**

Envolver cada linha da tabela num `<Link href={`/admin/pedido/${order.id}`}>` ou `<tr onClick={() => router.push(`/admin/pedido/${order.id}`)}>`.

- [ ] **Step 5: Destacar linhas em erro**

Adicionar `className={order.status === "ERRO_IMPRESSAO" ? "border-l-4 border-amber-400 bg-amber-400/5" : ""}` à `<tr>`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/admin/page.tsx
git commit -m "feat(frontend): /admin com progresso, filtros, linhas clicáveis"
```

### Task 6.6: Criar `/admin/pedido/[id]/page.tsx`

**Files:**
- Create: `frontend/src/app/admin/pedido/[id]/page.tsx`

- [ ] **Step 1: Criar a página detalhada**

```tsx
"use client";

import Script from "next/script";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { adminRequeueOrder, adminUpdateOrder, Order, OrderStatus } from "@/lib/api";
import { useOrderStream } from "@/lib/hooks/useOrderStream";

const BADGE_COLORS: Record<OrderStatus, string> = {
  AGUARDANDO_PAGAMENTO: "bg-gray-500/20 text-gray-300",
  PAGO: "bg-blue-500/20 text-blue-300",
  PREPARANDO: "bg-purple-500/20 text-purple-300",
  IMPRIMINDO: "bg-[#4ECDC4]/20 text-[#4ECDC4]",
  IMPRESSO: "bg-green-500/20 text-green-300",
  ERRO_IMPRESSAO: "bg-amber-500/20 text-amber-300",
  EMBALANDO: "bg-yellow-500/20 text-yellow-300",
  ENVIADO: "bg-cyan-500/20 text-cyan-300",
  ENTREGUE: "bg-emerald-500/20 text-emerald-300",
};

function formatMoney(centavos: number): string {
  return `R$ ${(centavos / 100).toFixed(2).replace(".", ",")}`;
}

function TimelineItem({ label, date, extra }: { label: string; date: string | null; extra?: string }) {
  if (!date && !extra) return null;
  return (
    <div className="flex items-start gap-3 pb-4 border-l-2 border-white/10 pl-4 relative">
      <div className="absolute -left-1.5 top-1.5 w-3 h-3 rounded-full bg-[#4ECDC4]" />
      <div>
        <div className="font-medium">{label}</div>
        {date && <div className="text-xs text-gray-400">{new Date(date).toLocaleString("pt-BR")}</div>}
        {extra && <div className="text-xs text-gray-400 font-mono">{extra}</div>}
      </div>
    </div>
  );
}

export default function AdminOrderDetail() {
  const params = useParams<{ id: string }>();
  const { order } = useOrderStream(params.id ?? null);
  const [password, setPassword] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setPassword(sessionStorage.getItem("adminPassword") || "");
  }, []);

  if (!order) return <div className="p-8">Carregando…</div>;

  const handleRequeue = async () => {
    setActionError(null);
    const res = await adminRequeueOrder(order.id, password);
    if (!res.success) setActionError(res.error ?? "erro");
  };

  const handleMarkPacked = async () => {
    await adminUpdateOrder(order.id, password, { status: "EMBALANDO" });
  };

  const handleMarkShipped = async () => {
    const code = prompt("Código de rastreio dos Correios:");
    if (!code) return;
    await adminUpdateOrder(order.id, password, { status: "ENVIADO", codigo_rastreio: code });
  };

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <Script
        src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js"
        type="module"
      />

      <div className="flex items-start justify-between">
        <div>
          <Link href="/admin" className="text-sm text-gray-400 hover:text-white">← Voltar</Link>
          <h1 className="text-3xl font-bold mt-2">{order.nome}</h1>
          <div className="text-gray-400 text-sm font-mono mt-1">{order.id}</div>
        </div>
        <div className={`px-4 py-2 rounded-lg text-sm font-semibold ${BADGE_COLORS[order.status]}`}>
          {order.status.replace(/_/g, " ")}
        </div>
      </div>

      {/* Timeline */}
      <section className="bg-white/[0.02] border border-white/[0.08] rounded-2xl p-6">
        <h2 className="text-lg font-semibold mb-4">Histórico</h2>
        <div className="space-y-0">
          <TimelineItem label="Criado" date={order.created_at} />
          <TimelineItem label="Impressão iniciada" date={order.impressao_iniciada_em} />
          <TimelineItem label="Impressão concluída" date={order.impressao_concluida_em} />
          {order.codigo_rastreio && (
            <TimelineItem label="Enviado" date={null} extra={order.codigo_rastreio} />
          )}
          {order.erro_mensagem && (
            <div className="mt-4 bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
              <div className="font-semibold text-amber-300 mb-2">Erro de impressão</div>
              <pre className="text-xs text-amber-200 whitespace-pre-wrap">{order.erro_mensagem}</pre>
            </div>
          )}
        </div>
      </section>

      {/* Detalhes técnicos */}
      <section className="bg-white/[0.02] border border-white/[0.08] rounded-2xl p-6">
        <h2 className="text-lg font-semibold mb-4">Detalhes</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div><span className="text-gray-400">Material:</span> <span className="font-mono">{order.material}</span></div>
          <div><span className="text-gray-400">Escala:</span> <span className="font-mono">{order.escala}x</span></div>
          <div><span className="text-gray-400">Peso:</span> <span className="font-mono">{order.peso_gramas}g</span></div>
          <div><span className="text-gray-400">Tempo:</span> <span className="font-mono">{order.tempo_impressao_horas}h</span></div>
          <div><span className="text-gray-400">Preço:</span> <span className="font-mono">{formatMoney(order.preco_centavos)}</span></div>
          <div><span className="text-gray-400">Frete:</span> <span className="font-mono">{formatMoney(order.frete_centavos)}</span></div>
          <div><span className="text-gray-400">Total:</span> <span className="font-mono">{formatMoney(order.total_centavos)}</span></div>
          <div><span className="text-gray-400">Prazo:</span> <span className="font-mono">{order.prazo_dias} dias</span></div>
        </div>
      </section>

      {/* Ações */}
      <section className="flex flex-wrap gap-3">
        {order.status === "ERRO_IMPRESSAO" && (
          <button onClick={handleRequeue} className="px-4 py-2 bg-[#4ECDC4] text-black rounded-lg font-semibold">
            Reenfileirar
          </button>
        )}
        {order.status === "IMPRESSO" && (
          <button onClick={handleMarkPacked} className="px-4 py-2 bg-white/10 rounded-lg">
            Marcar como Embalado
          </button>
        )}
        {order.status === "EMBALANDO" && (
          <button onClick={handleMarkShipped} className="px-4 py-2 bg-white/10 rounded-lg">
            Marcar como Enviado
          </button>
        )}
        {actionError && <div className="text-sm text-amber-400">{actionError}</div>}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/admin/pedido/
git commit -m "feat(frontend): /admin/pedido/[id] com timeline, detalhes e ações"
```

---

## Phase 7 — Documentação e smoke test

### Task 7.1: Atualizar `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Corrigir menção a SQLite**

Na seção "Tech stack", já está "PostgreSQL (asyncpg)" — ok. Na lista de env vars, trocar:
```
DATABASE_URL=sqlite:///./forja3d.db
```
por:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/forja3d
```

- [ ] **Step 2: Adicionar seção "Migrações"**

Adicionar uma nova seção depois de "Variáveis de ambiente necessárias":
```markdown
## Migrações (Alembic)

O backend usa Alembic pra gerenciar schema do Postgres.

Comandos principais:
- Criar migration a partir do schema atual: `cd backend && alembic revision --autogenerate -m "descrição"`
- Aplicar migrations: `cd backend && alembic upgrade head`
- Reverter última migration: `cd backend && alembic downgrade -1`
- Ver estado atual: `cd backend && alembic current`

Em produção (Railway), o start command roda `alembic upgrade head` antes do `uvicorn`.
```

- [ ] **Step 3: Adicionar seção "Agent lifecycle" descrevendo os estados**

Na seção "Fluxo principal do sistema", logo depois do passo 12 (webhook), adicionar:
```markdown

## Estados do pedido (state machine)

```
PAGO → PREPARANDO → IMPRIMINDO → IMPRESSO → EMBALANDO → ENVIADO → ENTREGUE
                         ↓
                  ERRO_IMPRESSAO → (admin requeue) → PAGO
```

- **PAGO → IMPRESSO:** automático via printer-agent (MQTT + bambulabs-api)
- **IMPRESSO → ENTREGUE:** manual via `/admin/pedido/[id]`
- **ERRO_IMPRESSAO:** qualquer falha na parte automática; admin reenfileira via botão
```

- [ ] **Step 4: Adicionar nota sobre higiene de segredos**

Na seção "Convenções", acrescentar:
```markdown
- Antes de commitar, rodar `git diff --cached | grep -iE 'secret|token|password|api.?key'` pra garantir que nenhum valor sensível foi staged
- `backend/.env` e `printer-agent/config.json` NUNCA devem ser commitados (ambos já estão no `.gitignore`)
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: atualiza CLAUDE.md com migrações, states, hygiene"
```

### Task 7.2: Smoke test end-to-end

**Files:** none (teste manual)

- [ ] **Step 1: Garantir serviços rodando**

Terminais:
1. `docker-compose up` (Postgres)
2. `cd backend && .venv/Scripts/alembic upgrade head` (aplicar migrations)
3. `cd backend && .venv/Scripts/uvicorn main:app --reload` (backend)
4. `cd frontend && npm run dev` (frontend)
5. `cd printer-agent && python agent.py` (agent — **só se tiver uma X1 Carbon conectada**; se não tiver, pule este passo e faça um teste de mock)

- [ ] **Step 2: Criar um pedido de teste via curl (sem fluxo real de pagamento)**

Inserir direto no DB pra pular geração + pagamento:
```bash
docker-compose exec db psql -U postgres -d forja3d <<SQL
INSERT INTO orders (
  id, nome, email, status, modelo_url, material, escala,
  peso_gramas, volume_cm3, tempo_impressao_horas,
  preco_centavos, frete_centavos, cep_destino, prazo_dias, created_at, updated_at
) VALUES (
  gen_random_uuid()::text, 'Teste Smoke', 'teste@local', 'PAGO',
  '/uploads/test.glb', 'PLA', 1.0,
  50, 30, 2.5,
  5000, 2000, '01310100', 5, NOW(), NOW()
);
SQL
```

- [ ] **Step 3: Verificar que o agent fez claim**

Se o agent estiver rodando com X1 conectada, após alguns segundos o pedido deve virar `PREPARANDO`. Verificar:
```bash
docker-compose exec db psql -U postgres -d forja3d -c "SELECT id, status, progresso_percentual FROM orders ORDER BY created_at DESC LIMIT 1;"
```

- [ ] **Step 4: Testar SSE manualmente**

Abrir `http://localhost:3002/pedido/<id>` no navegador e verificar que o status aparece.

Em outro terminal:
```bash
docker-compose exec db psql -U postgres -d forja3d -c "UPDATE orders SET progresso_percentual = 50, camada_atual = 100, camada_total = 200 WHERE id = '<id>';"
```
Expected: a tela do browser atualiza sozinha com `50%`.

- [ ] **Step 5: Testar requeue**

Mudar o pedido pra `ERRO_IMPRESSAO` no DB:
```bash
docker-compose exec db psql -U postgres -d forja3d -c "UPDATE orders SET status='ERRO_IMPRESSAO', erro_mensagem='teste' WHERE id='<id>';"
```

Abrir `/admin`, clicar na linha do pedido → `/admin/pedido/<id>`, clicar em "Reenfileirar". Verificar que volta pra `PAGO`.

- [ ] **Step 6: Resumir resultados**

Escrever um breve relatório em `docs/superpowers/plans/2026-04-10-printer-lifecycle.md` (append no fim) ou em comentário do PR final listando:
- o que funcionou
- o que não funcionou
- bugs encontrados (corrigir antes de merge)

### Task 7.3: Checklist operacional final

**Files:** none (checklist humana)

- [ ] **Step 1: Rotacionar credenciais expostas** (ver Seção 7.2 da spec)

Executar os passos da seção 7.2 da spec:
- Rotacionar `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY` no console Tencent Cloud
- Rotacionar `MP_ACCESS_TOKEN` no dashboard Mercado Pago
- Gerar novas `ADMIN_PASSWORD` e `AGENT_PASSWORD` (`openssl rand -hex 32`)
- Atualizar `.env` local e Railway
- Atualizar `printer-agent/config.json` com o novo `AGENT_PASSWORD`

- [ ] **Step 2: Registrar domínio no Resend**

1. Criar conta no Resend (se não tiver)
2. Adicionar domínio `forja3d.com.br`
3. Configurar DNS: SPF, DKIM (2 CNAMEs), DMARC
4. Verificar domínio no dashboard Resend
5. Gerar API key, colocar em `RESEND_API_KEY` no `.env` e Railway

- [ ] **Step 3: Configurar Railway start command**

No dashboard Railway, ajustar o start command para:
```
cd backend && alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 4: Atualizar `.env.example`** com todas as chaves

Verificar que `backend/.env.example` lista (mesmo que com valores placeholder):
- `TENCENT_SECRET_ID`, `TENCENT_SECRET_KEY`, `TENCENT_REGION`
- `MP_ACCESS_TOKEN`
- `CORREIOS_CEP_ORIGEM`
- `DATABASE_URL`
- `ADMIN_PASSWORD`, `AGENT_PASSWORD`
- `STORAGE_PATH`
- `FRONTEND_URL`, `ALLOWED_ORIGINS`
- `RESEND_API_KEY`, `EMAIL_FROM`
- `ORPHAN_PREPARING_MINUTES`

Se faltar alguma, adicionar e commitar:
```bash
git add backend/.env.example
git commit -m "docs(backend): .env.example completo"
```

---

## Recap

**Total de tasks:** 25 tasks distribuídas em 7 fases.

**Ordem de dependência:**
- Phase 0 é pré-requisito pra tudo
- Phase 1 precisa rodar antes da 2, 3, 4
- Phase 5 pode rodar em paralelo com 6 (ambas só dependem da 2)
- Phase 7 é final

**Critérios de sucesso:**
- Todos os testes de `backend/tests/*` passam (`pytest`)
- SSE atualiza em tempo real no browser ao rodar `UPDATE` no DB
- Admin panel mostra progresso e permite requeue
- Agent refatorado importa sem erro (com `bambulabs-api` instalado)
- CLAUDE.md atualizado e commitado
- Credenciais rotacionadas (check humano)
