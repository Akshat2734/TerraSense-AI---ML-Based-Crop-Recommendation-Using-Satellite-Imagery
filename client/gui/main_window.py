import sys
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog,
    QVBoxLayout, QHBoxLayout, QLineEdit,
    QTextEdit, QApplication, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

from server.features.builder import build_features
from client.model.inference import predict_crop
from PIL import Image


# Worker thread
class PredictionWorker(QThread):

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, image_path, lat, lon, acres, N, P, K, ph):
        super().__init__()
        self.image_path = image_path
        self.lat = lat
        self.lon = lon
        self.acres = acres
        self.N = N
        self.P = P
        self.K = K
        self.ph = ph

    def run(self):

        try:

            X, ndvi = build_features(
                self.lat, self.lon, self.acres,
                self.N, self.P, self.K, self.ph
            )
            
            temp = X[3]
            humidity = X[4]
            rainfall = X[6]

            soil, crop = predict_crop(self.image_path, X)

            result = {
                "soil": soil,
                "crop": crop,
                "ndvi": ndvi,
                "temp": temp,
                "humidity": humidity,
                "rainfall": rainfall,
                "ndvi_image": "field_ndvi.tif"            
            }

            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))


class TerraSenseGUI(QWidget):

    def __init__(self):

        super().__init__()

        self.image_path = None

        self.setWindowTitle("TerraSense AI")
        self.setMinimumSize(1200, 700)

        self.setStyleSheet(self.get_styles())

        self.build_ui()


    def build_ui(self):

        main_layout = QVBoxLayout()

        # Title
        title = QLabel("TerraSense AI — Precision Agriculture Platform")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("title")

        main_layout.addWidget(title)

        # Split layout
        split_layout = QHBoxLayout()

        split_layout.addWidget(self.build_input_panel(), 1)
        split_layout.addWidget(self.build_output_panel(), 2)

        main_layout.addLayout(split_layout)

        self.setLayout(main_layout)


    def build_input_panel(self):

        frame = QFrame()
        layout = QVBoxLayout()

        header = QLabel("INPUT")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        # Upload button
        self.upload_btn = QPushButton("Upload Soil Image")
        self.upload_btn.clicked.connect(self.upload_image)
        layout.addWidget(self.upload_btn)

        self.image_label = QLabel("No image selected")
        layout.addWidget(self.image_label)

        # Inputs
        self.lat = self.create_input(layout, "Latitude")
        self.lon = self.create_input(layout, "Longitude")
        self.acres = self.create_input(layout, "Acres")

        self.N = self.create_input(layout, "Nitrogen")
        self.P = self.create_input(layout, "Phosphorus")
        self.K = self.create_input(layout, "Potassium")
        self.ph = self.create_input(layout, "pH")

        # Button
        self.run_btn = QPushButton("Run Analysis")
        self.run_btn.clicked.connect(self.run_analysis)
        layout.addWidget(self.run_btn)

        layout.addStretch()

        frame.setLayout(layout)
        frame.setObjectName("inputPanel")

        return frame


    def build_output_panel(self):

        frame = QFrame()
        layout = QVBoxLayout()

        header = QLabel("OUTPUT")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        # Image preview
        self.ndvi_image = QLabel()
        self.ndvi_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ndvi_image.setMinimumHeight(400)
        self.ndvi_image.setObjectName("imagePreview")

        layout.addWidget(self.ndvi_image)

        # Output text
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                font-size: 14px;
                padding: 8px;
            }
        """)

        layout.addWidget(self.output_text)

        frame.setLayout(layout)
        frame.setObjectName("outputPanel")

        return frame


    def create_input(self, layout, label):

        row = QHBoxLayout()

        lbl = QLabel(label)
        lbl.setMinimumWidth(100)

        inp = QLineEdit()

        row.addWidget(lbl)
        row.addWidget(inp)

        layout.addLayout(row)

        return inp


    def upload_image(self):

        file, _ = QFileDialog.getOpenFileName()

        if file:
            self.image_path = file
            self.image_label.setText(file)


    def run_analysis(self):

        try:

            lat = float(self.lat.text())
            lon = float(self.lon.text())
            acres = float(self.acres.text())

            N = float(self.N.text())
            P = float(self.P.text())
            K = float(self.K.text())
            ph = float(self.ph.text())

            self.output_text.setText("Running satellite analysis...")

            self.worker = PredictionWorker(
                self.image_path,
                lat, lon, acres,
                N, P, K, ph
            )

            self.worker.finished.connect(self.show_result)
            self.worker.error.connect(self.show_error)

            self.worker.start()

        except Exception as e:
            self.output_text.setText(str(e))

    def show_result(self, result):

        # Show image
        tif_path = result["ndvi_image"]
        png_path = self.convert_tif_to_png(tif_path)
        pixmap = QPixmap(png_path)

        if not pixmap.isNull():

            scaled = pixmap.scaled(
                600, 400,
                Qt.AspectRatioMode.KeepAspectRatio
            )

            self.ndvi_image.setPixmap(scaled)

        text = f"""
        Detected Soil: {result['soil']}
        Recommended Crop: {result['crop']}
        NDVI Value: {result['ndvi']:.3f}
        Temperature: {result.get('temp', 'N/A')} °C
        Humidity: {result.get('humidity', 'N/A')} %
        Rainfall: {result.get('rainfall', 'N/A')} mm
        """

        self.output_text.setText(text)
        
    def convert_tif_to_png(self, tif_path):
        png_path = tif_path.replace(".tif", ".png")

        img = Image.open(tif_path)
        img.save(png_path)

        return png_path


    def show_error(self, msg):

        self.output_text.setText(msg)


    def get_styles(self):

        return """
        QWidget {
            background-color: #f4f6f8;
            font-size: 14px;
        }

        #title {
            font-size: 28px;
            font-weight: bold;
            color: #2e7d32;
            padding: 10px;
        }

        #panelHeader {
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
        }

        #inputPanel, #outputPanel {
            background-color: white;
            border-radius: 8px;
            padding: 15px;
            color: black;
        }

        QPushButton {
            background-color: #2e7d32;
            color: white;
            padding: 10px;
            border-radius: 6px;
        }

        QPushButton:hover {
            background-color: #1b5e20;
        }

        QLineEdit {
            background-color: white;
            color: black;
            padding: 6px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }

        #imagePreview {
            border: 2px solid #ccc;
            background-color: black;
        }
        
        QLabel {
            color: black;
        }
        """


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = TerraSenseGUI()
    window.show()

    sys.exit(app.exec())