from flask import Flask, request, jsonify, render_template_string
from collections import deque
from datetime import datetime

app = Flask(__name__)

# --- Reliable event delivery to phone (FIFO) ---
EVENT_QUEUE = deque(maxlen=50)
ROLE_QUEUES = {
    "LEFT": deque(maxlen=50),
    "RIGHT": deque(maxlen=50),
}
LATEST_EVENT = {"event": None, "target": "ALL"}

# --- Responses coming back from phone (latest first) ---
RESPONSES_LOG = deque(maxlen=30)

# --- ID counters ---
EVENT_COUNTER = 0
TASK_COUNTER = 0


def _now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)


def make_event_packet(event: str, target: str = "ALL", task_text: str | None = None):
    """
    Packet format that your Android MainActivity expects:
      event, task_text, task_id, event_id
    """
    global EVENT_COUNTER, TASK_COUNTER
    EVENT_COUNTER += 1
    now_ms = _now_ms()

    packet = {
        "event": event,
        "target": target,
        "task_text": (task_text or "").strip() or None,
        "task_id": None,
        "event_id": f"event-{now_ms}-{EVENT_COUNTER}",
    }

    if event == "TASK_ASSIGNED" and packet["task_text"]:
        TASK_COUNTER += 1
        packet["task_id"] = f"task-{now_ms}-{TASK_COUNTER}"

    return packet


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
    .row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
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
    input, select { font-size: 16px; padding: 10px; }
    input { min-width: 320px; }
  </style>
</head>
<body>
  <h1>Universal Response Interface — Demo Dashboard</h1>

  <div class="row">
    <button onclick="sendEvent('NAME_CALLED')">Your name was called</button>
    <button onclick="sendEvent('TASK_ASSIGNED')">Task assigned / instruction</button>
    <button onclick="sendEvent('URGENT')">Urgent / need attention</button>
  </div>

  <div class="label">Task Manager</div>
  <div class="row">
    <input id="taskInput" type="text" placeholder="e.g. Please submit the report by 5pm." />
    <select id="taskTarget">
      <option value="ALL" selected>Send to ALL</option>
      <option value="LEFT">Send to LEFT</option>
      <option value="RIGHT">Send to RIGHT</option>
    </select>
    <button onclick="sendTask()">Send task to phone</button>
  </div>

  <div class="label">Directional haptics</div>
  <div class="row">
    <button onclick="sendDirectional('LEFT')">Send LEFT vibration</button>
    <button onclick="sendDirectional('RIGHT')">Send RIGHT vibration</button>
  </div>

  <div class="meta">
    <span class="pill">Event queue size (all): <span id="qsize">0</span></span>
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
function updateQueueUi(data) {
  document.getElementById('qsize').textContent = data.queue_size ?? 0;
  document.getElementById('leftQsize').textContent = data.left_queue_size ?? 0;
  document.getElementById('rightQsize').textContent = data.right_queue_size ?? 0;
}

async function sendEvent(ev) {
  const res = await fetch('/api/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({event: ev})
  });
  const data = await res.json();
  updateQueueUi(data);
}

async function sendTask() {
  const taskInput = document.getElementById('taskInput');
  const task = taskInput.value.trim();
  const target = document.getElementById('taskTarget').value;

  if (!task) {
    alert('Please type a task first.');
    return;
  }

  const res = await fetch('/api/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({event: 'TASK_ASSIGNED', task_text: task, target: target})
  });

  const data = await res.json();
  updateQueueUi(data);

  taskInput.value = '';
}

async function sendDirectional(target) {
  const res = await fetch('/api/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({event: 'DIRECTIONAL_SIGNAL', target: target})
  });
  const data = await res.json();
  updateQueueUi(data);
}

async function refresh() {
  const res = await fetch('/api/status');
  const data = await res.json();

  updateQueueUi(data);

  let latest = data.latest_event || 'None';
  if (data.latest_event) {
    latest = `${data.latest_event} (target=${data.latest_target || 'ALL'})`;
  }
  document.getElementById('latestEvent').textContent = latest;

  const logs = data.responses || [];
  document.getElementById('responsesLog').textContent =
    logs.length ? logs.join("\\n") : 'No responses yet.';
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

    ev = str(payload.get("event", "")).strip()
    target = str(payload.get("target", "ALL")).upper()
    task_text = payload.get("task_text")

    if not ev:
        return jsonify({"ok": False, "error": "Missing event"}), 400

    if target not in {"ALL", "LEFT", "RIGHT"}:
        return jsonify({"ok": False, "error": "Invalid target. Use ALL/LEFT/RIGHT"}), 400

    # If user clicked TASK_ASSIGNED button without typing a task, just send a normal task vibration event
    # (Phone won't add to task list unless task_text exists)
    packet = make_event_packet(ev, target=target, task_text=task_text)

    # If it IS a task, enforce that task_text exists (so dashboard can't send empty tasks)
    if ev == "TASK_ASSIGNED" and packet["task_text"] is None:
        return jsonify({"ok": False, "error": "task_text is required for TASK_ASSIGNED"}), 400

    LATEST_EVENT["event"] = packet["event"]
    LATEST_EVENT["target"] = packet["target"]

    # IMPORTANT: store PACKETS (dict) in queues, not strings
    if target == "ALL":
        EVENT_QUEUE.append(packet)
    else:
        ROLE_QUEUES[target].append(packet)

    return jsonify({
        "ok": True,
        "queue_size": len(EVENT_QUEUE),
        "left_queue_size": len(ROLE_QUEUES["LEFT"]),
        "right_queue_size": len(ROLE_QUEUES["RIGHT"]),
    })


# Phone polls this to get next event
@app.route("/api/poll", methods=["GET"])
def api_poll():
    role = str(request.args.get("role", "ALL")).upper()

    def respond(packet):
        return jsonify({
            "event": packet.get("event"),
            "task_text": packet.get("task_text"),
            "task_id": packet.get("task_id"),
            "event_id": packet.get("event_id"),
        })

    # 1) Role-specific queue first
    if role in ROLE_QUEUES and ROLE_QUEUES[role]:
        pkt = ROLE_QUEUES[role].popleft()
        # Backward compatibility if any old string slips in
        if not isinstance(pkt, dict):
            pkt = make_event_packet(str(pkt), target=role)
        return respond(pkt)

    # 2) Then shared queue
    if EVENT_QUEUE:
        pkt = EVENT_QUEUE.popleft()
        if not isinstance(pkt, dict):
            pkt = make_event_packet(str(pkt), target="ALL")
        return respond(pkt)

    # 3) Nothing
    return jsonify({
        "event": None,
        "task_text": None,
        "task_id": None,
        "event_id": None,
    })


# Phone -> dashboard: send response
@app.route("/api/response", methods=["POST"])
def api_response():
    payload = request.get_json(silent=True) or {}

    code = payload.get("code")
    label = payload.get("label")
    user = payload.get("user", "PHONE")
    role = str(payload.get("role", "UNASSIGNED")).upper()
    custom_pattern = payload.get("custom_pattern")

    if not code and not label:
        return jsonify({"ok": False, "error": "Missing code/label"}), 400

    ts = datetime.now().strftime("%H:%M:%S")
    extra = f" [pattern={custom_pattern}]" if custom_pattern else ""
    line = f"[{role}] [{user}] {label} ({code}){extra} @ {ts}"

    RESPONSES_LOG.appendleft(line)
    return jsonify({"ok": True})


# Dashboard refresh uses this
@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "latest_event": LATEST_EVENT.get("event"),
        "latest_target": LATEST_EVENT.get("target"),
        "queue_size": len(EVENT_QUEUE),
        "left_queue_size": len(ROLE_QUEUES["LEFT"]),
        "right_queue_size": len(ROLE_QUEUES["RIGHT"]),
        "responses": list(RESPONSES_LOG),
    })


if __name__ == "__main__":
    # keep your port consistent with serverBase in MainActivity
    app.run(host="0.0.0.0", port=5002, debug=False)
