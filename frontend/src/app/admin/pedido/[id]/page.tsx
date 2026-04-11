"use client";

import Script from "next/script";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { adminRequeueOrder, adminUpdateOrder, OrderStatus } from "@/lib/api";
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

function TimelineItem({
  label,
  date,
  extra,
}: {
  label: string;
  date: string | null;
  extra?: string;
}) {
  if (!date && !extra) return null;
  return (
    <div className="flex items-start gap-3 pb-4 border-l-2 border-white/10 pl-4 relative">
      <div className="absolute -left-1.5 top-1.5 w-3 h-3 rounded-full bg-[#4ECDC4]" />
      <div>
        <div className="font-medium">{label}</div>
        {date && (
          <div className="text-xs text-gray-400">
            {new Date(date).toLocaleString("pt-BR")}
          </div>
        )}
        {extra && <div className="text-xs text-gray-400 font-mono">{extra}</div>}
      </div>
    </div>
  );
}

export default function AdminOrderDetail() {
  const params = useParams<{ id: string }>();
  const orderId = params?.id ?? null;
  const { order } = useOrderStream(orderId);
  const [password, setPassword] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    // Usa a mesma chave localStorage que o painel /admin
    setPassword(localStorage.getItem("admin_password") || "");
  }, []);

  if (!order) return <div className="p-8 text-gray-400">Carregando…</div>;

  const handleRequeue = async () => {
    setActionError(null);
    const res = await adminRequeueOrder(order.id, password);
    if (!res.success) setActionError(res.error ?? "erro");
  };

  const handleMarkPacked = async () => {
    setActionError(null);
    const res = await adminUpdateOrder(order.id, password, { status: "EMBALANDO" });
    if (!res.success) setActionError(res.error ?? "erro");
  };

  const handleMarkShipped = async () => {
    const code = prompt("Código de rastreio dos Correios:");
    if (!code) return;
    setActionError(null);
    const res = await adminUpdateOrder(order.id, password, {
      status: "ENVIADO",
      codigo_rastreio: code,
    });
    if (!res.success) setActionError(res.error ?? "erro");
  };

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <Script
        src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js"
        type="module"
      />

      <div className="flex items-start justify-between">
        <div>
          <Link href="/admin" className="text-sm text-gray-400 hover:text-white">
            ← Voltar
          </Link>
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
          <div>
            <span className="text-gray-400">Material:</span>{" "}
            <span className="font-mono">{order.material}</span>
          </div>
          <div>
            <span className="text-gray-400">Escala:</span>{" "}
            <span className="font-mono">{order.escala}x</span>
          </div>
          <div>
            <span className="text-gray-400">Peso:</span>{" "}
            <span className="font-mono">{order.peso_gramas}g</span>
          </div>
          <div>
            <span className="text-gray-400">Tempo:</span>{" "}
            <span className="font-mono">{order.tempo_impressao_horas}h</span>
          </div>
          <div>
            <span className="text-gray-400">Preço:</span>{" "}
            <span className="font-mono">{formatMoney(order.preco_centavos)}</span>
          </div>
          <div>
            <span className="text-gray-400">Frete:</span>{" "}
            <span className="font-mono">{formatMoney(order.frete_centavos)}</span>
          </div>
          <div>
            <span className="text-gray-400">Total:</span>{" "}
            <span className="font-mono">{formatMoney(order.total_centavos)}</span>
          </div>
          <div>
            <span className="text-gray-400">Prazo:</span>{" "}
            <span className="font-mono">{order.prazo_dias} dias</span>
          </div>
        </div>
      </section>

      {/* Ações */}
      <section className="flex flex-wrap gap-3">
        {order.status === "ERRO_IMPRESSAO" && (
          <button
            onClick={handleRequeue}
            className="px-4 py-2 bg-[#4ECDC4] text-black rounded-lg font-semibold"
          >
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
