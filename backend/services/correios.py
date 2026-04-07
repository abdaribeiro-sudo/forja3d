import os

import httpx


class CorreiosService:
    """Cálculo de frete via API dos Correios (ViaCEP + estimativa)."""

    def __init__(self):
        self.cep_origem = os.getenv("CORREIOS_CEP_ORIGEM", "28035030")

    async def validar_cep(self, cep: str) -> dict | None:
        """Valida CEP usando ViaCEP. Retorna dados do endereço ou None."""
        cep_limpo = cep.replace("-", "").strip()
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://viacep.com.br/ws/{cep_limpo}/json/")
            data = resp.json()
            if "erro" in data:
                return None
            return data

    async def calcular_frete(self, cep_destino: str, peso_gramas: float) -> dict:
        """
        Calcula frete PAC para o CEP destino.
        Usa estimativa baseada na região até integrar a API oficial.
        Retorna dict com preço em centavos e prazo em dias.
        """
        endereco = await self.validar_cep(cep_destino)
        if not endereco:
            raise ValueError(f"CEP inválido: {cep_destino}")

        uf = endereco.get("uf", "")
        peso_kg = max(peso_gramas / 1000.0, 0.3)  # Mínimo 300g para embalagem

        # Estimativa de frete PAC por região
        # Baseado em tabela simplificada de faixas de CEP
        frete_base, prazo = self._estimar_por_regiao(uf, peso_kg)

        return {
            "cep_destino": cep_destino,
            "uf": uf,
            "cidade": endereco.get("localidade", ""),
            "preco_centavos": frete_base,
            "prazo_dias": prazo,
        }

    def _estimar_por_regiao(self, uf: str, peso_kg: float) -> tuple[int, int]:
        """Retorna (preço em centavos, prazo em dias) baseado na UF."""
        # Origem: CEP 28035-030 (Nova Friburgo, RJ)
        # Tabela simplificada PAC
        tabela = {
            # Sudeste
            "RJ": (1800, 3), "SP": (2200, 4), "MG": (2200, 4), "ES": (2000, 4),
            # Sul
            "PR": (2800, 5), "SC": (3000, 6), "RS": (3200, 7),
            # Centro-Oeste
            "DF": (3000, 6), "GO": (3000, 6), "MT": (3500, 8), "MS": (3500, 8),
            # Nordeste
            "BA": (3200, 7), "SE": (3500, 8), "AL": (3500, 8), "PE": (3500, 8),
            "PB": (3800, 9), "RN": (3800, 9), "CE": (4000, 10), "PI": (4200, 10),
            "MA": (4500, 12),
            # Norte
            "PA": (4500, 12), "AP": (5000, 15), "AM": (5500, 15), "RR": (5500, 18),
            "AC": (5800, 18), "RO": (5000, 15), "TO": (4000, 10),
        }

        base, prazo = tabela.get(uf, (4000, 10))

        # Ajuste por peso (cada kg adicional acima de 1kg)
        if peso_kg > 1.0:
            base += int((peso_kg - 1.0) * 800)

        return base, prazo


correios_service = CorreiosService()
