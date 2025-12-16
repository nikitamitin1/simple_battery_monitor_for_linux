import gi
import subprocess
import re
import os
import datetime
from datetime import timedelta
import glob
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

BATTERY_HISTORY_DIR = "/var/lib/upower"

css = b"""
window, GtkWindow {
    background-color: #000000;
    color: #FFFFFF;
}

/* Toggle button inactive */
.toggle-button-inactive {
    background-color: #000000;
    color: #FFFFFF;
    border: 1px solid #FFFFFF;
    border-radius: 6px;
}

/* Toggle button active */
.toggle-button-active {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #FFFFFF;
    border-radius: 6px;
}

headerbar, .titlebar, .header-bar {
    background-color: #000000;
    color: #FFFFFF;
}

GtkLabel {
    color: #FFFFFF;
}
"""


style_provider = Gtk.CssProvider()
style_provider.load_from_data(css)
Gtk.StyleContext.add_provider_for_screen(
    Gdk.Screen.get_default(),
    style_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
)

class BatteryMonitor(Gtk.Window):
    def __init__(self):
        super().__init__()

        self.current_battery = "BAT0"
        self.battery_history_files = {}
        self.battery_metadata = {}
        # window settings
        self.set_default_size(500, 500)

        header_bar = Gtk.HeaderBar(title="Battery Monitor")
        header_bar.set_show_close_button(True)
        self.set_titlebar(header_bar)
        self.set_resizable(False)

        # main box
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_vbox.set_margin_top(10)
        main_vbox.set_margin_bottom(20)
        main_vbox.set_margin_start(20)
        main_vbox.set_margin_end(20)
        self.add(main_vbox)

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        main_vbox.pack_start(frame, True, True, 0)


        self.fig, self.ax = plt.subplots(figsize=(6, 3))
        self.fig.patch.set_facecolor("black")
        self.ax.set_facecolor("black")
        self.ax.title.set_color("white")
        self.ax.xaxis.label.set_color("white")
        self.ax.yaxis.label.set_color("white")
        self.ax.tick_params(axis="x", colors="white")
        self.ax.tick_params(axis="y", colors="white")

        self.canvas = FigureCanvas(self.fig)

        self.canvas.set_size_request(100, 150)
        frame.add(self.canvas)

        #box of batteries switch buttons
        self.battery_switch_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        main_vbox.pack_start(self.battery_switch_buttons, False, False, 0)

        # box of info and buttons
        info_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)
        main_vbox.pack_start(info_hbox, False, False, 0)


        #
        self.info_label = Gtk.Label(label="Loading battery data...")
        self.info_label.set_xalign(0)
        info_hbox.pack_start(self.info_label, True, True, 0)

        # box of buttons
        self.button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        info_hbox.pack_end(self.button_box, False, False, 0)

        # buttons
        self.button1 = Gtk.Button(label="Performance")
        self.button2 = Gtk.Button(label="Balanced")
        self.button3 = Gtk.Button(label="Power-Saver")

        current_power_profile = self.get_current_power_profile()

        # after launch set active style only for button associated with current profile
        for btn in (self.button1, self.button2, self.button3):
            btn.get_style_context().add_class("toggle-button-inactive")
            btn_label = str(btn.get_label().strip().lower())
            print(btn_label == current_power_profile)
            print(btn_label, current_power_profile)
            if btn_label == str(current_power_profile):
                print("YES")
                btn.get_style_context().remove_class("toggle-button-inactive")
                btn.get_style_context().add_class("toggle-button-active")


        batteries_list = self.get_batteries()
        if not batteries_list:
            batteries_list = ["BAT0"]
        self.current_battery = batteries_list[0]
        default_battery = self.current_battery
        self.battery_buttons = {}
        for battery in batteries_list:
            self.button_battery = Gtk.Button(label=f"{battery}")
            self.button_battery.connect("clicked", self.on_battery_switcher_button_clicked, battery)
            self.battery_switch_buttons.pack_start(self.button_battery, 0, 0, False)
            self.battery_buttons[battery] = self.button_battery
            if battery == default_battery:
                self.button_battery.get_style_context().add_class("toggle-button-active")
            else:
                self.button_battery.get_style_context().add_class("toggle-button-inactive")




        # add signals
        self.button1.connect("clicked", self.on_button_clicked, "performance")
        self.button2.connect("clicked", self.on_button_clicked, "balanced")
        self.button3.connect("clicked", self.on_button_clicked, "power-saver")


        self.button_box.pack_start(self.button1, False, False, 0)
        self.button_box.pack_start(self.button2, False, False, 0)
        self.button_box.pack_start(self.button3, False, False, 0)

        self.update_battery_data(self.current_battery)
        self.update_graph()
        self.update_timer()

        self.show_all()

    def on_battery_switcher_button_clicked(self, button, battery):
        for _, btn in self.battery_buttons.items():
            btn.get_style_context().remove_class("toggle-button-active")
            btn.get_style_context().remove_class("toggle-button-inactive")
            btn.get_style_context().add_class("toggle-button-inactive")

        button.get_style_context().remove_class("toggle-button-inactive")
        button.get_style_context().add_class("toggle-button-active")

        self.current_battery = battery
        self.update_battery_data(battery)
        self.update_graph(battery)

        print(f"{battery}")


    def get_batteries(self):
        batteries = subprocess.run(
            ["ls", "/sys/class/power_supply/"],
            capture_output=True,
            text=True
        )

        batteries_list = [i for i in batteries.stdout.split() if "BAT" in i]
        print(batteries_list)
        return batteries_list

    def on_button_clicked(self, button, btn_action):

        for btn in (self.button1, self.button2, self.button3):
            btn.get_style_context().remove_class("toggle-button-active")
            btn.get_style_context().remove_class("toggle-button-inactive")
            btn.get_style_context().add_class("toggle-button-inactive")

        button.get_style_context().remove_class("toggle-button-inactive")
        button.get_style_context().add_class("toggle-button-active")


        subprocess.run(
                ["powerprofilesctl", "set", f"{btn_action}"],
            )

    def get_current_power_profile(self):
        current_power_profile = subprocess.run(
                ["powerprofilesctl", "get"],
            capture_output=True,
            text=True
            )
        return current_power_profile.stdout.strip()

    def update_timer(self):
        self.update_battery_data()
        self.update_graph()
        GLib.timeout_add_seconds(1, self.update_timer)

    def locate_history_file(self, model, serial):
        if not model or not serial:
            return None
        safe_model = model.strip().replace(" ", "_")
        safe_serial = serial.strip()
        pattern = os.path.join(BATTERY_HISTORY_DIR, f"history-charge-{safe_model}*{safe_serial}.dat")
        matches = sorted(glob.glob(pattern))
        return matches[0] if matches else None

    def update_battery_data(self, battery=None):
        if battery is None:
            battery = self.current_battery
        try:
            result = subprocess.run(
                ["upower", "-i", f"/org/freedesktop/UPower/devices/battery_{battery}"],
                capture_output=True,
                text=True,
            )
            output = result.stdout

            model_match = re.search(r"model:\s+(.+)", output)
            serial_match = re.search(r"serial:\s+(.+)", output)
            charge_match = re.search(r"percentage:\s+(\d+)%", output)
            state_match = re.search(r"state:\s+(\w+)", output)
            time_match = re.search(r"time to (full|empty):\s+([\d,]+\s+(?:hours?|minutes?))", output)
            current_energy_match = re.search(r"energy:\s+([\d,]+)", output)
            design_energy_match = re.search(r"energy-full-design:\s+([\d,]+)", output)
            capacity_match = re.search(r"capacity:\s+([\d.]+)", output)
            warning_level_match = re.search(r"warning-level:\s+(\w+)", output)
            charge_cycles_match = re.search(r"charge-cycles:\s+(\w+)", output)

            model = model_match.group(1).strip() if model_match else ""
            serial = serial_match.group(1).strip() if serial_match else ""
            charge = charge_match.group(1) if charge_match else "Unknown"
            state = state_match.group(1) if state_match else "Unknown"
            time_left = time_match.group(2) if time_match else "Connected, fully charged"
            current_energy = f"{current_energy_match.group(1)} Wh" if current_energy_match else "Unknown"
            design_energy = f"{design_energy_match.group(1)} Wh" if design_energy_match else "Unknown"
            capacity = f"{capacity_match.group(1)}%" if capacity_match else "Unknown"
            warning_level = warning_level_match.group(1) if warning_level_match else "Unknown"
            charge_cycles = charge_cycles_match.group(1) if charge_cycles_match else "Unknown"

            info = f"🔋 Charge Level: {charge}%\n" \
                   f"⚡ State: {state}\n"
            if state == "charging":
                info += f"⏳ Time to Full: {time_left}\n"
            elif state == "discharging":
                info += f"⏳ Time to Empty: {time_left}\n"
            info += f"✚ Current Energy: {current_energy}\n" \
                    f"🔧 Designed Full Energy: {design_energy}\n" \
                    f"❤️ Battery Capacity: {capacity}\n" \
                    f"⚠️ Warning Level: {warning_level}\n" \
                    f"🔄 Charge Cycles: {charge_cycles}"

            self.info_label.set_text(info)
            if model and serial:
                self.battery_metadata[battery] = {"model": model, "serial": serial}
                history_path = self.locate_history_file(model, serial)
                if history_path:
                    self.battery_history_files[battery] = history_path

        except Exception as e:
            self.info_label.set_text(f"Error fetching battery data: {str(e)}")

    def read_battery_history(self, battery=None):
        if battery is None:
            battery = self.current_battery
        history_file = self.battery_history_files.get(battery)
        if history_file is None:
            metadata = self.battery_metadata.get(battery, {})
            model = metadata.get("model")
            serial = metadata.get("serial")
            history_file = self.locate_history_file(model, serial)
            if history_file:
                self.battery_history_files[battery] = history_file
        if not history_file or not os.path.exists(history_file):
            print(f"Warning: Battery history file not found for {battery}.")
            return [], []

        now = datetime.datetime.now()
        cutoff_time = now - datetime.timedelta(hours=24)
        intervals = {}

        with open(history_file, "r") as file:
            for line in file:
                parts = line.strip().split("\t")
                if len(parts) < 2:
                    continue
                try:
                    timestamp = int(parts[0])
                    charge_level = float(parts[1].replace(",", "."))
                    time_obj = datetime.datetime.fromtimestamp(timestamp)
                    if time_obj >= cutoff_time:
                        rounded_time = time_obj.replace(minute=30, second=0, microsecond=0)
                        if rounded_time not in intervals:
                            intervals[rounded_time] = charge_level
                except ValueError:
                    continue

        sorted_times = sorted(intervals.keys())
        sorted_charges = [intervals[t] for t in sorted_times]

        # Ensure we have 24 data points by filling missing hours with the last known value
        complete_times = []
        complete_charges = []
        last_charge = None
        for hour in range(24):
            hour_time = cutoff_time + timedelta(hours=hour + 1)
            hour_time = hour_time.replace(minute=30, second=0, microsecond=0)
            complete_times.append(hour_time)
            if hour_time in intervals:
                last_charge = intervals[hour_time]
                complete_charges.append(last_charge)
            else:
                complete_charges.append(last_charge if last_charge is not None else 0)

        return complete_times, complete_charges

    def update_graph(self, battery=None):
        if battery is None:
            battery = self.current_battery
        times, charges = self.read_battery_history(battery)
        self.ax.clear()

        if not times or not charges:
            print("No valid battery history data found for the last 24 hours.")
            self.canvas.draw()
            return

        self.ax.set_facecolor("black")
        x_values = mdates.date2num(times)
        bar_width = 0.8 / 24.0

        self.ax.bar(
            x_values,
            charges,
            width=bar_width,
            color="#D3D3D3",
            edgecolor="#D3D3D3",
            alpha=0.9,
            align='center'
        )

        self.ax.set_title("Battery Charge History (Hourly)", color="white")
        # self.ax.set_xlabel("Time", color="white", labelpad=10)
        self.ax.set_ylabel("Charge Level (%)", color="white")
        self.ax.grid(True, linestyle="--", alpha=0.5, color="#666666")

        self.ax.spines["bottom"].set_color("white")
        self.ax.spines["left"].set_color("white")
        self.ax.tick_params(axis="x", colors="white", rotation=0)
        self.ax.tick_params(axis="y", colors="white")

        self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))

        x_min = x_values[0] - bar_width / 2
        x_max = x_values[-1] + bar_width / 2
        self.ax.set_xlim(x_min, x_max)
        self.ax.set_ylim(0, 100)

        self.fig.subplots_adjust(bottom=0.2)

        self.canvas.draw()


if __name__ == "__main__":
    app = BatteryMonitor()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()
