import asyncio
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox as tkmsg
from threading import Thread
from concurrent.futures import Future
from typing import *

import meshtastic
from meshtastic import MeshInterface, SerialInterface, BLEInterface, TCPInterface

from bleak import BleakScanner
from pubsub import pub


class AppIO:
    """Singleton for managing application i/o thread."""
    # so help me goddess python async is impossible
    _io_thread: Thread
    _io_loop: asyncio.EventLoop

    @classmethod
    def init_state(cls):
        cls._io_thread = Thread(name="meshgui-io", target=cls._start_io_loop)
        cls._io_loop = asyncio.new_event_loop()
        cls._io_thread.start()

    @classmethod
    def _start_io_loop(cls):
        try:
            asyncio.set_event_loop(cls._io_loop)
            cls._io_loop.run_forever()
        finally:
            cls._io_thread.join()

    @classmethod
    def run_io_task(cls, coro: Coroutine, cb: Optional[Callable]=None):
        """Calls a coroutine in the application's designated IO thread"""
        future: Future = asyncio.run_coroutine_threadsafe(coro, cls._io_loop)
        if cb is not None:
            future.add_done_callback(cb)


class MeshtasticApplication(ttk.Frame):
    """Meshtastic main application window."""

    def __init__(self):
        AppIO.init_state()
        super().__init__(None)
        self.master.title("Meshtastic")
        #self.master.tk.call("wm", "group", )
        self.connections: dict[str, MeshInterface] = {}
        self._init_widgets()
        pub.subscribe(self._on_interface_connect, "meshtastic.connection.established")

    def _on_interface_connect(self, interface: MeshInterface):
        self.connections[interface.getShortName()] = interface

    def _init_widgets(self):
        self.ui_panes: ttk.PanedWindow = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.pack(expand=1)
        self.ui_panes.pack(fill=tk.BOTH, expand=1)
        self.ui_panes.add(DeviceList(self), weight=1)
        self.ui_panes.add(DevicePanel(self), weight=2)

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


class LabeledWidget(ttk.Frame):
    """A widget that is displayed next to a label"""

    def __init__(self, parent, text=None, texvariable=None, value=None):
        super().__init__(parent)
        self.label: ttk.Label = ttk.Label(self, text=text, textvariable=textvariable)
        self.value: tk.Widget
        if isinstance(value, tk.Widget):
            self.value = value
        elif isinstance(value, tk.Variable):
            self.value = ttk.Label(self, textvariable=value)

    def pack(self, **kwargs):
        super().pack(**kwargs)
        self.label.pack(side="left", fill=tk.X, expand=1)
        self.value.pack(side="right", fill=tk.X, expand=1)

    def grid(self, **kwargs):
        super().grid(**kwargs)
        self.label.grid(column=0, row=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.value.grid(column=1, row=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)


class DevicePanel(ttk.Notebook):
    """Contains information about a device interface"""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self.device: Optional[MeshInterface] = None
        self.tabs = meshtastic.util.dotdict()
        self.make_tabs()
        self.enable_traversal()

    def make_tabs(self):
        self.tabs.summary: DeviceSummary = DeviceSummary(self, self.device)
        self.add(self.tabs.summary, text="Device Summary")

    def set_device(self, device: MeshInterface):
        self.device = device


class DeviceSummary(ttk.Frame):
    """Displays a summary of basic info about a device interface"""

    def __init__(self, parent: tk.Widget, device: MeshInterface):
        super().__init__(parent)
        self.device: MeshInterface = device
        #self.


class CustomDialog(tk.Toplevel):
    """Convenience base class for custom dialog windows"""
    def __init__(self, parent: tk.Tk, title: str, grab_input: bool=True):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.wait_visibility()
        self.grab_set()

    def destroy(self):
        self.grab_release()
        super().destroy()

class DeviceConnectDialog(CustomDialog):
    """User dialog to connect to a meshtastic device"""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, "Add Meshtastic Device")
        self.parent = parent
        self.device_ctype: tk.StringVar = tk.StringVar(value="serial")
        self.device_ctype.trace_add("write", self.on_ctype_select)
        self.ctype_frame: ttk.LabelFrame = ttk.LabelFrame(self, text="Connection Interface")
        self.ctype_buttons: Tuple[ttk.Radiobutton] = (
            ttk.Radiobutton(self.ctype_frame, variable=self.device_ctype, value="serial", text="Serial/USB"),
            ttk.Radiobutton(self.ctype_frame, variable=self.device_ctype, value="ble", text="Bluetooth"),
            ttk.Radiobutton(self.ctype_frame, variable=self.device_ctype, value="tcp", text="TCP link"),
        )
        self.ctype_frame.pack(side="left", fill=tk.Y, expand=1)
        for button in self.ctype_buttons:
            button.pack(side="top", fill=tk.X, expand=0)

        self.interface_frame: ttk.Frame = ttk.Frame(self)
        self.current_interface_widget: ttk.Frame = self.SerialInterfaceWidget(self.interface_frame)
        self.connect_button = ttk.Button(self.interface_frame, text="Connect", command=self.do_connect)
        self.interface_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        self.connect_button.pack(side=tk.BOTTOM)
        self.current_interface_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def on_ctype_select(self, *args):
        "Changes the dialog when the selected connection type changes"
        self.current_interface_widget.destroy()
        selection: str = self.device_ctype.get()
        if selection == "serial":
            self.current_interface_widget = self.SerialInterfaceWidget(self.interface_frame)
        elif selection == "ble":
            self.current_interface_widget = self.BLEInterfaceWidget(self.interface_frame)
        elif selection == "tcp":
            self.current_interface_widget = self.TCPInterfaceWidget(self.interface_frame)

        self.current_interface_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def do_connect(self):
        interface, addr = self.current_interface_widget.connect_device()
        if interface is not None:
            self.parent.add_device(interface, self.current_interface_widget.ctype, addr)
            self.destroy()
        else:
            tkmsg.showwarning("Could Not Connect", "Failed to connect to the selected device.", parent=self)

    class SerialInterfaceWidget(ttk.Frame):
        ctype: str = "Serial/USB"
        def __init__(self, parent: tk.Widget):
            super().__init__(parent)
            self.ports_list_scroll: ttk.Scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
            self.ports_list: ttk.Treeview = ttk.Treeview(
                self, selectmode=tk.BROWSE, yscrollcommand=self.ports_list_scroll.set, show="tree"
            )
            self.ports_list_scroll["command"] = self.ports_list.yview
            #self.ports_list.bind("<<TreeViewSelect>>", self.validate_selection)
            self.ports_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
            self.ports_list_scroll.pack(side=tk.RIGHT, fill=tk.Y, expand=1)

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

        def connect_device(self) -> Optional[MeshInterface]:
            selection: tuple[str] = self.ports_list.selection()
            if len(selection) == 1 and self.ports_list.tag_has("port", selection[0]):
                iid: str = selection[0]
                port: str = self.ports_list.item(iid, "text")
                return meshtastic.serial_interface.SerialInterface(port), port

            return None

    class BLEInterfaceWidget(ttk.Frame):
        ctype: str = "Bluetooth"
        def __init__(self, parent: tk.Widget):
            super().__init__(parent)
            self.scan_state: tk.StringVar = tk.StringVar(value="scanning...")
            self.progress: ttk.ProgressBar = ttk.Progressbar(self, mode="determinate")
            self.progress_label: ttk.Label = ttk.Label(self, textvariable=self.scan_state)

            self.devlist_scroll: ttk.Scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
            # using treeview here because listview does not have ttk counterpart
            self.devlist: ttk.Treeview = ttk.Treeview(
                self, selectmode=tk.BROWSE, yscrollcommand=self.devlist_scroll.set,
                columns=("rssi"), displaycolumns=("#all")
            )
            self.devlist_scroll["command"] = self.devlist.yview
            self.devlist.heading("#0", text="Device")
            self.devlist.heading("rssi", text="RSSI")

            self.progress.pack(side=tk.TOP, fill=tk.X, expand=1, padx=5, pady=5)
            self.progress_label.pack(side=tk.TOP, fill=tk.X, expand=1)
            self.devlist.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
            self.devlist_scroll.pack(side=tk.RIGHT, fill=tk.Y, expand=1)

            self.devices: dict[str, str] = {}
            AppIO.run_io_task(self._scan_devices(), self._on_scan_complete)
            self.progress.start(10)

        async def _scan_devices(self):
            print("starting bt scan")
            uuid: str = meshtastic.ble_interface.SERVICE_UUID
            async with BleakScanner(self._on_device_found, service_uuids=[uuid]) as scanner:
                await asyncio.sleep(100)
                print("finished bt scan")

        # TODO: type annotations ommitted for now because bleak has horrid namespacing
        def _on_device_found(self, device, data):
            iid: str = self.devlist.insert("", tk.END, text=device.name, values=(data.rssi,))
            self.devices[iid] = device.address

        def _on_scan_complete(self, _: Any):
            self.scan_state.set("Scan Complete")
            self.progress.pack_forget()

        def connect_device(self) -> Optional[MeshInterface]:
            selection: tuple[str] = self.devlist.selection()
            if len(devlist) == 1:
                addr: str = self.devices[selection[0]]
                return BLEInterface(address=addr)

            return None

    class TCPInterfaceWidget(ttk.Frame):
        ctype: str = "TCP Link"
        def __init__(self, parent: tk.Widget):
            super().__init__(parent)
            self.host: tk.StringVar = tk.StringVar(value="localhost")
            self.port: tk.IntVar = tk.IntVar(value=4403)

            self.host_label: ttk.Label = ttk.Label(self, text="Address")
            self.host_entry: ttk.Entry = ttk.Entry(self, textvariable=self.host)
            self.port_label: ttk.Label = ttk.Label(self, text="Port")
            self.port_entry: ttk.Entry = ttk.Entry(self, textvariable=self.port)

            for widget in (self.host_label, self.host_entry, self.port_label, self.port_entry):
                widget.pack(side=tk.TOP, fill=tk.X, expand=True, ipadx=5)

        def connect_device(self) -> Optional[MeshInterface]:
            try:
                interface: TCPInterface = TCPInterface(host, portNumber=port)
                return interface
            except Exception:  # unsure what would actually get thrown here; python socket docs are unclear
                return None
