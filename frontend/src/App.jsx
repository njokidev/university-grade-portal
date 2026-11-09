import { useEffect, useState } from "react";
import { api, setToken, setUnauthorizedHandler } from "./api.js";
import {
  StudentGrades, LecturerCourses, PendingApprovals, IntegrityCheck,
  AuditLog, UserManagement, SecurityTests, Account,
} from "./panels.jsx";

// Which tabs each role sees. This is only for convenience: the real
// enforcement happens on the Django server (see the Security Tests tab).
const TABS = {
  student:   [["grades", "My Grades"], ["tests", "Security Tests"], ["account", "Account"]],
  lecturer:  [["courses", "My Courses"], ["tests", "Security Tests"], ["account", "Account"]],
  registrar: [["pending", "Pending Approvals"], ["courses", "All Courses"],
              ["integrity", "Integrity Check"], ["audit", "Audit Log"],
              ["tests", "Security Tests"], ["account", "Account"]],
  admin:     [["users", "User Management"], ["audit", "Audit Log"],
              ["tests", "Security Tests"], ["account", "Account"]],
};

const ROLE_LABEL = { student: "Student", lecturer: "Lecturer", registrar: "Registrar", admin: "System Admin" };

function Login({ onLogin, notice }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState(notice ? { kind: "info", text: notice } : null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    const r = await api("/auth/login/", { method: "POST", body: { username, password } });
    setBusy(false);
    setPassword("");
    if (r.ok) return onLogin(r.data);
    if (r.status === 423) return setMsg({ kind: "locked", text: r.data.detail });
    let text = r.data?.detail || "Login failed.";
    if (r.data?.attempts_left !== undefined)
      text += ` ${r.data.attempts_left} attempt${r.data.attempts_left === 1 ? "" : "s"} left before the account is locked.`;
    setMsg({ kind: "error", text });
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="brand">
          <span className="shield" aria-hidden>🛡</span>
          <div>
            <h1>SecureGrade</h1>
            <p>University Grade Portal</p>
          </div>
        </div>
        <label>Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label>Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 autoComplete="current-password" required />
        </label>
        {msg && <div className={`alert ${msg.kind}`} role="alert">
          {msg.kind === "locked" && <strong>🔒 Account locked. </strong>}{msg.text}
        </div>}
        <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="fine">Accounts lock after 3 failed attempts. All activity is logged.</p>
      </form>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [tab, setTab] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    setUnauthorizedHandler((detail) => {
      setToken(null);
      setSession(null);
      setNotice(detail || "Your session ended. Please sign in again.");
    });
  }, []);

  function handleLogin(data) {
    setToken(data.token);
    setNotice(null);
    setSession(data.user);
    setTab(TABS[data.user.role][0][0]);
  }

  async function logout() {
    await api("/auth/logout/", { method: "POST" });
    setToken(null);
    setSession(null);
  }

  if (!session) return <Login onLogin={handleLogin} notice={notice} />;

  const tabs = TABS[session.role];
  return (
    <div className="app">
      <header>
        <div className="brand small"><span className="shield">🛡</span><strong>SecureGrade</strong></div>
        <div className="who">
          <span>{session.full_name || session.username}</span>
          <span className={`role-badge ${session.role}`}>{ROLE_LABEL[session.role]}</span>
          <button className="ghost" onClick={logout}>Log out</button>
        </div>
      </header>
      <nav>
        {tabs.map(([key, label]) => (
          <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>
        ))}
      </nav>
      <main>
        {tab === "grades" && <StudentGrades />}
        {tab === "courses" && <LecturerCourses role={session.role} />}
        {tab === "pending" && <PendingApprovals />}
        {tab === "integrity" && <IntegrityCheck />}
        {tab === "audit" && <AuditLog />}
        {tab === "users" && <UserManagement me={session} />}
        {tab === "tests" && <SecurityTests role={session.role} />}
        {tab === "account" && <Account user={session} />}
      </main>
    </div>
  );
}
