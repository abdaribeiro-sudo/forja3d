"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";

const exemplos = [
  "Um vaso minimalista com formato hexagonal",
  "Uma miniatura de castelo medieval com torres",
  "Um suporte de celular em formato de mão aberta",
  "Um chaveiro personalizado com formato de gato",
  "Uma engrenagem mecânica steampunk decorativa",
];

export default function CriarPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [prompt, setPrompt] = useState("");
  const [imagemPreview, setImagemPreview] = useState<string | null>(null);
  const [imagemBase64, setImagemBase64] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setErro("Imagem muito grande. Máximo 10MB.");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      setImagemPreview(result);
      setImagemBase64(result.split(",")[1]);
    };
    reader.readAsDataURL(file);
  }

  async function handleGenerate() {
    if (!prompt && !imagemBase64) {
      setErro("Descreva o objeto ou envie uma foto.");
      return;
    }

    setLoading(true);
    setErro(null);

    const res = await apiPost<{ task_id: string }>("/api/generate", {
      prompt: prompt || null,
      imagem_base64: imagemBase64 || null,
    });

    if (res.success && res.data) {
      router.push(`/preview?task_id=${res.data.task_id}`);
    } else {
      setErro(res.error || "Erro ao gerar modelo.");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-2xl animate-slideUp">
        <h1 className="text-4xl font-bold mb-2">Criar modelo 3D</h1>
        <p className="text-gray-400 mb-10">
          Descreva o objeto que deseja ou envie uma foto de referência.
        </p>

        {/* Campo de texto */}
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">
            Descreva seu objeto
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ex: Um vaso moderno com formato geométrico e textura de madeira..."
            className="w-full h-32 px-4 py-3 rounded-xl bg-white/[0.05] border border-white/[0.08] text-white placeholder-gray-500 resize-none focus:outline-none focus:border-teal/50 transition-colors"
          />
        </div>

        {/* Sugestões de prompt */}
        <div className="mb-8 flex flex-wrap gap-2">
          {exemplos.map((ex) => (
            <button
              key={ex}
              onClick={() => setPrompt(ex)}
              className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-gray-500 text-xs hover:border-teal/30 hover:text-teal transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>

        {/* Divisor */}
        <div className="flex items-center gap-4 mb-6">
          <div className="flex-1 h-px bg-white/[0.08]" />
          <span className="text-gray-500 text-sm">ou</span>
          <div className="flex-1 h-px bg-white/[0.08]" />
        </div>

        {/* Upload de imagem */}
        <div className="mb-8">
          <label className="block text-sm text-gray-400 mb-2">
            Envie uma foto de referência
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={handleImageUpload}
            className="hidden"
          />
          {imagemPreview ? (
            <div className="relative group">
              <img
                src={imagemPreview}
                alt="Preview"
                className="w-full max-h-64 object-contain rounded-xl border border-white/[0.08]"
              />
              <button
                onClick={() => {
                  setImagemPreview(null);
                  setImagemBase64(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/80 text-white flex items-center justify-center hover:bg-red-500/80 transition-colors opacity-0 group-hover:opacity-100"
              >
                ×
              </button>
            </div>
          ) : (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-12 rounded-xl border-2 border-dashed border-white/[0.08] text-gray-500 hover:border-teal/30 hover:text-teal transition-colors flex flex-col items-center gap-2"
            >
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span className="text-sm">Clique para enviar imagem</span>
              <span className="text-xs text-gray-600">PNG, JPG ou WebP (máx. 10MB)</span>
            </button>
          )}
        </div>

        {/* Erro */}
        {erro && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {erro}
          </div>
        )}

        {/* Botão gerar */}
        <button
          onClick={handleGenerate}
          disabled={loading || (!prompt && !imagemBase64)}
          className="w-full py-4 rounded-2xl bg-gradient-to-r from-teal to-teal-dark text-black font-semibold text-lg hover:shadow-lg hover:shadow-teal/25 hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-3">
              <span className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
              Gerando modelo...
            </span>
          ) : (
            "Gerar modelo 3D"
          )}
        </button>

        {/* Info */}
        <p className="text-center text-gray-600 text-xs mt-4">
          A geração leva entre 30 segundos e 2 minutos dependendo da complexidade.
        </p>
      </div>
    </main>
  );
}
