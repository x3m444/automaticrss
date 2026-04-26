import sys
import os
import subprocess
import servicemanager
import win32event
import win32service
import win32serviceutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON   = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
MAIN     = os.path.join(BASE_DIR, "main.py")


class AutomaticRSSService(win32serviceutil.ServiceFramework):
    _svc_name_         = "AutomaticRSS"
    _svc_display_name_ = "AutomaticRSS — automatizare torrente"
    _svc_description_  = "Monitorizare RSS + Watchlist + Transmission"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process    = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.process:
            self.process.terminate()
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self.process = subprocess.Popen(
            [PYTHON, MAIN],
            cwd=BASE_DIR,
        )
        self.process.wait()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AutomaticRSSService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AutomaticRSSService)
