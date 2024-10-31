import tkinter as tk
import os

from LedDriverGUI.gui.utils.newport import NewPortWrapper

def _from_rgb(rgb):
    """translates an rgb tuple of int to a tkinter friendly color code
    """
    return "#%02x%02x%02x" % rgb

# TODO: improve this, terrible code
def run_gamma_check(self, dirname, step_size=1):
    instrum = NewPortWrapper()
    def record_power(control):
        power = instrum.measurePower()
        print(f"{control}, {power}")
        with open(gamma_check_power_filename, 'a') as file: # dank as fuck but whatever
            file.write(f'{control},{power},\n')

    for led in [0, 1, 2]:
        instrum.setInstrumWavelength(self.peak_wavelengths[led])
        
        gamma_check_power_filename = os.path.join(self.dirname, f'gamma_check_{led}.csv')
        with open(gamma_check_power_filename, 'w') as file:
            file.write('Control,Power\n')

        # Create main window
        root = tk.Tk()
        root.geometry('%dx%d+%d+%d' % (1140, 912, 1920, 0))
        root.configure(background=_from_rgb((0, 0, 0)))
        root.overrideredirect(True)
        root.state("zoomed")
        # root.attributes("-fullscreen", True)
        root.bind("<F11>", lambda event: root.attributes("-fullscreen",
                                            not root.attributes("-fullscreen")))
        root.bind("<Escape>", lambda event: root.attributes("-fullscreen", False))
        # root.geometry("500x500+200+200")
        root.title("Gamma Calibration Screen")
        root.resizable(width = False, height = False)

        def get_colour(index):
            colours = [_from_rgb(tuple([i if j == index else 0 for j in range(3)])) for i in range(0, 256, step_size)]
            values = [tuple([i if j == index else 0 for j in range(3)]) for i in range(0, 256, step_size)]
            for c, v in zip(colours, values):
                yield c, v
            yield None
        def start():
            out = next(colour_getter)
            if out is None:
                root.destroy()
                return
            color, value = out
            root.configure(background=color) # set the colour to the next colour generated
            record_power(value[led % 3])
            root.after(self.sleep_time * 1000, start) # unit is milliseconds
        
        colour_getter = get_colour(led % 3)

        start()
        root.mainloop()
