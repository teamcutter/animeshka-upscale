"""Push a folder of images through the running app in 2K and 4K (Sprint 5, S5-1 / Sprint 6 data).

Every upload becomes a job; the worker stores PSNR / SSIM / sharpness in the `metrics` table,
and export_features.sql then turns them into the training CSV for qop_regression.py.

    docker compose up --build                      # in another terminal
    python analytics/run_dataset.py path/to/images --modes 2k 4k

Only the standard library is used. Images must be <= 2048x2048 and <= 10 MB (app limits);
the server rejects larger ones and the script just reports them.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
import uuid
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.http = build_opener(HTTPCookieProcessor(CookieJar()))

    def call(self, method: str, path: str, body: bytes | None = None, ctype: str | None = None):
        req = Request(self.base + path, data=body, method=method)
        if ctype:
            req.add_header("Content-Type", ctype)
        with self.http.open(req, timeout=120) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None

    def json(self, method: str, path: str, payload: dict):
        return self.call(method, path, json.dumps(payload).encode(), "application/json")

    def login(self, email: str, password: str, name: str) -> None:
        try:
            self.json("POST", "/api/auth/login", {"email": email, "password": password})
        except HTTPError:
            self.json(
                "POST", "/api/auth/register", {"email": email, "password": password, "name": name}
            )

    def upload(self, path: Path, mode: str, max_size: int) -> dict:
        boundary = uuid.uuid4().hex
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="mode"\r\n\r\n{mode}\r\n',
            f'--{boundary}\r\nContent-Disposition: form-data; name="max_size"\r\n\r\n{max_size}\r\n',
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"'
            f"\r\nContent-Type: {ctype}\r\n\r\n",
        ]
        body = "".join(parts).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        return self.call("POST", "/api/upscale", body, f"multipart/form-data; boundary={boundary}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--modes", nargs="+", default=["2k", "4k"], choices=["2k", "4k"])
    ap.add_argument("--max-size", type=int, default=2048, help="output long side limit")
    ap.add_argument("--email", default="dataset@animeshka.local")
    ap.add_argument("--password", default="dataset-runs-2026")
    ap.add_argument("--wait", action="store_true", help="wait until every job is finished")
    args = ap.parse_args()

    files = sorted(p for p in args.folder.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS)
    if not files:
        raise SystemExit(f"No images in {args.folder}")
    client = Client(args.api)
    client.login(args.email, args.password, "Dataset runner")

    jobs, rejected = [], []
    for path in files:
        for mode in args.modes:
            try:
                job = client.upload(path, mode, args.max_size)
            except HTTPError as exc:
                rejected.append((path.name, mode, exc.code, exc.read().decode(errors="replace")))
                continue
            jobs.append(job["id"])
            print(f"queued {path.name:<40} {mode}  job {job['id']}")
    for name, mode, code, detail in rejected:
        print(f"REJECTED {name} {mode}: HTTP {code} {detail[:120]}")
    print(f"{len(jobs)} jobs queued, {len(rejected)} rejected")

    if args.wait and jobs:
        pending = set(jobs)
        while pending:
            time.sleep(3)
            for job_id in list(pending):
                status = client.call("GET", f"/api/jobs/{job_id}")["status"]
                if status in ("done", "failed"):
                    pending.discard(job_id)
            print(f"waiting: {len(pending)} left")
        print("all jobs finished; now run export_features.sql")


if __name__ == "__main__":
    main()
