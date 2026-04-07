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
