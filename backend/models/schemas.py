from pydantic import BaseModel
from enum import Enum
from typing import Optional


class MaterialEnum(str, Enum):
    PLA = "PLA"
    PETG = "PETG"
    TPU = "TPU"


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


class GenerateRequest(BaseModel):
    prompt: Optional[str] = None
    imagem_base64: Optional[str] = None


class GenerateResponse(BaseModel):
    task_id: str
    status: str


class OrderCreate(BaseModel):
    modelo_url: str
    material: MaterialEnum
    escala: float = 1.0
    cep_destino: str
    nome: str
    email: str


class OrderResponse(BaseModel):
    id: str
    status: StatusPedido
    preco_centavos: int
    frete_centavos: int
    codigo_rastreio: Optional[str] = None


class PriceEstimate(BaseModel):
    material: MaterialEnum
    peso_gramas: float
    tempo_impressao_horas: float
    custo_material_centavos: int
    custo_energia_centavos: int
    custo_api_centavos: int
    custo_embalagem_centavos: int
    preco_final_centavos: int


class ShippingEstimate(BaseModel):
    cep_destino: str
    peso_gramas: float
    preco_centavos: int
    prazo_dias: int
