import asyncio
import io
import os

import trimesh
import numpy as np


class MeshRepairService:
    """Reparo de malha 3D com trimesh."""

    DENSIDADES = {
        "PLA": 1.24,
        "PETG": 1.27,
        "TPU": 1.21,
    }

    async def repair_from_bytes(self, glb_bytes: bytes) -> tuple[bytes, dict]:
        """
        Repara malha GLB a partir de bytes em memória.
        Retorna (glb_reparado_bytes, mesh_info).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._repair_bytes_sync, glb_bytes)

    async def repair(self, input_path: str, output_path: str) -> dict:
        """Repara malha GLB de arquivo para arquivo."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._repair_file_sync, input_path, output_path)

    def _load_mesh(self, data):
        """Carrega e combina meshes de uma cena ou mesh única."""
        if isinstance(data, trimesh.Scene):
            return data.dump(concatenate=True)
        return data

    def _get_metrics(self, mesh) -> dict:
        """Extrai métricas da malha."""
        volume_mm3 = abs(mesh.volume) if mesh.is_watertight else abs(mesh.convex_hull.volume)
        volume_cm3 = volume_mm3 / 1000.0
        bounding_box = mesh.bounding_box.extents.tolist()

        return {
            "volume_cm3": round(volume_cm3, 2),
            "is_watertight": mesh.is_watertight,
            "bounding_box_mm": [round(d, 1) for d in bounding_box],
        }

    def _repair_mesh(self, mesh):
        """Aplica reparos na malha."""
        trimesh.repair.fix_normals(mesh)
        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_winding(mesh)
        return mesh

    def _repair_bytes_sync(self, glb_bytes: bytes) -> tuple[bytes, dict]:
        scene = trimesh.load(io.BytesIO(glb_bytes), file_type="glb")
        mesh = self._load_mesh(scene)
        mesh = self._repair_mesh(mesh)
        metrics = self._get_metrics(mesh)

        output = io.BytesIO()
        mesh.export(output, file_type="glb")
        return output.getvalue(), metrics

    def _repair_file_sync(self, input_path: str, output_path: str) -> dict:
        scene = trimesh.load(input_path)
        mesh = self._load_mesh(scene)
        mesh = self._repair_mesh(mesh)
        metrics = self._get_metrics(mesh)
        mesh.export(output_path)
        return metrics

    def estimate_weight(self, volume_cm3: float, material: str) -> float:
        """Estima peso em gramas baseado no volume e densidade do material."""
        densidade = self.DENSIDADES.get(material, 1.24)
        return round(volume_cm3 * densidade * 0.20, 1)

    def estimate_print_time(self, volume_cm3: float) -> float:
        """Estima tempo de impressão em horas."""
        return round(max(volume_cm3 / 10.0, 0.5), 1)

    def check_dimensions(self, bounding_box_mm: list[float], escala: float = 1.0) -> bool:
        """Verifica se cabe no volume da X1 Carbon (256x256x256mm)."""
        return all(d * escala <= 256.0 for d in bounding_box_mm)


mesh_service = MeshRepairService()
