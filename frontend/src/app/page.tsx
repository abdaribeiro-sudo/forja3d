"use client";

import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col">
      {/* Hero */}
      <section className="relative flex-1 flex flex-col items-center justify-center px-4 py-24 overflow-hidden">
        <div className="hero-glow" />
        <div className="animate-fadeIn text-center relative z-10">
          <div className="inline-block px-4 py-1.5 rounded-full border border-teal/20 bg-teal/5 text-teal text-sm font-medium mb-8">
            Impressão 3D com inteligência artificial
          </div>
          <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold mb-6 tracking-tight leading-[1.1]">
            Transforme ideias em
            <br />
            <span className="bg-gradient-to-r from-teal to-teal-dark bg-clip-text text-transparent">
              objetos reais
            </span>
          </h1>
          <p className="text-gray-400 text-lg md:text-xl text-center max-w-2xl mb-10 leading-relaxed mx-auto">
            Descreva por texto ou envie uma foto. Nossa IA gera o modelo 3D,
            imprimimos e enviamos para sua casa.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/criar"
              className="inline-block px-10 py-4 rounded-2xl bg-gradient-to-r from-teal to-teal-dark text-black font-semibold text-lg hover:shadow-lg hover:shadow-teal/25 hover:-translate-y-0.5 transition-all duration-300"
            >
              Começar a criar
            </Link>
            <a
              href="#como-funciona"
              className="inline-block px-10 py-4 rounded-2xl border border-white/[0.08] text-gray-300 font-medium text-lg hover:border-white/20 hover:text-white transition-all duration-300"
            >
              Como funciona
            </a>
          </div>
        </div>
      </section>

      {/* Números */}
      <section className="px-4 py-12 border-t border-white/[0.08]">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { valor: "500+", label: "mm/s de velocidade" },
            { valor: "0.1", label: "mm de precisão" },
            { valor: "3", label: "materiais disponíveis" },
            { valor: "24h", label: "tempo médio de envio" },
          ].map((stat) => (
            <div key={stat.label}>
              <p className="text-3xl font-bold font-mono text-teal">{stat.valor}</p>
              <p className="text-gray-500 text-sm mt-1">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Como funciona */}
      <section id="como-funciona" className="px-4 py-20 border-t border-white/[0.08]">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Como funciona</h2>
          <p className="text-gray-400 text-center mb-16 max-w-xl mx-auto">
            Do texto à peça impressa em poucos passos.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                numero: "01",
                titulo: "Descreva",
                descricao:
                  "Digite uma descrição do objeto ou envie uma foto de referência. A IA entende o que você quer.",
                icone: "M12 20h9 M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z",
              },
              {
                numero: "02",
                titulo: "Visualize",
                descricao:
                  "Veja o modelo 3D gerado, gire, amplie. Escolha material, ajuste a escala e veja o preço atualizar.",
                icone: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8zm0 0 M12 12m-3 0a3 3 0 1 0 6 0 3 3 0 1 0-6 0",
              },
              {
                numero: "03",
                titulo: "Receba",
                descricao:
                  "Pague por PIX ou cartão. Imprimimos na Bambu Lab X1 Carbon e enviamos pelos Correios.",
                icone: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z",
              },
            ].map((step) => (
              <div
                key={step.numero}
                className="p-6 rounded-2xl border border-white/[0.08] bg-white/[0.02] card-hover"
              >
                <span className="font-mono text-teal text-sm">{step.numero}</span>
                <h3 className="text-xl font-bold mt-3 mb-3">{step.titulo}</h3>
                <p className="text-gray-400 leading-relaxed text-sm">{step.descricao}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Materiais */}
      <section className="px-4 py-20 border-t border-white/[0.08]">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Materiais</h2>
          <p className="text-gray-400 text-center mb-16 max-w-xl mx-auto">
            Escolha o material ideal para o seu projeto.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                nome: "PLA",
                preco: "R$ 0,10/g",
                desc: "Rígido e com acabamento liso. Ideal para peças decorativas e protótipos.",
                temp: "190-220°C",
                destaque: "Mais popular",
              },
              {
                nome: "PETG",
                preco: "R$ 0,11/g",
                desc: "Resistente e flexível. Boa opção para peças funcionais e uso diário.",
                temp: "220-250°C",
                destaque: "Mais resistente",
              },
              {
                nome: "TPU",
                preco: "R$ 0,18/g",
                desc: "Flexível como borracha. Perfeito para capas, solas e peças elásticas.",
                temp: "210-230°C",
                destaque: "Flexível",
              },
            ].map((mat) => (
              <div
                key={mat.nome}
                className="p-6 rounded-2xl border border-white/[0.08] bg-white/[0.02] card-hover"
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-xl font-bold">{mat.nome}</h3>
                    <span className="text-xs text-gray-500">{mat.destaque}</span>
                  </div>
                  <span className="font-mono text-teal text-sm">{mat.preco}</span>
                </div>
                <p className="text-gray-400 leading-relaxed text-sm mb-3">{mat.desc}</p>
                <p className="text-xs text-gray-500">
                  Temperatura: <span className="font-mono">{mat.temp}</span>
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 py-20 border-t border-white/[0.08]">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">Pronto para criar?</h2>
          <p className="text-gray-400 mb-8">
            Comece agora e receba sua peça impressa em 3D no conforto da sua casa.
          </p>
          <Link
            href="/criar"
            className="inline-block px-10 py-4 rounded-2xl bg-gradient-to-r from-teal to-teal-dark text-black font-semibold text-lg hover:shadow-lg hover:shadow-teal/25 hover:-translate-y-0.5 transition-all duration-300"
          >
            Criar meu modelo 3D
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-4 py-8 border-t border-white/[0.08]">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-gray-500 text-sm">
            FORJA<span className="text-teal">3D</span> — Impressão 3D sob demanda
          </p>
          <div className="flex gap-6 text-sm text-gray-500">
            <span>Bambu Lab X1 Carbon</span>
            <span>PLA / PETG / TPU</span>
            <span>Envio para todo Brasil</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
