"use client";

interface OrderTrackerProps {
  status: string;
  codigoRastreio?: string;
}

const etapas = [
  "AGUARDANDO_PAGAMENTO",
  "PAGO",
  "IMPRIMINDO",
  "EMBALANDO",
  "ENVIADO",
  "ENTREGUE",
];

export default function OrderTracker({ status, codigoRastreio }: OrderTrackerProps) {
  const etapaAtual = etapas.indexOf(status);

  return (
    <div className="p-4 rounded-2xl border border-white/[0.08] bg-white/[0.02]">
      <h3 className="font-semibold mb-4">Status do pedido</h3>
      <div className="flex flex-col gap-2">
        {etapas.map((etapa, i) => (
          <div key={etapa} className="flex items-center gap-3">
            <div
              className={`w-3 h-3 rounded-full ${
                i <= etapaAtual ? "bg-teal" : "bg-white/10"
              }`}
            />
            <span className={i <= etapaAtual ? "text-white" : "text-gray-500"}>
              {etapa.replace(/_/g, " ")}
            </span>
          </div>
        ))}
      </div>
      {codigoRastreio && (
        <p className="mt-4 text-sm text-gray-400">
          Rastreio: <span className="font-mono text-teal">{codigoRastreio}</span>
        </p>
      )}
    </div>
  );
}
