# must precede anything except #comments, including the docstring
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
Define our editor, which holds the document and (for convenience) all its
related metadata, and provides it to the various other views.

The editor is a small modification of QPlainTextEdit, because QTextEdit is
oriented to rich-text and html docs and QPlainTextEdit is meant for flat
texts organized as lines. The base Qt editor is a modern one with full unicode
support and all the standard editing actions, including drag-n-drop and
undo/redo stacks, and graceful vertical and horizontal scrolling as the
window changes size.

The following properties are accessible to other code:
    .document()     QTextDocument being edited and its methods including:
                        .document().isModified() - dirty flag
                        .document().isEmpty()
                        .document().lineCount()
                        .document().findBlockByLineNumber() and others

We monitor keyEvents and add keystroke commands as follows:
  control-plus increases the display font size 1 point
  control-minus decreases it 1 point
  control-1..9 goes to bookmark 1..9
  control-alt-1..9 sets bookmark 1..9 to the current position

We implement a syntax-highlighter (a standard Qt feature meant to allow
program source syntax coloring) in order to provide scanno-hiliting and
spell-check-twiddly-red-underlines.
'''

from PyQt4.QtCore import (Qt, QChar, QCryptographicHash, QRect, QRegExp, QString, SIGNAL)
from PyQt4.QtGui import (
    QApplication, QBrush, QColor, QFont, QFontInfo, QMessageBox,
    QPlainTextEdit, QSyntaxHighlighter, QProgressDialog,
    QTextBlock, QTextCharFormat, QTextCursor,
    QTextDocument, QTextEdit
)

# get simple access to methods of the list objects
from pqLists import *
import pqMsgs
from collections import defaultdict

# Define a syntax highlighter object which will be linked into our editor.
# The edit init below instantiates this object and keeps addressability to it.
class wordHighLighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        global reWord
        super(wordHighLighter, self).__init__(parent)
        # store a local reference to the global regex
        self.wordMatch = reWord
        # Initialize text formats to apply to words from various lists.
        #  - Scanno candidates get a light lilac background.
        self.scannoFormat = QTextCharFormat()
        self.scannoFormat.setBackground(QBrush(QColor("#EBD7E6")))
        # Set the style for misspelt words. We underline in red using the
        # well-known wavy red underline, the same on all platforms.
        self.misspeltFormat = QTextCharFormat()
        self.misspeltFormat.setUnderlineStyle(QTextCharFormat.WaveUnderline)
        self.misspeltFormat.setUnderlineColor(QColor("red"))

    # The linked QPlainTextEdit calls this function for every text line in the
    # whole bloody document when highlighting is turned on via the View menu,
    # at least to judge by the hang-time. Later it only calls us to look at a
    # line as it changes in editing. Anyway it behooves us to be as quick as
    # possible. We don't actually check spelling, we just use the flag that
    # was set when the last spellcheck was done. In a new document there may
    # be no word census yet.
    # Note that either one or both of MC.scannoHiliteSwitch or IMC.spellingHiliteSwitch
    # are ON, or else we are called against an empty document -- see setHighlight below.
    def highlightBlock(self, text):
        # find each word in the text and test it against our lists
        i = self.wordMatch.indexIn(text,0) # first word if any
        while i >= 0:
            l = self.wordMatch.matchedLength()
            w = self.wordMatch.cap(0) # word as qstring
            if IMC.scannoHiliteSwitch: # we are checking for scannos:
                if IMC.scannoList.check(unicode(w)):
                    self.setFormat(i,l,self.scannoFormat)
            if IMC.spellingHiliteSwitch: # we are checking spelling:
                if (IMC.wordCensus.getFlag(w) & IMC.WordMisspelt):
                    self.setFormat(i,l,self.misspeltFormat)
            i = self.wordMatch.indexIn(text,i+l) # advance to next word

# Define the editor as a subclass of QPlainTextEdit. Only one object of this
# class is created, in ppqtMain. The fontsize arg is recalled from saved
# settings and passed in when the object is created.

class PPTextEditor(QPlainTextEdit):
    # Initialize the editor on creation.
    def __init__(self, parent=None, fontsize=12 ):
        super(PPTextEditor, self).__init__(parent)
        # Do not allow line-wrap; horizontal scrollbar appears when required.
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        # make sure when we jump to a line, it goes to the window center
        self.setCenterOnScroll(True)
        # Get a monospaced font as selected by the user with View>Font
        self.setFont(pqMsgs.getMonoFont(fontsize,True))
        # instantiate our "syntax" highlighter object, but link it to an empty
        # QTextDocument. We will redirect it to our actual document only after
        # loading a document, as it relies on metadata, and then only when/if
        # the IMC.*HiliteSwitch es are on.
        self.nulDoc = QTextDocument() # make a null document
        self.hiliter = wordHighLighter(self.nulDoc)
        # all the metadata lists will be initialized when self.clear() is
        # called from pqMain, shortly.
        # save a regex for quickly finding if a selection is a single word
        self.oneWordRE = QRegExp(u'^\W*(\w{2,})\W*$')
        self.menuWord = QString()
        # Create and initialize an SHA-1 hash machine
        self.cuisineart = QCryptographicHash(QCryptographicHash.Sha1)

    # switch on or off our text-highlighting. By switching the highlighter
    # to a null document we remove highlighting; by switching it back to
    # the real document, we cause re-highlighting of everything. This makes
    # significant delay for a large document, so put up a status message
    # during it by starting and ending a progress bar.
    def setHighlight(self, onoff):
        self.hiliter.setDocument(self.nulDoc) # turn off hiliting always
        if onoff:
            pqMsgs.showStatusMsg("Setting Scanno/Spelling Highlights...")
            self.hiliter.setDocument(self.document())
            pqMsgs.clearStatusMsg()

    # Implement clear/new. Just toss everything we keep.
    def clear(self):
        self.setHighlight(False)
        self.document().clear()
        self.document().setModified(False)
        self.bookMarkList = \
            [None, None, None, None, None, None, None, None, None]
        IMC.pageTable.clear()
        IMC.goodWordList.clear()
        IMC.badWordList.clear()
        IMC.wordCensus.clear()
        IMC.charCensus.clear()
        IMC.notesEditor.clear()
        IMC.pngPanel.clear()
        IMC.needSpellCheck = False
        IMC.needMetadataSave = 0x00
        IMC.staleCensus = 0x00
        IMC.bookSaveEncoding = QString(u'UTF-8')
        IMC.bookMainDict = IMC.spellCheck.mainTag
        # force a cursor "move" in order to create a cursorMoved signal that will
        # clear the status line - then undo it so the document isn't modified.
        self.textCursor().insertText(QString(' '))
        self.document().undo()


    # Implement the Edit menu items:
    # Edit > ToUpper,  Edit > ToTitle,  Edit > ToLower
    # Note that in full Unicode, changing letter case is not so simple as it
    # was in Latin-1! We use the QChar and QString facilities to do it, and
    # a regex in a loop to pick off words. Restore the current selection after
    # so another operation can be done on it.
    # N.B. it is not possible to do self.textCursor().setPosition(), it seems
    # that self.textCursor() is "const". One has to create a new cursor,
    # position it, and install it on the document with self.setTextCursor().
    def toUpperCase(self):
        global reWord
        tc = QTextCursor(self.textCursor())
        if not tc.hasSelection() :
            return # no selection, nothing to do
        startpos = tc.selectionStart()
        endpos = tc.selectionEnd()
        qs = QString(tc.selectedText()) # copy of selected text
        i = reWord.indexIn(qs,0) # index of first word if any
        if i < 0 : return # no words in selection, exit
        while i >= 0:
            w = reWord.cap(0) # found word as QString
            n = w.size() # its length
            qs.replace(i,n,w.toUpper()) # replace it with UC version
            i = reWord.indexIn(qs,i+n) # find next word if any
        # we have changed at least one word, replace selection with altered text
        tc.insertText(qs)
        # that wiped the selection, so restore it by "dragging" left to right
        tc.setPosition(startpos,QTextCursor.MoveAnchor) # click
        tc.setPosition(endpos,QTextCursor.KeepAnchor)   # drag
        self.setTextCursor(tc)

    # to-lower is identical except for the method call.
    def toLowerCase(self):
        global reWord # the regex \b\w+\b
        tc = QTextCursor(self.textCursor())
        if not tc.hasSelection() :
            return # no selection, nothing to do
        startpos = tc.selectionStart()
        endpos = tc.selectionEnd()
        qs = QString(tc.selectedText()) # copy of selected text
        i = reWord.indexIn(qs,0) # index of first word if any
        if i < 0 : return # no words in selection, exit
        while i >= 0:
            w = reWord.cap(0) # found word as QString
            n = w.size() # its length
            qs.replace(i,n,w.toLower()) # replace it with UC version
            i = reWord.indexIn(qs,i+n) # find next word if any
        # we have changed at least one word, replace selection with altered text
        tc.insertText(qs)
        # that wiped the selection, so restore it by "dragging" left to right
        tc.setPosition(startpos,QTextCursor.MoveAnchor) # click
        tc.setPosition(endpos,QTextCursor.KeepAnchor)   # drag
        self.setTextCursor(tc)

    # toTitle is similar but we have to change the word to lowercase (in case
    # it is uppercase now) and then change the initial character to upper.
    # Note it would be possible to write a smarter version that looked up the
    # word in a list of common adjectives, connectives, and adverbs and avoided
    # capitalizing a, and, of, by and so forth. Not gonna happen.
    def toTitleCase(self):
        global reWord # the regex \b\w+\b
        self.toLowerCase()
        tc = QTextCursor(self.textCursor())
        if not tc.hasSelection() :
            return # no selection, nothing to do
        startpos = tc.selectionStart()
        endpos = tc.selectionEnd()
        qs = QString(tc.selectedText()) # copy of selected text
        i = reWord.indexIn(qs,0) # index of first word if any
        if i < 0 : return # no words in selection, exit
        while i >= 0:
            w = reWord.cap(0) # found word as QString
            n = w.size()
            qs.replace(i,1,qs.at(i).toUpper()) # replace initial with UC
            i = reWord.indexIn(qs,i+n) # find next word if any
        # we have changed at least one word, replace selection with altered text
        tc.insertText(qs)
        # that wiped the selection, so restore it by "dragging" left to right
        tc.setPosition(startpos,QTextCursor.MoveAnchor) # click
        tc.setPosition(endpos,QTextCursor.KeepAnchor)   # drag
        self.setTextCursor(tc)

    # Re-implement the parent's keyPressEvent in order to provide some
    # special controls. (Note on Mac, "ctrl-" is "cmd-" and "alt-" is "opt-")
    # ctrl-plus increases the edit font size 1 pt
    # (n.b. ctrl-plus probably only comes from a keypad, we usually just get
    #  ctrl-shift-equals instead of plus)
    # ctrl-minus decreases the edit font size 1 pt
    # ctrl-<n> for n in 1..9 jumps the insertion point to bookmark <n>
    # ctrl-shift-<n> extends the selection to bookmark <n>
    # ctrl-alt-<n> sets bookmark n at the current position
    def keyPressEvent(self, event):
        #pqMsgs.printKeyEvent(event)
        kkey = int( int(event.modifiers()) & IMC.keypadDeModifier) | int(event.key())
        # add as little overhead as possible: if it isn't ours, pass it on.
        if kkey in IMC.keysOfInterest : # we trust python to do this quickly
            event.accept() # we handle this one
            if kkey in IMC.findKeys:
                # ^f, ^g, etc. -- just pass them straight to the Find panel
                self.emit(SIGNAL("editKeyPress"),kkey)
            elif kkey in IMC.zoomKeys :
                # n.b. the self.font and setFont methods inherit from QWidget
                # Point increment by which to change.
                n = (-1) if (kkey == IMC.ctl_minus) else 1
                # Actual point size currently in use, plus increment
                p = self.fontInfo().pointSize() + n
                if (p > 3) and (p < 65): # don't let's get ridiculous, hmm?
                    # Simply calling self.font().setPointSize() had no effect,
                    # we have to actually call setFont() to make change happen.
                    f = self.font() # so get our font,
                    f.setPointSize(p) # change its point size +/-
                    self.setFont(f) # and put the font back
                    IMC.fontSize = p # and remember the size for shutdown time
            elif kkey in IMC.markKeys : # ^1-9, jump to bookmark
                bkn = kkey - IMC.ctl_1 # make it 0-8
                if self.bookMarkList[bkn] is not None: # if that bookmark is set,
                    self.setTextCursor(self.bookMarkList[bkn]) # jump to it
            elif kkey in IMC.markShiftKeys : # shift-ctl-1/9, select to mark
                # Make our document cursor's selection go from our current ANCHOR
                # to the POSITION from the bookmark cursor.
                mark_tc = self.bookMarkList[kkey - IMC.ctl_shft_1]
                if mark_tc is not None:
                    tc = QTextCursor(self.textCursor())
                    tc.setPosition(mark_tc.position(),QTextCursor.KeepAnchor)
                    self.setTextCursor(tc)
            elif kkey in IMC.markSetKeys : # ctl-alt-1-9, set a bookmark
                bkn = kkey - IMC.ctl_alt_1 # make it 0-8
                self.bookMarkList[bkn] = QTextCursor(self.textCursor())
                IMC.needMetadataSave |= IMC.bookmarksChanged
        else: # not in keysOfInterest, so pass it up to parent
            event.ignore()
            super(PPTextEditor, self).keyPressEvent(event)

    # Called from pqFind after doing a successful search, this method centers the
    # current selection (which is the result of the find) in the window. If the selection
    # is large, put the top of the selection higher than center but on no account
    # above the top of the viewport. Two problems arise: One, the rectangles returned
    # by .cursorRect() and by .viewport().geometry() are in pixel units, while the
    # vertical scrollbar is sized in logical text lines. So we work out the adjustment
    # as a fraction of the viewport, times the scrollbar's pageStep value to get lines.
    # Two, cursorRect gives only the height of the actual cursor, not of the selected
    # text. To find out the height of the full selection we have to get a cursorRect
    # for the start of the selection, and another for the end of it.
    def centerCursor(self) :
        tc = QTextCursor(self.textCursor()) # copy the working cursor with its selection
        top_point = tc.position() # one end of selection, in character units
        bot_point = tc.anchor() # ..and the other end
        if top_point > bot_point : # often the position is > the anchor
            (top_point, bot_point) = (bot_point, top_point)
        tc.setPosition(top_point) # cursor for the top of the selection
        selection_top = self.cursorRect(tc).top() # ..get its top pixel
        line_height = self.cursorRect(tc).height() # and save height of one line
        tc.setPosition(bot_point) # cursor for the end of the selection
        selection_bot = self.cursorRect(tc).bottom() # ..selection's bottom pixel
        selection_height = selection_bot - selection_top + 1 # selection height in pixels
        view_height = self.viewport().geometry().height() # scrolled area's height in px
        view_half = view_height >> 1 # int(view_height/2)
        pixel_adjustment = 0
        if selection_height < view_half :
            # selected text is less than half the window height: center the top of the
            # selection, i.e., make the cursor_top equal to view_half.
            pixel_adjustment = selection_top - view_half # may be negative
        else :
            # selected text is taller than half the window, can we show it all?
            if selection_height < (view_height - line_height) :
                # all selected text fits in the viewport (with a little free): center it.
                pixel_adjustment = (selection_top + (selection_height/2)) - view_half
            else :
                # not all selected text fits the window, put text top near window top
                pixel_adjustment = selection_top - line_height
        # OK, convert the pixel adjustment to a line-adjustment based on the assumption
        # that a scrollbar pageStep is the height of the viewport in lines.
        adjust_fraction = pixel_adjustment / view_height
        vscroller = self.verticalScrollBar()
        page_step = vscroller.pageStep() # lines in a viewport page, actually less 1
        adjust_lines = int(page_step * adjust_fraction)
        target = vscroller.value() + adjust_lines
        if (target >= 0) and (target <= vscroller.maximum()) :
            vscroller.setValue(target)



    # Catch the contextMenu event and extend the standard context menu with
    # a separator and the option to add a word to good-words, but only when
    # there is a selection and it encompasses just one word.
    def contextMenuEvent(self,event) :
        ctx_menu = self.createStandardContextMenu()
        if self.textCursor().hasSelection :
            qs = self.textCursor().selectedText()
            if 0 == self.oneWordRE.indexIn(qs) : # it matches at 0 or not at all
                self.menuWord = self.oneWordRE.cap(1) # save the word
                ctx_menu.addSeparator()
                gw_name = QString(self.menuWord) # make a copy
                gw_action = ctx_menu.addAction(gw_name.append(QString(u' -> Goodwords')))
                self.connect(gw_action, SIGNAL("triggered()"), self.addToGW)
        ctx_menu.exec_(event.globalPos())

    # This slot receives the "someword -> good_words" context menu action
    def addToGW(self) :
        IMC.goodWordList.insert(self.menuWord)
        IMC.needMetadataSave |= IMC.goodwordsChanged
        IMC.needSpellCheck = True
        IMC.mainWindow.setWinModStatus()

    # Implement save: the main window opens the files for output using
    # QIODevice::WriteOnly, which wipes the contents (contrary to the doc)
    # so we need to write the document and metadata regardless of whether
    # they've been modified. However we avoid rebuilding metadata if we can.
    def save(self, dataStream, metaStream):
        # Get the contents of the document as a QString
        doc_text = self.toPlainText()
        # Calculate the SHA-1 hash over the document and save it in both hash
        # fields of the IMC.
        self.cuisineart.reset()
        self.cuisineart.addData(doc_text)
        IMC.metaHash = IMC.documentHash = bytes(self.cuisineart.result()).__repr__()
        # write the document, which is pretty simple in the QStream world
        dataStream << doc_text
        dataStream.flush()
        #self.rebuildMetadata() # update any census that needs it
        self.writeMetadata(metaStream)
        metaStream.flush()
        IMC.needMetadataSave = 0x00
        self.document().setModified(False) # this triggers main.setWinModStatus()

    def writeMetadata(self,metaStream):
        # Writing the metadata takes a bit more work.
        # pageTable goes out between {{PAGETABLE}}..{{/PAGETABLE}}
        metaStream << u"{{VERSION 0}}\n" # meaningless at the moment
        metaStream << u"{{ENCODING "
        metaStream << unicode(IMC.bookSaveEncoding)
        metaStream << u"}}\n"
        metaStream << u"{{STALECENSUS "
        if 0 == IMC.staleCensus :
            metaStream << u"FALSE"
        else:
            metaStream << u"TRUE"
        metaStream << u"}}\n"
        metaStream << u"{{NEEDSPELLCHECK "
        if 0 == IMC.needSpellCheck :
            metaStream << u"FALSE"
        else:
            metaStream << u"TRUE"
        metaStream << u"}}\n"
        metaStream << u"{{MAINDICT "
        metaStream << unicode(IMC.bookMainDict)
        metaStream << u"}}\n"
        # The hash could contain any character. Using __repr__ ensured
        # it is enclosed in balanced single or double quotes but to be
        # double sure we will fence it in characters we can spot with a regex.
        metaStream << u"{{DOCHASH " + IMC.documentHash + u" }}\n"
        if IMC.pageTable.size() :
            metaStream << u"{{PAGETABLE}}\n"
            for i in range(IMC.pageTable.size()) :
                metaStream << IMC.pageTable.metaStringOut(i)
            metaStream << u"{{/PAGETABLE}}\n"
        if IMC.charCensus.size() :
            metaStream << u"{{CHARCENSUS}}\n"
            for i in range(IMC.charCensus.size()):
                (w,n,f) = IMC.charCensus.get(i)
                metaStream << "{0} {1} {2}\n".format(unicode(w), n, f)
            metaStream << u"{{/CHARCENSUS}}\n"
        if IMC.wordCensus.size() :
            metaStream << u"{{WORDCENSUS}}\n"
            for i in range(IMC.wordCensus.size()):
                (w,n,f) = IMC.wordCensus.get(i)
                metaStream << "{0} {1} {2}\n".format(unicode(w), n, f)
            metaStream << u"{{/WORDCENSUS}}\n"
        metaStream << u"{{BOOKMARKS}}\n"
        for i in range(9): # 0..8
            if self.bookMarkList[i] is not None :
                metaStream << "{0} {1} {2}\n".format(i,self.bookMarkList[i].position(),self.bookMarkList[i].anchor())
        metaStream << u"{{/BOOKMARKS}}\n"
        metaStream << u"{{NOTES}}\n"
        d = IMC.notesEditor.document()
        if not d.isEmpty():
            for i in range( d.blockCount() ):
                t = d.findBlockByNumber(i).text()
                if t.startsWith("{{"):
                    t.prepend(u"\xfffd") # Unicode Replacement char
                metaStream << t + "\n"
            IMC.notesEditor.document().setModified(False)
        metaStream << u"{{/NOTES}}\n"
        if IMC.goodWordList.active() : # have some good words
            metaStream << u"{{GOODWORDS}}\n"
            IMC.goodWordList.save(metaStream)
            metaStream << u"{{/GOODWORDS}}\n"
        if IMC.badWordList.active() : # have some bad words
            metaStream << u"{{BADWORDS}}\n"
            IMC.badWordList.save(metaStream)
            metaStream << u"{{/BADWORDS}}\n"
        p1 = self.textCursor().selectionStart()
        p2 = self.textCursor().selectionEnd()
        metaStream << u"{{CURSOR "+unicode(p1)+u' '+unicode(p2)+u"}}\n"
        metaStream.flush()

    # Implement load: the main window has the job of finding and opening files
    # then passes QTextStreams ready to read here. If metaStream is None,
    # no metadata file was found and we construct the metadata.
    # n.b. before main calls here, it calls our .clear, hence lists are
    # empty, hiliting is off, etc.

    def load(self, dataStream, metaStream, goodStream, badStream):
        # Load the document file into the editor
        self.setPlainText(dataStream.readAll())
        # Initialize the hash value for the document, which will be equal unless
        # we read something different from the metadata file.
        self.cuisineart.reset()
        self.cuisineart.addData(self.toPlainText())
        IMC.metaHash = IMC.documentHash = bytes(self.cuisineart.result()).__repr__()
        if metaStream is None:
            # load goodwords, badwords, and take census
            if goodStream is not None:
                IMC.goodWordList.load(goodStream)
            if badStream is not None:
                IMC.badWordList.load(badStream)
            self.rebuildMetadata(page=True) # build page table & vocab from scratch
        else:
            self.loadMetadata(metaStream)
        # If the metaData and document hashes now disagree, it is because the metadata
        # had a DOCHASH value for a different book or version. Warn the user.
        if IMC.metaHash != IMC.documentHash :
            pqMsgs.warningMsg(u"The document file and metadata file do not match!",
                              u"Bookmarks, page breaks and other metadata will be wrong! Strongly recommend you not edit or save this book.")
        # restore hiliting if the user wanted it. Note this can cause a
        # serious delay if the new book is large. However the alternative is
        # to not set it on and then we are out of step with the View menu
        # toggles, so the user has to set it off before loading, or suffer.
        self.setHighlight(IMC.scannoHiliteSwitch or IMC.spellingHiliteSwitch)
        # set a different main dict if there was one in the metadata
        if IMC.bookMainDict is not None:
            IMC.spellCheck.setMainDict(IMC.bookMainDict)

    # load page table & vocab from the .meta file as a stream.
    # n.b. QString has a split method we could use but instead
    # we take the input line to a Python u-string and split it. For
    # the word/char census we have to take the key back to a QString.
    def loadMetadata(self,metaStream):
        sectionRE = QRegExp( u"\{\{(" + '|'.join (
            ['PAGETABLE','CHARCENSUS','WORDCENSUS','BOOKMARKS',
             'NOTES','GOODWORDS','BADWORDS','CURSOR','VERSION',
             'STALECENSUS','NEEDSPELLCHECK','ENCODING', 'DOCHASH', 'MAINDICT'] ) \
                             + u")(.*)\}\}",
            Qt.CaseSensitive)
        metaVersion = 0 # base version
        while not metaStream.atEnd() :
            qline = metaStream.readLine().trimmed()
            if qline.isEmpty() : continue # allow blank lines between sections
            if sectionRE.exactMatch(qline) : # section start
                section = sectionRE.cap(1)
                argument = unicode(sectionRE.cap(2).trimmed())
                endsec = QString(u"{{/" + section + u"}}")
                if section == u"VERSION":
                    if len(argument) != 0 :
                        metaVersion = int(argument)
                    continue # no more data after {{VERSION x }}
                elif section == u"STALECENSUS" :
                    if argument == u"TRUE" :
                        IMC.staleCensus = IMC.staleCensusLoaded
                    continue # no more data after {{STALECENSUS x}}
                elif section == u"NEEDSPELLCHECK" :
                    if argument == u"TRUE" :
                        IMC.needSpellCheck = True
                    continue # no more data after {{NEEDSPELLCHECK x}}
                elif section == u"ENCODING" :
                    IMC.bookSaveEncoding = QString(argument)
                    continue
                elif section == u"MAINDICT" :
                    IMC.bookMainDict = QString(argument)
                    continue
                elif section == u"DOCHASH" :
                    IMC.metaHash = argument
                    continue
                elif section == u"PAGETABLE":
                    qline = metaStream.readLine()
                    while (not qline.startsWith(endsec)) and (not qline.isEmpty()):
                        IMC.pageTable.metaStringIn(qline)
                        qline = metaStream.readLine()
                    continue
                elif section == u"CHARCENSUS":
                    qline = metaStream.readLine()
                    while (not qline.startsWith(endsec)) and (not qline.isEmpty()):
                        # can't just .split the char census, the first
                        # char is the char being counted and it can be a space.
                        str = unicode(qline)
                        parts = str[2:].split(' ')
                        IMC.charCensus.append(QString(str[0]),int(parts[0]),int(parts[1]))
                        qline = metaStream.readLine()
                    continue
                elif section == u"WORDCENSUS":
                    qline = metaStream.readLine()
                    while (not qline.startsWith(endsec)) and (not qline.isEmpty()):
                        parts = unicode(qline).split(' ')
                        IMC.wordCensus.append(QString(parts[0]),int(parts[1]),int(parts[2]))
                        qline = metaStream.readLine()
                    continue
                elif section == u"BOOKMARKS":
                    qline = metaStream.readLine()
                    while (not qline.startsWith(endsec)) and (not qline.isEmpty()):
                        parts = unicode(qline).split(' ')
                        tc = QTextCursor(self.document() )
                        tc.setPosition(int(parts[1]))
                        if len(parts) == 3 : # early versions didn't save anchor
                            tc.movePosition(int(parts[2]),QTextCursor.KeepAnchor)
                        self.bookMarkList[int(parts[0])] = tc
                        qline = metaStream.readLine()
                    continue
                elif section == u"NOTES":
                    e = IMC.notesEditor
                    e.setUndoRedoEnabled(False)
                    qline = metaStream.readLine()
                    while (not qline.startsWith(endsec)) and not metaStream.atEnd():
                        if qline.startsWith(u"\xfffd"): # escaped {{
                            qline.remove(0,1)
                        e.appendPlainText(qline)
                        qline = metaStream.readLine()
                    e.setUndoRedoEnabled(True)
                    continue
                elif section == u"GOODWORDS" :
                    # not going to bother checking for endsec return,
                    # if it isn't that then we will shortly fail anyway
                    w = IMC.goodWordList.load(metaStream,endsec)
                    continue
                elif section == u"BADWORDS" :
                    w = IMC.badWordList.load(metaStream,endsec)
                    continue
                elif section == u"CURSOR" : # restore selection as of save
                    p1p2 = argument.split(' ')
                    tc = QTextCursor(self.document())
                    tc.setPosition(int(p1p2[0]),QTextCursor.MoveAnchor)
                    tc.setPosition(int(p1p2[1]),QTextCursor.KeepAnchor)
                    self.setTextCursor(tc)
                else:
                    # this can't happen; section is text captured by the RE
                    # and we have accounted for all possibilities
                    raise AssertionError, "impossible metadata"
            else: # Non-blank line that doesn't match sectionRE?
                pqMsgs.infoMsg(
                    "Unexpected line in metadata: {0}".format(pqMsgs.trunc(qline,20)),
                        "Metadata may be incomplete, suggest quit")
                break

    # Rebuild as much of the char/word census and spellcheck as we need to.
    # This is called from load, above, and from the Char and Word panels
    # Refresh buttons. If page=True we are loading a doc for which there is
    # no metadata file, so cache page definitions; otherwise just skip the
    # page definitions (see doCensus). If the doc has changed we need to
    # rerun the full char/word census. But if not, we might still need a
    # spellcheck, if the dictionary has changed.
    def rebuildMetadata(self,page=False):
        if page or (0 != IMC.staleCensus) :
            self.doCensus(page)
        if IMC.needSpellCheck :
            self.doSpellcheck()

    # Go through vocabulary census and check the spelling (it would be a big
    # waste of time to check every word as it was read). If the spellcheck
    # is not up (i.e. it couldn't find a dictionary) we only mark as bad the
    # words in the badwords list.
    def doSpellcheck(self):
        canspell = IMC.spellCheck.isUp()
        nwords = IMC.wordCensus.size()
        if 0 >= nwords : # could be zero in a null document
            return
        pqMsgs.startBar(nwords,"Checking spelling...")
        for i in range(IMC.wordCensus.size()):
            (qword, cnt, wflags) = IMC.wordCensus.get(i)
            wflags = wflags & (0xff - IMC.WordMisspelt) # turn off flag if on
            # some words have /dict-tag, split that out as string or ""
            (w,x,d) = unicode(qword).partition("/")
            if IMC.goodWordList.check(w):
                pass
            elif IMC.badWordList.check(w) :
                wflags |= IMC.WordMisspelt
            elif canspell : # check word in its optional dictionary
                if not ( IMC.spellCheck.check(w,d) ) :
                    wflags |= IMC.WordMisspelt
            IMC.wordCensus.setflags(i,wflags)
            if 0 == i & 0x1f :
                pqMsgs.rollBar(i)
        pqMsgs.endBar()
        IMC.needMetadataSave |= IMC.wordlistsChanged
        IMC.needSpellCheck = False
        if IMC.spellingHiliteSwitch :
            self.setHighlight(True) # force refresh of spell underlines

    # Scan the successive lines of the document and build the census of chars,
    # words, and (first time only) the table of page separators.
    #
    # If this is an HTML file (from IMC.bookType), and if its first line is
    # <!DOCTYPE..., we skip until we see <body>. This avoids polluting our
    # char and word censii with CSS comments and etc. Regular HTML tags
    # like <table> and <b> are skipped over automatically during parsing.
    #
    # Qt obligingly supplies each line as a QTextBlock. We examine the line
    # to see if it is a page separator. If we are opening a file having no
    # metadata, the Page argument is True and we build a page table entry.
    # Other times (e.g. from the Refresh button of the Word or Char panel),
    # we skip over page separator lines.

    # Each non-separator line is first scanned by characters and then for words.
    # The character scan counts characters for the Chars panel. We do NOT parse
    # the text for PGDP productions [oe] and [OE] nor other markups for accented
    # characters such as [=o] for o-with-macron or [^a] for a-with-circumflex.
    # These are just counted as [, o, e, ]. Reasons: (1) the alternative, to parse
    # them into their proper unicode values and count those, entails a whole lotta
    # code that would slow this census badly; (2) having the unicode chars in
    # the Chars panel would be confusing when they are not actually in the text;
    # (3) there is some value in having the counts of [ and ]. For similar reasons
    # we count all the chars in HTML e.g. "<i>" is three characters even though it
    # is effectively unprinted metadata.

    # In scanning words, we collect numbers as words. We collect internal hyphens
    # as letters ("mother-in-law") but not at end of word ("help----" or emdash).
    # We collect internal apostrophes ("it's", "hadn't") but not apostrophes at ends,
    # "'Twas" is counted as "Twas", "students' work" as "students work". This is because
    # there seems to be no way to distinguish the contractive prefix ('Twas)
    # and the final possessive (students') from normal single-quote marks!
    # And we collect leading and internal, but not trailing, square brackets as
    # letters. Thus [OE]dipus and ma[~n]ana are words (but will fail spellcheck)
    # while Einstein[A] (a footnote key) is not.

    # We also collect HTML productions ("</i>" and "<table>") as words. They do not
    # go in the census but we check them for lang= attributes and set the alternate
    # spellcheck dictionary from them.

    def doCensus(self, page=False) :
        global reLineSep, reTokens, reLang, qcLess
        # Clear the current census values
        IMC.wordCensus.clear()
        IMC.charCensus.clear()
        # Count chars locally for speed
        local_char_census = defaultdict(int)
        # Name of current alternate dictionary
        alt_dict = QString() # isEmpty when none
        # Tag from which we set an alternate dict
        alt_dict_tag = QString()
        # Start the progress bar based on the number of lines in the document
        pqMsgs.startBar(self.document().blockCount(),"Counting words and chars...")
        # Find the first text block of interest, skipping an HTML header file
        qtb = self.document().begin() # first text block
        if IMC.bookType.startsWith(QString(u"htm")) \
        and qtb.text().startsWith(QString(u"<!DOCTYPE")) :
            while (qtb != self.document().end()) \
            and (not qtb.text().startsWith(QString(u"<body"))) :
                qtb = qtb.next()
        # Scan all lines of the document to the end.
        while qtb != self.document().end() :
            qsLine = qtb.text() # text of line as qstring
            dbg = qsLine.size()
            dbg2 = qtb.length()
            if reLineSep.exactMatch(qsLine): # this is a page separator line
                if page :
                    # We are doing page seps, it's for Open with no .meta seen,
                    # the page table has been cleared. Store the page sep
                    # data in the page table, with a textCursor to its start.
                    qsfilenum = reLineSep.cap(1) # xxx from "File: xxx.png"
                    qsproofers = reLineSep.cap(2) # \who\x\blah\etc
                    # proofer names can contain spaces, replace with en-space char
                    qsproofers.replace(QChar(" "),QChar(0x2002))
                    # create a new TextCursor instance
                    tcursor = QTextCursor(self.document())
                    # point it to this text block
                    tcursor.setPosition(qtb.position())
                    # dump all that in the page table
                    IMC.pageTable.loadPsep(tcursor, qsfilenum, qsproofers)
                # else not doing pages, just ignore this psep line
            else: # not psep, ordinary text line, count chars and words
                pyLine = unicode(qsLine) # move into Python space to count
                for c in pyLine :
                    local_char_census[c] += 1
                j = 0
                while True:
                    j = reTokens.indexIn(qsLine,j)
                    if j < 0 : # no more word-like units
                        break
                    qsWord = reTokens.cap(0)
                    j += qsWord.size()
                    if qsWord.startsWith(qcLess) :
                        # Examine a captured HTML production.
                        if not reTokens.cap(2).isEmpty() :
                            # HTML open tag, look for lang='dict'
                            if 0 <= reLang.indexIn(reTokens.cap(3)) :
                                # found it: save tag and dict name
                                alt_dict_tag = QString(reTokens.cap(2))
                                alt_dict = QString(reLang.cap(1))
                                alt_dict.prepend(u'/') # make "/en_GB"
                            # else no lang= attribute
                        else:
                            # HTML close tag, see if it closes alt dict use
                            if reTokens.cap(5) == alt_dict_tag :
                                # yes, matches open-tag for dict, clear it
                                alt_dict_tag = QString()
                                alt_dict = QString()
                            # else no alt dict in use, or didn't match
                    else : # did not start with "<", process as a word
                        # Set the property flags, which is harder now we don't
                        # look at every character. Use the QString facilities
                        # rather than python because python .isalnum fails
                        # for a hyphenated number "1850-1910".
                        flag = 0
                        if 0 != qsWord.compare(qsWord.toLower()) :
                            flag |= IMC.WordHasUpper
                        if 0 != qsWord.compare(qsWord.toUpper()) :
                            flag |= IMC.WordHasLower
                        if qsWord.contains(qcHyphen) :
                            flag |= IMC.WordHasHyphen
                        if qsWord.contains(qcApostrophe) or qsWord.contains(qcCurlyApostrophe) :
                            flag |= IMC.WordHasApostrophe
                        if qsWord.contains(reDigit) :
                            flag |= IMC.WordHasDigit
                        IMC.wordCensus.count(qsWord.append(alt_dict),flag)
                # end "while any more words in this line"
            # end of not-a-psep-line processing
            qtb = qtb.next() # move on to next block
            if (0 == (qtb.blockNumber() & 255)) : #every 256th block
                pqMsgs.rollBar(qtb.blockNumber()) # roll the bar
                QApplication.processEvents()
        # end of scanning all text blocks in the doc
        pqMsgs.endBar()
        # we accumulated the char counts in localCharCensus. Now read it out
        # in sorted order and stick it in the IMC.charCensus list.
        for one_char in sorted(local_char_census.keys()):
            qc = QChar(ord(one_char)) # get to QChar for category() method
            IMC.charCensus.append(QString(qc),local_char_census[one_char],qc.category())
        IMC.needSpellCheck = True # after a census this is true
        IMC.staleCensus = 0 # but this is no longer true
        IMC.needMetadataSave |= IMC.wordlistsChanged

# Regex to exactly match all of a page separator line. Note that the proofer
# names can contain almost any junk; proofer names can be null (\name\\name);
# and the end hyphens just fill the line out to 75 and may be absent.
# The outer parens, accessed as cap(2), capture all the proofers, while the
# inner parens, cap(3), (\\[^\\]+) captures one proofer name, e.g. \JulietS.

reLineSep = QRegExp(u'-----File: ([^\\.]+)\\.png---((\\\\[^\\\\]*)+)\\\\-*',Qt.CaseSensitive)

# Regexes for parsing a line into word-like tokens:
# First, a word composed of digits and/or letters, where
# the letters may include PGDP ligature notation: [OE]dipus ma[~n]ana

xp_word = "(\\w*(\\[..\\])?\\w+)+"

# Note that xp_word does NOT recognize adjacent ligatures (problem?)
# and does NOT recognize terminal ligatures on the grounds that a
# terminal [12] or [ac] is likely a two-digit footnote anchor.

# Next: the above with embedded hyphens or apostrophes (incl. u2019's):
# she's my mother-in-law's 100-year-old bric-a-brac ph[oe]nix

xp_hyap = "(" + xp_word + "[\\'\\-\u2019])*" + xp_word

# reWord is used by the syntax highlighter above.

reWord = QRegExp(xp_hyap, Qt.CaseInsensitive)

# HTML starting tag with possible attributes:
# <div lang=en_GB>, <hr class='major'>, or <br />

xp_start = '''(<(\w+)([^>]*)>)'''

# HTML end tag, not allowing for any attributes (or spaces)

xp_end = '''(</(\w+)>)'''

# Put it all together: a token is any of those three things:

xp_any = xp_start + '|' + xp_end + '|' + xp_hyap

reTokens = QRegExp(xp_any, Qt.CaseInsensitive)

# When reTokens matches an HTML close tag, reTokens.cap(5) is the closed tag name.
# When reTokens matches an HTML open tag, reTokens.cap(2) is the tag name
# ("i" or "span" or "div"), reTokens.cap(3) has whatever attributes it had
# (class='x', lang='en_GB'). We scan that for lang='value' (optional quotes).

reLang = QRegExp(u'''lang=[\\'\\"]*([\\w\\-]+)[\\'\\"]*''')

# The 'value' matched by reLang.cap(0) is a language designation but we require
# it to be a dictionary tag such as 'en_US' or 'fr_FR'. It is not clear from
# the W3C docs whether all (or any) of our dic tags are language designations.

# According to W3C (http://www.w3.org/TR/html401/struct/dirlang.html) you can
# put lang= into any tag, esp. span, para, div, td, and so forth.
# We save the dict tag as an alternate dictionary for all words until the
# matching close tag is seen.

reDigit = QRegExp(u'\\d')
qcLess = QChar(u"<")
qcHyphen = QChar(u"-")
qcApostrophe = QChar(u"'")
qcCurlyApostrophe = QChar(8217) # aka \u2019