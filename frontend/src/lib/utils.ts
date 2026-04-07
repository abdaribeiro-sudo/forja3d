/**
 * Formata valor em centavos para reais (ex: 1500 → "R$ 15,00")
 */
export function formatarPreco(centavos: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(centavos / 100);
}

/**
 * Formata peso em gramas (ex: 1500 → "1,5 kg")
 */
export function formatarPeso(gramas: number): string {
  if (gramas >= 1000) {
    return `${(gramas / 1000).toFixed(1).replace(".", ",")} kg`;
  }
  return `${gramas} g`;
}

/**
 * Valida formato de CEP (8 dígitos)
 */
export function validarCep(cep: string): boolean {
  return /^\d{8}$/.test(cep.replace(/\D/g, ""));
}

/**
 * Formata CEP com hífen (ex: 01001000 → "01001-000")
 */
export function formatarCep(cep: string): string {
  const limpo = cep.replace(/\D/g, "");
  if (limpo.length <= 5) return limpo;
  return `${limpo.slice(0, 5)}-${limpo.slice(5, 8)}`;
}

/**
 * Valida formato de e-mail
 */
export function validarEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Formata data ISO para DD/MM/YYYY HH:MM
 */
export function formatarData(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}
