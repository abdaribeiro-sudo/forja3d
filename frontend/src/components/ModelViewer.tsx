"use client";

import { useEffect, useRef } from "react";

interface ModelViewerProps {
  src: string;
  alt?: string;
}

export default function ModelViewer({ src, alt = "Modelo 3D" }: ModelViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Cria o model-viewer via DOM para evitar problemas de tipagem
    if (!containerRef.current) return;
    const existing = containerRef.current.querySelector("model-viewer");
    if (existing) existing.remove();

    const viewer = document.createElement("model-viewer");
    viewer.setAttribute("src", src);
    viewer.setAttribute("alt", alt);
    viewer.setAttribute("auto-rotate", "");
    viewer.setAttribute("camera-controls", "");
    viewer.setAttribute("shadow-intensity", "1");
    viewer.setAttribute("environment-image", "neutral");
    viewer.setAttribute("tone-mapping", "commerce");
    viewer.style.width = "100%";
    viewer.style.height = "100%";
    viewer.style.backgroundColor = "transparent";
    containerRef.current.appendChild(viewer);
  }, [src, alt]);

  return (
    <div
      ref={containerRef}
      className="w-full aspect-square rounded-2xl border border-white/[0.08] overflow-hidden bg-black/50"
    />
  );
}
