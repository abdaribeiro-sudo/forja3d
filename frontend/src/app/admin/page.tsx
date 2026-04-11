"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost, Order, OrderStatus } from "@/lib/api";
import { formatarPreco, formatarData } from "@/lib/utils";

const statusColors: Record<string, string> = {
  AGUARDANDO_PAGAMENTO: "bg-yellow-500/20 text-yellow-400",
  PAGO: "bg-blue-500/20 text-blue-400",
  PREPARANDO: "bg-sky-500/20 text-sky-400",
  IMPRIMINDO: "bg-purple-500/20 text-purple-400",
  IMPRESSO: "bg-indigo-500/20 text-indigo-400",
  EMBALANDO: "bg-orange-500/20 text-orange-400",
  ENVIADO: "bg-teal/20 text-teal",
  ENTREGUE: "bg-green-500/20 text-green-400",
  ERRO_IMPRESSAO: "bg-amber-500/20 text-amber-400",
};

const STATUS_FILTERS: (OrderStatus | "TODOS")[] = [
  "TODOS",
  "AGUARDANDO_PAGAMENTO",
  "PAGO",
  "PREPARANDO",
  "IMPRIMINDO",
  "IMPRESSO",
  "EMBALANDO",
  "ENVIADO",
  "ENTREGUE",
  "ERRO_IMPRESSAO",
];

const statusOrder: OrderStatus[] = [
  "AGUARDANDO_PAGAMENTO",
  "PAGO",
  "PREPARANDO",
  "IMPRIMINDO",
  "IMPRESSO",
  "EMBALANDO",
  "ENVIADO",
  "ENTREGUE",
  "ERRO_IMPRESSAO",
];

export default function AdminPage() {
  const router = useRouter();
  const [autenticado, setAutenticado] = useState(false);
  const [senha, setSenha] = useState("");
  const [erroAuth, setErroAuth] = useState(false);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [filtroStatus, setFiltroStatus] = useState<OrderStatus | "TODOS">("TODOS");

  const [editando, setEditando] = useState<string | null>(null);
  const [novoStatus, setNovoStatus] = useState("");
  const [novoRastreio, setNovoRastreio] = useState("");

  // Estatísticas
  const stats = useMemo(() => {
    const totalPedidos = orders.length;
    const faturamento = orders
      .filter((o) => o.status !== "AGUARDANDO_PAGAMENTO")
      .reduce((acc, o) => acc + o.total_centavos, 0);
    const pendentes = orders.filter((o) => o.status === "PAGO").length;
    const imprimindo = orders.filter((o) => o.status === "IMPRIMINDO").length;
    const entregues = orders.filter((o) => o.status === "ENTREGUE").length;

    const materiais: Record<string, number> = {};
    orders.forEach((o) => {
      materiais[o.material] = (materiais[o.material] || 0) + 1;
    });

    return { totalPedidos, faturamento, pendentes, imprimindo, entregues, materiais };
  }, [orders]);

  async function handleLogin() {
    setLoading(true);
    const res = await apiPost<{ authenticated: boolean }>("/api/admin/login", {
      password: senha,
    });
    if (res.success && res.data?.authenticated) {
      setAutenticado(true);
      localStorage.setItem("admin_password", senha);
      loadOrders();
    } else {
      setErroAuth(true);
    }
    setLoading(false);
  }

  async function loadOrders() {
    setLoading(true);
    const pwd = localStorage.getItem("admin_password") || senha;
    const res = await apiGet<Order[]>(
      `/api/admin/orders?password=${encodeURIComponent(pwd)}`
    );
    if (res.success && res.data) {
      setOrders(res.data);
    }
    setLoading(false);
  }

  async function handleUpdateOrder(orderId: string) {
    const pwd = localStorage.getItem("admin_password") || "";
    await apiPost(`/api/admin/orders/${orderId}`, {
      password: pwd,
      status: novoStatus || undefined,
      codigo_rastreio: novoRastreio || undefined,
    });
    setEditando(null);
    setNovoStatus("");
    setNovoRastreio("");
    loadOrders();
  }

  function handleLogout() {
    localStorage.removeItem("admin_password");
    setAutenticado(false);
    setSenha("");
    setOrders([]);
  }

  useEffect(() => {
    const saved = localStorage.getItem("admin_password");
    if (saved) {
      setSenha(saved);
      apiPost<{ authenticated: boolean }>("/api/admin/login", {
        password: saved,
      }).then((res) => {
        if (res.success && res.data?.authenticated) {
          setAutenticado(true);
        }
      });
    }
  }, []);

  useEffect(() => {
    if (autenticado) loadOrders();
  }, [autenticado]);

  const filteredOrders =
    filtroStatus === "TODOS"
      ? orders
      : orders.filter((o) => o.status === filtroStatus);

  // Login
  if (!autenticado) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-sm animate-slideUp">
          <h1 className="text-3xl font-bold mb-2 text-center">Admin</h1>
          <p className="text-gray-400 text-center mb-8">
            Digite a senha de administrador.
          </p>
          <input
            type="password"
            value={senha}
            onChange={(e) => {
              setSenha(e.target.value);
              setErroAuth(false);
            }}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            placeholder="Senha"
            className="w-full px-4 py-3 rounded-xl bg-white/[0.05] border border-white/[0.08] text-white placeholder-gray-500 focus:outline-none focus:border-teal/50 transition-colors mb-4"
          />
          {erroAuth && (
            <p className="text-red-400 text-sm mb-4">Senha incorreta.</p>
          )}
          <button
            onClick={handleLogin}
            disabled={loading || !senha}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-teal to-teal-dark text-black font-semibold hover:shadow-lg hover:shadow-teal/25 transition-all disabled:opacity-50"
          >
            {loading ? "Verificando..." : "Entrar"}
          </button>
        </div>
      </main>
    );
  }

  // Painel
  return (
    <main className="min-h-screen px-4 py-12">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-4xl font-bold mb-1">Painel Administrativo</h1>
            <p className="text-gray-400">
              {orders.length} pedido{orders.length !== 1 ? "s" : ""} no total
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={loadOrders}
              className="px-4 py-2 rounded-xl border border-white/[0.08] text-gray-400 hover:text-white hover:border-white/20 transition-colors text-sm"
            >
              Atualizar
            </button>
            <button
              onClick={handleLogout}
              className="px-4 py-2 rounded-xl border border-red-500/20 text-red-400 hover:bg-red-500/10 transition-colors text-sm"
            >
              Sair
            </button>
          </div>
        </div>

        {/* Dashboard */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          <div className="p-4 rounded-xl border border-white/[0.08] bg-white/[0.02]">
            <p className="text-gray-500 text-xs mb-1">Faturamento</p>
            <p className="text-2xl font-mono font-bold text-teal">
              {formatarPreco(stats.faturamento)}
            </p>
          </div>
          <div className="p-4 rounded-xl border border-white/[0.08] bg-white/[0.02]">
            <p className="text-gray-500 text-xs mb-1">Fila de impressão</p>
            <p className="text-2xl font-mono font-bold text-blue-400">
              {stats.pendentes}
            </p>
          </div>
          <div className="p-4 rounded-xl border border-white/[0.08] bg-white/[0.02]">
            <p className="text-gray-500 text-xs mb-1">Imprimindo agora</p>
            <p className="text-2xl font-mono font-bold text-purple-400">
              {stats.imprimindo}
            </p>
          </div>
          <div className="p-4 rounded-xl border border-white/[0.08] bg-white/[0.02]">
            <p className="text-gray-500 text-xs mb-1">Entregues</p>
            <p className="text-2xl font-mono font-bold text-green-400">
              {stats.entregues}
            </p>
          </div>
        </div>

        {/* Materiais */}
        {Object.keys(stats.materiais).length > 0 && (
          <div className="flex gap-4 mb-8">
            {Object.entries(stats.materiais).map(([mat, count]) => (
              <div
                key={mat}
                className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-gray-400"
              >
                {mat}: <span className="text-white font-mono">{count}</span>
              </div>
            ))}
          </div>
        )}

        {/* Filtros */}
        <div className="flex flex-wrap gap-2 mb-6 overflow-x-auto pb-2">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setFiltroStatus(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                filtroStatus === s
                  ? "bg-[#4ECDC4] text-black"
                  : "bg-white/[0.05] text-gray-400 hover:bg-white/10 hover:text-white"
              }`}
            >
              {s.replace(/_/g, " ")}
              {s !== "TODOS" && (
                <span className="ml-1 opacity-60">
                  ({orders.filter((o) => o.status === s).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Pedidos */}
        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 border-4 border-teal/30 border-t-teal rounded-full animate-spin" />
          </div>
        ) : filteredOrders.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            Nenhum pedido{filtroStatus !== "TODOS" ? " com este status" : ""}.
          </div>
        ) : (
          <div className="space-y-3">
            {filteredOrders.map((order) => (
              <div
                key={order.id}
                onClick={() => router.push(`/admin/pedido/${order.id}`)}
                className={`p-4 rounded-xl border border-white/[0.08] bg-white/[0.02] hover:border-white/[0.12] transition-colors cursor-pointer ${
                  order.status === "ERRO_IMPRESSAO"
                    ? "border-l-4 border-amber-400 bg-amber-400/5"
                    : ""
                }`}
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <a
                        href={`/pedido/${order.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="font-mono text-teal text-sm hover:underline"
                      >
                        #{order.id.slice(0, 8)}
                      </a>
                      <span
                        className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium ${
                          statusColors[order.status] || "bg-gray-500/20 text-gray-400"
                        }`}
                      >
                        {order.status.replace(/_/g, " ")}
                      </span>
                      {order.status === "IMPRIMINDO" && order.progresso_percentual !== null && (
                        <span className="font-mono text-xs text-purple-300">
                          {order.progresso_percentual}%
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-400 truncate">
                      <span className="text-white">{order.nome}</span>
                      <span className="mx-2">·</span>
                      {order.email}
                      <span className="mx-2">·</span>
                      {order.material} ({order.peso_gramas?.toFixed(0)}g)
                      <span className="mx-2">·</span>
                      <span className="font-mono">{formatarPreco(order.total_centavos)}</span>
                    </div>
                    {order.erro_mensagem && order.status === "ERRO_IMPRESSAO" && (
                      <p className="text-xs text-amber-400/80 mt-1 truncate">
                        Erro: {order.erro_mensagem}
                      </p>
                    )}
                    {order.codigo_rastreio && (
                      <p className="text-xs text-gray-500 mt-1">
                        Rastreio:{" "}
                        <span className="font-mono text-teal">{order.codigo_rastreio}</span>
                      </p>
                    )}
                    {order.created_at && (
                      <p className="text-xs text-gray-600 mt-0.5">
                        {formatarData(order.created_at)}
                      </p>
                    )}
                  </div>

                  {editando === order.id ? (
                    <div className="flex flex-wrap items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      <select
                        value={novoStatus}
                        onChange={(e) => setNovoStatus(e.target.value)}
                        className="px-2 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.08] text-white text-xs focus:outline-none"
                      >
                        <option value="">Status...</option>
                        {statusOrder.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                      <input
                        type="text"
                        placeholder="Código rastreio"
                        value={novoRastreio}
                        onChange={(e) => setNovoRastreio(e.target.value)}
                        className="px-2 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.08] text-white text-xs w-36 focus:outline-none"
                      />
                      <button
                        onClick={() => handleUpdateOrder(order.id)}
                        className="px-3 py-1.5 rounded-lg bg-teal/20 text-teal text-xs font-medium hover:bg-teal/30 transition-colors"
                      >
                        Salvar
                      </button>
                      <button
                        onClick={() => setEditando(null)}
                        className="px-3 py-1.5 rounded-lg bg-white/[0.05] text-gray-400 text-xs hover:text-white transition-colors"
                      >
                        Cancelar
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditando(order.id);
                        setNovoStatus(order.status);
                        setNovoRastreio(order.codigo_rastreio || "");
                      }}
                      className="px-3 py-1.5 rounded-lg border border-white/[0.08] text-gray-400 text-xs hover:text-white hover:border-white/20 transition-colors shrink-0"
                    >
                      Editar
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
