"""Serve the HatKalkani API and the static web/ folder (offline, no network calls)."""

from __future__ import annotations

import argparse

import uvicorn

from hatkalkani.api import create_app


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--aoi", default=None, help="AOI id (default: config/aoi.yaml selected)")
    args = p.parse_args()
    app = create_app(aoi_id=args.aoi)
    store = app.state.store
    print(f"AOI {store.aoi_id}; as_of {store.as_ofs}; http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
