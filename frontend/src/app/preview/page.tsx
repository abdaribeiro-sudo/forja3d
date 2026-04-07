"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiGet, apiPost, API_URL } from "@/lib/api";
import { formatarPreco, validarEmail, validarCep, formatarCep } from "@/lib/utils";
import ModelViewer from "@/components/ModelViewer";
import MaterialSelector from "@/components/MaterialSelector";

interface MeshInfo {
  volume_cm3: number;
  is_watertight: boolean;
  bounding_box_mm: number[];
}

interface StatusData {
  task_id: string;
  status: string;
  model_url: string | null;
  mesh_info?: MeshInfo;
}

function PreviewContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const taskId = searchParams.get("task_id");

  const [status, setStatus] = useState("PENDING");
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [meshInfo, setMeshInfo] = useState<MeshInfo | null>(null);
  const [material, setMaterial] = useState("PLA");
  const [escala, setEscala] = useState(1.0);
  const [cep, setCep] = useState("");
  const [precoEstimado, setPrecoEstimado] = useState<number | null>(null);
  const [freteEstimado, setFreteEstimado] = useState<number | null>(null);
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Polling do status da geração
  const checkStatus = useCallback(async () => {
    if (!taskId) return;
    const res = await apiGet<StatusData>(`/api/generate/${taskId}/status`);
    if (res.success && res.data) {
      setStatus(res.data.status);
      if (res.data.status === "FINISHED" && res.data.model_url) {
        setModelUrl(`${API_URL}${res.data.model_url}`);
        if (res.data.mesh_info) setMeshInfo(res.data.mesh_info);
      }
    }
  }, [taskId]);

  useEffect(() => {
    if (!taskId) return;
    checkStatus();
    const interval = setInterval(() => {
      if (status !== "FINISHED") checkStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, [taskId, status, checkStatus]);

  // Cálculo de preço em tempo real (estimativa no frontend)
  useEffect(() => {
    if (!meshInfo) return;
    const custoPorG: Record<string, number> = { PLA: 10, PETG: 11, TPU: 18 };
    const densidades: Record<string, number> = { PLA: 1.24, PETG: 1.27, TPU: 1.21 };
    const volume = meshInfo.volume_cm3 * escala ** 3;
    const peso = volume * (densidades[material] || 1.24) * 0.2;
    const tempoH = Math.max(volume / 10, 0.5);
    const custoMat = peso * (custoPorG[material] || 10);
    const custoEnergia = tempoH * 50;
    const total = (custoMat + custoEnergia + 180 + 300) * 1.8;
    setPrecoEstimado(Math.round(total));
  }, [meshInfo, material, escala]);

  // Consulta frete quando CEP completo
  useEffect(() => {
    const cepLimpo = cep.replace(/\D/g, "");
    if (cepLimpo.length !== 8 || !meshInfo) return;
    const peso =
      meshInfo.volume_cm3 *
      escala ** 3 *
      ({ PLA: 1.24, PETG: 1.27, TPU: 1.21 }[material] || 1.24) *
      0.2;
    apiGet<{ preco_centavos: number }>(
      `/api/shipping/estimate?cep_destino=${cepLimpo}&peso_gramas=${peso}`
    ).then((res) => {
      if (res.success && res.data) setFreteEstimado(res.data.preco_centavos);
    });
  }, [cep, meshInfo, material, escala]);

  async function handleOrder() {
    if (!modelUrl || !nome || !email || !cep) {
      setErro("Preencha todos os campos.");
      return;
    }
    if (!validarEmail(email)) {
      setErro("E-mail inválido.");
      return;
    }
    if (!validarCep(cep)) {
      setErro("CEP inválido. Informe 8 dígitos.");
      return;
    }
    setLoading(true);
    setErro(null);

    const modelPath = modelUrl.replace(API_URL, "");
    const res = await apiPost<{ id: string }>("/api/orders", {
      modelo_url: modelPath,
      material,
      escala,
      cep_destino: cep.replace(/\D/g, ""),
      nome,
      email,
    });

    if (res.success && res.data) {
      router.push(`/checkout?order_id=${res.data.id}`);
    } else {
      setErro(res.error || "Erro ao criar pedido.");
      setLoading(false);
    }
  }

  if (!taskId) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400">
        Nenhuma geração em andamento.
      </div>
    );
  }

  return (
    <main className="min-h-screen px-4 py-12">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">Preview 3D</h1>

        {status !== "FINISHED" ? (
          <div className="flex flex-col items-center justify-center py-32">
            <div className="w-12 h-12 border-4 border-teal/30 border-t-teal rounded-full animate-spin mb-6" />
            <p className="text-gray-400 text-lg">Gerando seu modelo 3D...</p>
            <p className="text-gray-500 text-sm mt-2">
              Status: {status}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Viewer */}
            <div>
              {modelUrl && <ModelViewer src={modelUrl} alt="Seu modelo 3D" />}
              {meshInfo && (
                <div className="mt-4 p-4 rounded-xl bg-white/[0.02] border border-white/[0.08] text-sm text-gray-400">
                  <p>
                    Volume: <span className="font-mono text-white">{(meshInfo.volume_cm3 * escala ** 3).toFixed(1)} cm³</span>
                  </p>
                  <p>
                    Dimensões:{" "}
                    <span className="font-mono text-white">
                      {meshInfo.bounding_box_mm.map((d) => (d * escala).toFixed(0)).join(" × ")} mm
                    </span>
                  </p>
                  <p>
                    Watertight: <span className={meshInfo.is_watertight ? "text-teal" : "text-yellow-400"}>{meshInfo.is_watertight ? "Sim" : "Não"}</span>
                  </p>
                </div>
              )}
            </div>

            {/* Configurações */}
            <div className="flex flex-col gap-6">
              <MaterialSelector selected={material} onSelect={setMaterial} />

              {/* Escala */}
              <div>
                <label className="block text-sm text-gray-400 mb-2">
                  Escala: <span className="font-mono text-white">{escala.toFixed(1)}x</span>
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="3.0"
                  step="0.1"
                  value={escala}
                  onChange={(e) => setEscala(parseFloat(e.target.value))}
                  className="w-full accent-teal"
                />
              </div>

              {/* Dados pessoais */}
              <div className="flex flex-col gap-3">
                <input
                  type="text"
                  placeholder="Seu nome"
                  value={nome}
                  onChange={(e) => setNome(e.target.value)}
                  className="px-4 py-3 rounded-xl bg-white/[0.05] border border-white/[0.08] text-white placeholder-gray-500 focus:outline-none focus:border-teal/50 transition-colors"
                />
                <input
                  type="email"
                  placeholder="Seu e-mail"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="px-4 py-3 rounded-xl bg-white/[0.05] border border-white/[0.08] text-white placeholder-gray-500 focus:outline-none focus:border-teal/50 transition-colors"
                />
                <input
                  type="text"
                  placeholder="CEP de entrega"
                  value={cep}
                  onChange={(e) => setCep(formatarCep(e.target.value))}
                  maxLength={9}
                  className="px-4 py-3 rounded-xl bg-white/[0.05] border border-white/[0.08] text-white placeholder-gray-500 focus:outline-none focus:border-teal/50 transition-colors"
                />
              </div>

              {/* Preço */}
              <div className="p-4 rounded-2xl border border-white/[0.08] bg-white/[0.02]">
                <h3 className="font-semibold mb-3">Estimativa de preço</h3>
                <div className="flex justify-between text-gray-400 text-sm mb-1">
                  <span>Impressão</span>
                  <span className="font-mono">{precoEstimado ? formatarPreco(precoEstimado) : "--"}</span>
                </div>
                <div className="flex justify-between text-gray-400 text-sm mb-2">
                  <span>Frete (PAC)</span>
                  <span className="font-mono">{freteEstimado ? formatarPreco(freteEstimado) : "--"}</span>
                </div>
                <div className="border-t border-white/[0.08] pt-2 flex justify-between">
                  <span className="font-semibold">Total</span>
                  <span className="font-mono text-teal text-xl">
                    {precoEstimado && freteEstimado
                      ? formatarPreco(precoEstimado + freteEstimado)
                      : "--"}
                  </span>
                </div>
              </div>

              {/* Erro */}
              {erro && (
                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {erro}
                </div>
              )}

              {/* Botão */}
              <button
                onClick={handleOrder}
                disabled={loading || !modelUrl}
                className="w-full py-4 rounded-2xl bg-gradient-to-r from-teal to-teal-dark text-black font-semibold text-lg hover:shadow-lg hover:shadow-teal/25 hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Criando pedido..." : "Prosseguir para pagamento"}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default function PreviewPage() {
  return (
    <Suspense>
      <PreviewContent />
    </Suspense>
  );
}
