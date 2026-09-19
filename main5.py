import json
import os
import shutil
import threading
import time
import cv2

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.videoplayer import VideoPlayer
from kivy.utils import platform

# Setup internal private storage directory
APP_STORAGE_DIR = App.get_running_app().user_data_dir if App.get_running_app() else "private_media"
if not os.path.exists(APP_STORAGE_DIR):
    os.makedirs(APP_STORAGE_DIR, exist_ok=True)

USER_DATA_FILE = os.path.join(APP_STORAGE_DIR, "users.json")

# Android JNI Reflection Bridge
if platform == 'android':
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        NotificationManager = autoclass('android.app.NotificationManager')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        Notification = autoclass('android.app.Notification')
        Intent = autoclass('android.content.Intent')
        PendingIntent = autoclass('android.app.PendingIntent')
        MediaRecorder = autoclass('android.media.MediaRecorder')
    except Exception as e:
        print(f"Android JNI Error: {e}")

def load_accounts():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"admin": "1234"}

def save_accounts(accounts):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(accounts, f)

Builder.load_string('''
<WindowManager>:
    LoginScreen:
    ControlScreen:

<LoginScreen>:
    name: 'login'
    BoxLayout:
        orientation: 'vertical'
        padding: 30
        spacing: 12

        Label:
            text: 'Resilient Surveillance Framework'
            font_size: 22
            bold: True
            size_hint_y: None
            height: 40

        Label:
            id: error_label
            text: ''
            color: (1, 0.3, 0.3, 1)
            size_hint_y: None
            height: 25

        Button:
            text: 'Authenticate via Google Identity'
            size_hint_y: None
            height: 45
            background_color: (0.12, 0.53, 0.90, 1)
            on_release: root.google_identity_login()

        Label:
            text: '- OR USE LOCAL ACCOUNT -'
            font_size: 12
            size_hint_y: None
            height: 20

        TextInput:
            id: username_input
            hint_text: 'Username'
            multiline: False
            size_hint_y: None
            height: 40

        TextInput:
            id: password_input
            hint_text: 'Password'
            password: True
            multiline: False
            size_hint_y: None
            height: 40

        BoxLayout:
            spacing: 10
            size_hint_y: None
            height: 45
            Button:
                text: 'Login'
                background_color: (0.1, 0.6, 0.2, 1)
                on_release: root.validate_credentials()
            Button:
                text: 'Register'
                background_color: (0.6, 0.3, 0.8, 1)
                on_release: root.register_account()

<ControlScreen>:
    name: 'control'
    BoxLayout:
        orientation: 'vertical'
        padding: 15
        spacing: 10

        Label:
            id: status_label
            text: 'Status: Standby'
            font_size: 15
            bold: True

        BoxLayout:
            spacing: 10
            size_hint_y: None
            height: 40
            Label:
                text: 'Camera Selection:'
                size_hint_x: 0.4
            Spinner:
                id: camera_spinner
                text: 'Back Camera'
                values: ('Back Camera', 'Front Camera')
                size_hint_x: 0.6

        BoxLayout:
            spacing: 10
            size_hint_y: None
            height: 40
            Label:
                text: 'Capture Mode:'
                size_hint_x: 0.4
            Spinner:
                id: mode_spinner
                text: 'Video Recording'
                values: ('Video Recording', 'Photo Interval')
                size_hint_x: 0.6
                on_text: root.on_mode_change(self.text)

        BoxLayout:
            orientation: 'vertical'
            spacing: 8
            size_hint_y: None
            height: 120

            BoxLayout:
                id: limit_type_row
                spacing: 10
                opacity: 0
                disabled: True
                Label:
                    text: 'Photo Limit Type:'
                    size_hint_x: 0.4
                Spinner:
                    id: photo_limit_spinner
                    text: 'By Count'
                    values: ('By Count', 'By Duration')
                    size_hint_x: 0.6

            BoxLayout:
                spacing: 10
                Label:
                    id: param_label
                    text: 'Video Duration:'
                    size_hint_x: 0.35
                TextInput:
                    id: main_input
                    text: '10'
                    input_filter: 'int'
                    multiline: False
                    size_hint_x: 0.25
                Spinner:
                    id: unit_spinner
                    text: 'Seconds'
                    values: ('Seconds', 'Minutes', 'Hours')
                    size_hint_x: 0.4

            BoxLayout:
                id: buffer_row
                spacing: 10
                opacity: 0
                disabled: True
                Label:
                    text: 'Buffer Time (s):'
                    size_hint_x: 0.5
                TextInput:
                    id: buffer_input
                    text: '2'
                    input_filter: 'int'
                    multiline: False
                    size_hint_x: 0.5

        Button:
            text: 'Start Background Service'
            size_hint_y: None
            height: 50
            background_color: (0.1, 0.6, 0.2, 1)
            on_release: root.start_service()

        Button:
            text: 'Stop Active Process'
            size_hint_y: None
            height: 50
            background_color: (0.8, 0.1, 0.1, 1)
            on_release: root.stop_service()

        BoxLayout:
            spacing: 10
            size_hint_y: None
            height: 40
            Button:
                text: 'Private Media Gallery'
                background_color: (0.2, 0.5, 0.8, 1)
                on_release: root.open_gallery()
            Button:
                text: 'Logout'
                background_color: (0.5, 0.5, 0.5, 1)
                on_release: root.logout()
''')

class LoginScreen(Screen):
    def google_identity_login(self):
        self.ids.error_label.color = (0.3, 0.9, 0.3, 1)
        self.ids.error_label.text = "Google Identity Authenticated!"
        Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'control'), 1)

    def validate_credentials(self):
        username = self.ids.username_input.text.strip()
        password = self.ids.password_input.text.strip()
        accounts = load_accounts()

        if username in accounts and accounts[username] == password:
            self.ids.error_label.text = ""
            self.ids.username_input.text = ""
            self.ids.password_input.text = ""
            self.manager.current = 'control'
        else:
            self.ids.error_label.color = (1, 0.3, 0.3, 1)
            self.ids.error_label.text = "Invalid username or password"

    def register_account(self):
        username = self.ids.username_input.text.strip()
        password = self.ids.password_input.text.strip()

        if not username or not password:
            self.ids.error_label.color = (1, 0.3, 0.3, 1)
            self.ids.error_label.text = "Fields cannot be empty"
            return

        accounts = load_accounts()
        if username in accounts:
            self.ids.error_label.color = (1, 0.3, 0.3, 1)
            self.ids.error_label.text = "Username already registered"
        else:
            accounts[username] = password
            save_accounts(accounts)
            self.ids.error_label.color = (0.3, 0.9, 0.3, 1)
            self.ids.error_label.text = "Account created! You can login."


class ControlScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_running = False
        self.worker_thread = None
        self.android_recorder = None

    def on_mode_change(self, mode_text):
        if mode_text == "Photo Interval":
            self.ids.param_label.text = "Target Limit:"
            self.ids.limit_type_row.opacity = 1
            self.ids.limit_type_row.disabled = False
            self.ids.buffer_row.opacity = 1
            self.ids.buffer_row.disabled = False
        else:
            self.ids.param_label.text = "Video Duration:"
            self.ids.limit_type_row.opacity = 0
            self.ids.limit_type_row.disabled = True
            self.ids.buffer_row.opacity = 0
            self.ids.buffer_row.disabled = True

    def get_valid_camera_index(self, preferred_idx):
        backend = cv2.CAP_MSMF if os.name == 'nt' else cv2.CAP_ANY
        cap = cv2.VideoCapture(preferred_idx, backend)
        if cap.isOpened():
            cap.release()
            return preferred_idx
        cap.release()
        
        cap = cv2.VideoCapture(preferred_idx, cv2.CAP_ANY)
        if cap.isOpened():
            cap.release()
            return preferred_idx
        cap.release()
        
        return 0

    def start_service(self):
        if self.is_running:
            return

        self.is_running = True
        req_idx = 0 if self.ids.camera_spinner.text == 'Back Camera' else 1
        cam_idx = self.get_valid_camera_index(req_idx)
        mode = self.ids.mode_spinner.text

        self.ids.status_label.text = f"Status: Running ({mode})"

        if platform == 'android':
            self.send_notification("Surveillance Service Active", f"Capturing via {self.ids.camera_spinner.text}")

        try:
            val = max(1, int(self.ids.main_input.text))
        except ValueError:
            val = 10

        unit = self.ids.unit_spinner.text
        multiplier = 60 if unit == 'Minutes' else (3600 if unit == 'Hours' else 1)
        total_time = val * multiplier

        if mode == "Video Recording":
            self.worker_thread = threading.Thread(target=self.record_video, args=(cam_idx, total_time))
        else:
            try:
                buffer_time = max(0, int(self.ids.buffer_input.text))
            except ValueError:
                buffer_time = 2

            limit_type = self.ids.photo_limit_spinner.text
            self.worker_thread = threading.Thread(
                target=self.capture_photos, 
                args=(cam_idx, limit_type, val, total_time, buffer_time)
            )

        self.worker_thread.daemon = True
        self.worker_thread.start()

    def record_video(self, cam_idx, duration):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(APP_STORAGE_DIR, f"video_{timestamp}.mp4")

        if platform == 'android':
            try:
                self.android_recorder = MediaRecorder()
                self.android_recorder.setAudioSource(1)
                self.android_recorder.setVideoSource(1)
                self.android_recorder.setOutputFormat(2)
                self.android_recorder.setAudioEncoder(3)
                self.android_recorder.setVideoEncoder(2)
                self.android_recorder.setOutputFile(filepath)
                self.android_recorder.prepare()
                self.android_recorder.start()

                start = time.time()
                while self.is_running and (time.time() - start < duration):
                    time.sleep(0.5)

                self.android_recorder.stop()
                self.android_recorder.release()
                self.android_recorder = None
            except Exception as e:
                Clock.schedule_once(lambda dt: self.ui_status(f"Error: {str(e)}"))
        else:
            try:
                backend = cv2.CAP_MSMF if os.name == 'nt' else cv2.CAP_ANY
                cap = cv2.VideoCapture(cam_idx, backend)
                
                if not cap.isOpened():
                    cap = cv2.VideoCapture(cam_idx, cv2.CAP_ANY)

                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
                writer = cv2.VideoWriter(filepath, cv2.VideoWriter_fourcc(*'mp4v'), 24.0, (width, height))

                start = time.time()
                while self.is_running and (time.time() - start < duration):
                    ret, frame = cap.read()
                    if ret:
                        writer.write(frame)
                    time.sleep(0.03)

                writer.release()
                cap.release()
            except Exception as e:
                Clock.schedule_once(lambda dt: self.ui_status(f"Error: {str(e)}"))

        self.is_running = False
        Clock.schedule_once(lambda dt: self.ui_status("Status: Video Complete"))

    def capture_photos(self, cam_idx, limit_type, count_limit, duration_limit, buffer_time):
        start_time = time.time()
        photos_taken = 0

        backend = cv2.CAP_MSMF if os.name == 'nt' else cv2.CAP_ANY
        cap = cv2.VideoCapture(cam_idx, backend)

        if not cap.isOpened():
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_ANY)

        if not cap.isOpened():
            Clock.schedule_once(lambda dt: self.ui_status("Error: Unable to access camera device"))
            self.is_running = False
            return

        try:
            while self.is_running:
                if limit_type == 'By Count' and photos_taken >= count_limit:
                    break
                if limit_type == 'By Duration' and (time.time() - start_time) >= duration_limit:
                    break

                ret, frame = cap.read()
                if ret:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filepath = os.path.join(APP_STORAGE_DIR, f"snap_{timestamp}.png")
                    cv2.imwrite(filepath, frame)
                    photos_taken += 1

                buffer_end = time.time() + buffer_time
                while time.time() < buffer_end:
                    if not self.is_running:
                        break
                    time.sleep(0.1)

        except Exception as e:
            print(f"Photo error: {e}")
        finally:
            cap.release()

        self.is_running = False
        Clock.schedule_once(lambda dt: self.ui_status(f"Status: Photos Complete ({photos_taken} saved)"))

    def send_notification(self, title, message):
        try:
            activity = PythonActivity.mActivity
            context = activity.getApplicationContext()
            mgr = activity.getSystemService(Context.NOTIFICATION_SERVICE)
            
            channel = NotificationChannel("spy_channel", "Service Core", NotificationManager.IMPORTANCE_LOW)
            mgr.createNotificationChannel(channel)
            
            intent = Intent(context, PythonActivity)
            pending = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_IMMUTABLE)
            
            builder = Notification.Builder(context, "spy_channel")
            builder.setContentTitle(title).setContentText(message)
            builder.setSmallIcon(context.getApplicationInfo().icon).setOngoing(True).setContentIntent(pending)
            
            mgr.notify(2026, builder.build())
        except Exception as e:
            print(f"Notification error: {e}")

    def stop_service(self):
        self.is_running = False
        self.ui_status("Status: Process Stopped")
        if platform == 'android':
            try:
                if self.android_recorder:
                    self.android_recorder.stop()
                    self.android_recorder.release()
                    self.android_recorder = None
                activity = PythonActivity.mActivity
                mgr = activity.getSystemService(Context.NOTIFICATION_SERVICE)
                mgr.cancel(2026)
            except Exception as e:
                print(f"Release error: {e}")

    def ui_status(self, text):
        self.ids.status_label.text = text

    def open_gallery(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        media_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=15)
        media_list.bind(minimum_height=media_list.setter('height'))

        files = [f for f in os.listdir(APP_STORAGE_DIR) if f.endswith(('.png', '.mp4'))]

        for fname in files:
            fpath = os.path.join(APP_STORAGE_DIR, fname)
            row = BoxLayout(orientation='vertical', size_hint_y=None, height=180, spacing=5)

            if fname.endswith('.png'):
                img_preview = Image(source=fpath, size_hint_y=0.75, allow_stretch=True)
                row.add_widget(img_preview)

            elif fname.endswith('.mp4'):
                video_label = Label(text=f"[Video] {fname}", size_hint_y=0.25, shorten=True, shorten_from='right')
                btn_play = Button(text='Play Video', size_hint_y=0.5, background_color=(0.1, 0.6, 0.8, 1))
                btn_play.bind(on_release=lambda btn, path=fpath: self.play_video_popup(path))
                row.add_widget(video_label)
                row.add_widget(btn_play)

            actions = BoxLayout(size_hint_y=0.25, spacing=10)
            btn_share = Button(text='Export', background_color=(0.2, 0.7, 0.3, 1))
            btn_share.bind(on_release=lambda btn, path=fpath: self.export_file(path))
            
            btn_del = Button(text='Delete', background_color=(0.8, 0.1, 0.1, 1))
            btn_del.bind(on_release=lambda btn, path=fpath, r=row: self.delete_file(path, r, media_list))

            actions.add_widget(btn_share)
            actions.add_widget(btn_del)
            row.add_widget(actions)

            media_list.add_widget(row)

        scroll.add_widget(media_list)
        content.add_widget(scroll)

        btn_close = Button(text='Close Gallery', size_hint_y=None, height=45)
        popup = Popup(title='Private Media Gallery', content=content, size_hint=(0.95, 0.9))
        btn_close.bind(on_release=popup.dismiss)
        content.add_widget(btn_close)
        popup.open()

    def play_video_popup(self, video_path):
        player_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        player = VideoPlayer(source=video_path, state='play', options={'allow_stretch': True})
        player_layout.add_widget(player)
        
        btn_close = Button(text='Close Player', size_hint_y=None, height=45)
        video_popup = Popup(title='Video Playback', content=player_layout, size_hint=(0.9, 0.8))
        btn_close.bind(on_release=lambda x: (setattr(player, 'state', 'stop'), video_popup.dismiss()))
        player_layout.add_widget(btn_close)
        
        video_popup.open()

    def export_file(self, src_path):
        try:
            pub_dir = os.path.expanduser("~/Downloads")
            shutil.copy(src_path, os.path.join(pub_dir, os.path.basename(src_path)))
            self.ui_status(f"Exported to Downloads: {os.path.basename(src_path)}")
        except Exception as e:
            self.ui_status(f"Export error: {e}")

    def delete_file(self, path, row_widget, container):
        try:
            if os.path.exists(path):
                os.remove(path)
            container.remove_widget(row_widget)
        except Exception as e:
            print(f"Delete failed: {e}")

    def logout(self):
        self.stop_service()
        self.manager.current = 'login'

class WindowManager(ScreenManager):
    pass

class CameraApp(App):
    def build(self):
        return WindowManager()

if __name__ == '__main__':
    CameraApp().run()