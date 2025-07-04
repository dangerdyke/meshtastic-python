"""A tkinter gui for meshtastic client functionality"""

from .application import MeshtasticApplication

def run_app():
    application: MeshtasticApplication = MeshtasticApplication()
    application.mainloop()
