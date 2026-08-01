const yard = document.body.dataset.yard;

async function api(path, opts) {
  const res = await fetch(path, opts);
  return res.json();
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

async function loadTasks() {
  const tasks = await api(`/api/tasks?yard=${yard}`);
  const container = document.getElementById("tasks");
  container.innerHTML = "";

  const doneCount = tasks.filter((t) => t.done).length;
  document.getElementById("progress-text").textContent =
    `${doneCount} of ${tasks.length} done`;
  document.getElementById("progress-pct").textContent =
    tasks.length ? Math.round((doneCount / tasks.length) * 100) + "%" : "0%";
  document.getElementById("progress-fill").style.width =
    tasks.length ? (doneCount / tasks.length) * 100 + "%" : "0%";

  let currentPhase = null;
  for (const t of tasks) {
    if (t.phase !== currentPhase) {
      currentPhase = t.phase;
      container.appendChild(el("h2", "phase", t.phase));
    }
    const card = el("div", "task" + (t.done ? " done" : ""));
    const cb = el("input");
    cb.type = "checkbox";
    cb.checked = !!t.done;
    cb.addEventListener("change", async () => {
      await api("/api/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: t.id }),
      });
      loadTasks();
    });
    const body = el("div");
    const title = el("div", "title", t.title);
    title.addEventListener("click", () => cb.click());
    body.appendChild(title);
    if (t.detail) body.appendChild(el("div", "detail", t.detail));
    if (t.done && t.done_date)
      body.appendChild(el("div", "done-date", "✓ completed " + t.done_date));
    card.append(cb, body);
    container.appendChild(card);
  }
}

async function loadLogs() {
  const logs = await api(`/api/logs?yard=${yard}`);
  const list = document.getElementById("log-list");
  list.innerHTML = "";
  if (!logs.length) {
    list.appendChild(el("div", "empty", "No entries yet — log waterings, fertilizer, mowing, anything."));
    return;
  }
  for (const l of logs) {
    const row = el("div", "log-entry");
    const del = el("button", null, "✕");
    del.title = "Delete entry";
    del.addEventListener("click", async () => {
      await api("/api/logs/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: l.id }),
      });
      loadLogs();
    });
    row.append(el("span", "date", l.date), el("span", "note", l.note), del);
    list.appendChild(row);
  }
}

document.getElementById("log-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const note = document.getElementById("log-note");
  const date = document.getElementById("log-date");
  if (!note.value.trim()) return;
  await api("/api/logs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ yard, note: note.value, date: date.value || undefined }),
  });
  note.value = "";
  loadLogs();
});

document.getElementById("log-date").value = new Date().toISOString().slice(0, 10);
loadTasks();
loadLogs();
