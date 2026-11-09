import { useEffect, useState } from "react";
import { api } from "./api.js";

function useLoad(path) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const reload = async () => {
    const r = await api(path);
    setState({ loading: false, data: r.ok ? r.data : null, error: r.ok ? null : r.data?.detail });
  };
  useEffect(() => { reload(); }, [path]);
  return [state, reload];
}

const fmt = (d) => new Date(d).toLocaleString();
const Status = ({ s }) => <span className={`pill ${s}`}>{s === "published" ? "Published" : "Pending approval"}</span>;

// ------------------------------------------------------------- Student
export function StudentGrades() {
  const [{ loading, data, error }] = useLoad("/grades/mine/");
  if (loading) return <p>Loading…</p>;
  if (error) return <div className="alert error">{error}</div>;
  return (
    <section>
      <h2>My Grades</h2>
      <p className="hint">Only grades approved by the Registrar appear here.</p>
      <table>
        <thead><tr><th>Course</th><th>Title</th><th>Score</th><th>Grade</th></tr></thead>
        <tbody>{data.map((g) => (
          <tr key={g.id}><td>{g.course_code}</td><td>{g.course_title}</td>
            <td>{g.score}</td><td><strong>{g.letter}</strong></td></tr>))}
        </tbody>
      </table>
    </section>
  );
}

// ---------------------------------------------- Lecturer / Registrar view
export function LecturerCourses({ role }) {
  const [{ data: courses }] = useLoad("/courses/");
  const [selected, setSelected] = useState(null);
  if (!courses) return <p>Loading…</p>;
  return (
    <section>
      <h2>{role === "lecturer" ? "My Courses" : "All Courses"}</h2>
      {role === "lecturer" && <p className="hint">You can only see and edit the courses you teach.
        Every change goes to the Registrar for approval.</p>}
      <div className="course-list">
        {courses.map((c) => (
          <button key={c.id} className={`course ${selected === c.id ? "active" : ""}`} onClick={() => setSelected(c.id)}>
            <strong>{c.code}</strong><span>{c.title}</span><small>{c.lecturer}</small>
          </button>))}
      </div>
      {selected && <CourseGrades id={selected} editable={role === "lecturer"} />}
    </section>
  );
}

function CourseGrades({ id, editable }) {
  const [{ data, error }, reload] = useLoad(`/courses/${id}/grades/`);
  const [edits, setEdits] = useState({});
  const [msg, setMsg] = useState(null);
  if (error) return <div className="alert error">{error}</div>;
  if (!data) return <p>Loading…</p>;

  async function save(g) {
    const r = await api(`/grades/${g.id}/`, { method: "PATCH", body: { score: edits[g.id] } });
    setMsg(r.ok ? { kind: "ok", text: `${g.student}: saved as ${r.data.score} — sent to Registrar for approval.` }
                : { kind: "error", text: r.data?.detail });
    if (r.ok) { setEdits({ ...edits, [g.id]: undefined }); reload(); }
  }

  return (
    <div className="card">
      <h3>{data.course.code} — {data.course.title}</h3>
      {msg && <div className={`alert ${msg.kind}`}>{msg.text}</div>}
      <table>
        <thead><tr><th>Reg. No.</th><th>Student</th><th>Score</th><th>Grade</th><th>Status</th>{editable && <th></th>}</tr></thead>
        <tbody>{data.grades.map((g) => (
          <tr key={g.id}>
            <td>{g.reg_number}</td><td>{g.student}</td>
            <td>{editable
              ? <input className="score" type="number" min="0" max="100"
                       value={edits[g.id] ?? g.score ?? ""} onChange={(e) => setEdits({ ...edits, [g.id]: e.target.value })} />
              : g.score}</td>
            <td>{g.letter}</td><td><Status s={g.status} /></td>
            {editable && <td><button className="small" disabled={edits[g.id] === undefined} onClick={() => save(g)}>Save</button></td>}
          </tr>))}
        </tbody>
      </table>
    </div>
  );
}

// ----------------------------------------------------------- Registrar
export function PendingApprovals() {
  const [{ data }, reload] = useLoad("/grades/pending/");
  const [msg, setMsg] = useState(null);
  if (!data) return <p>Loading…</p>;
  async function approve(g) {
    const r = await api(`/grades/${g.id}/approve/`, { method: "POST" });
    setMsg(r.ok ? { kind: "ok", text: `Approved ${g.course_code} for ${g.student}.` } : { kind: "error", text: r.data?.detail });
    reload();
  }
  return (
    <section>
      <h2>Pending Grade Approvals</h2>
      <p className="hint">Separation of duties: lecturers enter marks, but only the Registrar can publish them.</p>
      {msg && <div className={`alert ${msg.kind}`}>{msg.text}</div>}
      {data.length === 0 ? <p className="empty">No grades waiting for approval.</p> : (
        <table>
          <thead><tr><th>Course</th><th>Student</th><th>New score</th><th>Grade</th><th>Entered by</th><th></th></tr></thead>
          <tbody>{data.map((g) => (
            <tr key={g.id}><td>{g.course_code}</td><td>{g.student}</td><td>{g.score}</td><td>{g.letter}</td>
              <td>{g.entered_by}</td><td><button className="small" onClick={() => approve(g)}>Approve</button></td></tr>))}
          </tbody>
        </table>)}
    </section>
  );
}

export function IntegrityCheck() {
  const [result, setResult] = useState(null);
  async function run() { const r = await api("/grades/integrity/"); setResult(r.data); }
  return (
    <section>
      <h2>Grade Integrity Check</h2>
      <p className="hint">Every grade carries an HMAC-SHA256 signature. If someone edits the database
        directly, the signature no longer matches and the record is flagged.</p>
      <button onClick={run}>Run integrity check</button>
      {result && (result.tampered.length === 0
        ? <div className="alert ok">✅ All {result.checked} grade records are intact.</div>
        : <>
            <div className="alert locked">⚠️ {result.tampered.length} of {result.checked} records have been tampered with!</div>
            <table>
              <thead><tr><th>Course</th><th>Student</th><th>Score in database</th></tr></thead>
              <tbody>{result.tampered.map((g) => (
                <tr key={g.id} className="bad"><td>{g.course_code}</td><td>{g.student} ({g.reg_number})</td><td>{g.score}</td></tr>))}
              </tbody>
            </table>
          </>)}
    </section>
  );
}

// --------------------------------------------------------------- Audit
const SEVERITY = { ACCOUNT_LOCKED: "high", LOGIN_BLOCKED: "high", INTEGRITY_FAIL: "high",
  ACCESS_DENIED: "med", LOGIN_FAILED: "med", PASSWORD_CHANGE_FAILED: "med" };

export function AuditLog() {
  const [{ data }, reload] = useLoad("/audit/");
  if (!data) return <p>Loading…</p>;
  return (
    <section>
      <div className="row"><h2>Audit Log</h2><button className="ghost" onClick={reload}>Refresh</button></div>
      <p className="hint">Append-only record of every security event (latest 200).</p>
      <table className="audit">
        <thead><tr><th>Time</th><th>User</th><th>Role</th><th>Event</th><th>Detail</th><th>IP</th></tr></thead>
        <tbody>{data.map((e, i) => (
          <tr key={i} className={SEVERITY[e.action] || ""}>
            <td>{fmt(e.timestamp)}</td><td>{e.username}</td><td>{e.role}</td>
            <td><code>{e.action}</code></td><td>{e.detail}</td><td>{e.ip}</td></tr>))}
        </tbody>
      </table>
    </section>
  );
}

// --------------------------------------------------------------- Admin
export function UserManagement({ me }) {
  const [{ data }, reload] = useLoad("/users/");
  const [msg, setMsg] = useState(null);
  const [form, setForm] = useState({ username: "", first_name: "", last_name: "", reg_number: "", role: "student", password: "" });

  async function act(path, body, ok) {
    const r = await api(path, { method: "POST", body });
    setMsg(r.ok ? { kind: "ok", text: ok } : { kind: "error", text: r.data?.detail });
    reload();
    return r.ok;
  }
  async function create(e) {
    e.preventDefault();
    if (await act("/users/", form, `Created ${form.username}.`))
      setForm({ ...form, username: "", first_name: "", last_name: "", reg_number: "", password: "" });
  }
  if (!data) return <p>Loading…</p>;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <section>
      <h2>User Management</h2>
      <p className="hint">Admins manage accounts but cannot view or change grades (separation of duties).</p>
      {msg && <div className={`alert ${msg.kind}`}>{msg.text}</div>}
      <table>
        <thead><tr><th>Username</th><th>Name</th><th>Role</th><th>Failed attempts</th><th>Status</th><th></th></tr></thead>
        <tbody>{data.map((u) => (
          <tr key={u.id} className={u.is_locked ? "bad" : ""}>
            <td>{u.username}</td><td>{u.full_name}</td>
            <td>
              <select value={u.role} disabled={u.id === me.id}
                      onChange={(e) => act(`/users/${u.id}/role/`, { role: e.target.value }, `${u.username} is now ${e.target.value}.`)}>
                <option value="student">Student</option><option value="lecturer">Lecturer</option>
                <option value="registrar">Registrar</option><option value="admin">Admin</option>
              </select>
            </td>
            <td>{u.failed_login_attempts} / 3</td>
            <td>{u.is_locked ? <span className="pill locked">🔒 Locked</span> : <span className="pill published">Active</span>}</td>
            <td>{u.is_locked && <button className="small" onClick={() => act(`/users/${u.id}/unlock/`, null, `Unlocked ${u.username}.`)}>Unlock</button>}</td>
          </tr>))}
        </tbody>
      </table>

      <form className="card form-grid" onSubmit={create}>
        <h3>Create account</h3>
        <input placeholder="Username" value={form.username} onChange={set("username")} required />
        <input placeholder="First name" value={form.first_name} onChange={set("first_name")} />
        <input placeholder="Last name" value={form.last_name} onChange={set("last_name")} />
        <input placeholder="Reg / staff number" value={form.reg_number} onChange={set("reg_number")} />
        <select value={form.role} onChange={set("role")}>
          <option value="student">Student</option><option value="lecturer">Lecturer</option>
          <option value="registrar">Registrar</option><option value="admin">Admin</option>
        </select>
        <input type="password" placeholder="Initial password" value={form.password} onChange={set("password")} required />
        <button>Create</button>
        <small>Password policy: 8+ characters with uppercase, lowercase, digit and symbol.</small>
      </form>
    </section>
  );
}

// ------------------------------------------------------ Security tests
// These calls go straight to the API, bypassing the UI's hidden tabs, to
// prove that access control is enforced on the server. They are designed
// not to change any data (invalid values or non-existent IDs).
const TESTS = [
  ["View my own grades", "GET", "/grades/mine/"],
  ["List courses", "GET", "/courses/"],
  ["Change a grade (Database Systems)", "PATCH", "/grades/__CSC__/", { score: 999 }],
  ["Approve a grade", "POST", "/grades/999999/approve/"],
  ["Read the audit log", "GET", "/audit/"],
  ["List all user accounts", "GET", "/users/"],
  ["Unlock an account", "POST", "/users/999999/unlock/"],
];

export function SecurityTests({ role }) {
  const [results, setResults] = useState([]);
  async function run() {
    // Grade #3 in the seed data is Brian Kamau's Database Systems (CSC 3102) mark.
    const out = [];
    for (const [label, method, path, body] of TESTS) {
      const r = await api(path.replace("__CSC__", "3"), { method, body });
      out.push({ label, method, path: path.replace("__CSC__", "3"), status: r.status, detail: r.data?.detail });
    }
    setResults(out);
  }
  return (
    <section>
      <h2>Server-side Access Control Test</h2>
      <p className="hint">Sends requests directly to the API as a <strong>{role}</strong>, ignoring which tabs
        the interface shows. Requests are built so they never change real data.</p>
      <button onClick={run}>Run tests</button>
      {results.length > 0 && (
        <table>
          <thead><tr><th>Action</th><th>Request</th><th>HTTP</th><th>Result</th></tr></thead>
          <tbody>{results.map((t) => {
            const denied = t.status === 403;
            return (
              <tr key={t.label} className={denied ? "bad" : "good"}>
                <td>{t.label}</td><td><code>{t.method} {t.path}</code></td><td>{t.status}</td>
                <td>{denied ? <span className="pill locked">DENIED</span> : <span className="pill published">ALLOWED</span>}
                  {denied && <small className="why"> {t.detail}</small>}</td>
              </tr>);
          })}</tbody>
        </table>)}
    </section>
  );
}

// ------------------------------------------------------------- Account
export function Account({ user }) {
  const [{ data }] = useLoad("/auth/me/");
  const [cur, setCur] = useState(""), [nw, setNw] = useState("");
  const [msg, setMsg] = useState(null);
  async function change(e) {
    e.preventDefault();
    const r = await api("/auth/change-password/", { method: "POST", body: { current_password: cur, new_password: nw } });
    setMsg({ kind: r.ok ? "ok" : "error", text: r.data?.detail });
    setCur(""); setNw("");
  }
  return (
    <section>
      <h2>Account</h2>
      <div className="card">
        <p><strong>{user.full_name}</strong> · {user.username} · {user.reg_number}</p>
      </div>
      {data && (
        <div className="card">
          <h3>Role permission matrix</h3>
          <table className="matrix">
            <thead><tr><th>Action</th>{["student", "lecturer", "registrar", "admin"].map((r) =>
              <th key={r} className={r === user.role ? "me" : ""}>{r}</th>)}</tr></thead>
            <tbody>{Object.entries(data.permission_matrix).map(([action, roles]) => (
              <tr key={action}><td>{action}</td>{["student", "lecturer", "registrar", "admin"].map((r) =>
                <td key={r} className={r === user.role ? "me" : ""}>{roles.includes(r) ? "✔" : "—"}</td>)}</tr>))}
            </tbody>
          </table>
        </div>)}
      <form className="card form-grid" onSubmit={change}>
        <h3>Change password</h3>
        <input type="password" placeholder="Current password" value={cur} onChange={(e) => setCur(e.target.value)} required />
        <input type="password" placeholder="New password" value={nw} onChange={(e) => setNw(e.target.value)} required />
        <button>Change password</button>
        {msg && <div className={`alert ${msg.kind}`}>{msg.text}</div>}
      </form>
    </section>
  );
}
