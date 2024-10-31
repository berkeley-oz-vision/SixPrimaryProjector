import tkinter as tk
from screeninfo import get_monitors

class VisualCalibrationApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry("400x300")
        self.root.title("Calibration Selection")
        self.setup_ui()
        self.calibration_window = None
        self.second_screen_geometry = self.get_second_screen_geometry()

    def setup_ui(self):
        tk.Label(self.root, text="Select Calibration Mode:", font=("Arial", 14)).pack(pady=10)
        tk.Button(self.root, text="Bitmask Linearity Check", command=self.show_bitmask_linearity).pack(pady=5)
        tk.Button(self.root, text="Gradient Linearity Check", command=self.show_gradient_linearity).pack(pady=5)
        tk.Button(self.root, text="Select Full Color Check", command=self.show_full_color_selection).pack(pady=5)
        tk.Button(self.root, text="Select Two Colors", command=self.show_two_color_selection).pack(pady=5)

    def get_second_screen_geometry(self):
        monitors = get_monitors()
        if len(monitors) > 1:
            main_screen = monitors[0]
            second_screen = monitors[1]  # Assumes the second monitor is the one we want
            width, height = second_screen.width, second_screen.height
            self.second_screen_width = width
            self.second_screen_height = height
            return f"{width}x{height}+{main_screen.width}+0"
        else:
            # Fallback to fullscreen on the primary display if only one monitor is detected
            self.second_screen_width = monitors[0].width
            self.second_screen_height = monitors[0].height
            return f"{monitors[0].width}x{monitors[0].height}+0+0"

    def open_fullscreen_window(self):
        self.calibration_window = tk.Toplevel(self.root)
        self.calibration_window.geometry(self.second_screen_geometry)
        
        # Remove window decorations and make fullscreen
        self.calibration_window.attributes('-fullscreen', True)
        self.calibration_window.configure(bg="black")

        # Bind Escape key to exit fullscreen
        self.calibration_window.bind("<Escape>", lambda e: self.calibration_window.destroy())
        self.calibration_window.configure(bg="black")

        self.color_display = tk.Label(self.calibration_window, text="Click on a color to view its RGB value", font=("Arial", 14), fg="white", bg="black")
        self.color_display.pack()

    def on_click(self, event, color_value):
        # Get RGB value from the hex color
        rgb_color = self.hex_to_rgb(color_value)
        self.color_display.config(text=f"Clicked color RGB: {rgb_color}")

    def show_bitmask_linearity(self):
        self.open_fullscreen_window()

        colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
        intensity_steps = [(0, 1)] + [(2**i-1, 2**i) for i in range(1, 8)]
        window_width, window_height = 1140, 912

        def create_color_frame(parent, r, g, b, width, height):
            color = f"#{r:02x}{g:02x}{b:02x}"
            frame = tk.Frame(parent, bg=color, width=width, height=height)
            frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
            frame.bind("<Button-1>", lambda event, color_value=color: self.on_click(event, color))
            return frame

        for row, (r_base, g_base, b_base) in enumerate(colors):
            row_frame = tk.Frame(self.calibration_window)
            row_frame.pack(fill=tk.BOTH, expand=True)
            for low, high in intensity_steps:
                r, g, b = r_base * low, g_base * low, b_base * low
                create_color_frame(row_frame, r, g, b, width=window_width // (len(intensity_steps) * 2), height=window_height // 3)
                r, g, b = r_base * high, g_base * high, b_base * high
                create_color_frame(row_frame, r, g, b, width=window_width // (len(intensity_steps) * 2), height=window_height // 3)

    def show_gradient_linearity(self):
        self.open_fullscreen_window()

        colors = ["#ff0000", "#00ff00", "#0000ff"]
        for color in colors:
            row_frame = tk.Frame(self.calibration_window, bg="black")
            row_frame.pack(fill=tk.BOTH, expand=True)
            for i in range(256):
                intensity_color = self.rgb_to_hex(i if color == "#ff0000" else 0,
                                                  i if color == "#00ff00" else 0,
                                                  i if color == "#0000ff" else 0)
                frame = tk.Frame(row_frame, bg=intensity_color, width=self.second_screen_width / 256, height=self.second_screen_height // 3)
                frame.pack(side=tk.LEFT, fill=tk.Y)

                # Bind the click event to show RGB color on click
                frame.bind("<Button-1>", lambda event, color_value=intensity_color: self.on_click(event, color_value))

    def show_full_color_selection(self):
        color_input_window = tk.Toplevel(self.root)
        color_input_window.title("Select RGB Value")
        
        tk.Label(color_input_window, text="Red (0-255):").grid(row=0, column=0)
        red_entry = tk.Entry(color_input_window)
        red_entry.grid(row=0, column=1)
        
        tk.Label(color_input_window, text="Green (0-255):").grid(row=1, column=0)
        green_entry = tk.Entry(color_input_window)
        green_entry.grid(row=1, column=1)
        
        tk.Label(color_input_window, text="Blue (0-255):").grid(row=2, column=0)
        blue_entry = tk.Entry(color_input_window)
        blue_entry.grid(row=2, column=1)

        def display_color():
            try:
                r, g, b = int(red_entry.get()), int(green_entry.get()), int(blue_entry.get())
                if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                    self.open_fullscreen_window()
                    color_hex = self.rgb_to_hex(r, g, b)
                    self.calibration_window.configure(bg=color_hex)
                    self.calibration_window.bind("<Button-1>", lambda event, color_value=color_hex: self.on_click(event, color_value))
                else:
                    raise ValueError("RGB values must be between 0 and 255.")
            except ValueError as e:
                tk.messagebox.showerror("Invalid Input", str(e))
        
        tk.Button(color_input_window, text="Display Color", command=display_color).grid(row=3, column=0, columnspan=2)
    
    def show_two_color_selection(self):
        color_input_window = tk.Toplevel(self.root)
        color_input_window.title("Select Two RGB Values")
        
        tk.Label(color_input_window, text="Red 1 (0-255):").grid(row=0, column=0)
        red1_entry = tk.Entry(color_input_window)
        red1_entry.grid(row=0, column=1)
        
        tk.Label(color_input_window, text="Green 1 (0-255):").grid(row=1, column=0)
        green1_entry = tk.Entry(color_input_window)
        green1_entry.grid(row=1, column=1)
        
        tk.Label(color_input_window, text="Blue 1 (0-255):").grid(row=2, column=0)
        blue1_entry = tk.Entry(color_input_window)
        blue1_entry.grid(row=2, column=1)

        # Second color entries
        tk.Label(color_input_window, text="Red 2 (0-255):").grid(row=0, column=2)
        red2_entry = tk.Entry(color_input_window)
        red2_entry.grid(row=0, column=3)

        tk.Label(color_input_window, text="Green 2 (0-255):").grid(row=1, column=2)
        green2_entry = tk.Entry(color_input_window)
        green2_entry.grid(row=1, column=3)

        tk.Label(color_input_window, text="Blue 2 (0-255):").grid(row=2, column=2)
        blue2_entry = tk.Entry(color_input_window)
        blue2_entry.grid(row=2, column=3)

        def display_colors():
            try:
                r1, g1, b1 = int(red1_entry.get()), int(green1_entry.get()), int(blue1_entry.get())
                r2, g2, b2 = int(red2_entry.get()), int(green2_entry.get()), int(blue2_entry.get())
                
                if all(0 <= value <= 255 for value in [r1, g1, b1, r2, g2, b2]):
                    self.open_fullscreen_window()
                    
                    left_color = self.rgb_to_hex(r1, g1, b1)
                    right_color = self.rgb_to_hex(r2, g2, b2)

                    left_frame = tk.Frame(self.calibration_window, bg=left_color)
                    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                    left_frame.bind("<Button-1>", lambda event, color_value=left_color: self.on_click(event, color_value))

                    right_frame = tk.Frame(self.calibration_window, bg=right_color)
                    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
                    right_frame.bind("<Button-1>", lambda event, color_value=right_color: self.on_click(event, color_value))
                else:
                    raise ValueError("RGB values must be between 0 and 255.")
            except ValueError as e:
                tk.messagebox.showerror("Invalid Input", str(e))

        tk.Button(color_input_window, text="Display Colors", command=display_colors).grid(row=3, column=0, columnspan=4, pady=10)

    def rgb_to_hex(self, r, g, b):
        return f'#{r:02x}{g:02x}{b:02x}'

    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return r, g, b


if __name__ == "__main__":
    root = tk.Tk()
    app = VisualCalibrationApp(root)
    root.mainloop()