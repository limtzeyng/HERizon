Hello! We are a team of 5 women (Tze Yng, Hikaru, Jia Yuun, Grace, and Suxin) working on a project for Women-in-Tech Hackathon Track 1.

This project focuses on using haptics for ease of communication for people with disabilities. HERizon LinkBand is a wearable-assisted mobile system designed to help users discreetly receive and respond to important cues in real-world environments. The system combines an Android app with a Flask backend to deliver reliable event-based communication, supporting accessibility, safety, and inclusive interaction. We hope that this brings more convenience to them.

Devices:
1. 1 working Laptop
2. 2 Android Phones (minimally 1; 2 Phones to utilise directional haptics feature well)
3. 1 Cable to connect said laptop and phone to transfer files

Instructions on setting up:
1. Install Android Studio. Please find the installer compatible to your device here: https://developer.android.com/studio/install 
2. On the Android Phone, change to Developer Mode (Go to Settings -> About device -> Version -> Tap 7 times on the Version Name).
3. On the Android Phone, go to Developer Options and turn on USB debugging (Make sure to authorise anything similar to this).
4. Ensure that the Android Phone and the Laptop are connected to the same WIFI, preferably a private network (e.g., hotspot).
5. Disable any firewalls for Python on the Laptop. (This may be preventing the code from running.)
6. Download all the files in the repository and open the file "server.py" on any IDE, such as Visual Studio Code.
7. Open the folder "HERizon-main" on Android Studio.
8. Use the Cable to connect the laptop and phone.
9. Allow changes to be made and drag down the notifications that pop up, tap on it to set up and select "Transfer files".
10. Run the code for "server.py" and copy the second address to the "MainActivity" file under the app -> src -> main -> java -> example.
11. Open the first address in your browser. A dashboard will pop up.
12. Return to "HERizon-main" window and check that the Android Phone is connected properly. (Shows up at the top of the window)
13. Run "HERizon-main". The app will be installed in the Android Phone.
14. Congrats! You can now unplug the cable and send events and responses to the dashboard on the Laptop and the app on the Android Phone.

## Features 
Core function:
* The dashboard can send events to the Android Phone.
* The Android Phone can be interacted with and will send responses to the dashboard.
* They communicate via vibrations.
* Different vibration patterns are mapped to different meaning.

Directional haptics:
* Install the app on 2 Android phones.
* In each app, set one phone as **LEFT** and the other as **RIGHT** using the role buttons.
* On the dashboard, press **Send LEFT vibration** to vibrate only the LEFT phone, or **Send RIGHT vibration** to vibrate only the RIGHT phone.
* Existing event buttons (name called / task assigned / urgent) continue to work as shared events.

Task Manager:
* On the dashboard, type a task (for example: "Please submit the report by 5pm.") and click **Send task to phone**.
* The phone will receive the `TASK_ASSIGNED` event and vibrate using the task-assigned pattern.
* The task will appear in the app's **Task Manager** checklist, where the user can tick tasks as done.
* Use **Clear completed** in the app to remove finished tasks.

## Architecture Diagram
<img width="7457" height="3612" alt="Diagram" src="https://github.com/user-attachments/assets/1b3d508f-8868-4306-b6bb-04d0d39e93b5" />

```bash
HOST=0.0.0.0 PORT=5002 FLASK_DEBUG=0 python uri-demo/server.py
```



