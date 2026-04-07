"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";
import { formatarPreco } from "@/lib/utils";

interface OrderData {
  id: string;
  nome: string;
  status: string;
  material: string;
  escala: number;
  peso_gramas: number;
  preco_centavos: number;
  frete_centavos: number;
  total_centavos: number;
  prazo_dias: number;
}

interface PaymentData {
  preference_id: string;
  init_point: string;
}

function CheckoutContent() {
  const searchParams = useSearchParams();
  const orderId = searchParams.get("order_id");
  const mpStatus = searchParams.get("status");
  const erro_param = searchParams.get("error");

  const [order, setOrder] = useState<OrderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [pagando, setPagando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Se voltou do Mercado Pago com erro
  useEffect(() => {
    if (erro_param) setErro("O pagamento não foi concluído. Tente novamente.");
  }, [erro_param]);

  useEffect(() => {
    if (!orderId) return;
    apiGet<OrderData>(`/api/orders/${orderId}`).then((res) => {
      if (res.success && res.data) {
        setOrder(res.data);
      } else {
        setErro(res.error || "Pedido não encontrado.");
      }
      setLoading(false);
    });
  }, [orderId]);

  async function handlePagar() {
    if (!orderId) return;
    setPagando(true);
    setErro(null);

    const res = await apiPost<PaymentData>(`/api/payment/create/${orderId}`, {});
    if (res.success && res.data) {
      window.location.href = res.data.init_point;
    } else {
      setErro(res.error || "Erro ao criar pagamento.");
      setPagando(false);
    }
  }

  if (!orderId) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400">
        Nenhum pedido selecionado.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-teal/30 border-t-teal rounded-full animate-spin" />
      </div>
    );
  }

  // Pagamento aprovado — retorno do Mercado Pago
  if (mpStatus === "approved" || (order && order.status === "PAGO")) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center px-4">
        <div className="w-full max-w-md text-center animate-slideUp">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-teal/20 flex items-center justify-center">
            <svg className="w-10 h-10 text-teal" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold mb-3">Pagamento confirmado!</h1>
          <p className="text-gray-400 mb-8">
            Seu pedido foi recebido e entrará na fila de impressão em breve.
          </p>
          <Link
            href={`/pedido/${orderId}`}
            className="inline-block px-8 py-3 rounded-xl bg-gradient-to-r from-teal to-teal-dark text-black font-semibold hover:shadow-lg hover:shadow-teal/25 transition-all"
          >
            Acompanhar pedido
          </Link>
        </div>
      </main>
    );
  }

  if (!order) {
    return (
      <div className="min-h-screen flex items-center justify-center text-red-400">
        {erro || "Pedido não encontrado."}
      </div>
    );
  }

  return (
    <main className="min-h-screen flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-lg animate-slideUp">
        <h1 className="text-4xl font-bold mb-2">Checkout</h1>
        <p className="text-gray-400 mb-10">Revise e finalize seu pedido.</p>

        {/* Resumo */}
        <div className="p-6 rounded-2xl border border-white/[0.08] bg-white/[0.02] mb-6">
          <h3 className="font-semibold mb-4">Resumo do pedido</h3>
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
              <span>Escala</span>
              <span className="font-mono text-white">{order.escala.toFixed(1)}x</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Peso estimado</span>
              <span className="font-mono text-white">{order.peso_gramas.toFixed(1)}g</span>
            </div>
            <div className="border-t border-white/[0.08] my-3" />
            <div className="flex justify-between text-gray-400">
              <span>Impressão 3D</span>
              <span className="font-mono">{formatarPreco(order.preco_centavos)}</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Frete (PAC Correios)</span>
              <span className="font-mono">{formatarPreco(order.frete_centavos)}</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Prazo estimado</span>
              <span>{order.prazo_dias} dias úteis</span>
            </div>
            <div className="border-t border-white/[0.08] my-3" />
            <div className="flex justify-between text-lg">
              <span className="font-semibold">Total</span>
              <span className="font-mono text-teal font-bold">
                {formatarPreco(order.total_centavos)}
              </span>
            </div>
          </div>
        </div>

        {/* Formas de pagamento */}
        <div className="p-6 rounded-2xl border border-white/[0.08] bg-white/[0.02] mb-6">
          <h3 className="font-semibold mb-4">Formas de pagamento</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
              <p className="text-sm font-medium mb-1">PIX</p>
              <p className="text-xs text-gray-500">Aprovação instantânea</p>
            </div>
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center">
              <p className="text-sm font-medium mb-1">Cartão de crédito</p>
              <p className="text-xs text-gray-500">Até 6x sem juros</p>
            </div>
          </div>
          <p className="text-gray-500 text-xs mt-3">
            Pagamento processado pelo Mercado Pago com total segurança.
          </p>
        </div>

        {/* Erro */}
        {erro && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {erro}
          </div>
        )}

        {/* Botão pagar */}
        <button
          onClick={handlePagar}
          disabled={pagando}
          className="w-full py-4 rounded-2xl bg-gradient-to-r from-teal to-teal-dark text-black font-semibold text-lg hover:shadow-lg hover:shadow-teal/25 hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {pagando ? (
            <span className="flex items-center justify-center gap-3">
              <span className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
              Redirecionando...
            </span>
          ) : (
            `Pagar ${formatarPreco(order.total_centavos)}`
          )}
        </button>

        <p className="text-center text-gray-600 text-xs mt-4">
          Ao clicar, você será redirecionado para o ambiente seguro do Mercado Pago.
        </p>
      </div>
    </main>
  );
}

export default function CheckoutPage() {
  return (
    <Suspense>
      <CheckoutContent />
    </Suspense>
  );
}
