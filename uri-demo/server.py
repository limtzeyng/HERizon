from flask import Flask, request, jsonify, render_template_string
from collections import deque
from datetime import datetime

app = Flask(__name__)

# --- Reliable event delivery ---
EVENT_QUEUE = deque(maxlen=50)  # Broadcast queue (ALL)
ROLE_QUEUES = {
    "LEFT": deque(maxlen=50),
    "RIGHT": deque(maxlen=50),
}
LATEST_EVENT = {"event": None, "target": "ALL"}

# --- Responses coming back from phone ---
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
    .meta { margin-top: 8px; font-size: 14px; display: flex; gap: 10px; flex-wrap: wrap; }
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

  <div class="label">Directional haptics</div>
  <div class="row">
    <button onclick="sendDirectional('LEFT')">Send LEFT vibration</button>
    <button onclick="sendDirectional('RIGHT')">Send RIGHT vibration</button>
  </div>

  <div class="meta">
    <span class="pill">Event queue size (ALL): <span id="qsize">0</span></span>
    <span class="pill">Left queue: <span id="leftQsize">0</span></span>
    <span class="pill">Right queue: <span id="rightQsize">0</span></span>
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
    body: JSON.stringify({event: ev, target: 'ALL'})
  });
  const data = await res.json();
  updateCounts(data);
}

async function sendDirectional(target) {
  const res = await fetch('/api/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({event: 'DIRECTIONAL_SIGNAL', target: target})
  });
  const data = await res.json();
  updateCounts(data);
}

function updateCounts(data) {
  document.getElementById('qsize').textContent = data.queue_size ?? 0;
  document.getElementById('leftQsize').textContent = data.left_queue_size ?? 0;
  document.getElementById('rightQsize').textContent = data.right_queue_size ?? 0;
}

async function refresh() {
  const res = await fetch('/api/status');
  const data = await res.json();

  updateCounts(data);

  const latest = data.latest_event
      ? data.latest_event + " (target=" + (data.latest_target || "ALL") + ")"
      : "None";

  document.getElementById('latestEvent').textContent = latest;

  const logs = data.responses || [];
  document.getElementById('responsesLog').textContent =
      logs.length === 0 ? "No responses yet." : logs.join("\\n");
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


# Dashboard -> phone
@app.route("/api/send", methods=["POST"])
def api_send():
    payload = request.get_json(silent=True) or {}
    ev = payload.get("event")
    target = str(payload.get("target", "ALL")).upper()

    if not ev:
        return jsonify({"ok": False, "error": "Missing event"}), 400

    if target not in {"ALL", "LEFT", "RIGHT"}:
        return jsonify({"ok": False, "error": "Invalid target. Use ALL/LEFT/RIGHT"}), 400

    LATEST_EVENT["event"] = ev
    LATEST_EVENT["target"] = target

    if target == "ALL":
        EVENT_QUEUE.append(ev)
    else:
        ROLE_QUEUES[target].append(ev)

    return jsonify({
        "ok": True,
        "queue_size": len(EVENT_QUEUE),
        "left_queue_size": len(ROLE_QUEUES["LEFT"]),
        "right_queue_size": len(ROLE_QUEUES["RIGHT"]),
    })


# Phone polls this
@app.route("/api/poll", methods=["GET"])
def api_poll():
    role = str(request.args.get("role", "ALL")).upper()

    # Serve role-specific queue first
    if role in ROLE_QUEUES and ROLE_QUEUES[role]:
        ev = ROLE_QUEUES[role].popleft()
        return jsonify({
            "event": ev,
            "target": role,
            "queue_size": len(EVENT_QUEUE),
            "left_queue_size": len(ROLE_QUEUES["LEFT"]),
            "right_queue_size": len(ROLE_QUEUES["RIGHT"]),
        })

    # Otherwise serve broadcast queue
    if EVENT_QUEUE:
        ev = EVENT_QUEUE.popleft()
        return jsonify({
            "event": ev,
            "target": "ALL",
            "queue_size": len(EVENT_QUEUE),
            "left_queue_size": len(ROLE_QUEUES["LEFT"]),
            "right_queue_size": len(ROLE_QUEUES["RIGHT"]),
        })

    return jsonify({
        "event": None,
        "target": None,
        "queue_size": len(EVENT_QUEUE),
        "left_queue_size": len(ROLE_QUEUES["LEFT"]),
        "right_queue_size": len(ROLE_QUEUES["RIGHT"]),
    })


# Phone -> dashboard
@app.route("/api/response", methods=["POST"])
def api_response():
    payload = request.get_json(silent=True) or {}

    code = payload.get("code")
    label = payload.get("label")
    user = payload.get("user", "PHONE")
    role = str(payload.get("role", "UNASSIGNED")).upper()

    if not code and not label:
        return jsonify({"ok": False, "error": "Missing code/label"}), 400

    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{role}] [{user}] {label} ({code}) @ {ts}"

    RESPONSES_LOG.appendleft(line)
    return jsonify({"ok": True})


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "latest_event": LATEST_EVENT.get("event"),
        "latest_target": LATEST_EVENT.get("target"),
        "queue_size": len(EVENT_QUEUE),
        "left_queue_size": len(ROLE_QUEUES["LEFT"]),
        "right_queue_size": len(ROLE_QUEUES["RIGHT"]),
        "responses": list(RESPONSES_LOG)
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)
