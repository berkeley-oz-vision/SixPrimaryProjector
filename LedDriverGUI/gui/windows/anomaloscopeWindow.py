from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import pyqtSignal, QThread
from collections import OrderedDict

from .. import guiSequence as seq


# Legacy code commented out - replaced with new implementation in testAnomaloscopeSync.py


def runSequenceLoop(gui):
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
