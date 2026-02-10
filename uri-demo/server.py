from flask import Flask, request, jsonify, render_template_string
from collections import deque
from datetime import datetime

app = Flask(__name__)

# --- Reliable event delivery to phone (FIFO) ---
EVENT_QUEUE = deque(maxlen=50)
LATEST_EVENT = {"event": None}

# --- Responses coming back from phone (latest first) ---
RESPONSES_LOG = deque(maxlen=30)

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Universal Response Interface — Demo Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    h1 { margin-bottom: 18px; }
    button { font-size: 16px; padding: 12px 18px; margin-right: 10px; margin-bottom: 10px; cursor: pointer; }
    .row { display: flex; flex-wrap: wrap; gap: 10px; }
    .panel { margin-top: 18px; }
    .label { font-weight: 700; font-size: 22px; margin: 18px 0 10px; }
    .box {
      background: #f4f4f4;
      border-radius: 10px;
      padding: 14px;
      min-height: 40px;
      white-space: pre-wrap;
    }
    .meta { margin-top: 8px; color: #444; font-size: 14px; }
    .pill { display: inline-block; background: #eee; padding: 4px 10px; border-radius: 999px; }
  </style>
</head>
<body>
  <h1>Universal Response Interface — Demo Dashboard</h1>

  <div class="row">
    <button onclick="sendEvent('NAME_CALLED')">Your name was called</button>
    <button onclick="sendEvent('TASK_ASSIGNED')">Task assigned / instruction</button>
    <button onclick="sendEvent('URGENT')">Urgent / need attention</button>
  </div>

  <div class="meta">
    <span class="pill">Event queue size: <span id="qsize">0</span></span>
  </div>

  <div class="panel">
    <div class="label">Latest Event:</div>
    <div class="box" id="latestEvent">None</div>
  </div>

  <div class="panel">
    <div class="label">Responses Log:</div>
    <div class="box" id="responsesLog">No responses yet.</div>
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
  // latest event updates via refresh() loop
}

async function refresh() {
  const res = await fetch('/api/status');
  const data = await res.json();

  document.getElementById('qsize').textContent = data.queue_size ?? 0;
  document.getElementById('latestEvent').textContent = data.latest_event || "None";

  const logs = data.responses || [];
  if (logs.length === 0) {
    document.getElementById('responsesLog').textContent = "No responses yet.";
  } else {
    document.getElementById('responsesLog').textContent = logs.join("\\n");
  }
}

setInterval(refresh, 700);
refresh();
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

# Dashboard -> phone: enqueue event
@app.route("/api/send", methods=["POST"])
def api_send():
    payload = request.get_json(silent=True) or {}
    ev = payload.get("event")

    if not ev:
        return jsonify({"ok": False, "error": "Missing event"}), 400

    LATEST_EVENT["event"] = ev
    EVENT_QUEUE.append(ev)
    return jsonify({"ok": True, "queue_size": len(EVENT_QUEUE)})

# Phone polls this to get next event
@app.route("/api/poll", methods=["GET"])
def api_poll():
    if EVENT_QUEUE:
        ev = EVENT_QUEUE.popleft()
        return jsonify({"event": ev, "queue_size": len(EVENT_QUEUE)})
    return jsonify({"event": None, "queue_size": 0})

# Phone -> dashboard: send response (Yes/No/Repeat/Help)
@app.route("/api/response", methods=["POST"])
def api_response():
    payload = request.get_json(silent=True) or {}

    code = payload.get("code")
    label = payload.get("label")
    user = payload.get("user", "PHONE")

    if not code and not label:
        return jsonify({"ok": False, "error": "Missing code/label"}), 400

    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{user}] {label} ({code}) @ {ts}"

    RESPONSES_LOG.appendleft(line)
    return jsonify({"ok": True})

# Dashboard refresh uses this
@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "latest_event": LATEST_EVENT.get("event"),
        "queue_size": len(EVENT_QUEUE),
        "responses": list(RESPONSES_LOG)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)

