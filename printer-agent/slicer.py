"""Wrapper do BambuStudio CLI para fatiar GLB → 3MF."""
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SlicerError(Exception):
    pass


@dataclass
class SliceResult:
    output_path: str
    estimated_weight_g: float | None = None
    estimated_time_min: int | None = None


class Slicer:
    def __init__(self, cli_path: str):
        self.cli = cli_path

    def slice(self, glb_path: str, material: str, output_3mf: str) -> SliceResult:
        """Fatia um GLB em 3MF usando BambuStudio CLI.

        Material esperado: "PLA", "PETG" ou "TPU".
        """
        cmd = [
            self.cli,
            "--export-3mf", output_3mf,
            "--load-filament", material,
            glb_path,
        ]
        logger.info("Slicing: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 min
            )
        except subprocess.CalledProcessError as e:
            raise SlicerError(f"BambuStudio CLI falhou (exit {e.returncode}): {e.stderr[:500]}")
        except subprocess.TimeoutExpired:
            raise SlicerError("BambuStudio CLI passou de 30 min (timeout)")
        except FileNotFoundError:
            raise SlicerError(f"BambuStudio CLI não encontrado: {self.cli}")

        # Parse best-effort de peso/tempo do stdout (formato varia)
        weight = None
        time_min = None
        for line in proc.stdout.splitlines():
            lower = line.lower()
            if "filament used" in lower and "g" in lower:
                try:
                    weight = float(line.split()[-1].rstrip("gG"))
                except (ValueError, IndexError):
                    pass
            if "total time" in lower or "print time" in lower:
                try:
                    time_min = int(line.split()[-1])
                except (ValueError, IndexError):
                    pass

        return SliceResult(
            output_path=output_3mf,
            estimated_weight_g=weight,
            estimated_time_min=time_min,
        )
