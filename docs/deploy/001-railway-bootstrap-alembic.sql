-- ============================================================================
-- Railway Bootstrap: adapta DB de produção pra começar a usar Alembic
-- ============================================================================
-- RODAR UMA ÚNICA VEZ antes do primeiro deploy com start command que inclui
-- `alembic upgrade head`.
--
-- O que este script faz:
-- 1. Adiciona as 8 colunas de lifecycle na tabela `orders` (ALTER, não CREATE)
-- 2. Cria a função e trigger de pg_notify pra SSE
-- 3. Cria a tabela alembic_version e stampa a revisão 002_sse_notify_trigger
--    (assim o `alembic upgrade head` do start command é no-op no primeiro run)
--
-- Como rodar:
-- - Opção 1 (Railway CLI):
--     railway run psql $DATABASE_URL -f docs/deploy/001-railway-bootstrap-alembic.sql
-- - Opção 2 (Railway web console):
--     Dashboard → Postgres service → Data / Query → colar este script → Run
-- - Opção 3 (psql direto):
--     psql "$DATABASE_URL" -f docs/deploy/001-railway-bootstrap-alembic.sql
--
-- IDEMPOTÊNCIA: o script usa `ADD COLUMN IF NOT EXISTS` e `CREATE OR REPLACE`
-- onde possível. Rodar 2x não quebra. Só a parte de alembic_version pode dar
-- erro de "duplicate key" se rodar 2x — isso é esperado e seguro.
-- ============================================================================

BEGIN;

-- 1. Adicionar colunas novas ao Order (idempotente via IF NOT EXISTS)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS progresso_percentual INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS camada_atual INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS camada_total INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS erro_mensagem TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS erro_em TIMESTAMP;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS impressao_iniciada_em TIMESTAMP;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS impressao_concluida_em TIMESTAMP;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS arquivo_3mf_path TEXT;

-- 2. Criar função de NOTIFY (idempotente via CREATE OR REPLACE)
CREATE OR REPLACE FUNCTION notify_order_update() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('order_' || NEW.id, row_to_json(NEW)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Criar trigger (drop+create pra ser idempotente)
DROP TRIGGER IF EXISTS order_update_notify ON orders;
CREATE TRIGGER order_update_notify
    AFTER UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION notify_order_update();

-- 4. Criar tabela alembic_version (só cria se não existir)
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- 5. Stampar na revisão 002 (só insere se alembic_version estiver vazia)
INSERT INTO alembic_version (version_num)
SELECT '002_sse_notify_trigger'
WHERE NOT EXISTS (SELECT 1 FROM alembic_version);

COMMIT;

-- Verificação: deve mostrar '002_sse_notify_trigger'
SELECT version_num AS alembic_revision FROM alembic_version;

-- Verificação: deve mostrar as 8 colunas novas
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'orders'
  AND column_name IN (
    'progresso_percentual','camada_atual','camada_total',
    'erro_mensagem','erro_em',
    'impressao_iniciada_em','impressao_concluida_em','arquivo_3mf_path'
  )
ORDER BY column_name;

-- Verificação: deve mostrar a função e o trigger
SELECT tgname FROM pg_trigger WHERE tgname = 'order_update_notify';
