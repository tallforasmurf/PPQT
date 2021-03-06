# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.3.0"
__author__  = "David Cortesi"
__copyright__ = "Copyright 2011, 2012, 2013 David Cortesi"
__maintainer__ = "David Cortesi"
__email__ = "tallforasmurf@yahoo.com"
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
Create a plain-text editor for the user's personal notes, saved with the
file metadata. Implement extra keystrokes to allow easy storing of the
current line- or page-number of the main document or navigation to a
noted line or page.
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
        self.findText = QString()

    # called from pqEdit.clear()
    def clear(self):
        self.clearing = True
        self.document().clear()
        self.document().setModified(False)
        self.findText = QString()
        self.clearing = False

    # slot to receive the modificationChanged(bool) signal from our document.
    # if it indicates we are modified, set needMetadataSave true if it isn't
    # already. Should the user undo out of all changes, modval will be false
    # and we clear our flag, possibly making the flag 0.
    def eek(self,modval):
        if not self.clearing :
            if modval :
                IMC.needMetadataSave |= IMC.notePanelChanged
            else :
                IMC.needMetadataSave &= (0xff ^ IMC.notePanelChanged)
        IMC.mainWindow.setWinModStatus()

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
        kkey = int( int(event.modifiers()) & IMC.keypadDeModifier) | int(event.key())
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
            elif (kkey == IMC.ctl_alt_M): # ctrl/cmd-m with shift
                self.insertLine()
            elif (kkey == IMC.ctl_M): # ctrl/cmd-m (no shift)
                self.goToLine()
            elif (kkey == IMC.ctl_alt_P): # ctl/cmd-p
                self.insertPage()
            elif (kkey == IMC.ctl_P): #ctl/cmd-P
                self.goToPage()
            elif (kkey == IMC.ctl_F) or (kkey == IMC.ctl_G): # ctl/cmd f/g
                self.doFind(kkey)
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
        if IMC.currentImageNumber is not None:
            tc.insertText("[{0}]".format(unicode(IMC.currentImageNumber)))

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
                if (pn >= 0) and (pn < IMC.pageTable.size()) :
                    etc = IMC.pageTable.getCursor(pn) # cursor for that page
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
    def doFind(self,kkey):
        if (kkey == IMC.ctl_F) or (self.findText.isEmpty()) :
            # ctl+F, or ctl+G but no previous find done, show the find dialog
            # with a COPY of current selection as pqMsgs might truncate it
            prepText = QString(self.textCursor().selectedText())
            (ok, self.findText) = pqMsgs.getFindMsg(self,prepText)
        # dialog or no dialog, we should have some findText now
        if not self.findText.isEmpty() :
            if not self.find(self.findText): # no hits going down
                self.moveCursor(QTextCursor.Start) # go to top
                if not self.find(self.findText): # still no hit
                    pqMsgs.beep()