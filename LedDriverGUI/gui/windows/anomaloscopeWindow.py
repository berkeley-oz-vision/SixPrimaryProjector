from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal, QThread
from collections import OrderedDict

from .. import guiSequence as seq
from .anomaloscopeMainWindow import AnomaloscopeWindow


def runTestCycler(gui):
    """Start LED cycling sequence - now redirects to new window implementation."""
    from ...testAnomaloscopeSync import createAnomaloscopeSyncWindow

    # Create and show the new anomaloscope sync window
    window = createAnomaloscopeSyncWindow(gui.app, gui)

    # Store reference to window in GUI object to prevent garbage collection
    if not hasattr(gui, 'anomaloscope_windows'):
        gui.anomaloscope_windows = []
    gui.anomaloscope_windows.append(window)

    print("Anomaloscope sync window created")
    return window


def runAnomaloscopeExperiment(gui):
    """Create and show the anomaloscope experiment window."""
    # Create and show the new anomaloscope experiment window
    window = AnomaloscopeWindow(gui.app, gui)

    # Store reference to window in GUI object to prevent garbage collection
    if not hasattr(gui, 'anomaloscope_experiment_windows'):
        gui.anomaloscope_experiment_windows = []
    gui.anomaloscope_experiment_windows.append(window)

    window.show()
    print("Anomaloscope experiment window created")
    return window


def runControllerWindow(gui):
    """Create and show a new controller status window."""
    # Create and show the controller window
    gui.createControllerWindow()
    print("Controller window created")
