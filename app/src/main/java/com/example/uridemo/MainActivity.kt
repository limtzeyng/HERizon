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

    // ✅ CHANGE THIS to the IP printed by Flask
    private val serverBase = "http://172.20.10.2:5002"

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
            // Name called / attention: 2 short pulses
            "NAME_CALLED" -> vibratePattern(longArrayOf(0, 200, 120, 200))

            // Task assigned: 3 short pulses
            "TASK_ASSIGNED" -> vibratePattern(longArrayOf(0, 180, 100, 180, 100, 180))

            // Urgent: rapid pulses (approx a few seconds)
            "URGENT" -> vibratePattern(
                longArrayOf(
                    0, 120, 80, 120, 80, 120, 80, 120, 80, 120, 80, 120, 80, 120,
                    80, 120, 80, 120, 80, 120, 80, 120, 80, 120
                )
            )

            else -> vibratePattern(longArrayOf(0, 250))
        }
    }

    // ---------- NETWORK: POLL EVENTS ----------
    private suspend fun pollEventOnce(): Pair<String?, String> = withContext(Dispatchers.IO) {
        try {
            val url = URL("$serverBase/api/poll")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 2000
                readTimeout = 2000
            }

            val code = conn.responseCode
            val body = conn.inputStream.bufferedReader().readText()

            val json = JSONObject(body)
            val ev = json.optString("event", null)
            val cleanEv = if (ev == "null" || ev.isNullOrBlank()) null else ev

            Pair(cleanEv, "HTTP $code")
        } catch (e: Exception) {
            Pair(null, "ERROR: ${e.javaClass.simpleName}")
        }
    }

    // ---------- NETWORK: SEND RESPONSE ----------
    private suspend fun sendResponse(code: String, label: String) = withContext(Dispatchers.IO) {
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

                var status by remember { mutableStateOf("Server: $serverBase") }
                var lastEvent by remember { mutableStateOf("Last event: None") }
                var lastSent by remember { mutableStateOf("Last response: None") }

                // ---------- AUTO POLL LOOP ----------
                LaunchedEffect(Unit) {
                    while (true) {
                        val (ev, dbg) = pollEventOnce()
                        status = "Status: $dbg"
                        if (ev != null) {
                            lastEvent = "Last event: $ev"
                            playHapticForEvent(ev)
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
                    scope.launch { sendResponse(code, label) }
                    // confirmation micro-buzz
                    vibratePattern(longArrayOf(0, 60))
                }

                fun registerTap() {
                    val now = SystemClock.elapsedRealtime()

                    if (tapCount == 0) {
                        tapCount = 1
                        firstTapTime = now
                        lastTapTime = now

                        // Wait briefly to see if a second tap arrives
                        scope.launch {
                            delay(350)
                            // still only one tap after the wait => single tap
                            if (tapCount == 1 && abs(SystemClock.elapsedRealtime() - lastTapTime) >= 300) {
                                send("YES_SINGLE_TAP", "Acknowledge / Yes")
                                tapCount = 0
                            }
                        }
                    } else {
                        // second tap within window => double tap
                        if (now - firstTapTime <= 400) {
                            tapCount = 0
                            send("NO_DOUBLE_TAP", "No / can’t comply")
                        } else {
                            // too slow; treat as new first tap
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
                            .padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text("Universal Response Interface", fontSize = 20.sp)
                        Text(status, fontSize = 12.sp)
                        Text(lastEvent)
                        Text(lastSent)

                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(onClick = { playHapticForEvent("NAME_CALLED") }) {
                                Text("Test vibration")
                            }
                            Button(onClick = {
                                scope.launch {
                                    val (ev, _) = pollEventOnce()
                                    if (ev != null) {
                                        lastEvent = "Last event: $ev"
                                        playHapticForEvent(ev)
                                    }
                                }
                            }) { Text("Poll once") }
                        }

                        Spacer(Modifier.height(8.dp))

                        // ---------- RESPONSE PAD (tap / hold 2s / hold 5s) ----------
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
                                            val downChange = awaitPointerEvent().changes.firstOrNull { it.pressed }
                                            if (downChange != null) {
                                                val downTime = SystemClock.elapsedRealtime()

                                                // Wait for release
                                                while (downChange.pressed) {
                                                    val ev = awaitPointerEvent()
                                                    ev.changes.forEach { it.consume() }
                                                    if (ev.changes.all { !it.pressed }) break
                                                }

                                                val upTime = SystemClock.elapsedRealtime()
                                                val duration = upTime - downTime

                                                when {
                                                    duration >= 5000 -> {
                                                        send("HELP_HOLD_5S", "Help / emergency")
                                                    }
                                                    duration >= 2000 -> {
                                                        send("REPEAT_HOLD_2S", "Repeat / clarify")
                                                    }
                                                    else -> {
                                                        registerTap() // single/double logic
                                                    }
                                                }
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
