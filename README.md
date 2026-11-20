# Curtainclock（幕窗钟）

骨架：**批窗定义 → 算力槽/执行器资源依赖就绪 → 开窗租约占用 → 关窗释放与冲突水位互证**

- 前端：http://127.0.0.1:6100 （React + Vite）
- API：http://127.0.0.1:11100

## 维护态口径（全局贯彻一种）

算力槽维护采「**以维护挡新开、在途保留为准**」：

- 维护中禁止任何新开窗；就绪探针、开窗闸、冲突落库的原因均取自 `rooms` 行同源（`算力槽维护中：<原因>`）。
- 已存在的 open 租约保持占用至关窗，挂维护不回写在途租约、水位不因挂维护自动减。
- 维护结束（`POST /api/rooms/{code}/maintenance/clear`）恢复额定，可否开窗回到就绪探针常判。
- 挂维护（`POST /api/rooms/{code}/maintenance`）与开窗共用 `BEGIN IMMEDIATE` 事务序列化，并发不得假启用。
- 维护登记、就绪、开窗、在途租约、原因记录、槽位卡片、总览（`maintenance_rooms`）七环节同源于 `rooms` 行。

## 本地冒烟（推荐）

```powershell
cd D:\Asolo11\claude-workspace\curtainclock\source
# 本机若无 3.11：py -V:Astral/CPython3.11.15 -m venv .venv
py -V:Astral/CPython3.11.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
$env:PYTHONPATH = "$PWD\backend"
Start-Process .\.venv\Scripts\uvicorn.exe -ArgumentList 'app.main:app','--host','127.0.0.1','--port','11100' -WorkingDirectory "$PWD\backend"
cd frontend
# 前端需 Node ≥18；不足时用 docker compose 起 web
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:6100 ：开一节课 → 同算力槽冲突 → 关窗释放。

维护核对（API 运行中执行）：`python _smoke_maintenance.py` —— 维护即拒、在途保留、结束恢复额定、并发挂维护与开窗。

## Docker

```powershell
docker compose up -d --build
```
