import Link from "next/link";

export default function NotFound() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <p className="font-mono text-teal text-7xl font-bold mb-4">404</p>
      <h1 className="text-2xl font-bold mb-2">Página não encontrada</h1>
      <p className="text-gray-400 mb-8">
        A página que você procura não existe ou foi removida.
      </p>
      <Link
        href="/"
        className="px-6 py-3 rounded-xl bg-gradient-to-r from-teal to-teal-dark text-black font-semibold hover:shadow-lg hover:shadow-teal/25 transition-all"
      >
        Voltar ao início
      </Link>
    </main>
  );
}
