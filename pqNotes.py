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

from PyQt4.QtCore import ( QChar, QRegExp, QString, Qt, QString)
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

    def clear(self):
        self.document().clear()
    
    # Re-implement the parent's keyPressEvent in order to provide zoom:
    # ctrl-plus and ctrl-minus step the font size one point. Other keys:
    # shift-ctl-L inserts the current line number as {nnn}
    # ctl-L looks for a nearby {nnn} (braces required), selects it, and
    # tells the main editor to jump to that line.
    # shift-ctl-P insert the current page (scan) number as [nnn]
    # ctl-P looks for a nearby [nnn] (brackets required), selects it, and
    # tells the main editor to jump to that page position.
    def keyPressEvent(self, event):
	kkey = int(event.modifiers())+int(event.key())
	if kkey in IMC.keysOfInterest :
	    if (kkey == IMC.ctl_plus) or (kkey == IMC.ctl_minus) \
	    or (kkey == IMC.ctl_shft_equal) :
                event.accept()
                n = (-1) if (kkey == IMC.ctl_minus) else 1
                p = self.fontInfo().pointSize() + n
                if (p > 3) and (p < 65): # don't let's get ridiculous, hmm?
                    f = self.font() # so get our font,
                    f.setPointSize(p) # change its point size +/-
                    self.setFont(f) # and put the font back
	    elif (kkey == IMC.ctl_alt_L): # ctrl/cmd-l with shift
		event.accept()
		self.insertLine()
	    elif (kkey == IMC.ctl_L): # ctrl/cmd-l (no shift)
		event.accept()
		self.goToLine()
	    elif (kkey == IMC.ctl_alt_P): # ctl/cmd-p
		event.accept()
		self.insertPage()
	    elif (kkey == IMC.ctl_P): #ctl/cmd-P
		event.accept()
		self.goToPage()
            else: # one of the keys we support but not in this panel
                event.ignore()
        else: # not one of our keys at all
            event.ignore()
        # ignored or accepted, pass the event along.
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
		else: # should not occur
		    pqMsgs.beep()
	    else: # no [ppp] seen
		pqMsgs.beep()
	else: # no [ preceding the cursor on same line
	    pqMsgs.beep()
