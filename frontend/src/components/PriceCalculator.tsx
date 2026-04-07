"use client";

import { formatarPreco } from "@/lib/utils";

interface PriceCalculatorProps {
  pesoGramas: number;
  material: "PLA" | "PETG" | "TPU";
  tempoImpressaoHoras: number;
}

const CUSTO_MATERIAL: Record<string, number> = { PLA: 10, PETG: 11, TPU: 18 };
const CUSTO_ENERGIA_HORA = 50;
const CUSTO_API = 180;
const CUSTO_EMBALAGEM = 300;
const MARGEM = 1.8;

function calcular(peso: number, material: string, tempo: number) {
  const custoMat = Math.round(peso * (CUSTO_MATERIAL[material] || 10));
  const custoEnergia = Math.round(tempo * CUSTO_ENERGIA_HORA);
  const total = custoMat + custoEnergia + CUSTO_API + CUSTO_EMBALAGEM;
  return {
    material: custoMat,
    energia: custoEnergia,
    api: CUSTO_API,
    embalagem: CUSTO_EMBALAGEM,
    final: Math.round(total * MARGEM),
  };
}

export default function PriceCalculator({
  pesoGramas,
  material,
  tempoImpressaoHoras,
}: PriceCalculatorProps) {
  const preco = calcular(pesoGramas, material, tempoImpressaoHoras);

  return (
    <div className="p-4 rounded-2xl border border-white/[0.08] bg-white/[0.02]">
      <h3 className="font-semibold mb-3">Estimativa de preço</h3>
      <div className="space-y-1 text-sm">
        <div className="flex justify-between text-gray-400">
          <span>Material ({material}, {pesoGramas.toFixed(1)}g)</span>
          <span className="font-mono">{formatarPreco(preco.material)}</span>
        </div>
        <div className="flex justify-between text-gray-400">
          <span>Energia ({tempoImpressaoHoras.toFixed(1)}h)</span>
          <span className="font-mono">{formatarPreco(preco.energia)}</span>
        </div>
        <div className="flex justify-between text-gray-400">
          <span>Geração IA</span>
          <span className="font-mono">{formatarPreco(preco.api)}</span>
        </div>
        <div className="flex justify-between text-gray-400">
          <span>Embalagem</span>
          <span className="font-mono">{formatarPreco(preco.embalagem)}</span>
        </div>
        <div className="border-t border-white/[0.08] my-2" />
        <div className="flex justify-between">
          <span className="font-semibold">Total</span>
          <span className="text-xl font-mono text-teal">{formatarPreco(preco.final)}</span>
        </div>
      </div>
    </div>
  );
}
