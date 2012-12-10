# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.01.0" # refer to PEP-0008
__author__  = "David Cortesi"
__copyright__ = "Copyright 2011, 2012 David Cortesi"
__maintainer__ = "?"
__email__ = "tallforasmurf@yahoo.com"
__status__ = "first-draft"
__license__ = '''
 License (GPL-3.0) :
    This file is part of PPQT.
    PPQT is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You can find a copy of the GNU General Public License in the file
    extras/COPYING.TXT included in the distribution of this program, or see:
    <http://www.gnu.org/licenses/>.
'''

'''
Misc message services factored out of various modules
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

# Subroutine to get a QFont for an available monospaced font, preferably using
# the font family named in IMC.fontFamily -- set from the View menu in pqMain.
# If the msg parm is True and we don't get the requested font, we notify the user.
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
    q2 = QString(qs) # make a copy
    if q2.length() > maxl:
	q2.truncate(maxl-3)
	q2.append(u"...")
    q2 = q2.replace(QString("<"),QString("&lt;"))
    return q2

# Internal function to initialize a Qt message-box object with an icon,
# a main message line, and an optional second message line.

def makeMsg ( text, icon, info = None):
    mb = QMessageBox( )
    mb.setText( text )
    mb.setIcon( icon )
    if info is not None:
	mb.setInformativeText( info )
    return mb

# Display a modal info message, blocking until the user clicks OK.
# No return value.

def infoMsg ( text, info = None ):
    mb = makeMsg(text, QMessageBox.Information, info)
    mb.exec_()

# Display a modal warning message, blocking until the user clicks OK.
# No return value

def warningMsg ( text, info = None ):
    mb = makeMsg(text, QMessageBox.Warning, info)
    mb.exec_()

# Display a modal query message, blocking until the user clicks OK/Cancel
# Return True for OK, False for Cancel.

def okCancelMsg ( text, info = None ):
    mb = makeMsg ( text, QMessageBox.Question, info)
    mb.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    return QMessageBox.Ok == mb.exec_()

# Display a modal request for string input, blocking until the user
# clicks Ok/Cancel. The parameters to QInputDialog.getText are:
# * the parent widget over which it will center,
# * title string for the dialog
# * label for the input field
# If no preset text is passed, the rest are defaulted.
# When preset text is passed, two additional parameters:
# * the default flag for echo mode QLineEdit::Normal
# * prepared text to put in the input field
# It returns a tuple of (entered-text, Ok-clicked).

def getStringMsg( title, text, preset=None ):
    if preset is None:
	(ans, ok) = QInputDialog.getText(IMC.mainWindow, title, text)
    else:
	(ans, ok) = QInputDialog.getText(IMC.mainWindow, title, text,
	                                 QLineEdit.Normal, preset)
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

def getChoiceMsg( title, text, qsl, current=0):
    (ans, ok) = QInputDialog.getItem(IMC.mainWindow,title,text,qsl,
                                     current,False)
    return (ans, ok)

# This is the UI to a simple find, used by the Notes, Preview, and Help panels.
# What is passed is:
# * parent widget over which to center the dialog
# * QString to initialize the dialog, typically the current selection
# We use the property-based api to QInputDialog so we can prime the input
# field with the provided text.

def getFindMsg( parentWidget, prepText = None ):
    qd = QInputDialog(parentWidget)
    qd.setInputMode(QInputDialog.TextInput)
    qd.setOkButtonText(QString('Find'))
    qd.setLabelText(QString('Text to find'))
    if (prepText is not None):
	if prepText.size() > 40 :
	    prepText.truncate(40)
	qd.setTextValue(prepText)
    b = (QDialog.Accepted == qd.exec_() )
    if b :
	return (True, qd.textValue())
    else:
	return (False, QString() )

    
# Functions to create and manage a progress bar in our status bar
# makeBar is called from pqMain to initialize the bar, on the right in
# the status area (addPermanentWidget installs to the right).
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
# goes in the status area to say what we're doing. Guard against callers
# e.g. pqFlow with a maxval of 0.
def startBar(maxval,msg):
    IMC.progressBar.reset()
    IMC.progressBar.setMaximum(max(maxval,10))
    IMC.statusBar.showMessage(QString(msg))
    QApplication.processEvents() # force graphic update

# Move the progress bar presumably higher, and force a round of app processing
# otherwise we never see the bar move. Guard against callers who don't
# really advance the bar.
def rollBar(newval):
    IMC.progressBar.setValue(max(newval,IMC.progressBar.value()))
    QApplication.processEvents() # force graphic update

# The big job is finished, clear the bar and its message.
def endBar():
    IMC.progressBar.reset()
    IMC.statusBar.clearMessage()
    QApplication.processEvents() # force graphic update

# Flash a brief message in the status bar, and if desired also beep.
def flash(message, dobeep=False, msecs=1000):
    IMC.statusBar.showMessage(message,msecs)
    if dobeep:
	beep()
    
# Make a noise of some kind.
def beep():
    QApplication.beep()

# Subclass of QLineEdit to make our line-number widget for the status bar.
# Defined here because it's a "message" of sorts. But actually it is
# instantiated and hooked up to signals in pqMain.

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
    # to the start of that line, or to the end of the document. Then put the
    # keyboard focus back in the editor so the cursor can be seen.
    def moveCursor(self):
        doc = IMC.editWidget.document()
        (bn, flag) = self.text().toInt()
        tb = doc.findBlockByLineNumber(bn)
        if not tb.isValid():
            tb = doc.end()
        tc = IMC.editWidget.textCursor()
        tc.setPosition(tb.position())
        IMC.editWidget.setTextCursor(tc)
	IMC.editWidget.setFocus(Qt.TabFocusReason)

    # This slot is connected to the editor's cursorPositionChanged signal.
    # Change the contents of the line number display to match the new position.
    def cursorMoved(self):
        bn = IMC.editWidget.textCursor().blockNumber()
        self.setText(QString(repr(bn)))

# debugging function to display a keyevent on the console
from PyQt4.QtCore import (QEvent)
from PyQt4.QtGui import (QKeyEvent)
def printKeyEvent(event):
    key = int(event.key())
    mods = int(event.modifiers())
    if key & 0x01000000 : # special/standard key
	print('logical key: mods {0:08X} key {1:08X}'.format(mods,key))
    else:
	cmods = u''
	if mods & Qt.ControlModifier : cmods += u'Ctl '
	if mods & Qt.AltModifier: cmods += u'Alt '
	if mods & Qt.ShiftModifier : cmods += u'Shft '
	if mods & Qt.KeypadModifier : cmods += u'Kpd '
	if mods & Qt.MetaModifier : cmods += u'Meta '
	cmods += "'{0:c}'".format(key)
	print(u'data key: mods {0:08X} key {1:08X} {2}'.format(mods,key,cmods))

# debugging function to note an event and its time on the console.
import time
time_now = time.clock() # moment module is imported

def noteEvent(description) :
    stamp = int(1000 * (time.clock() - time_now))
    print(u'{0:08d} {1}'.format(stamp,description))

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv) # create an app
    from PyQt4.QtGui import QWidget
    import pqIMC
    IMC = pqIMC.tricorder()
    IMC.mainWindow = QWidget()
    beep()
    noteEvent("about to call infoMsg")
    infoMsg("This is the message","Did you hear that beep?")
    noteEvent("about to call getStringMsg")
    (s, b) = getStringMsg("TITLE STRING", "label text")
    if b : print( "got "+s)
    else: print("cancel")
    (s, b) = getStringMsg("TITLE STRING", "what you should enter", "prepared")
    if b : print( "got "+s)
    else: print("cancel")    
    noteEvent("Whatever...")
    #ew = QTextEdit()
    #(b,qs) = getFindMsg(ew)
    #print(b,qs)
    qsl = QStringList()
    qsl.append("ONE")
    qsl.append("TWO")
    (s, b) = getChoiceMsg("TITLE STRING", "label text",qsl)
    if b : print ("Choice "+unicode(s))
    else: print ("Cancel "+unicode(s))
    printKeyEvent(
        QKeyEvent(QEvent.KeyPress,43,Qt.AltModifier|Qt.ControlModifier) )
    