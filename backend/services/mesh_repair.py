import asyncio
import trimesh
import numpy as np


class MeshRepairService:
    """Reparo de malha 3D com trimesh."""

    # Densidades em g/cm³
    DENSIDADES = {
        "PLA": 1.24,
        "PETG": 1.27,
        "TPU": 1.21,
    }

    async def repair(self, input_path: str, output_path: str) -> dict:
        """
        Repara malha GLB: fix_normals, fill_holes, watertight check.
        Retorna dict com volume_cm3, is_watertight e bounding_box.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._repair_sync, input_path, output_path)

    def _repair_sync(self, input_path: str, output_path: str) -> dict:
        scene = trimesh.load(input_path)

        # Se for uma cena com múltiplas meshes, combina em uma só
        if isinstance(scene, trimesh.Scene):
            mesh = scene.dump(concatenate=True)
        else:
            mesh = scene

        # Reparos
        trimesh.repair.fix_normals(mesh)
        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_winding(mesh)

        # Métricas (volume em cm³, assumindo unidades em mm do GLB)
        volume_mm3 = abs(mesh.volume) if mesh.is_watertight else abs(mesh.convex_hull.volume)
        volume_cm3 = volume_mm3 / 1000.0  # mm³ → cm³

        bounding_box = mesh.bounding_box.extents.tolist()  # [x, y, z] em mm

        # Salva arquivo reparado
        mesh.export(output_path)

        return {
            "volume_cm3": round(volume_cm3, 2),
            "is_watertight": mesh.is_watertight,
            "bounding_box_mm": [round(d, 1) for d in bounding_box],
        }

    def estimate_weight(self, volume_cm3: float, material: str) -> float:
        """Estima peso em gramas baseado no volume e densidade do material."""
        densidade = self.DENSIDADES.get(material, 1.24)
        # Infill de ~20% típico
        return round(volume_cm3 * densidade * 0.20, 1)

    def estimate_print_time(self, volume_cm3: float) -> float:
        """Estima tempo de impressão em horas (aproximação simples)."""
        # ~10 cm³/h para velocidade média da X1 Carbon
        return round(max(volume_cm3 / 10.0, 0.5), 1)

    def check_dimensions(self, bounding_box_mm: list[float], escala: float = 1.0) -> bool:
        """Verifica se cabe no volume da X1 Carbon (256x256x256mm)."""
        max_dim = 256.0
        return all(d * escala <= max_dim for d in bounding_box_mm)


mesh_service = MeshRepairService()
