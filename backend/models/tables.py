import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    nome: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="AGUARDANDO_PAGAMENTO")

    # Modelo 3D
    modelo_url: Mapped[str] = mapped_column(Text)
    modelo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    material: Mapped[str] = mapped_column(String(10))
    escala: Mapped[float] = mapped_column(Float, default=1.0)

    # Dimensões e peso
    peso_gramas: Mapped[float] = mapped_column(Float, default=0.0)
    volume_cm3: Mapped[float] = mapped_column(Float, default=0.0)
    tempo_impressao_horas: Mapped[float] = mapped_column(Float, default=0.0)

    # Preços (em centavos)
    preco_centavos: Mapped[int] = mapped_column(Integer, default=0)
    frete_centavos: Mapped[int] = mapped_column(Integer, default=0)

    # Entrega
    cep_destino: Mapped[str] = mapped_column(String(8))
    prazo_dias: Mapped[int] = mapped_column(Integer, default=0)
    codigo_rastreio: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Pagamento
    mp_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mp_preference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

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

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id: Mapped[str] = mapped_column(String(255), unique=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    model_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
