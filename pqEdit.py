# must precede anything except #comments, including the docstring
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

# Global regex used by wordHighLighter and by textTitleCase to find words
# of one character and longer.
WordMatch = QRegExp(u"\\b\\w+\\b")
# Define a syntax highlighter object which will be linked into our editor.
# The edit init below instantiates this object and keeps addressability to it.
class wordHighLighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        global WordMatch
        super(wordHighLighter, self).__init__(parent)
        # store a local reference to the global regex
        self.wordMatch = WordMatch
        # Initialize text formats to apply to words from various lists.
        #  - Scanno candidates get a light lilac background.
        self.scannoFormat = QTextCharFormat()
        self.scannoFormat.setBackground(QBrush(QColor("plum")))
        # Set the style for misspelt words. We underline in red using the
        # platform's spellcheck underline style. An option would be to
        # specify QTextCharFormat.WaveUnderline style so it would be the
        # same on all platforms.
        self.misspeltFormat = QTextCharFormat()
        self.misspeltFormat.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        self.misspeltFormat.setUnderlineColor(QColor("red"))

    # The linked QPlainTextEdit calls this function for every text line in the
    # whole bloody document when highlighting is turned on via the View menu,
    # at least to judge by the hang-time. Later it only calls us to look at a
    # line as it changes in editing. Anyway it behooves us to be as quick as
    # possible. We don't actually check spelling, we just use the flag that
    # was set when the last spellcheck was done.
    def highlightBlock(self, text):
        # quickly bail when nothing to do
        if text.length() == 0 : return
        if (IMC.scannoHiliteSwitch or IMC.spellingHiliteSwitch) :
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
            pqMsgs.startBar(100,"Setting Spelling Highlights...")
            self.hiliter.setDocument(self.document())
            pqMsgs.endBar()

    # Implement clear/new. Just toss everything we keep.
    def clear(self):
        self.setHighlight(False)
        self.document().clear()
        self.document().setModified(False)
        self.bookMarkList = \
            [None, None, None, None, None, None, None, None, None]
        IMC.pageTable = []
        IMC.goodWordList.clear()
        IMC.badWordList.clear()
        IMC.wordCensus.clear()
        IMC.charCensus.clear()
        IMC.notesEditor.clear()
        IMC.pngPanel.clear()
        IMC.needSpellCheck = False
        IMC.needMetadataSave = 0x00
        IMC.staleCensus = 0x00

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
        global WordMatch # the regex \b\w+\b
        tc = QTextCursor(self.textCursor())
        if not tc.hasSelection() :
            return # no selection, nothing to do
        startpos = tc.selectionStart()
        endpos = tc.selectionEnd()
        qs = QString(tc.selectedText()) # copy of selected text
        i = WordMatch.indexIn(qs,0) # index of first word if any
        if i < 0 : return # no words in selection, exit
        while i >= 0:
            w = WordMatch.cap(0) # found word as QString
            n = w.size() # its length
            qs.replace(i,n,w.toUpper()) # replace it with UC version
            i = WordMatch.indexIn(qs,i+n) # find next word if any
        # we have changed at least one word, replace selection with altered text
        tc.insertText(qs)
        # that wiped the selection, so restore it by "dragging" left to right
        tc.setPosition(startpos,QTextCursor.MoveAnchor) # click
        tc.setPosition(endpos,QTextCursor.KeepAnchor)   # drag
        self.setTextCursor(tc)

    # to-lower is identical except for the method call.
    def toLowerCase(self):
        global WordMatch # the regex \b\w+\b
        tc = QTextCursor(self.textCursor())
        if not tc.hasSelection() :
            return # no selection, nothing to do
        startpos = tc.selectionStart()
        endpos = tc.selectionEnd()
        qs = QString(tc.selectedText()) # copy of selected text
        i = WordMatch.indexIn(qs,0) # index of first word if any
        if i < 0 : return # no words in selection, exit
        while i >= 0:
            w = WordMatch.cap(0) # found word as QString
            n = w.size() # its length
            qs.replace(i,n,w.toLower()) # replace it with UC version
            i = WordMatch.indexIn(qs,i+n) # find next word if any
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
        global WordMatch # the regex \b\w+\b
        self.toLowerCase()
        tc = QTextCursor(self.textCursor())
        if not tc.hasSelection() :
            return # no selection, nothing to do
        startpos = tc.selectionStart()
        endpos = tc.selectionEnd()
        qs = QString(tc.selectedText()) # copy of selected text
        i = WordMatch.indexIn(qs,0) # index of first word if any
        if i < 0 : return # no words in selection, exit
        while i >= 0:
            w = WordMatch.cap(0) # found word as QString
            n = w.size()
            qs.replace(i,1,qs.at(i).toUpper()) # replace initial with UC
            i = WordMatch.indexIn(qs,i+n) # find next word if any
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
    # ctrl-shift-<n> extends the selection ot bookmark <n>
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
                self.bookMarkList[bkn].clearSelection() # don't save the selection
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
        # The hash could contain any character. Using __repr__ ensured
        # it is enclosed in balanced single or double quotes but to be
        # double sure we will fence it in characters we can spot with a regex.
        metaStream << u"{{DOCHASH " + IMC.documentHash + u" }}\n"
        if len(IMC.pageTable) :
            metaStream << u"{{PAGETABLE}}\n"
            for (tc,fn,pr,f1,f2,f3) in IMC.pageTable :
                metaStream << "{0} {1} {2} {3} {4} {5}\n".format(tc.position(), fn, pr, f1, f2, f3 )
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
            metaStream << u"{{GOODWORDS}}\n"
            IMC.badWordList.save(metaStream)
            metaStream << u"{{/GOODWORDS}}\n"
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

    # load page table & vocab from the .meta file as a stream.
    # n.b. QString has a split method we could use but instead
    # we take the input line to a Python u-string and split it. For
    # the word/char census we have to take the key back to a QString.
    def loadMetadata(self,metaStream):
        sectionRE = QRegExp( u"\{\{(" + '|'.join (
            ['PAGETABLE','CHARCENSUS','WORDCENSUS','BOOKMARKS',
             'NOTES','GOODWORDS','BADWORDS','CURSOR','VERSION',
             'STALECENSUS','NEEDSPELLCHECK','ENCODING', 'DOCHASH'] ) \
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
                    IMC.bookSaveEncoding = argument
                    continue
                elif section == u"DOCHASH" :
                    IMC.metaHash = argument
                    continue
                elif section == u"PAGETABLE":
                    qline = metaStream.readLine()
                    while (not qline.startsWith(endsec)) and (not qline.isEmpty()):
                        # we eliminate spaces in proofer names in buildMeta()
                        parts = unicode(qline).split(' ')
                        tc = QTextCursor(self.document())
                        tc.setPosition(int(parts[0]))
                        tup = [tc, parts[1], parts[2], int(parts[3]), int(parts[4]), int(parts[5]) ]
                        IMC.pageTable.append(tup)
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

    # For any other line we scan by characters, parsing out words and taking
    # the char and word counts. Note that the word and char census lists
    # should be cleared before this method is called.

    # In scanning words, we assume that this is a properly proofed document
    # with no broken words at end of line (although there can be broken words
    # at end of a page, proof-* at end of line). We collect internal hyphens as
    # part of the word ("mother-in-law") but not at end of word (lacunae like
    # "help----" or emdashes) Similarly we collect internal apostrophes
    # ("it's", "hadn't" are words) but not apostrophes at ends ("'Twas" is
    # parsed as Twas, "students' work" as "students work"). This is because
    # there seems to be no way to distinguish the case of "'Twas brillig"
    # ('Twas as a word) from "'That's Amore' was a song" ('That's is not).
    # Accepting internal hyphens and apostrophes requires a one-char lookahead.

    # Harder is (a) recognizing [oe] and [OE] ligatures, and skipping <i>
    # and other html-like markups. For these we use the QString::indexIn
    # and a regex to do lookahead.

    # The first version of this code used nested if-logic, but in an attempt to
    # simplify and speed up we now use a modified finite-state system driven by
    # a two-row table. Each column represents one of the 30 Unicode categories
    # returned by QChar::category(). The two rows represent the inWord
    # state true/false. Each cell contains a tuple (func,[arg[,arg]]). We call
    # the next action as tup[0](*tup[1:]) (ooh, very pythonic). The executed
    # function does something and sets the next action-tuple. The functions are
    # all local to the main function, which makes for a long piece of code.

    def doCensus(self,page=False):
        global reLineSep, reMarkup, qcDash, qcApost, qcLess, qcLbr, qslcLig
        global qsucLig, qsLine, qsDict, i, qcThis, uiCat, inWord
        global uiWordFlags, qsWord, nextAction, parseArray
        # actions called from the finite-state table
        def GET(): # acquire the next char and category, push action
            global qcThis, uiCat, nextAction, i
            qcThis = qsLine.at(i)
            uiCat = qcThis.category()
            nextAction = parseArray[inWord][uiCat]
        def COUNT1(): # count the current character, advance index
            global qcThis, uiCat, nextAction, i
            #IMC.charCensus.count(QString(qcThis),uiCat)
            u = qcThis.unicode() # a long integer
            localCharCensus[u] = 1+localCharCensus.get(u,0)
            i += 1
            # since most letters end up here, save one cycle by doing GET now
            # if i is off the end, it's ok: QString.at(toobig) returns 0.
            qcThis = qsLine.at(i)
            uiCat = qcThis.category()
            nextAction = parseArray[inWord][uiCat]
        def COUNTN(n): # census chars of a known-length string like [OE], </i>
            global qcThis, uiCat, qsLine, nextAction, i
            for j in range(n): # i.e. do this n times
                #IMC.charCensus.count(QString(qcThis),uiCat)
                u = qcThis.unicode() # a long integer
                localCharCensus[u] = 1+localCharCensus.get(u,0)
                i += 1
                qcThis = qsLine.at(i)
                uiCat = qcThis.category()
            nextAction = (GET, )
        # The following are called when inWord is false
        def WORDBEGIN(flag): # uppercase, lowercase, or digit
            global qcThis, qsWord, inWord, uiWordFlags, nextAction
            qsWord.append(qcThis)
            inWord = True
            uiWordFlags = flag
            nextAction = (COUNT1,)
        def PUNCOPEN(): # could be [, look for oe-ligs
            global qsLine, qslcLig, i, qsWord, inWord, uiWordFlags, nextAction
            if i == qsLine.indexOf(qslcLig,i,Qt.CaseSensitive):
                # [oe] starts a word
                qsWord.append(qslcLig)
                inWord = True
                uiWordFlags = IMC.WordHasLower
                nextAction = (COUNTN, 4)
            elif i == qsLine.indexOf(qsucLig,i,Qt.CaseSensitive):
                # [OE] starts a word
                qsWord.append(qsucLig)
                inWord = True
                uiWordFlags = IMC.WordHasUpper
                nextAction = (COUNTN, 4)
            else: # just a random [ or (
                nextAction = ( COUNT1, )
        def SYMBOL(): # math symbol can be <, look for markup
            global i, qsLine, qsDict, reMarkup, nextAction
            if i == reMarkup.indexIn(qsLine,i) :
                # </? i/b/sc/xx > markup starts here, suck it up
                if reMarkup.cap(1) == sdMarkup :
                    if reMarkup.cap(2).isNull() : # assume </sd>
                        qsDict = QString() # no alternate dict
                    else: # assume <sd dict_tag>
                        # start tagging words with /dictag
                        qsDict.append(u"/")
                        qsDict.append(reMarkup.cap(2).trimmed())
                # regardless, skip the whole markup
                nextAction = (COUNTN, reMarkup.matchedLength() )
            else:
                # it may be < but it isn't markup, continue 1 char at a time
                nextAction = (COUNT1,)
        # The following are called when inWord is True
        def WORDCONTINUE(flag):
            global qsWord, qcThis, uiWordFlags, nextAction
            qsWord.append(qcThis)
            uiWordFlags |= flag
            nextAction = (COUNT1,)
        def WORDEND(): # char definitely not a wordchar and not <
            global qsWord, qsDict, uiWordFlags, inWord, nextAction
            qsWord.append(qsDict)
            IMC.wordCensus.count(qsWord,uiWordFlags)
            qsWord.clear()
            uiWordFlags = 0
            inWord = False
            nextAction = (COUNT1,)
        def PUNCOPENW(): # could be [oe] inside a word
            global qsLine, qslcLig, qsucLig, i, qsWord, uiWordFlags, nextAction
            if i == qsLine.indexOf(qslcLig,i,Qt.CaseSensitive):
                qsWord.append(qslcLig)
                uiWordFlags |= IMC.WordHasLower
                nextAction = (COUNTN, 4)
            elif i == qsLine.indexOf(qsucLig,i,Qt.CaseSensitive):
                # [OE] inside a word? oh well...
                qsWord.append(qsucLig)
                uiWordFlags |= IMC.WordHasUpper
                nextAction = (COUNTN, 4)
            else:
                nextAction = (WORDEND, )
        def WORDASH(): # hyphen when inWord, look ahead
            global qsLine, i, nextAction
            lacat = qsLine.at(i+1).category()
            if (lacat == QChar.Letter_Lowercase) \
            or (lacat == QChar.Letter_Uppercase):
                nextAction =  ( WORDCONTINUE, IMC.WordHasHyphen)
            else:
                nextAction = ( WORDEND, )
        def PUNCAPO(): # possible apostrophe inside word
            global qcThis, qcApost, qsLine, nextAction
            if qcThis == qcApost : # apostrophe, isn't it
                lacat = qsLine.at(i+1).category()
                if (lacat == QChar.Letter_Lowercase) \
                or (lacat == QChar.Letter_Uppercase):
                    nextAction = ( WORDCONTINUE, IMC.WordHasApostrophe)
                else:
                    nextAction = ( WORDEND, )
            else:
                nextAction = ( WORDEND, )
        def WORDENDLT(): # symbol-math ending a word
            global qsWord, qsDict, uiWordFlags, inWord, qcThis, qcLess, nextAction
            qsWord.append(qsDict)
            IMC.wordCensus.count(qsWord,uiWordFlags)
            qsWord.clear()
            inWord = False
            if qcThis != qcLess:
                nextAction = (COUNT1,)
            else:
                nextAction = (SYMBOL,)

        # List of unicode categories can be seen in pqChars.py
        parseArray = [ [ (COUNT1,), (WORDBEGIN, 0), (WORDBEGIN, 0), (COUNT1,),
            (WORDBEGIN, IMC.WordHasDigit), (WORDBEGIN, IMC.WordHasDigit),
            (WORDBEGIN, IMC.WordHasDigit),  (COUNT1,), (COUNT1,), (COUNT1,),
            (COUNT1,), (COUNT1,), (COUNT1,), (COUNT1,), (COUNT1,),
            (WORDBEGIN, IMC.WordHasUpper), (WORDBEGIN, IMC.WordHasLower),
            (WORDBEGIN, IMC.WordHasLower), (WORDBEGIN, IMC.WordHasLower),
            (WORDBEGIN, IMC.WordHasLower), (COUNT1,), (COUNT1,), (PUNCOPEN,),
            (COUNT1,), (COUNT1,), (COUNT1,), (COUNT1,), (SYMBOL,), (COUNT1,),
            (COUNT1,), (COUNT1,) ],
            [ (WORDEND, ), (WORDCONTINUE, 0), (WORDCONTINUE, 0),(WORDEND, ),
            (WORDCONTINUE, IMC.WordHasDigit), (WORDCONTINUE, IMC.WordHasDigit),
            (WORDCONTINUE, IMC.WordHasDigit),(WORDEND, ),(WORDEND, ),(WORDEND, ),
            (WORDEND, ),(WORDEND, ),(WORDEND, ),(WORDEND, ),(WORDEND, ),
            (WORDCONTINUE, IMC.WordHasUpper), (WORDCONTINUE, IMC.WordHasLower),
            (WORDCONTINUE, IMC.WordHasLower), (WORDCONTINUE, IMC.WordHasLower),
            (WORDCONTINUE, IMC.WordHasLower), (WORDEND, ), (WORDASH, ),
            (PUNCOPENW, ), (WORDEND, ), (WORDEND, ), (WORDEND, ),
            (PUNCAPO, ), (WORDENDLT, ),(WORDEND, ),(WORDEND, ),(WORDEND, )] ]

        IMC.wordCensus.clear()
        IMC.charCensus.clear()
        localCharCensus = {}
        iFolio = 0 # page number for line separator records
        pqMsgs.startBar(self.document().blockCount(),"Counting words and chars...")
        qtb = self.document().begin() # first text block
        if IMC.bookType.startsWith(QString(u"htm")) \
        and qtb.text().startsWith(QString(u"<!DOCTYPE")) :
            while (qtb != self.document().end()) \
            and (not qtb.text().startsWith(QString(u"<body"))) :
                qtb = qtb.next()
        while qtb != self.document().end(): # up to end of document
            qsLine = qtb.text() # text of line as qstring
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
                    # initialize this page's folio
                    iFolio += 1
                    # dump all that in the page table
                    IMC.pageTable.append(
    [tcursor, qsfilenum, qsproofers, IMC.FolioRuleAdd1, IMC.FolioFormatArabic, iFolio]
                                      )
                # else not doing pages, just ignore this psep line
            else: # not psep, ordinary text line, count chars and words
                i = 0
                inWord = False
                qsWord = QString()
                uiWordFlags = 0
                nextAction = (GET,)
                while i < qsLine.size():
                    nextAction[0](*nextAction[1:])

                if inWord : # line ends with a word, not unsurprising
                    qsWord.append(qsDict)
                    IMC.wordCensus.count(qsWord,uiWordFlags)
            qtb = qtb.next() # next textblock == next line
            if (0 == (qtb.blockNumber() & 255)) : #every 256th block
                pqMsgs.rollBar(qtb.blockNumber()) # roll the bar
                QApplication.processEvents()
        pqMsgs.endBar()
        # to save time by not calling charCensus.count() for every character
        # we accumulated the char counts in localCharCensus. Now read it out
        # in sorted order and stick it in the IMC.charCensus list.
        for uc in sorted(localCharCensus.keys()):
            qc = QChar(uc) # long int to QChar
            IMC.charCensus.append(QString(qc),localCharCensus[uc],qc.category())
        IMC.needSpellCheck = True # after a census this is true
        IMC.staleCensus = 0 # but this is not true
        IMC.needMetadataSave |= IMC.wordlistsChanged

# The following are global names referenced from inside the parsing functions
# Regex to exactly match all of a page separator line. Note that the proofer
# names can contain almost any junk; proofer names can be null (\name\\name);
# and the end hyphens just fill the line out to 75 and may be absent.
# The inner parens, cap(3), (\\[^\\]+) captures one proofer name, e.g. \JulietS
# and the outer parens, .cap(2) capture all of however many there are.
reLineSep = QRegExp(u'-----File: ([^\\.]+)\\.png---((\\\\[^\\\\]*)+)\\\\-*',Qt.CaseSensitive)
# Regex to match html markup: < /? spaces? (tag) spaces? whoknowswhat >
# the cap(1) is the markup verb, and cap(2) is possibly a dict tag
reMarkup = QRegExp("\\<\\/?\\s*(\\w+)\\s*([^>]*)>",Qt.CaseInsensitive)
# Global literal for start of alternate spell dict markup <sd tag>
sdMarkup = QString(u"sd")
# Regex to match exactly end of a spelling dictionary span, </sd>
sxMarkup = QRegExp("\\</sd>",Qt.CaseSensitive)
qcDash = QChar("-")
qcApost = QChar("'")
qcLess = QChar("<")
qcLbr = QChar("[")
qslcLig = QString("[oe]")
qsucLig = QString("[OE]")
qsLine = QString() # text line we are scanning
i = 0 # index over qsLine
qcThis = QChar() # current character from qsLine.at(i)
uiCat = 0 # holds current category
inWord = False # state of parser
uiWordFlags = 0 # see ppqt defs IMC.WordHasUpper etc
qsWord = QString() # accumulated letters of word
qsDict = QString() # alt-dictionary suffix
nextAction = (None,) # holds the tuple of the next parse action
parseArray = [[],[]] # holds the list of parse actions by category
