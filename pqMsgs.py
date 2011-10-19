# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
Misc message services factored out of various modules
'''

__version__ = "0.1.0" # refer to PEP-0008
__author__  = "David Cortesi"
__copyright__ = "Copyright 2011, David Cortesi"
__maintainer__ = "?"
__email__ = "nobody@pgdp.net"
__status__ = "first-draft"
__license__ = '''
Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0)
http://creativecommons.org/licenses/by-nc-sa/3.0/
'''
from PyQt4.QtCore import (Qt, QString )
from PyQt4.QtGui import (QApplication, 
    QFont,QFontInfo,
    QInputDialog,
    QLineEdit,
    QProgressBar,
    QSizePolicy,
    QStatusBar,
    QMessageBox)

# Subroutine to get a QFont for a monospaced font, with the caller's preferred
# font family specified.
def getMonoFont(fontsize=12, msg=False):
    monofont = QFont()
    monofont.setStyleStrategy(QFont.PreferAntialias+QFont.PreferMatch)
    monofont.setStyleHint(QFont.Courier)
    monofont.setFamily(IMC.fontFamily)
    monofont.setFixedPitch(True) # probably unnecessary
    monofont.setPointSize(fontsize)
    monoinf = QFontInfo(monofont)
    if msg and (monoinf.family() != IMC.fontFamily):
	infoMsg("Font {0} not available, using {1}".format(
	    IMC.fontFamily, monoinf.family()) )
    return monofont

# Convenience function to truncate a qstring to a given length and append ...
# if necessary. Also, since Qt message boxes support html, convert any <
# into &lt;.
def trunc(qs,maxl):
    if qs.length() > maxl:
	qs.truncate(maxl-3)
	qs.append(u"...")
    q2 = qs.replace(QString("<"),QString("&lt;"))
    return q2

# Display a modal info message, blocking until the user clicks OK
# No return value.

def infoMsg ( text, info = None ):
    mb = QMessageBox( )
    mb.setText(text)
    mb.setIcon(QMessageBox.Information)
    if info is not None:
        mb.setInformativeText(info)
    mb.exec_()

# Display a modal warning message, blocking until the user clicks OK
# No return value.

def warningMsg ( text, info = None ):
    mb = QMessageBox( )
    mb.setText(text)
    mb.setIcon(QMessageBox.Warning)
    if info is not None:
        mb.setInformativeText(info)
    mb.exec_()

# Display a modal query message, blocking until the user clicks OK/Cancel
# Return True for OK

def okCancelMsg ( text, info = None ):
    mb = QMessageBox( )
    mb.setIcon(QMessageBox.Question)
    mb.setText(text)
    if info is not None:
        mb.setInformativeText(info)
    mb.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    return QMessageBox.Ok == mb.exec_()

# Display a modal request for string input, blocking until the user
# clicks Ok/Cancel. The parameters to getText are in order,
# * the parent widget over which it will center,
# * title string for the dialog
# * label for the input field and the rest are defaulted.
# It returns a tuple of (entered-text, Ok-clicked).

def getStringMsg( title, text ):
    (ans, ok) = QInputDialog.getText(IMC.mainWindow, title, text)
    return (ans, ok)

# Functions to create and manage a progress bar in our status bar
def makeBarIn(status):
    IMC.statusBar = status # keep global ref to status bar
    IMC.progressBar = QProgressBar() # Keep a global ref to progress bar too
    IMC.progressBar.setOrientation(Qt.Horizontal)
    IMC.progressBar.reset()
    IMC.progressBar.setMinimumWidth(25)
    IMC.progressBar.setMaximumWidth(300)
    status.addPermanentWidget(IMC.progressBar)
    #IMC.progressBar.hide()

def startBar(maxval,msg):
    IMC.progressBar.reset()
    IMC.progressBar.setMaximum(maxval)
    #IMC.progressBar.show()
    IMC.statusBar.showMessage(QString(msg))
    QApplication.processEvents() # force graphic update

def rollBar(newval):
    IMC.progressBar.setValue(newval)
    QApplication.processEvents() # force graphic update

def endBar():
    IMC.progressBar.reset()
    IMC.statusBar.clearMessage()
    QApplication.processEvents() # force graphic update

def beep():
    QApplication.beep()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv) # create an app
    from PyQt4.QtGui import QWidget
    class tricorder():
	def __init__(self):
		pass
    IMC = tricorder()
    IMC.mainWindow = QWidget()
    beep()
    infoMsg("This is the message","Did you get that?")
    (s, b) = getStringMsg("TITLE STRING", "label text")
    if b : print( "got "+s)
    else: print("cancel")

