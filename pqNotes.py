# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
Create a plain-text editor for the user's personal notes, saved with the
file metadata. Implement extra keystrokes to allow easy storing of the
current line- or page-number of the main document or navigation to a
noted line or page.
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
import pqMsgs

from PyQt4.QtCore import ( QChar, QRegExp, QString, Qt, QString, SIGNAL)
from PyQt4.QtGui import (
    QFont, QFontInfo,
    QPlainTextEdit,
    QTextBlock, QTextCursor,
    QTextDocument, QTextEdit
)

class notesEditor(QPlainTextEdit):

    def __init__(self, parent=None, fontsize=12 ):
        super(notesEditor, self).__init__(parent)
        # Do not allow line-wrap; horizontal scrollbar appears when required.
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
	# get same font as main editor uses
        self.setFont(pqMsgs.getMonoFont(12,False))
	self.connect(self.document(), SIGNAL("modificationChanged(bool)"),self.eek)

    # called from pqEdit.clear()
    def clear(self):
	self.clearing = True
        self.document().clear()
	self.document().setModified(False)
	self.clearing = False

    # slot to receive the modificationChanged(bool) signal from our document.
    # if it indicates we are modified, set needMetadataSave true if it isn't
    # already. Should the user undo out of all changes, modval will be false
    # but we can't assume that negates a need to save metadata, some other
    # module might have set the flag since we did.
    def eek(self,modval):
	if not self.clearing :
	    IMC.needMetadataSave |= modval

    # Re-implement the parent's keyPressEvent in order to provide zoom:
    # ctrl-plus and ctrl-minus step the font size one point. Other keys:
    # shift-ctl-L inserts the current line number as {nnn}
    # ctl-L looks for a nearby {nnn} (braces required), selects it, and
    # tells the main editor to jump to that line.
    # shift-ctl-P insert the current page (scan) number as [nnn]
    # ctl-P looks for a nearby [nnn] (brackets required), selects it, and
    # tells the main editor to jump to that page position.
    def keyPressEvent(self, event):
	#pqMsgs.printKeyEvent(event)
	kkey = int(event.modifiers())+int(event.key())
	if kkey in IMC.keysOfInterest :
	    # tentatively assume we will process this key
	    event.accept()
	    if kkey in IMC.zoomKeys :
                n = (-1) if (kkey == IMC.ctl_minus) else 1
                p = self.fontInfo().pointSize() + n
                if (p > 3) and (p < 65): # don't let's get ridiculous, hmm?
                    f = self.font() # so get our font,
                    f.setPointSize(p) # change its point size +/-
                    self.setFont(f) # and put the font back
	    elif (kkey == IMC.ctl_alt_L): # ctrl/cmd-l with shift
		self.insertLine()
	    elif (kkey == IMC.ctl_L): # ctrl/cmd-l (no shift)
		self.goToLine()
	    elif (kkey == IMC.ctl_alt_P): # ctl/cmd-p
		self.insertPage()
	    elif (kkey == IMC.ctl_P): #ctl/cmd-P
		self.goToPage()
	    elif (kkey == IMC.ctl_F): # ctl/cmd f
		self.doFind()
            else: # one of the keys we support but not in this panel
                event.ignore() # so clear the accepted flag
        else: # not one of our keys at all
            event.ignore() # ensure the accepted flag is off
	if not event.isAccepted() : # if we didn't handle it, pass it up
	    super(notesEditor, self).keyPressEvent(event)

    # on ctl-alt-l (mac: opt-cmd-l), insert the current edit line number in
    # notes as {nnn}
    def insertLine(self):
	tc = self.textCursor() 
	bn = IMC.editWidget.textCursor().blockNumber() # line num
	tc.insertText(u"{{{0}}}".format(bn))

    # on ctl-l (mac: cmd-l) look for a {nnn} line number "near" our cursor in
    # the notes. Strategy: find-backwards for '{', the forward for regex (\d+)\}
    def goToLine(self):
	tc = self.document().find(QString(u'{'),
	                self.textCursor(), QTextDocument.FindBackward)
	if not tc.isNull(): # found it, or one. tc now selects the {
	    re = QRegExp(QString(u'\{\d+\}'))
	    tc.setPosition(tc.selectionStart()) # start looking left of {
	    tc = self.document().find(re,tc)
	    if not tc.isNull(): # found that. 
		self.setTextCursor(tc) # highlight the found string
		qs = tc.selectedText() # "{nnn}"
		qs.remove(0,1) # "nnn}"
		qs.chop(1) # "nnn"
		# toInt returns a tuple, (int, flag) where flag is false
		# if the conversion fails. In this case it cannot fail
		# since we found \d+ in the first place. However, the
		# number might be invalid as a line number.
		(bn,flg) = qs.toInt() # line number as int
		doc = IMC.editWidget.document() # main document
		tb = doc.findBlockByNumber(bn) # text block number bn
		if tb.isValid(): # if it exists,
		    tc = IMC.editWidget.textCursor() # cursor on main doc
		    tc.setPosition(tb.position()) # set it on block
		    IMC.editWidget.setTextCursor(tc) # make it visible
		    IMC.editWidget.setFocus(Qt.TabFocusReason)
	    else: # no {ddd} seen
		pqMsgs.beep()
	else: # no { preceding the cursor on same line
	    pqMsgs.beep()
    # Insert current page number as [ppp]. Conveniently, pqPngs saves the
    # index of the current page in the page table whenever the cursor moves.
    # (BUG: if there is no pngs folder, that won't happen)
    def insertPage(self):
	tc = self.textCursor()
	if IMC.currentPageIndex is not None:
	    qspn = IMC.pageTable[IMC.currentPageIndex][1]
	    tc.insertText("[{0}]".format(unicode(qspn)))

    # on ^p, look for [ppp] "near" our cursor in notes, and if found, tell
    # editor to go to that page text. See above for strategy.
    def goToPage(self):
	tc = self.document().find(QString(u'['),
	                self.textCursor(), QTextDocument.FindBackward)
	if not tc.isNull(): # found it, or one. tc now selects the [
	    re = QRegExp(QString(u'\[\d+\]'))
	    tc.setPosition(tc.selectionStart()) # start looking left of [
	    tc = self.document().find(re,tc)
	    if not tc.isNull(): # found that. 
		self.setTextCursor(tc) # highlight the found string
		qs = tc.selectedText() # "[nnn]"
		qs.remove(0,1) # "nnn]"
		qs.chop(1) # "nnn"
		(pn,flg) = qs.toInt() # page number as int 
		pn -= 1 # index to that page in the page table
		if (pn >= 0) and (pn < len(IMC.pageTable)) :
		    etc = IMC.pageTable[pn][0] # cursor for that page
		    doc = IMC.editWidget.document() # main document
		    IMC.editWidget.setTextCursor(etc) # make it visible
		    IMC.editWidget.setFocus(Qt.TabFocusReason)
		else: # should not occur
		    pqMsgs.beep()
	    else: # no [ppp] seen
		pqMsgs.beep()
	else: # no [ preceding the cursor on same line
	    pqMsgs.beep()

    # Do a simple find. getFindMsg returns (ok,find-text). This is a VERY
    # simple find from the present cursor position downward, case-insensitive.
    # If we get no hit we try once more from the top, thus in effect wrapping.    
    def doFind(self):
	(ok, findText) = pqMsgs.getFindMsg(self)
	if ok and (not findText.isNull()) :
	    if not self.find(findText): # no hits going down
		self.moveCursor(QTextCursor.Start) # go to top
		if not self.find(findText): # still no hit
		    pqMsgs.beep()