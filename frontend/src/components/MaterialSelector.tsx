"use client";

interface MaterialSelectorProps {
  selected: string;
  onSelect: (material: string) => void;
}

const materiais = [
  { id: "PLA", nome: "PLA", preco: "R$ 0,10/g", descricao: "Rígido, acabamento liso" },
  { id: "PETG", nome: "PETG", preco: "R$ 0,11/g", descricao: "Resistente, flexível" },
  { id: "TPU", nome: "TPU", preco: "R$ 0,18/g", descricao: "Flexível, borrachudo" },
];

export default function MaterialSelector({ selected, onSelect }: MaterialSelectorProps) {
  return (
    <div className="flex flex-col gap-3">
      <h3 className="font-semibold">Material</h3>
      {materiais.map((mat) => (
        <button
          key={mat.id}
          onClick={() => onSelect(mat.id)}
          className={`p-4 rounded-xl border text-left transition-all ${
            selected === mat.id
              ? "border-teal bg-teal/10"
              : "border-white/[0.08] hover:border-white/20"
          }`}
        >
          <div className="flex justify-between">
            <span className="font-medium">{mat.nome}</span>
            <span className="font-mono text-sm text-teal">{mat.preco}</span>
          </div>
          <p className="text-sm text-gray-400 mt-1">{mat.descricao}</p>
        </button>
      ))}
    </div>
  );
}
