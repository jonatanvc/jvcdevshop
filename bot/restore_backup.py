import argparse
import asyncio
from pathlib import Path

from bot.services.backup_service import backup_service


async def restore(path: Path) -> None:
    with path.open("rb") as backup_file:
        counts = await backup_service.restore_backup_file(backup_file)
    total = sum(counts.values())
    print(f"Restauración completada: {total} filas en {len(counts)} tablas.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaura un backup cifrado en una base de datos vacía.")
    parser.add_argument("backup", type=Path, help="Ruta al archivo .json.gz.enc")
    args = parser.parse_args()
    asyncio.run(restore(args.backup))


if __name__ == "__main__":
    main()
