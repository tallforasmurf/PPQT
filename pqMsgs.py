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
__email__ = "tallforasmurf@yahoo.com"
__status__ = "first-draft"
__license__ = '''
Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0)
http://creativecommons.org/licenses/by-nc-sa/3.0/
'''
from PyQt4.QtCore import (Qt, QString, QStringList )
from PyQt4.QtGui import (QApplication,
    QDialog,
    QFont,QFontInfo,
    QInputDialog,
    QIntValidator,
    QLineEdit,
    QProgressBar,
    QSizePolicy,
    QStatusBar,
    QMessageBox,
    QTextEdit,
    QTextCursor,
    QTextDocument)

# Subroutine to get a QFont for a monospaced font, preferably using the font
# family named in IMC.fontFamily -- set from the View menu in pqMain. If the
# msg parm is True and we don't get the requested font, we notify the user.
# (Only happens when pqEdit is setting up.)
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
# No return value. The first line of text is required. The second
# line, displayed in a smaller size, is optional.

def makeMsg ( text, icon, info = None):
    mb = QMessageBox( )
    mb.setText( text )
    mb.setIcon( icon )
    if info is not None:
	mb.setInformativeText( info )
    return mb

def infoMsg ( text, info = None ):
    mb = makeMsg(text,QMessageBox.Information,info)
    mb.exec_()

# Display a modal warning message, blocking until the user clicks OK
# No return value.

def warningMsg ( text, info = None ):
    mb = makeMsg(text, QMessageBox.Warning, info)
    mb.exec_()

# Display a modal query message, blocking until the user clicks OK/Cancel
# Return True for OK

def okCancelMsg ( text, info = None ):
    mb = makeMsg ( text, QMessageBox.Question, info)
    mb.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    return QMessageBox.Ok == mb.exec_()

# Display a modal request for string input, blocking until the user
# clicks Ok/Cancel. The parameters to QInputDialog.getText are:
# * the parent widget over which it will center,
# * title string for the dialog
# * label for the input field and the rest are defaulted.
# It returns a tuple of (entered-text, Ok-clicked).

def getStringMsg( title, text ):
    (ans, ok) = QInputDialog.getText(IMC.mainWindow, title, text)
    return (ans, ok)

# Display a modal request for a selection from a list of options.
# Blocks until the user clicks OK/Cancel. The parameters to getItem are:
# * the parent widget over which it will center
# * title string for the dialog
# * label text above the input combobox
# * QStringList of items among which to choose, e.g. dictionary tags
# * int initial selection index
# * bool for editable
# Others defaulted.
# QInputDialog returns a boolean True for OK, false for Cancel,
# and the actual text of the selected item or of the default item.

def getChoiceMsg( title, text, qsl):
    (ans, ok) = QInputDialog.getItem(IMC.mainWindow,title,text,qsl,
                                     0,False)
    return (ans, ok)

# Do a simple find for the Notes or Help panel. What is passed here is
# the Q[Plain]TextEdit on which the find will be done. We use that for the
# parent widget, so the dialog will center on that. Also we use the
# property-based api to QInputDialog so we can prime the input field with
# the currently selected edit text.

def getFindMsg( editWidget ):
    qd = QInputDialog(editWidget)
    qd.setInputMode(QInputDialog.TextInput)
    qd.setOkButtonText(QString("Find"))
    qd.setLabelText(QString("Text to find"))
    tc = editWidget.textCursor()
    if tc.hasSelection():
	qs = tc.selectedText()
	if qs.size() > 40 :
	    qs.truncate(40)
	qd.setTextValue(qs)
    b = (QDialog.Accepted == qd.exec_() )
    if b :
	return (True, qd.textValue())
    else:
	return (False, QString("") )

    
# Functions to create and manage a progress bar in our status bar
# makeBar is called from pqMain to initialize the bar, on the right in
# the status area.
def makeBarIn(status):
    IMC.statusBar = status # keep global ref to status bar
    IMC.progressBar = QProgressBar() # Keep a global ref to progress bar too
    IMC.progressBar.setOrientation(Qt.Horizontal)
    IMC.progressBar.reset()
    IMC.progressBar.setMinimumWidth(25)
    IMC.progressBar.setMaximumWidth(300)
    status.addPermanentWidget(IMC.progressBar)

# Initialize the bar at the beginning of some lengthy task, maxval is the
# number the lengthy task is working toward (e.g. count of lines) and msg
# goes in the status area to say what we're doing.
def startBar(maxval,msg):
    IMC.progressBar.reset()
    IMC.progressBar.setMaximum(maxval)
    IMC.statusBar.showMessage(QString(msg))
    QApplication.processEvents() # force graphic update

# Move the progress bar presumably higher, and force a round of app processing
# otherwise we never see the bar move.
def rollBar(newval):
    IMC.progressBar.setValue(newval)
    QApplication.processEvents() # force graphic update

# The big job is finished, clear the bar and its message.
def endBar():
    IMC.progressBar.reset()
    IMC.statusBar.clearMessage()
    QApplication.processEvents() # force graphic update

# Make a noise of some kind.
def beep():
    QApplication.beep()

# Subclass of QLineEdit to make our line-number widget for the status bar.
# Instantiated and hooked up to signals in pqMain.

class lineLabel(QLineEdit):
    def __init__(self, parent=None):
        super(QLineEdit, self).__init__(parent)
        self.setAlignment(Qt.AlignRight)
        # allow up to 5 digits. Editing a doc with > 99K lines? Good luck.
        val = QIntValidator()
        val.setRange(0,99999)
        self.setValidator(val)
        pxs = self.fontInfo().pixelSize()
        self.setMaximumWidth(6*pxs)
    # This slot receives the ReturnPressed signal from our widget, meaning
    # the user has finished editing the number. Move the editor's cursor
    # to the start of that line, or to the end of the document.
    def moveCursor(self):
        doc = IMC.editWidget.document()
        (bn, flag) = self.text().toInt()
        tb = doc.findBlockByLineNumber(bn)
        if not tb.isValid():
            tb = doc.end()
        tc = IMC.editWidget.textCursor()
        tc.setPosition(tb.position())
        IMC.editWidget.setTextCursor(tc)

    # This slot is connected to the editor's cursorPositionChanged signal.
    # Change the contents of the line number display to match the new position.
    def cursorMoved(self):
        bn = IMC.editWidget.textCursor().blockNumber()
        self.setText(QString(repr(bn)))

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv) # create an app
    from PyQt4.QtGui import QWidget
    class tricorder():
	def __init__(self):
		pass
    IMC = tricorder()
    IMC.mainWindow = QWidget()
    #beep()
    #infoMsg("This is the message","Did you get that?")
    #(s, b) = getStringMsg("TITLE STRING", "label text")
    #if b : print( "got "+s)
    #else: print("cancel")
    #ew = QTextEdit()
    #(b,qs) = getFindMsg(ew)
    #print(b,qs)
    qsl = QStringList()
    qsl.append("ONE")
    qsl.append("TWO")
    (s, b) = getChoiceMsg("TITLE STRING", "label text",qsl)
    if b : print ("Choice "+unicode(s))
    else: print ("Cancel "+unicode(s))