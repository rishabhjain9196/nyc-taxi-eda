"""Download the 2023 NYC yellow taxi trip records and the taxi zone shapefile."""

from pathlib import Path
import urllib.request
import zipfile

BASE_URL = "https://d37ci6vzurychx.cloudfront.net"
ROOT = Path(__file__).resolve().parents[1]
TRIPS_DIR = ROOT / "data" / "raw" / "trip_records"
ZONES_DIR = ROOT / "data" / "raw" / "taxi_zones"


def download(url: str, target: Path) -> None:
    if target.exists():
        print(f"Already present: {target.name}")
        return
    temp = target.with_suffix(target.suffix + ".part")
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, temp)
    temp.rename(target)


def main() -> None:
    TRIPS_DIR.mkdir(parents=True, exist_ok=True)
    ZONES_DIR.mkdir(parents=True, exist_ok=True)

    for month in range(1, 13):
        name = f"yellow_tripdata_2023-{month:02d}.parquet"
        download(f"{BASE_URL}/trip-data/{name}", TRIPS_DIR / name)

    archive = ZONES_DIR.parent / "taxi_zones.zip"
    download(f"{BASE_URL}/misc/taxi_zones.zip", archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(ZONES_DIR.parent)
    print("Done.")


if __name__ == "__main__":
    main()
