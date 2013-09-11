# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.02.0" # refer to PEP-0008
__author__  = "David Cortesi"
__copyright__ = "Copyright 2011, 2012, 2013 David Cortesi"
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

from PyQt4.QtCore import (
    Qt,
    QString,
    QStringList,
    SIGNAL, SLOT
)
from PyQt4.QtGui import (QApplication,
                         QDialog,
                         QFont,QFontInfo,
                         QHBoxLayout,
                         QInputDialog,
                         QIntValidator,
                         QLabel,
                         QLineEdit,
                         QProgressBar,
                         QPushButton,
                         QSizePolicy,
                         QStatusBar,
                         QMessageBox,
                         QTextEdit,
                         QTextCursor,
                         QTextDocument,
                         QWidget
                         )
# Subroutine to get a QFont for an available monospaced font, preferably using
# the font family named in IMC.fontFamily (which is initialized above and set later
# by user selection from View > Font).
#
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

# Display a desperate query for how to open a file when the codec
# cannot be inferred. Offer choices of UTF-8, Latin-1, and Cancel
# n.b. Qt Assistant says (for C++) that the return is the pushButton
# object itself, but in PyQt, it is the button's index left to right.

def utfLtnMsg ( text, info=None ) :
    mb = makeMsg ( text, QMessageBox.Question, info)
    utf_button = mb.addButton("Open as UTF-8", QMessageBox.ActionRole)
    ltn_button = mb.addButton("Open as Latin-1", QMessageBox.ActionRole)
    mb.setStandardButtons(QMessageBox.Cancel)
    mb.setDefaultButton(QMessageBox.Cancel)
    ret = mb.exec_()
    if ret == QMessageBox.Cancel : return None
    if ret == 0 : return 'UTF-8'
    return 'ISO-8859-1'

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

# Functions to show and erase status bar messages. These are used for
# long-running operations such as setting scanno highlights where it
# is not practical to run a progress bar.
def showStatusMsg(text):
    IMC.statusBar.showMessage(text)
    QApplication.processEvents() # essential: force graphic update
def clearStatusMsg():
    IMC.statusBar.clearMessage()
    QApplication.processEvents() # force graphic update

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
    # Following line removed because its presence causes an error during
    # refresh of HTML preview of certain large files, "Error in sys.excepthook:
    # RuntimeError: maximum recursion depth exceeded while calling a Python object"
    #QApplication.processEvents() # force graphic update

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

# Formerly a single line-number widget, this is now a little info
# panel containing four widgets in an HBox layout, left to right:
#  Image [ nnnn].png  Line [ nnnnn] Col [ nnn] folio [ rrrrrrrrrr]
# Image and Line are QLineEdits, and the user can enter new values
# causing the edit cursor to move. Col and folio are labels displaying
# the current column and the folio number for the current page.

# The object is instantiated from, and hooked to its signal in, pqMain.
#

class lineLabel(QWidget):
    def __init__(self, parent=None):
        super(QWidget, self).__init__(parent)
        # Make a layout frame
        hb = QHBoxLayout()

	# Create the png display. Assuming scan filenames are always numeric.
	hb.addWidget(self.makeCaption(u"Image"))
	self.image = QLineEdit()
	self.image.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
	self.setWidth(self.image, 5)
	val = QIntValidator()
	val.setRange(1,9999) # png numbers start at 1
	self.image.setValidator(val)
	hb.addWidget(self.image)
	# Connect the image ReturnPressed signal to our slot for that
	self.connect(self.image, SIGNAL("returnPressed()"), self.movePng)

	# Create our line number widget
	hb.addWidget(self.makeCaption(u"Line"))
	self.lnum = QLineEdit()
	self.lnum.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
	# allow up to 5 digits, and ensure only digits can be entered.
	val = QIntValidator()
	val.setRange(1,99999) # Line numbers start at 1
	self.lnum.setValidator(val)
	self.setWidth(self.lnum, 6)
	hb.addWidget(self.lnum)
	# connect the lnum ReturnPressed signal to our slot for that
	self.connect(self.lnum, SIGNAL("returnPressed()"), self.moveLine)

	# Create a column-number display label
	hb.addWidget(self.makeCaption(u"Column"))
	self.cnum = QLabel()
	self.cnum.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
	self.setWidth(self.cnum, 3)
	hb.addWidget(self.cnum)

	# Create a folio display label which needs to be quite wide
	# because a roman-numeral can be long
	hb.addWidget(self.makeCaption(u"Folio"))
        self.folio = QLabel()
        self.folio.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setWidth(self.folio, 12)
        hb.addWidget(self.folio)

	# Add stretch to the right to keep the other things compact left
	hb.addStretch()
        self.setLayout(hb)

    # Convenience function to create a right-aligned caption label
    def makeCaption(self,text):
	    lbl = QLabel(text)
	    lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
	    return lbl
    # Convenience to set a width in digits on an object
    def setWidth(self,object, digits):
	    w = self.fontInfo().pixelSize() * digits
	    object.setMaximumWidth(w)
	    object.setMinimumWidth(w)

    # This slot receives the ReturnPressed signal from the image widget.
    # Check that the image is a valid index to the page table; if not
    # treat it as the very last page.  Get the textCursor for that page.
    # Pass its position to moveCursor.
    def movePng(self):
	(pn, flag) = self.image.text().toInt()
	pn -= 1 # page indices are origin-0
	mx = IMC.pageTable.size()
	if mx : # there is some page table data
	    if pn >= mx : # requested page doesn't exist
		pn = mx - 1 # go to last existing one
		self.image.setText(QString(str(pn)))
	    tc = IMC.pageTable.getCursor(pn-1)
	    self.moveCursor(tc.position())
	else : # this is not a paginated book document
	    self.image.setText(QString())
	    beep()
    # This slot receives the ReturnPressed signal from the lnum widget.
    # Get the specified textblock by number, or if it doesn't exist, the
    # end textblock, and use that to position the document.
    def moveLine(self):
	(bn, flag) = self.lnum.text().toInt()
	doc = IMC.editWidget.document()
	tb = doc.findBlockByLineNumber(bn-1) # text block is origin-0
	if not tb.isValid():
	    tb = doc.end()
	self.moveCursor(tb.position())
    # Given a document position, set the cursor to that spot, and put
    # the focus back in the editor so the cursor will be visible.
    def moveCursor(self, position):
        doc = IMC.editWidget.document()
        tc = IMC.editWidget.textCursor()
        tc.setPosition(position)
        IMC.editWidget.setTextCursor(tc)
        IMC.editWidget.setFocus(Qt.TabFocusReason)

    # This slot is connected to the editor's cursorPositionChanged signal.
    # Change the contents of the line number display to match the new position.
    # Change the contents of the column number display to match the new position.
    def cursorMoved(self):
        tc = IMC.editWidget.textCursor()
        bn = tc.blockNumber()
        self.lnum.setText(QString(str(bn+1)))
        cn = tc.positionInBlock()
        self.cnum.setText(QString(str(cn)))
	pn = IMC.pageTable.getIndex(tc.position())
	if pn >= 0 : # valid position, index is known
	    self.image.setText(IMC.pageTable.getScan(pn))
	    self.folio.setText(IMC.pageTable.getDisplay(pn))
	else : # no page data or cursor is ahead of first psep
	    self.image.setText(QString())
	    self.folio.setText(QString())

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

# Routine called during initialization (or anytime really) to
# note something with a timestamp on standard output.
# In theory one could take a command-line argument --log-level or
# such and control this output at run-time.
def noteEvent(description) :
    stamp = int(1000 * (time.clock() - time_now))
    #print(u'{0:08d} {1}'.format(stamp,description))

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
