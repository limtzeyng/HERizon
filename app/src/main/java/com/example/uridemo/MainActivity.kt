package com.example.uridemo

import android.content.Context
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.abs

class MainActivity : ComponentActivity() {

    companion object {
        private const val PREFS_NAME = "uri_demo_prefs"
        private const val PREF_DEVICE_ROLE = "device_role"
        private const val ROLE_ALL = "ALL"
        private const val ROLE_LEFT = "LEFT"
        private const val ROLE_RIGHT = "RIGHT"
    }

    data class PollResult(
        val event: String?,
        val taskText: String?,
        val taskId: String?,
        val debug: String
    )

    data class TaskItem(
        val id: String,
        val text: String,
        val completed: Boolean
    )

    // ✅ CHANGE THIS to the IP printed by Flask
    private val serverBase = "http://192.168.68.101:5002"

    // ---------- VIBRATION ----------
    private fun getVibrator(): Vibrator {
        return if (Build.VERSION.SDK_INT >= 31) {
            val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vm.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
    }

    private fun vibratePattern(pattern: LongArray) {
        val effect = VibrationEffect.createWaveform(pattern, -1)
        getVibrator().vibrate(effect)
    }

    // Workplace event -> haptic language
    private fun playHapticForEvent(event: String) {
        when (event) {
            "NAME_CALLED" -> vibratePattern(longArrayOf(0, 200, 120, 200))
            "TASK_ASSIGNED" -> vibratePattern(longArrayOf(0, 180, 100, 180, 100, 180))
            "URGENT" -> vibratePattern(
                longArrayOf(
                    0, 120, 80, 120, 80, 120, 80, 120, 80, 120, 80, 120, 80, 120,
                    80, 120, 80, 120, 80, 120, 80, 120, 80, 120
                )
            )
            else -> vibratePattern(longArrayOf(0, 250))
        }
    }

    private fun normalizeRole(role: String): String {
        return when (role.uppercase()) {
            ROLE_LEFT -> ROLE_LEFT
            ROLE_RIGHT -> ROLE_RIGHT
            else -> ROLE_ALL
        }
    }

    private fun loadRole(): String {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return normalizeRole(prefs.getString(PREF_DEVICE_ROLE, ROLE_ALL) ?: ROLE_ALL)
    }

    private fun saveRole(role: String) {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(PREF_DEVICE_ROLE, normalizeRole(role)).apply()
    }

    // ---------- NETWORK: POLL EVENTS ----------
    private suspend fun pollEventOnce(role: String): PollResult = withContext(Dispatchers.IO) {
        try {
            val safeRole = normalizeRole(role)
            val url = URL("$serverBase/api/poll?role=$safeRole")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 2000
                readTimeout = 2000
            }

            val code = conn.responseCode
            val body = conn.inputStream.bufferedReader().readText()

            val json = JSONObject(body)
            val rawEvent = json.optString("event", null)
            val cleanEv = if (rawEvent == "null" || rawEvent.isNullOrBlank()) null else rawEvent
            val rawTask = json.optString("task_text", null)
            val cleanTask = if (rawTask == "null" || rawTask.isNullOrBlank()) null else rawTask
            val rawTaskId = json.optString("task_id", null)
            val cleanTaskId = if (rawTaskId == "null" || rawTaskId.isNullOrBlank()) null else rawTaskId

            PollResult(cleanEv, cleanTask, cleanTaskId, "HTTP $code")
        } catch (e: Exception) {
            PollResult(null, null, null, "ERROR: ${e.javaClass.simpleName}")
        }
    }

    // ---------- NETWORK: SEND RESPONSE ----------
    private suspend fun sendResponse(code: String, label: String, role: String) = withContext(Dispatchers.IO) {
        try {
            val url = URL("$serverBase/api/response")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                setRequestProperty("Content-Type", "application/json")
                doOutput = true
                connectTimeout = 2000
                readTimeout = 2000
            }

            val payload = JSONObject().apply {
                put("code", code)
                put("label", label)
                put("user", "Phone user")
                put("role", normalizeRole(role))
            }

            conn.outputStream.use { it.write(payload.toString().toByteArray()) }
            conn.inputStream.close()
        } catch (_: Exception) {
            // keep silent for demo stability
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            MaterialTheme {
                val scope = rememberCoroutineScope()

                var selectedRole by remember { mutableStateOf(loadRole()) }
                var status by remember { mutableStateOf("Server: $serverBase") }
                var lastEvent by remember { mutableStateOf("Last event: None") }
                var lastSent by remember { mutableStateOf("Last response: None") }
                val taskItems = remember { mutableStateListOf<TaskItem>() }

                // ---------- AUTO POLL LOOP ----------
                LaunchedEffect(selectedRole) {
                    while (true) {
                        val result = pollEventOnce(selectedRole)
                        status = "Status: ${result.debug} | Role: $selectedRole"

                        if (result.event != null) {
                            val suffix = if (result.taskText != null) " | Task: ${result.taskText}" else ""
                            lastEvent = "Last event: ${result.event}$suffix"
                            playHapticForEvent(result.event)

                            if (result.event == "TASK_ASSIGNED" && !result.taskText.isNullOrBlank()) {
                                val generatedId = result.taskId ?: "task-${SystemClock.elapsedRealtime()}"
                                val exists = taskItems.any { it.id == generatedId }
                                if (!exists) {
                                    taskItems.add(TaskItem(id = generatedId, text = result.taskText, completed = false))
                                }
                            }
                        }

                        delay(700)
                    }
                }

                // ---------- TAP LOGIC (single vs double) ----------
                var tapCount by remember { mutableStateOf(0) }
                var firstTapTime by remember { mutableStateOf(0L) }
                var lastTapTime by remember { mutableStateOf(0L) }

                fun send(code: String, label: String) {
                    lastSent = "Last response: $label"
                    scope.launch { sendResponse(code, label, selectedRole) }
                    vibratePattern(longArrayOf(0, 60))
                }

                fun registerTap() {
                    val now = SystemClock.elapsedRealtime()

                    if (tapCount == 0) {
                        tapCount = 1
                        firstTapTime = now
                        lastTapTime = now

                        scope.launch {
                            delay(350)
                            if (tapCount == 1 && abs(SystemClock.elapsedRealtime() - lastTapTime) >= 300) {
                                send("YES_SINGLE_TAP", "Acknowledge / Yes")
                                tapCount = 0
                            }
                        }
                    } else {
                        if (now - firstTapTime <= 400) {
                            tapCount = 0
                            send("NO_DOUBLE_TAP", "No / can’t comply")
                        } else {
                            tapCount = 1
                            firstTapTime = now
                        }
                        lastTapTime = now
                    }
                }

                // ---------- UI ----------
                Surface(modifier = Modifier.fillMaxSize()) {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(20.dp)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text("Universal Response Interface", fontSize = 20.sp)
                        Text("This phone role: $selectedRole", fontSize = 12.sp)

                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Button(onClick = { selectedRole = ROLE_LEFT; saveRole(selectedRole) }) { Text("Set LEFT") }
                            Button(onClick = { selectedRole = ROLE_RIGHT; saveRole(selectedRole) }) { Text("Set RIGHT") }
                            Button(onClick = { selectedRole = ROLE_ALL; saveRole(selectedRole) }) { Text("Set GENERAL") }
                        }

                        Text(status, fontSize = 12.sp)
                        Text(lastEvent)
                        Text(lastSent)

                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(onClick = { playHapticForEvent("NAME_CALLED") }) {
                                Text("Test vibration")
                            }
                            Button(onClick = {
                                scope.launch {
                                    val result = pollEventOnce(selectedRole)
                                    if (result.event != null) {
                                        val suffix = if (result.taskText != null) " | Task: ${result.taskText}" else ""
                                        lastEvent = "Last event: ${result.event}$suffix"
                                        playHapticForEvent(result.event)

                                        if (result.event == "TASK_ASSIGNED" && !result.taskText.isNullOrBlank()) {
                                            val generatedId = result.taskId ?: "task-${SystemClock.elapsedRealtime()}"
                                            val exists = taskItems.any { it.id == generatedId }
                                            if (!exists) {
                                                taskItems.add(TaskItem(id = generatedId, text = result.taskText, completed = false))
                                            }
                                        }
                                    }
                                }
                            }) { Text("Poll once") }
                        }

                        Spacer(Modifier.height(8.dp))

                        // ---------- TASK MANAGER ----------
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(
                                modifier = Modifier.padding(14.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text("Task Manager", style = MaterialTheme.typography.titleMedium)
                                    Button(
                                        onClick = { taskItems.removeAll { it.completed } },
                                        enabled = taskItems.any { it.completed }
                                    ) {
                                        Text("Clear completed")
                                    }
                                }

                                if (taskItems.isEmpty()) {
                                    Text("No tasks yet.", fontSize = 12.sp)
                                } else {
                                    taskItems.forEachIndexed { index, item ->
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                                        ) {
                                            Checkbox(
                                                checked = item.completed,
                                                onCheckedChange = { checked ->
                                                    taskItems[index] = item.copy(completed = checked)
                                                }
                                            )
                                            Text(item.text, modifier = Modifier.weight(1f))
                                        }
                                    }
                                }
                            }
                        }

                        // ---------- RESPONSE PAD ----------
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(190.dp)
                                .background(
                                    color = MaterialTheme.colorScheme.primaryContainer,
                                    shape = RoundedCornerShape(18.dp)
                                )
                                .pointerInput(Unit) {
                                    awaitPointerEventScope {
                                        while (true) {
                                            val down = awaitPointerEvent().changes.firstOrNull { it.pressed } ?: continue
                                            val trackedPointerId = down.id
                                            val downTime = SystemClock.elapsedRealtime()

                                            // Wait until same finger released/cancelled
                                            while (true) {
                                                val ev = awaitPointerEvent()
                                                ev.changes.forEach { it.consume() }

                                                val trackedChange = ev.changes.firstOrNull { it.id == trackedPointerId }
                                                val isReleased = trackedChange?.pressed == false
                                                val isCancelled = trackedChange == null
                                                if (isReleased || isCancelled) break
                                            }

                                            val upTime = SystemClock.elapsedRealtime()
                                            val duration = upTime - downTime

                                            when {
                                                duration >= 5000 -> send("HELP_HOLD_5S", "Help / emergency")
                                                duration >= 2000 -> send("REPEAT_HOLD_2S", "Repeat / clarify")
                                                else -> registerTap()
                                            }
                                        }
                                    }
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("RESPONSE PAD", fontSize = 18.sp)
                                Text("Tap / Double tap / Hold 2s / Hold 5s", fontSize = 12.sp)
                            }
                        }

                        Text(
                            "Mappings:\n" +
                                    "• Single tap = Acknowledge / Yes\n" +
                                    "• Double tap = No / can’t comply\n" +
                                    "• Hold 2s = Repeat / clarify\n" +
                                    "• Hold 5s = Help / emergency",
                            fontSize = 12.sp
                        )
                    }
                }
            }
        }
    }
}
