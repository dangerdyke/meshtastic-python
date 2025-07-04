import tkinter as tk
from tkinter import ttk
from tkinter import messagebox as tkmsg
from typing import *

import meshtastic
from meshtastic.mesh_interface import MeshInterface
from meshtastic.serial_interface import SerialInterface
from meshtastic.ble_interface import BLEInterface
from meshtastic.tcp_interface import TCPInterface

from pubsub import pub


class MeshtasticApplication(ttk.Frame):
    """Meshtastic main application window."""

    def __init__(self):
        super().__init__(None)
        self.master.title("Meshtastic")
        #self.master.tk.call("wm", "group", )
        self.pack(expand=1)

        self.dev_list: DeviceList = DeviceList(self)
        self.dev_list.pack(fill="both", expand=1)


class DeviceList(ttk.LabelFrame):
    """A scrollable list of detected nodes over serial, BLE, and network"""

    def __init__(self, master: tk.Tk):
        super().__init__(master, text="Meshtastic Devices", labelanchor="n")

        self.refresh_button: ttk.Button = ttk.Button(self, text="Add Device",
                                                     command=lambda: DeviceConnectDialog(self))
        self.y_scroll: ttk.Scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.list: ttk.Treeview = ttk.Treeview(
            self, selectmode=tk.BROWSE, yscrollcommand=self.y_scroll.set,
            columns=("device", "status", "ctype", "addr"),
            displaycolumns=("status", "ctype", "addr")
        )
        self.y_scroll["command"] = self.list.yview
        self.list.heading("#0", text="Device", anchor=tk.CENTER)
        self.list.heading("status", text="Status", anchor=tk.CENTER)
        self.list.heading("ctype", text="Interface", anchor=tk.CENTER)
        self.list.heading("addr", text="Address", anchor=tk.CENTER)

        self.refresh_button.pack(side="top", fill="x", expand=1)
        self.y_scroll.pack(side="right", fill="y", expand=1)
        self.list.pack(side="left", fill="both", expand=1)

    def add_device(self, device: MeshInterface, ctype: str, addr: str):
        self.list.insert("", "end", text=device.getLongName(), values=(device, "Connected", ctype, addr))


class CustomDialog(tk.Toplevel):
    """Convenience base class for custom dialog windows"""
    def __init__(self, parent, title):
        super().__init__()
        self.transient(parent)
        self.title(title)


class DeviceConnectDialog(CustomDialog):
    """User dialog to connect to a meshtastic device"""

    def __init__(self, parent):
        super().__init__(parent, "Add Meshtastic Device")
        self.parent = parent
        self.device_ctype: tk.StringVar = tk.StringVar(value="serial")
        self.ctype_frame: ttk.LabelFrame = ttk.LabelFrame(self, text="Connection Interface")
        self.ctype_buttons: Tuple[ttk.Radiobutton] = (
            ttk.Radiobutton(self.ctype_frame, variable=self.device_ctype, value="serial", text="Serial/USB"),
            ttk.Radiobutton(self.ctype_frame, variable=self.device_ctype, value="ble", text="Bluetooth"),
            ttk.Radiobutton(self.ctype_frame, variable=self.device_ctype, value="tcp", text="TCP link"),
        )
        self.ctype_frame.pack(side="left", fill=tk.Y, expand=1)
        for button in self.ctype_buttons:
            button.pack(side="top", fill=tk.X, expand=0)
            button.bind("<Button-1>", self.on_ctype_select)

        self.interface_frame: ttk.Frame = ttk.Frame(self)
        self.serial_interface_widget: SerialInterfaceWidget = self.SerialInterfaceWidget(self.interface_frame)
        self.ble_interface_widget: BLEInterfaceWidget = self.BLEInterfaceWidget(self.interface_frame)
        self.tcp_interface_widget: TCPInterfaceWidget = self.TCPInterfaceWidget(self.interface_frame)
        self.current_interface_widget: ttk.Frame = self.serial_interface_widget
        self.connect_button = ttk.Button(self.interface_frame, text="Connect", command=self.do_connect)
        self.interface_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        self.connect_button.pack(side=tk.BOTTOM)
        self.current_interface_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.current_interface_widget.on_active()

    def on_ctype_select(self, event: tk.Event):
        "Changes the dialog when the selected connection type changes"
        self.current_interface_widget.pack_forget()
        selection: str = event.widget["value"]
        if selection == "serial":
            self.current_interface_widget = self.serial_interface_widget
        elif selection == "ble":
            self.current_interface_widget = self.ble_interface_widget
        elif selection == "tcp":
            self.current_interface_widget = self.tcp_interface_widget

        self.current_interface_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.current_interface_widget.on_active()

    def do_connect(self):
        interface, addr = self.current_interface_widget.connect_device()
        if interface is not None:
            self.parent.add_device(interface, self.current_interface_widget.ctype, addr)
            self.destroy()
        else:
            tkmsg.showwarning("Could Not Connect", "Failed to connect to the selected device.", parent=self)

    class SerialInterfaceWidget(ttk.Frame):
        ctype: str = "Serial/USB"
        def __init__(self, parent):
            super().__init__(parent)
            self.ports_list_scroll: ttk.Scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
            self.ports_list: ttk.Treeview = ttk.Treeview(
                self, selectmode=tk.BROWSE, yscrollcommand=self.ports_list_scroll.set, show="tree"
            )
            self.ports_list_scroll["command"] = self.ports_list.yview
            #self.ports_list.bind("<<TreeViewSelect>>", self.validate_selection)

        def on_active(self):
            print("Serial connection dialog active")
            print(f"Searching for any of VIDs: {meshtastic.util.get_unique_vendor_ids()}")
            self.ports_list.delete(*self.ports_list.get_children())
            devices = meshtastic.util.detect_supported_devices()
            if len(devices) > 0:
                for device in devices:
                    print(f"Found serial device: {device.name}")
                    iid: str = self.ports_list.insert(
                        "", tk.END, text=f"{device.name} ({device.device_class})", tags=("device",), open=True
                    )
                    for port in meshtastic.util.active_ports_on_supported_devices((device,), True):
                        self.ports_list.insert(iid, tk.END, text=port, tags=("port",))
            else:
                for port in meshtastic.util.findPorts(True):
                    self.ports_list.insert("", tk.END, text=port, tags=("port",))

            self.ports_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
            self.ports_list_scroll.pack(side=tk.RIGHT, fill=tk.Y, expand=1)

        def connect_device(self) -> Optional[MeshInterface]:
            selection: tuple[str] = self.ports_list.selection()
            if len(selection) == 1 and self.ports_list.tag_has("port", selection[0]):
                iid: str = selection[0]
                port: str = self.ports_list.item(iid, "text")
                return meshtastic.serial_interface.SerialInterface(port), port

            return None

    class BLEInterfaceWidget(ttk.Frame):
        pass

    class TCPInterfaceWidget(ttk.Frame):
        ctype: str = "TCP Link"
        def __init__(self, parent):
            pass
