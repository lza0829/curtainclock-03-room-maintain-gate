import { useEffect, useState } from "react";
import { api } from "../api";

export default function Resources() {
  const [rooms, setRooms] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState("");
  const [reason, setReason] = useState("");

  async function load() {
    const [r, t] = await Promise.all([api.rooms(), api.teachers()]);
    setRooms(r);
    setTeachers(t);
  }

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, []);

  async function setMaint(code) {
    setMsg("");
    setErr("");
    try {
      const r = await api.setRoomMaintenance(code, reason);
      setMsg(
        `已挂维护：${r.code}（${r.maintenance_reason}）；在途租约 ${r.open_leases} 保持占用`
      );
      setEditing("");
      setReason("");
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function clearMaint(code) {
    setMsg("");
    setErr("");
    try {
      const r = await api.clearRoomMaintenance(code);
      setMsg(`已结束维护：${r.code}，恢复额定开窗`);
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  if (err && rooms.length === 0) return <div className="msg err">{err}</div>;

  return (
    <>
      <section className="panel">
        <h2>算力槽</h2>
        {msg && <div className="msg">{msg}</div>}
        {err && <div className="msg err">{err}</div>}
        <table>
          <thead>
            <tr>
              <th>编码</th>
              <th>名称</th>
              <th>容量</th>
              <th>在途租约</th>
              <th>状态</th>
              <th>维护登记</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rooms.map((r) => (
              <tr key={r.code}>
                <td>{r.code}</td>
                <td>{r.name}</td>
                <td>{r.capacity}</td>
                <td>{r.open_leases}</td>
                <td>
                  {r.maintenance ? (
                    <span className="tag maint">维护中</span>
                  ) : r.active ? (
                    "启用"
                  ) : (
                    "停用"
                  )}
                </td>
                <td>
                  {r.maintenance ? (
                    <>
                      {r.maintenance_reason}
                      <br />
                      <small>自 {r.maintenance_since}</small>
                    </>
                  ) : editing === r.code ? (
                    <span className="row-actions">
                      <input
                        className="reason"
                        placeholder="维护原因"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      />
                      <button onClick={() => setMaint(r.code)}>确认</button>
                      <button
                        className="secondary"
                        onClick={() => {
                          setEditing("");
                          setReason("");
                        }}
                      >
                        取消
                      </button>
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  {r.maintenance ? (
                    <button
                      className="secondary"
                      onClick={() => clearMaint(r.code)}
                    >
                      结束维护
                    </button>
                  ) : (
                    editing !== r.code && (
                      <button
                        className="secondary"
                        onClick={() => {
                          setEditing(r.code);
                          setReason("");
                        }}
                      >
                        挂维护
                      </button>
                    )
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>执行器</h2>
        <table>
          <thead>
            <tr>
              <th>编码</th>
              <th>姓名</th>
              <th>作业类型</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {teachers.map((t) => (
              <tr key={t.code}>
                <td>{t.code}</td>
                <td>{t.name}</td>
                <td>{t.subject}</td>
                <td>{t.active ? "启用" : "停用"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
