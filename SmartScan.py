import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import datetime

# -------- Utility functions --------
def order_points_clockwise(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]     # top-left
    rect[2] = pts[np.argmax(s)]     # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect

def four_point_transform(image, pts):
    rect = order_points_clockwise(pts)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxW = max(int(widthA), int(widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxH = max(int(heightA), int(heightB))
    dst = np.array([[0,0],[maxW-1,0],[maxW-1,maxH-1],[0,maxH-1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxW, maxH))
    return warped

def detect_document_contour(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5,5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            return approx.reshape(4,2)
    return None

def enhance_document(warped):
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    th = cv2.adaptiveThreshold(gray, 255,
                               cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 15, 8)
    return th

# -------- Tkinter GUI --------
class SmartScanApp:
    def __init__(self, root):
        self.root = root
        root.title("SmartScan - Document Scanner")
        self.cap = None
        self.running = False
        self.frame = None
        self.last_scan = None

        # Buttons
        controls = ttk.Frame(root)
        controls.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

        ttk.Button(controls, text="Start Camera", command=self.start_camera).pack(side=tk.LEFT)
        ttk.Button(controls, text="Stop Camera", command=self.stop_camera).pack(side=tk.LEFT)
        ttk.Button(controls, text="Load Image", command=self.load_image).pack(side=tk.LEFT)
        ttk.Button(controls, text="Save Scan", command=self.save_scan).pack(side=tk.LEFT)
        ttk.Button(controls, text="Quit", command=self.quit).pack(side=tk.RIGHT)

        # Display frames
        display = ttk.Frame(root)
        display.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.left_label = ttk.Label(display)
        self.left_label.pack(side=tk.LEFT, padx=6, pady=6)
        self.right_label = ttk.Label(display)
        self.right_label.pack(side=tk.LEFT, padx=6, pady=6)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(root, textvariable=self.status_var).pack(side=tk.BOTTOM, fill=tk.X)

    def start_camera(self):
        if self.running: return
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Cannot open camera")
            return
        self.running = True
        self.root.after(10, self.video_loop)

    def stop_camera(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files","*.png;*.jpg;*.jpeg;*.bmp")])
        if not path: return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", "Failed to load image")
            return
        self.process_and_show(img)

    def process_and_show(self, frame):
        disp = frame.copy()
        pts = detect_document_contour(frame)
        if pts is not None:
            cv2.drawContours(disp, [pts.astype(int)], -1, (0,255,0), 2)
            warped = four_point_transform(frame, pts)
            enhanced = enhance_document(warped)
            enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        else:
            enhanced_rgb = np.zeros_like(frame)
            cv2.putText(enhanced_rgb, "No doc detected", (30,50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
        # resize
        left = cv2.resize(disp, (400,300))
        right = cv2.resize(enhanced_rgb, (400,300))
        self.tk_left = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(left, cv2.COLOR_BGR2RGB)))
        self.tk_right = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(right, cv2.COLOR_BGR2RGB)))
        self.left_label.configure(image=self.tk_left)
        self.right_label.configure(image=self.tk_right)
        self.last_scan = enhanced_rgb

    def video_loop(self):
        if not self.running: return
        ret, frame = self.cap.read()
        if not ret:
            self.stop_camera()
            return
        self.frame = frame
        self.process_and_show(frame)
        self.root.after(30, self.video_loop)

    def save_scan(self):
        if self.last_scan is None:
            messagebox.showinfo("Info", "No scan to save")
            return
        out_dir = filedialog.askdirectory()
        if not out_dir: return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(out_dir, f"scan_{ts}.png")
        cv2.imwrite(filename, self.last_scan)
        messagebox.showinfo("Saved", f"Saved to {filename}")

    def quit(self):
        self.stop_camera()
        self.root.quit()
        self.root.destroy()

def main():
    root = tk.Tk()
    SmartScanApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
