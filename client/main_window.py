import sys
import base64
import time
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog,
    QVBoxLayout, QHBoxLayout, QLineEdit, QApplication, QFrame, QMessageBox, QScrollArea, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

# Import the backend bridge we built earlier
from api_client import TerraSenseClient

# ---------------------------------------------------------
# Async API Worker Thread
# ---------------------------------------------------------
class PredictionWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, client, payload):
        super().__init__()
        self.client = client
        self.payload = payload

    def run(self):
        try:
            self.progress.emit("Submitting data to server...")
            response_data = self.client.submit_prediction(self.payload)
            
            if response_data.get("status") == "SUCCESS" and "data" in response_data:
                self.progress.emit("Result loaded instantly from Redis cache!")
                self.finished.emit(response_data["data"])
                return # Exit early, no polling needed!
            
            # Otherwise, it's a new job. Grab the task_id and poll Celery
            task_id = response_data.get("task_id")
            if not task_id:
                self.error.emit("Server did not return a task_id.")
                return
            
            self.progress.emit("Job queued. Waiting for ML worker...")
            
            while True:
                result = self.client.check_task_status(task_id)
                status = result.get("status")
                
                if status == "SUCCESS":
                    self.finished.emit(result.get("data", {}))
                    break
                elif status == "FAILURE":
                    self.error.emit(result.get("error", "Unknown server error."))
                    break
                
                time.sleep(2)
        except Exception as e:
            self.error.emit(str(e))

# ---------------------------------------------------------
# Main GUI Application
# ---------------------------------------------------------
class TerraSenseGUI(QWidget):
    def __init__(self, api_client, user_email):
        super().__init__()
        
        self.client = api_client
        self.user_email = user_email
        self.image_path = None

        self.setWindowTitle(f"TerraSense AI - Dashboard ({self.user_email})")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(self.get_styles())
        self.build_ui()

    def build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("TerraSense AI — Precision Agriculture Platform")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("title")
        main_layout.addWidget(title)
        main_layout.addSpacing(20)

        # Split layout
        split_layout = QHBoxLayout()
        split_layout.setSpacing(30)
        split_layout.addWidget(self.build_input_panel(), 1)
        split_layout.addWidget(self.build_output_panel(), 2)

        main_layout.addLayout(split_layout)
        self.setLayout(main_layout)

    def build_input_panel(self):
        frame = QFrame()
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        header = QLabel("Location & Soil Data")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        # Upload button
        self.upload_btn = QPushButton("Upload Satellite Image")
        self.upload_btn.clicked.connect(self.upload_image)
        layout.addWidget(self.upload_btn)

        self.image_label = QLabel("No image selected")
        self.image_label.setObjectName("helperText")
        self.image_label.setWordWrap(True)
        layout.addWidget(self.image_label)
        
        layout.addSpacing(10)

        # Inputs
        self.lat = self.create_input(layout, "Latitude", "e.g., 28.6139")
        self.lon = self.create_input(layout, "Longitude", "e.g., 77.2090")
        self.acres = self.create_input(layout, "Acres", "e.g., 12.5")
        self.N = self.create_input(layout, "Nitrogen (N)", "e.g., 45")
        self.P = self.create_input(layout, "Phosphorus (P)", "e.g., 30")
        self.K = self.create_input(layout, "Potassium (K)", "e.g., 20")
        self.ph = self.create_input(layout, "pH Level", "e.g., 6.5")

        layout.addSpacing(20)

        # Submit Button
        self.run_btn = QPushButton("Run Distributed Analysis")
        self.run_btn.setObjectName("primaryButton")
        self.run_btn.clicked.connect(self.run_analysis)
        layout.addWidget(self.run_btn)

        layout.addStretch()
        frame.setLayout(layout)
        frame.setObjectName("cardPanel")
        return frame

    def build_output_panel(self):
        frame = QFrame()
        frame.setObjectName("cardPanel")
        layout = QVBoxLayout(frame)
        
        # Header
        header = QLabel("Prediction History")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        # Refresh Button
        self.refresh_btn = QPushButton("Refresh History")
        self.refresh_btn.clicked.connect(self.load_history)
        layout.addWidget(self.refresh_btn)

        # Scroll Area for History
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("imagePreview") # Reuse style
        
        # Container for the cards
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)
        
        self.scroll.setWidget(self.history_container)
        layout.addWidget(self.scroll)

        return frame

    def load_history(self):
        # Clear existing
        for i in reversed(range(self.history_layout.count())): 
            self.history_layout.itemAt(i).widget().setParent(None)

        try:
            history = self.client.get_history()
            for p in history:
                # Create a card for each prediction
                card = QFrame()
                card.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 5px;")
                card_layout = QVBoxLayout(card)
                
                info = QLabel(
                    f"<b>Crop:</b> {p['crop'].capitalize()}<br>"
                    f"<b>Soil:</b> {p['soil'].capitalize()}<br>"
                    f"<b>NDVI:</b> {p['ndvi']:.3f}<br>"
                    f"<b>Date:</b> {p['date']}"
                )
                card_layout.addWidget(info)
                self.history_layout.addWidget(card)
        except Exception as e:
            self.history_layout.addWidget(QLabel(f"Could not load history: {e}"))

    def create_input(self, layout, label_text, placeholder):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setMinimumWidth(110)
        lbl.setStyleSheet("color: #334155; font-weight: 600;")
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        row.addWidget(lbl)
        row.addWidget(inp)
        layout.addLayout(row)
        return inp

    def upload_image(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.tif)")
        if file:
            self.image_path = file
            self.image_label.setText(file.split('/')[-1])

    def run_analysis(self):
        if not self.image_path:
            self.output_text.setText("Error: Please select a soil/satellite image first.")
            return

        try:
            # Gather and parse form data
            payload = {
                "lat": float(self.lat.text() or 0),
                "lon": float(self.lon.text() or 0),
                "acres": float(self.acres.text() or 0),
                "N": float(self.N.text() or 0),
                "P": float(self.P.text() or 0),
                "K": float(self.K.text() or 0),
                "ph": float(self.ph.text() or 0)
            }

            # Encode image to Base64 for the API payload
            with open(self.image_path, "rb") as img_file:
                payload["image_base64"] = base64.b64encode(img_file.read()).decode('utf-8')

            self.output_text.setText("Initializing API payload...")
            self.run_btn.setEnabled(False)

            # Spin up the background thread
            self.worker = PredictionWorker(self.client, payload)
            self.worker.progress.connect(self.update_log)
            self.worker.finished.connect(self.show_result)
            self.worker.error.connect(self.show_error)
            self.worker.start()

        except ValueError:
            self.output_text.setText("Error: Please ensure all inputs are valid numbers.")

    def update_log(self, msg):
        current_text = self.output_text.toPlainText()
        self.output_text.setText(f"{current_text}\n> {msg}")

    def show_result(self, result):
        self.run_btn.setEnabled(True)
        
        # If the API returns a base64 processed NDVI image, display it
        if "ndvi_image_base64" in result:
            img_data = base64.b64decode(result["ndvi_image_base64"])
            image = QImage.fromData(img_data)
            pixmap = QPixmap.fromImage(image)
            if not pixmap.isNull():
                scaled = pixmap.scaled(600, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.ndvi_image.setPixmap(scaled)
                self.ndvi_image.setStyleSheet("border: none;")

        text = f"""
            <b>ANALYSIS COMPLETE</b><br>
            ----------------------------------<br>
            <b>Detected Soil:</b> {result.get('detected_soil', 'N/A').upper()}<br>
            <b>Recommended Crop:</b> <span style='color: #2e7d32; font-weight: bold;'>{result.get('recommended_crop', 'N/A').upper()}</span><br>
            <b>NDVI Value:</b> {result.get('ndvi', 0.0):.3f}
            """
        self.output_text.setHtml(text)

    def show_error(self, msg):
        self.run_btn.setEnabled(True)
        self.output_text.setText(f"SERVER ERROR:\n{msg}")

    def get_styles(self):
        return """
        QWidget {
            background-color: #f8fafc;
            font-size: 14px;
            font-family: 'Segoe UI', Arial, sans-serif;
        }

        #title {
            font-size: 26px;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: 0.5px;
        }

        #cardPanel {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
        }

        #panelHeader {
            font-size: 18px;
            font-weight: bold;
            color: #334155;
            border-bottom: 2px solid #f1f5f9;
            padding-bottom: 8px;
        }

        #helperText {
            color: #64748b;
            font-size: 12px;
            font-style: italic;
        }

        QPushButton {
            background-color: #f1f5f9;
            color: #334155;
            padding: 10px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            font-weight: bold;
        }

        QPushButton:hover {
            background-color: #e2e8f0;
            border: 1px solid #94a3b8;
        }

        #primaryButton {
            background-color: #10b981;
            color: white;
            border: none;
            font-size: 15px;
            padding: 12px;
        }

        #primaryButton:hover {
            background-color: #059669;
        }
        
        #primaryButton:disabled {
            background-color: #94a3b8;
        }

        QLineEdit {
            background-color: #f8fafc;
            color: #0f172a;
            padding: 8px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
        }
        
        QLineEdit:focus {
            border: 1px solid #10b981;
            background-color: #ffffff;
        }

        QTextEdit {
            background-color: #f8fafc;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 12px;
            font-size: 14px;
        }

        #imagePreview {
            border: 2px dashed #cbd5e1;
            border-radius: 8px;
            background-color: #f8fafc;
            color: #94a3b8;
        }
        
        QWidget {
            background-color: #f8fafc;
            color: #0f172a; /* Force dark text globally */
            font-size: 14px;
        }
        
        QTextEdit {
            background-color: #ffffff;
            color: #0f172a; /* Explicitly set text color */
            border: 1px solid #cbd5e1;
            padding: 10px;
        }

        QFrame#cardPanel {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #e2e8f0;
        }

        QLabel {
            color: #0f172a;
        }
        """
        
class LoginWindow(QWidget):
        login_successful = pyqtSignal(str)
        def __init__(self, api_client=None):
            super().__init__()
            self.api_client = api_client or TerraSenseClient(base_url="http://localhost:8000")
            
            self.setWindowTitle("TerraSense AI - Authentication")
            self.resize(450, 500)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setStyleSheet(TerraSenseGUI(None, "").get_styles()) # Inherit styles

            layout = QVBoxLayout(self)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Build the card
            frame = QFrame()
            frame.setObjectName("cardPanel")
            frame.setFixedSize(400, 350)
            
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(30, 30, 30, 30)
            frame_layout.setSpacing(20)

            # Logo / Title
            logo = QLabel("TerraSense AI")
            logo.setObjectName("title")
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_layout.addWidget(logo)

            # Inputs
            self.email_input = QLineEdit()
            self.email_input.setPlaceholderText("Email Address")
            frame_layout.addWidget(self.email_input)
            
            self.password_input = QLineEdit()
            self.password_input.setPlaceholderText("Password")
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            frame_layout.addWidget(self.password_input)

            frame_layout.addSpacing(10)

            # Buttons
            self.sign_in_btn = QPushButton("Sign In")
            self.sign_in_btn.setObjectName("primaryButton")
            self.sign_in_btn.clicked.connect(self.sign_in)
            frame_layout.addWidget(self.sign_in_btn)
            
            layout.addWidget(frame)

        def sign_in(self):
            email = self.email_input.text().strip()
            password = self.password_input.text().strip()
            
            if not email or not password:
                QMessageBox.warning(self, "Input Error", "Please enter both email and password.")
                return

            self.sign_in_btn.setEnabled(False)
            self.sign_in_btn.setText("Authenticating...")
            QApplication.processEvents()

            try:
                # Authenticate against the backend
                success = self.api_client.login(email, password)
                if success:
                    self.route_user(email)
                else:
                    QMessageBox.warning(self, "Sign In Failed", "Invalid credentials. Please try again.")
            except Exception as e:
                QMessageBox.critical(self, "Connection Error", f"Failed to connect to server:\n{str(e)}")
            finally:
                self.sign_in_btn.setEnabled(True)
                self.sign_in_btn.setText("Sign In")

        def route_user(self, email):
            # Instantiate the main dashboard, passing the authenticated client
            self.app_window = TerraSenseGUI(self.api_client, email)
            self.app_window.show()
            
            # Close the login window
            self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())