# -*- coding: utf-8 -*-
"""维护态核对夹具（对运行中的 API @127.0.0.1:11100）。

全局贯彻「以维护挡新开、在途保留为准」：
- 维护中禁止任何新开窗，拒绝原因与 rooms 行同源落冲突桶；
- 已在途 open 租约保持占用至关窗，水位不因挂维护自动减；
- 维护结束恢复额定；挂维护与开窗并发不得假启用。

核对：维护即拒失败 / 挂维护后旧 open 仍在 / 维护结束恢复额定 /
夹具并发挂维护与开窗。每轮用新批窗码，可重复运行。
"""
from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:11100/api"
RUN = str(int(time.time()))


def call(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"detail": raw}
        return e.code, payload


def new_session(code: str, room: str, teacher: str, start: int, end: int) -> None:
    st, s = call(
        "POST",
        "/sessions",
        {
            "code": code,
            "title": f"维护冒烟 {code}",
            "subject": "ETL",
            "room_code": room,
            "teacher_code": teacher,
            "day": DAY,
            "start_min": start,
            "end_min": end,
        },
    )
    assert st == 200, s


st, dash0 = call("GET", "/dashboard")
assert st == 200, dash0
DAY = dash0["fixture_day"]

# ---------- 核对一：维护即拒失败，登记/就绪/开窗/原因/卡片/总览同源 ----------
slot_a, teacher_a = "S-BI-01", "E-BI-01"
code_a = f"W-MAINT-A-{RUN}"
new_session(code_a, slot_a, teacher_a, 15 * 60, 15 * 60 + 30)

st, m = call("POST", f"/rooms/{slot_a}/maintenance", {"reason": "冒烟：更换散热"})
assert st == 200 and m["maintenance"] == 1, m
assert m["maintenance_reason"] == "冒烟：更换散热", m
expect_reason = "算力槽维护中：冒烟：更换散热"

st, rooms = call("GET", "/rooms")
card = next(r for r in rooms if r["code"] == slot_a)
assert card["maintenance"] == 1 and card["maintenance_reason"] == "冒烟：更换散热", card

st, ready = call("GET", f"/sessions/{code_a}/ready")
assert st == 200 and ready["ready"] is False, ready
assert expect_reason in ready["reasons"], ready

st, rej = call("POST", "/leases/open", {"session_code": code_a})
assert st == 409 and "维护" in json.dumps(rej, ensure_ascii=False), rej

st, conflicts = call("GET", "/conflicts")
hit = [c for c in conflicts if c["session_code"] == code_a and c["kind"] == "maintenance"]
assert hit, conflicts
assert hit[0]["reason"] == expect_reason and hit[0]["resource_code"] == slot_a, hit[0]

st, dash = call("GET", "/dashboard")
assert dash["maintenance_rooms"] >= 1, dash
print("A 维护即拒 + 七环节同源 OK", {"reason": expect_reason})

# ---------- 核对二：挂维护后旧 open 仍在，水位不自动减，在途至关窗 ----------
slot_b, teacher_b = "S-BI-02", "E-BI-02"
code_b = f"W-MAINT-B-{RUN}"
new_session(code_b, slot_b, teacher_b, 15 * 60, 15 * 60 + 30)

st, opened = call("POST", "/leases/open", {"session_code": code_b})
assert st == 200, opened
lease_b, w0 = opened["lease_no"], opened["open_leases"]

st, m2 = call("POST", f"/rooms/{slot_b}/maintenance", {"reason": "冒烟：固件升级"})
assert st == 200 and m2["open_leases"] == 1, m2

st, leases = call("GET", "/leases")
mine = next(l for l in leases if l["lease_no"] == lease_b)
assert mine["status"] == "open" and mine["room_maintenance"] == 1, mine

st, dash = call("GET", "/dashboard")
assert dash["open_leases"] == w0, (dash, w0)

st, closed = call("POST", "/leases/close", {"lease_no": lease_b})
assert st == 200 and closed["open_leases"] == w0 - 1, closed

st, c2 = call("POST", f"/rooms/{slot_b}/maintenance/clear")
assert st == 200 and c2["maintenance"] == 0, c2
print("B 在途保留 + 水位不自动减 OK", {"lease": lease_b})

# ---------- 核对三：维护结束恢复额定 ----------
st, c1 = call("POST", f"/rooms/{slot_a}/maintenance/clear")
assert st == 200 and c1["maintenance"] == 0, c1

st, ready = call("GET", f"/sessions/{code_a}/ready")
assert ready["ready"] is True, ready

st, opened = call("POST", "/leases/open", {"session_code": code_a})
assert st == 200, opened
st, closed = call("POST", "/leases/close", {"lease_no": opened["lease_no"]})
assert st == 200, closed
print("C 维护结束恢复额定 OK", {"slot": slot_a})

# ---------- 核对四：夹具并发挂维护与开窗，不得假启用、在途不改脏 ----------
slot_d, teacher_d = "S-ETL-01", "E-PIPE-01"


def maintainer():
    time.sleep(random.uniform(0, 0.05))
    return call("POST", f"/rooms/{slot_d}/maintenance", {"reason": "冒烟：并发挂维护"})


def opener(c: str):
    time.sleep(random.uniform(0, 0.05))
    return c, call("POST", "/leases/open", {"session_code": c})


saw_opened = saw_rejected = False
for rnd in range(6):
    codes = []
    for i in range(4):
        c = f"W-RACE-{RUN}-{rnd}-{i}"
        new_session(c, slot_d, teacher_d, 11 * 60 + i * 30, 11 * 60 + i * 30 + 30)
        codes.append(c)

    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(maintainer)] + [ex.submit(opener, c) for c in codes]
        results = [f.result() for f in futs]

    st_m, body_m = results[0]
    assert st_m == 200 and body_m["maintenance"] == 1, body_m
    opened_codes = sorted(c for c, (s, _) in results[1:] if s == 200)
    rejected_codes = sorted(c for c, (s, _) in results[1:] if s == 409)
    assert len(opened_codes) + len(rejected_codes) == 4, results
    saw_opened |= bool(opened_codes)
    saw_rejected |= bool(rejected_codes)

    # 维护已挂：未开出的窗再开一律被维护原因拒掉（不得假启用）
    for c in rejected_codes:
        st, rej = call("POST", "/leases/open", {"session_code": c})
        assert st == 409 and "维护" in json.dumps(rej, ensure_ascii=False), (c, rej)

    # 竞速中已开出的租约 = 在途保留：仍 open，不被挂维护改脏
    st, leases = call("GET", "/leases")
    race_open = [l for l in leases if l["session_code"] in opened_codes and l["status"] == "open"]
    assert len(race_open) == len(opened_codes), (opened_codes, leases)

    # 水位与在途实数一致
    st, dash = call("GET", "/dashboard")
    actual_open = sum(1 for l in leases if l["status"] == "open")
    assert dash["open_leases"] == actual_open, (dash, actual_open)

    for l in race_open:
        st, _ = call("POST", "/leases/close", {"lease_no": l["lease_no"]})
        assert st == 200, l
    st, c3 = call("POST", f"/rooms/{slot_d}/maintenance/clear")
    assert st == 200 and c3["maintenance"] == 0, c3
    print(f"D{rnd} 并发挂维护与开窗 OK", {"opened": opened_codes, "rejected": rejected_codes})

assert saw_opened and saw_rejected, "竞速两种时序均应出现"

print("MAINTENANCE_SMOKE_OK")
