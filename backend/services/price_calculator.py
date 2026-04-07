class PriceCalculatorService:
    """Cálculo de preço conforme fórmula definida no CLAUDE.md."""

    # Custo por grama de cada material (em centavos)
    CUSTO_MATERIAL = {
        "PLA": 10,   # R$ 0,10/g
        "PETG": 11,  # R$ 0,11/g
        "TPU": 18,   # R$ 0,18/g
    }
    CUSTO_ENERGIA_HORA = 50   # R$ 0,50/h em centavos
    CUSTO_API = 180           # R$ 1,80 em centavos
    CUSTO_EMBALAGEM = 300     # R$ 3,00 em centavos
    MARGEM = 1.8              # 80% de margem

    def calcular(
        self, peso_gramas: float, material: str, tempo_impressao_horas: float
    ) -> dict:
        """Calcula preço final em centavos."""
        custo_material = int(peso_gramas * self.CUSTO_MATERIAL.get(material, 10))
        custo_energia = int(tempo_impressao_horas * self.CUSTO_ENERGIA_HORA)
        custo_total = custo_material + custo_energia + self.CUSTO_API + self.CUSTO_EMBALAGEM
        preco_final = int(custo_total * self.MARGEM)

        return {
            "custo_material_centavos": custo_material,
            "custo_energia_centavos": custo_energia,
            "custo_api_centavos": self.CUSTO_API,
            "custo_embalagem_centavos": self.CUSTO_EMBALAGEM,
            "preco_final_centavos": preco_final,
        }


price_service = PriceCalculatorService()
