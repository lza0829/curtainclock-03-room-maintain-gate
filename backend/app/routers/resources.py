from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import connect, transaction

router = APIRouter(tags=["resources"])


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _room_payload(conn, code: str) -> dict:
    """槽位卡片同源视图：rooms 行 + 该槽在途 open 租约数（ leases 表实数）。"""
    row = conn.execute(
        "SELECT code, name, capacity, active, maintenance, maintenance_reason, maintenance_since "
        "FROM rooms WHERE code=?",
        (code,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"算力槽不存在：{code}")
    item = dict(row)
    item["open_leases"] = conn.execute(
        "SELECT COUNT(*) c FROM leases WHERE room_code=? AND status='open'",
        (code,),
    ).fetchone()["c"]
    return item


@router.get("/rooms")
def list_rooms():
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT code FROM rooms ORDER BY code"
        ).fetchall()
        return [_room_payload(conn, r["code"]) for r in rows]
    finally:
        conn.close()


@router.get("/teachers")
def list_teachers():
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT code, name, subject, active FROM teachers ORDER BY code"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class MaintenanceBody(BaseModel):
    reason: str = ""


@router.post("/rooms/{code}/maintenance")
def set_maintenance(code: str, body: MaintenanceBody):
    """挂维护：只写 rooms 行（旗标/原因/起始时刻），不回写在途租约、不动水位。

    与开窗共用 BEGIN IMMEDIATE 事务序列化：维护一旦提交，其后的开窗闸
    经就绪探针同源判拒，不得假启用；已在途 open 租约保持占用至关窗。
    """
    reason = body.reason.strip() or "例行维护"
    with transaction() as conn:
        row = conn.execute(
            "SELECT maintenance, maintenance_since FROM rooms WHERE code=?",
            (code,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"算力槽不存在：{code}")
        # 重复登记只更新原因，保留首次进入维护的时刻
        since = (
            row["maintenance_since"]
            if row["maintenance"] == 1 and row["maintenance_since"]
            else _now()
        )
        conn.execute(
            "UPDATE rooms SET maintenance=1, maintenance_reason=?, maintenance_since=? "
            "WHERE code=?",
            (reason, since, code),
        )
        return {"ok": True, **_room_payload(conn, code)}


@router.post("/rooms/{code}/maintenance/clear")
def clear_maintenance(code: str):
    """结束维护：清旗标/原因/时刻，槽位恢复额定（是否可开窗回到就绪探针常判）。"""
    with transaction() as conn:
        row = conn.execute(
            "SELECT code FROM rooms WHERE code=?", (code,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"算力槽不存在：{code}")
        conn.execute(
            "UPDATE rooms SET maintenance=0, maintenance_reason=NULL, maintenance_since=NULL "
            "WHERE code=?",
            (code,),
        )
        return {"ok": True, **_room_payload(conn, code)}
