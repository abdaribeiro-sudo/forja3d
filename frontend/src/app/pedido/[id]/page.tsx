"use client";

import { useParams } from "next/navigation";

import OrderTracker from "@/components/OrderTracker";
import { useOrderStream } from "@/lib/hooks/useOrderStream";
import { formatarPreco } from "@/lib/utils";

export default function PedidoPage() {
  const params = useParams<{ id: string }>();
  const orderId = params?.id ?? null;
  const { order } = useOrderStream(orderId);

  if (!order) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-teal/30 border-t-teal rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <main className="min-h-screen flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-lg animate-slideUp">
        <h1 className="text-4xl font-bold mb-2">Pedido</h1>
        <p className="text-gray-400 font-mono mb-10">#{order.id.slice(0, 8)}</p>

        <OrderTracker order={order} />

        <div className="mt-8 p-6 rounded-2xl border border-white/[0.08] bg-white/[0.02]">
          <h3 className="font-semibold mb-4">Detalhes</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-gray-400">
              <span>Cliente</span>
              <span className="text-white">{order.nome}</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Material</span>
              <span className="text-white">{order.material}</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Impressão</span>
              <span className="font-mono">{formatarPreco(order.preco_centavos)}</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Frete</span>
              <span className="font-mono">{formatarPreco(order.frete_centavos)}</span>
            </div>
            <div className="border-t border-white/[0.08] my-3" />
            <div className="flex justify-between">
              <span className="font-semibold">Total</span>
              <span className="font-mono text-teal">{formatarPreco(order.total_centavos)}</span>
            </div>
            {order.created_at && (
              <div className="flex justify-between text-gray-400 pt-2">
                <span>Criado em</span>
                <span>{new Date(order.created_at).toLocaleDateString("pt-BR")}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
