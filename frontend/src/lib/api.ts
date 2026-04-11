const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T;
  error: string | null;
}

async function handleResponse<T>(res: Response): Promise<ApiResponse<T>> {
  if (!res.ok) {
    return {
      success: false,
      data: null as T,
      error: `Erro de conexão (${res.status})`,
    };
  }
  return res.json();
}

export async function apiGet<T>(endpoint: string): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${API_URL}${endpoint}`);
    return handleResponse<T>(res);
  } catch {
    return {
      success: false,
      data: null as T,
      error: "Não foi possível conectar ao servidor.",
    };
  }
}

export async function apiPost<T>(
  endpoint: string,
  body: unknown
): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return handleResponse<T>(res);
  } catch {
    return {
      success: false,
      data: null as T,
      error: "Não foi possível conectar ao servidor.",
    };
  }
}

export { API_URL };

export type OrderStatus =
  | "AGUARDANDO_PAGAMENTO"
  | "PAGO"
  | "PREPARANDO"
  | "IMPRIMINDO"
  | "IMPRESSO"
  | "ERRO_IMPRESSAO"
  | "EMBALANDO"
  | "ENVIADO"
  | "ENTREGUE";

export interface Order {
  id: string;
  nome: string;
  email?: string;
  status: OrderStatus;
  material: "PLA" | "PETG" | "TPU";
  escala: number;
  peso_gramas: number;
  preco_centavos: number;
  frete_centavos: number;
  total_centavos: number;
  prazo_dias: number;
  codigo_rastreio: string | null;
  progresso_percentual: number | null;
  camada_atual: number | null;
  camada_total: number | null;
  erro_mensagem: string | null;
  impressao_iniciada_em: string | null;
  impressao_concluida_em: string | null;
  tempo_impressao_horas: number;
  created_at: string;
}

export async function getOrder(id: string): Promise<ApiResponse<Order>> {
  return apiGet<Order>(`/api/orders/${id}`);
}

export async function adminRequeueOrder(
  id: string,
  password: string
): Promise<ApiResponse<{ id: string; status: OrderStatus }>> {
  return apiPost(`/api/admin/orders/${id}/requeue`, { password });
}

export async function adminUpdateOrder(
  id: string,
  password: string,
  updates: { status?: OrderStatus; codigo_rastreio?: string }
): Promise<ApiResponse<unknown>> {
  return apiPost(`/api/admin/orders/${id}`, { password, ...updates });
}

export function orderStreamUrl(id: string): string {
  return `${API_URL}/api/orders/${id}/stream`;
}
