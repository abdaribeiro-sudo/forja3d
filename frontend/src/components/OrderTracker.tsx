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
