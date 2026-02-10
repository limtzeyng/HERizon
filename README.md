Hello! We are a team of 5 women working on a project for Women-in-Tech Hackathon Track 1. 

This project focuses on using haptics for ease of communication for people with disabilities. HERizon LinkBand is a wearable-assisted mobile system designed to help users discreetly receive and respond to important cues in real-world environments. The system combines an Android app with a Flask backend to deliver reliable event-based communication, supporting accessibility, safety, and inclusive interaction. We hope that this brings more convenience to them.

Devices:
1. 1 working Laptop
2. 1 Android Phone
3. 1 Cable to connect said laptop and phone to transfer files

Instructions on setting up:
1. Install Android Studio. Please find the installer compatible to your device here: https://developer.android.com/studio/install 
2. On the Android Phone, change to Developer Mode (Go to Settings -> About device -> Version -> Tap 7 times on the Version Name).
3. On the Android Phone, go to Developer Options and turn on USB debugging (Make sure to authorise anything similar to this).
4. Ensure that the Android Phone and the Laptop are connected to the same WIFI, preferably a private network (e.g., hotspot).
5. Disable any firewalls for Python on the Laptop. (This may be preventing the code from running.)
6. Download and open the file "server.py" on any IDE, such as Visual Studio Code.
7. Download and open the folder "WIT version 1" on Android Studio.
8. Open the folder "App" under "WIT version 1" in a new window.
9. Use the Cable to connect the laptop and phone.
10. Allow changes to be made and drag down the notifications that pop up, tap on it to set up and select "Transfer files".
11. Run the code for "server.py" and copy the second address to the "MainActivity" file under the "App" window.
12. Open the first address in your browser. A dashboard will pop up.
13. Return to "WIT version 1" window and check that the Android Phone is connected properly. (Show up at the top of the window)
14. Run "WIT version 1". The app will be installed in the Android Phone.

 How it works:
* The dashboard can send events to the Android Phone.
* The Android Phone can be interacted with and will send responses to the dashboard.
* They communicate via vibrations.
* Different vibration patterns are mapped to different meaning. 

```mermaid
flowchart LR

  subgraph Operator[Operator / Caregiver (Laptop)]
    B[Web Dashboard (Browser)]
  end

  subgraph Backend[Backend (Laptop)]
    S[Flask Server<br/>uri-demo/server.py]
    Q[(Event Queue<br/>FIFO deque)]
    L[(Responses Log<br/>latest-first deque)]
  end

  subgraph Mobile[User (Android Phone)]
    A[Android App<br/>Kotlin + Jetpack Compose]
    H[Haptics Layer<br/>Vibrator / Wristband Interface]
  end

  B -- "POST /api/send" --> S
  B -- "GET /api/status" --> S

  A -- "GET /api/poll" --> S
  S -- "JSON event" --> A

  A -- "POST /api/response" --> S

  S --> Q
  S --> L
  Q --> S
  L --> S

  N1[[Same WiFi / Hotspot<br/>Use http://&lt;laptop-ip&gt;:&lt;port&gt;]] --- B
  N1 --- A
