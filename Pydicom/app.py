import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QSlider, QComboBox, QMessageBox, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
import numpy as np
import pydicom
from PIL import Image
import cv2
import axis
import app_functions


class DicomViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window setup
        self.setWindowTitle("DICOM PyQt Edition")
        self.setGeometry(200,200, 1000, 900)

        # Globals
        self.dicom_files = []
        self.single_file_mode = False
        self.max_v = None
        self.min_v = None
        self.actual_slice_number = 0

        # Central widget + scroll area for responsiveness
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout_main = QVBoxLayout(central_widget)
        layout_main.addWidget(scroll_area)

        scroll_content = QWidget()
        scroll_area.setWidget(scroll_content)
        self.layout = QVBoxLayout(scroll_content)

        # Title
        title = QLabel("DICOM Viewer")
        title.setStyleSheet("font-size: 36px; font-weight: bold; color: #2ECC71;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)

        # Notification Label
        self.notification = QLabel("Please select a DICOM directory or file")
        self.notification.setStyleSheet("color: red; font-size: 14px;")
        self.notification.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.notification)

        # Buttons Section
        self.create_buttons_section()

        # Image Display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # set a preferred fixed display area for consistent scaling
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setMaximumSize(1000, 1000)
        self.layout.addWidget(self.image_label)
        self.show_placeholder()

        # Preset Selector
        self.create_preset_section()

        # Sliders Section
        self.create_sliders_section()

    # -------------------- UI Setup -------------------- #
    def create_buttons_section(self):
        button_layout = QHBoxLayout()

        buttons = [
            ("Open Folder", self.open_dicoms),
            ("Open Single DICOM", self.open_single_dicom),
            ("Show Info", self.show_info),
            ("Save PNG", self.save_png),
            ("Anonymize", self.anonymize),
            ("Convert to MP4", self.convert_to_mp4),
            ("Show Axis Views", self.show_axis_views)
        ]

        for text, func in buttons:
            btn = QPushButton(text)
            btn.setStyleSheet("padding: 8px 12px; font-size: 14px;")
            btn.clicked.connect(func)
            button_layout.addWidget(btn)

        container = QWidget()
        container.setLayout(button_layout)
        self.layout.addWidget(container)

    def create_preset_section(self):
        preset_layout = QHBoxLayout()
        label = QLabel("Select HU Preset:")
        label.setStyleSheet("font-weight: bold;")
        preset_layout.addWidget(label)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Select Region", "Brain", "Chest", "Abdomen", "Neck", "Bone", "Lung", "Soft Tissue"])
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        preset_layout.addWidget(self.preset_combo)

        container = QWidget()
        container.setLayout(preset_layout)
        self.layout.addWidget(container)

    def create_sliders_section(self):
        slider_frame = QFrame()
        slider_layout = QVBoxLayout(slider_frame)

        # Each create_slider returns: (slider_widget, value_label, layout)
        self.slice_slider_widget, self.slice_value_label, slice_layout = self.create_slider("Slice", self.scroll_slider)
        self.max_slider_widget, self.max_value_label, max_layout = self.create_slider("Max", self.change_max)
        self.min_slider_widget, self.min_value_label, min_layout = self.create_slider("Min", self.change_min)

        # default ranges: slices will be updated after loading folder
        self.slice_slider_widget.setRange(0, 0)
        # sensible HU ranges for max/min (typical CT range)
        self.max_slider_widget.setRange(-2000, 4000)
        self.min_slider_widget.setRange(-2000, 4000)

        slider_layout.addLayout(slice_layout)
        slider_layout.addLayout(max_layout)
        slider_layout.addLayout(min_layout)

        self.layout.addWidget(slider_frame)

    def create_slider(self, label_text, func):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(60)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 0)  # default; will be set later when needed
        slider.valueChanged.connect(func)
        value_label = QLabel("0")
        value_label.setFixedWidth(60)
        layout.addWidget(label)
        layout.addWidget(slider)
        layout.addWidget(value_label)
        return slider, value_label, layout

    def show_placeholder(self):
        placeholder_path = os.path.join(os.getcwd(), "doc.jpg")
        if os.path.exists(placeholder_path):
            pixmap = QPixmap(placeholder_path).scaled(
                self.image_label.width(), self.image_label.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("No Image Loaded")

    # -------------------- Core Logic -------------------- #
    def open_dicoms(self):
        folder = QFileDialog.getExistingDirectory(self, "Select DICOM Folder")
        if folder:
            files = sorted([os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".dcm")])
            if not files:
                QMessageBox.warning(self, "No DICOMs", "No .dcm files found in the selected folder.")
                return
            self.dicom_files = files
            self.single_file_mode = False
            self.notification.setText(f"DICOM Folder Loaded ({len(self.dicom_files)} files)")

            # set slice slider range to match number of files
            self.slice_slider_widget.setRange(0, max(0, len(self.dicom_files) - 1))
            self.slice_slider_widget.setValue(0)
            self.slice_value_label.setText("0")

            # auto-display first image after folder load
            self.actual_slice_number = 0
            img = self.prepare_dicoms(self.dicom_files[0], self.min_v, self.max_v)
            self.show_image(img)

    def open_single_dicom(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select DICOM File", "", "DICOM Files (*.dcm)")
        if file_path:
            self.dicom_files = [file_path]
            self.single_file_mode = True
            self.notification.setText("Single DICOM File Loaded")
            # disable slice slider (only one slice)
            self.slice_slider_widget.setRange(0, 0)
            self.slice_slider_widget.setValue(0)
            self.slice_value_label.setText("0")
            img = self.prepare_dicoms(file_path, self.min_v, self.max_v)
            self.show_image(img)

    def convert_to_hu(self, ds):
        # convert pixel data to HU using RescaleSlope and RescaleIntercept safely
        image = ds.pixel_array.astype(np.int32)
        intercept = getattr(ds, 'RescaleIntercept', 0)
        slope = getattr(ds, 'RescaleSlope', 1)
        try:
            image = (image * float(slope)) + float(intercept)
        except Exception:
            image = image
        return image.astype(np.int32)

    def prepare_dicoms(self, dcm_file, min_v=None, max_v=None):
        """
        dcm_file: path to single DICOM file
        min_v, max_v: HU window values (min, max). Use None to auto-calc.
        returns: uint8 image scaled to 0..255
        """
        ds = pydicom.dcmread(dcm_file)
        dicom_array = self.convert_to_hu(ds)  # HU values (int)

        # Safe handling: use provided min/max only if not None
        if max_v is not None:
            try:
                HMAX = int(float(max_v))
            except Exception:
                HMAX = int(np.max(dicom_array))
        else:
            HMAX = int(np.max(dicom_array))

        if min_v is not None:
            try:
                HMIN = int(float(min_v))
            except Exception:
                HMIN = int(np.min(dicom_array))
        else:
            HMIN = int(np.min(dicom_array))

        # Swap if user provided min > max
        if HMIN > HMAX:
            HMIN, HMAX = HMAX, HMIN

        # avoid division by zero
        if HMAX == HMIN:
            out = np.full_like(dicom_array, fill_value=128, dtype=np.uint8)
            return out

        clipped = np.clip(dicom_array, HMIN, HMAX).astype(np.float32)
        normalized = (clipped - HMIN) / (HMAX - HMIN)
        out = np.uint8(np.round(normalized * 255.0))
        return out


    def show_image(self, img):
        # handle both 2d and 3d (if accidentally passed color)
        if img.ndim == 3 and img.shape[2] == 3:
            h, w, _ = img.shape
            bytes_per_line = 3 * w
            qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
            pixmap = QPixmap.fromImage(qimg)
        else:
            h, w = img.shape
            bytes_per_line = w
            qimg = QImage(img.data.tobytes(), w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            pixmap = QPixmap.fromImage(qimg)

        # Proper, consistent scaling to image_label's display area with smooth transformation
        target_w = self.image_label.width()
        target_h = self.image_label.height()
        scaled = pixmap.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled)

    def scroll_slider(self, value):
        # called when slice slider changes
        if not self.dicom_files:
            return
        idx = int(value)
        idx = max(0, min(idx, len(self.dicom_files) - 1))
        self.slice_value_label.setText(str(idx))
        self.actual_slice_number = idx
        slice_path = self.dicom_files[idx]
        img = self.prepare_dicoms(slice_path, self.min_v, self.max_v)
        self.show_image(img)

    def change_max(self, value):
        # update max HU value and refresh current image
        self.max_v = int(value)
        self.max_value_label.setText(str(self.max_v))
        if self.dicom_files:
            idx = getattr(self, "actual_slice_number", 0)
            idx = max(0, min(idx, len(self.dicom_files) - 1))
            img = self.prepare_dicoms(self.dicom_files[idx], self.min_v, self.max_v)
            self.show_image(img)

    def change_min(self, value):
        # update min HU value and refresh current image
        self.min_v = int(value)
        self.min_value_label.setText(str(self.min_v))
        if self.dicom_files:
            idx = getattr(self, "actual_slice_number", 0)
            idx = max(0, min(idx, len(self.dicom_files) - 1))
            img = self.prepare_dicoms(self.dicom_files[idx], self.min_v, self.max_v)
            self.show_image(img)

    def show_info(self):
        if not self.dicom_files:
            return
        dcm = pydicom.dcmread(self.dicom_files[0])
        infos_1, infos_2 = app_functions.return_information(dcm)
        QMessageBox.information(self, "DICOM Info", infos_1 + "\n" + infos_2)

    def save_png(self):
        if not self.dicom_files:
            return
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save")
        if folder:
            for dcm in self.dicom_files:
                name = os.path.basename(dcm)[:-4]
                img = self.prepare_dicoms(dcm, self.min_v, self.max_v)
                Image.fromarray(img).save(f"{folder}/{name}.png")
            QMessageBox.information(self, "Saved", "PNG images saved successfully!")

    def anonymize(self):
        if not self.dicom_files:
            return
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save Anonymized DICOMs")
        if folder:
            for dcm in self.dicom_files:
                name = os.path.basename(dcm)[:-4]
                anonymized = app_functions.anonymize_case(dcm)
                anonymized.save_as(f"{folder}/{name}.dcm")                                                
            QMessageBox.information(self, "Done", "Anonymization completed!")
                                      
    def convert_to_mp4(self):
        if not self.dicom_files:
            return
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save MP4")
        if folder:
            first_img = self.prepare_dicoms(self.dicom_files[0], self.min_v, self.max_v)
            h, w = first_img.shape
            frameSize = (w, h)
            out = cv2.VideoWriter(f'{folder}/output_video.mp4', cv2.VideoWriter_fourcc(*"mp4v"), 15, frameSize)
            for dcm in self.dicom_files:
                img = self.prepare_dicoms(dcm, self.min_v, self.max_v)
                bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                out.write(bgr)
            out.release()
            QMessageBox.information(self, "Done", "MP4 created!")

    def show_axis_views(self):
        if not self.dicom_files:
            QMessageBox.warning(self, "Warning", "Please open a DICOM first!")
            return
        folder = os.path.dirname(self.dicom_files[0])
        axis.show_axis_views(folder)

    def apply_preset(self, text):
        # presets map to (min, max)
        presets = {
            "Brain": (-100, 100),
            "Chest": (-160, 240),
            "Abdomen": (-150, 250),
            "Neck": (-120, 200),
            "Bone": (300, 2000),
            "Lung": (-1000, 400),
            "Soft Tissue": (-100, 300)
        }
        if text in presets and self.dicom_files:
            # note: preset tuple is (min, max)
            self.min_v, self.max_v = presets[text]
            # update slider widgets to show applied preset values
            self.min_slider_widget.setValue(self.min_v)
            self.max_slider_widget.setValue(self.max_v)
            self.min_value_label.setText(str(self.min_v))
            self.max_value_label.setText(str(self.max_v))
            img = self.prepare_dicoms(self.dicom_files[0], self.min_v, self.max_v)
            self.show_image(img)
            self.notification.setText(f"Preset applied: {text}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = DicomViewer()
    viewer.show()
    sys.exit(app.exec())
