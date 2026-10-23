"""秒杀活动时间边界造数（E-04 / E-05 / E-06）。

用法:
  python output/seckill_time_boundary_upcoming.py
  python -c "from seckill_time_boundary_lib import seed; seed('active')"
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

PROFILES: dict[str, dict[str, Any]] = {
    "upcoming": {
        "start_offset_sec": 2,
        "end_offset_sec": 3600,
        "status": "UPCOMING",
        "prepare_stock": False,
    },
    "active": {
        "start_offset_sec": 2,
        "end_offset_sec": 3600,
        "status": "ACTIVE",
        "prepare_stock": True,
    },
    "ended": {
        "start_offset_sec": -3600,
        "end_offset_sec": -2,
        "status": "ENDED",
        "prepare_stock": False,
    },
}


def engine_root() -> Path:
    return Path(__file__).resolve().parent.parent


def output_dir() -> Path:
    d = engine_root() / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def base_url() -> str:
    return os.environ.get("TEST_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


def _iso_local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def post_json(
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> requests.Response:
    url = base_url() + path
    hdr = {"Content-Type": "application/json"}
    if headers:
        hdr.update(headers)
    return requests.post(url, json=json_body, headers=hdr, timeout=timeout)


def get_json(path: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> requests.Response:
    url = base_url() + path
    hdr = {"Content-Type": "application/json"}
    if headers:
        hdr.update(headers)
    return requests.get(url, headers=hdr, timeout=timeout)


def init_test_env() -> None:
    init_path = os.environ.get("TEST_INIT_PATH", "/api/test/init")
    if not init_path.startswith("/"):
        init_path = "/" + init_path
    body_raw = os.environ.get("TEST_INIT_BODY")
    body = json.loads(body_raw) if body_raw else {}
    r = post_json(init_path, json_body=body or None)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"test/init failed: {r.status_code} {r.text[:500]}")


def login(username: str, password: str) -> str:
    r = post_json(
        "/api/auth/login",
        json_body={"username": username, "password": password},
    )
    if r.status_code != 200:
        raise RuntimeError(f"login failed ({username}): {r.status_code} {r.text[:300]}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if not token and isinstance(data.get("data"), dict):
        token = data["data"].get("token") or data["data"].get("access_token")
    if not token:
        raise RuntimeError(f"login response missing token: {data}")
    return str(token)


def admin_token() -> str:
    user = os.environ.get("TEST_USERNAME", "admin")
    pwd = os.environ.get("TEST_PASSWORD", "admin123")
    return login(user, pwd)


def customer_token() -> str:
    user = os.environ.get("TEST_CUSTOMER_USERNAME", "customer_01")
    pwd = os.environ.get("TEST_CUSTOMER_PASSWORD", "pass1234")
    return login(user, pwd)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_product(admin_h: dict[str, str], *, suffix: str | None = None) -> int:
    tag = suffix or str(int(time.time()))
    r = post_json(
        "/api/products",
        json_body={
            "name": f"秒杀时间边界-{tag}",
            "description": "seckill_time_boundary_lib",
            "price": 19.9,
            "stock": 100,
        },
        headers=admin_h,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"create product failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    pid = data.get("id")
    if pid is None and isinstance(data.get("data"), dict):
        pid = data["data"].get("id")
    if pid is None:
        raise RuntimeError(f"create product missing id: {data}")
    return int(pid)


def create_activity(
    admin_h: dict[str, str],
    *,
    start_offset_sec: int,
    end_offset_sec: int,
    status: str,
    name_suffix: str,
) -> int:
    now = datetime.now()
    start = _iso_local(now + timedelta(seconds=start_offset_sec))
    end = _iso_local(now + timedelta(seconds=end_offset_sec))
    r = post_json(
        "/api/seckill/activities",
        json_body={
            "name": f"时间边界-{name_suffix}-{int(time.time())}",
            "start_time": start,
            "end_time": end,
            "status": status,
        },
        headers=admin_h,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"create activity failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    aid = data.get("id")
    if aid is None:
        raise RuntimeError(f"create activity missing id: {data}")
    return int(aid)


def link_product(
    admin_h: dict[str, str],
    activity_id: int,
    product_id: int,
    *,
    seckill_stock: int = 10,
) -> None:
    r = post_json(
        f"/api/seckill/activities/{activity_id}/products",
        json_body={
            "product_id": product_id,
            "seckill_price": 9.9,
            "seckill_stock": seckill_stock,
            "seckill_limit": 1,
        },
        headers=admin_h,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"link product failed: {r.status_code} {r.text[:300]}")


def prepare_stock(admin_h: dict[str, str], activity_id: int) -> None:
    r = post_json(
        f"/api/seckill/activities/{activity_id}/prepare-stock",
        headers=admin_h,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"prepare-stock failed: {r.status_code} {r.text[:300]}")


def write_seed_files(
    *,
    profile: str,
    activity_id: int,
    product_id: int,
    start_offset_sec: int,
    end_offset_sec: int,
    status: str,
) -> dict[str, Any]:
    payload = {
        "profile": profile,
        "activity_id": activity_id,
        "product_id": product_id,
        "start_offset_sec": start_offset_sec,
        "end_offset_sec": end_offset_sec,
        "status": status,
        "base_url": base_url(),
    }
    out = output_dir()
    (out / "test_seed.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    env_lines = [
        f"SECKILL_TIME_PROFILE={profile}",
        f"ACTIVITY_ID={activity_id}",
        f"PRODUCT_ID={product_id}",
        f"SECKILL_ACTIVITY_ID={activity_id}",
        f"SECKILL_PRODUCT_ID={product_id}",
    ]
    (out / "test_seed.env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    for line in env_lines:
        key, _, val = line.partition("=")
        os.environ[key] = val
    return payload


def seed(profile: str = "upcoming") -> dict[str, Any]:
    """造数并写入 output/test_seed.env + test_seed.json。"""
    cfg = PROFILES.get(profile)
    if not cfg:
        raise ValueError(f"unknown profile: {profile!r}, expected one of {list(PROFILES)}")

    init_test_env()
    admin_h = bearer(admin_token())
    product_id = create_product(admin_h, suffix=profile)
    activity_id = create_activity(
        admin_h,
        start_offset_sec=int(cfg["start_offset_sec"]),
        end_offset_sec=int(cfg["end_offset_sec"]),
        status=str(cfg["status"]),
        name_suffix=profile,
    )
    link_product(admin_h, activity_id, product_id)
    if cfg.get("prepare_stock"):
        prepare_stock(admin_h, activity_id)

    result = write_seed_files(
        profile=profile,
        activity_id=activity_id,
        product_id=product_id,
        start_offset_sec=int(cfg["start_offset_sec"]),
        end_offset_sec=int(cfg["end_offset_sec"]),
        status=str(cfg["status"]),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def seckill_order(activity_id: int, product_id: int, *, customer: bool = True) -> requests.Response:
    token = customer_token() if customer else admin_token()
    return post_json(
        f"/api/seckill/{activity_id}/{product_id}",
        headers=bearer(token),
    )


def get_activity(activity_id: int) -> dict[str, Any]:
    r = get_json(f"/api/seckill/activities/{activity_id}")
    if r.status_code != 200:
        raise RuntimeError(f"get activity failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":
    prof = sys.argv[1] if len(sys.argv) > 1 else "upcoming"
    seed(prof)
