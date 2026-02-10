from flask import Flask, request, jsonify, render_template_string
from collections import deque
from datetime import datetime

app = Flask(__name__)

# Event queue so the phone never misses events
EVENT_QUEUE = deque(maxlen=50)

# Responses log from phone -> shown on dashboard
RESPONSES_LOG = deque(maxlen=30)

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>URI Demo Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 20px; }
    button { padding: 12px 16px; margin: 8px 8px 8px 0; font-size: 16px; cursor: pointer; }
    .row { display: flex; gap: 10px; flex-wrap: wrap; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 12px; margin-top: 14px; }
    .title { font-weight: 700; margin-bottom: 8px; }
    .pill { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #f3f3f3; }
    pre { background: #f7f7f7; padding: 12px; border-radius: 10px; overflow: auto; }
    .logitem { padding: 10px; border-bottom: 1px solid #eee; }
    .logitem:last-child { border-bottom: none; }
    .meta { color: #555; font-size: 13px; margin-top: 4px; }
  </style>
</head>
<body>
  <h2>Universal Response Interface — Dashboard</h2>

  <div class="card">
    <div class="title">Send Workplace Event (to Phone)</div>
    <div class="row">
      <button onclick="sendEvent('NAME_CALLED')">Your name was called</button>
      <button onclick="sendEvent('TASK_ASSIGNED')">Task assigned / instruction</button>
      <button onclick="sendEvent('URGENT')">Urgent / need attention</button>
    </div>
    <div style="margin-top:8px;">
      <span class="pill">Event queue size: <span id="qsize">0</span></span>
    </div>
  </div>

  <div class="card">
    <div class="title">Responses Log (from Phone)</div>
    <div id="responses">(waiting...)</div>
  </div>

  <div class="card">
    <div class="title">Debug</div>
    <pre id="debug">Ready.</pre>
  </div>

<script>
async function sendEvent(ev) {
  const res = await fetch('/api/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({event: ev})
  });
  const data = await res.json();
  document.getElementById('qsize').textContent = data.queue_size;
  document.getElementById('debug').textContent = "Sent event: " + ev + "\\n" + JSON.stringify(data, null, 2);
}

async function refreshStatus() {
  const res = await fetch('/api/status');
  const data = await res.json();
  document.getElementById('qsize').textContent = data.queue_size;

  // render responses
  const box = document.getElementById('responses');
  if (!data.responses || data.responses.length === 0) {
    box.innerHTML = "<div class='logitem'>No responses yet.</div>";
    return;
  }

  box.innerHTML = data.responses.map(r => {
    const who = r.user || "Phone user";
    const msg = r.label || r.code || "(unknown)";
    const ts = r.time || "";
    return `
      <div class="logitem">
        <div><b>${who}</b>: ${msg}</div>
        <div class="meta">${ts} • code=${r.code || ""}</div>
      </div>`;
  }).join("");
}

setInterval(refreshStatus, 1000);
refreshStatus();
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/api/send", methods=["POST"])
def api_send():
    payload = request.get_json(silent=True) or {}
    ev = payload.get("event")
    if not ev:
        return jsonify({"ok": False, "error": "Missing event"}), 400
    EVENT_QUEUE.append(ev)
    return jsonify({"ok": True, "queue_size": len(EVENT_QUEUE)})

@app.route("/api/poll", methods=["GET"])
def api_poll():
    # Phone calls this repeatedly
    if EVENT_QUEUE:
        ev = EVENT_QUEUE.popleft()
        return jsonify({"event": ev, "queue_size": len(EVENT_QUEUE)})
    return jsonify({"event": None, "queue_size": 0})

@app.route("/api/response", methods=["POST"])
def api_response():
    payload = request.get_json(silent=True) or {}
    code = payload.get("code")
    label = payload.get("label")
    user = payload.get("user", "Phone user")

    item = {
        "code": code,
        "label": label,
        "user": user,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    RESPONSES_LOG.appendleft(item)
    return jsonify({"ok": True})

@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "queue_size": len(EVENT_QUEUE),
        "responses": list(RESPONSES_LOG)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
