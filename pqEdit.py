# must precede anything except #comments, including the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

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

from PyQt4.QtCore import (Qt, QChar, QRegExp, QString, SIGNAL)
from PyQt4.QtGui import (
    QBrush, QColor, QFont, QFontInfo, QMessageBox,
    QPlainTextEdit, QSyntaxHighlighter, QProgressDialog,
    QTextBlock, QTextCharFormat, QTextCursor,
    QTextDocument, QTextEdit
)

# get simple access to methods of the list objects
from pqLists import *
import pqMsgs

# Define a syntax highlighter object which will be linked into our editor.
# The edit init below instantiates this object and keeps addressability to it.
class wordHighLighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super(wordHighLighter, self).__init__(parent)
        # regex to find words of 1 characters and longer
        # n.b. won't work unless backslashes doubled on \b
        self.wordMatch = QRegExp(u"\\b\\w+\\b")
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

    # switch on or off our text-highlighting. By switching the highlighter
    # to a null document we remove highlighting; by switching it back to
    # the real document, we cause re-highlighting of everything (and a 
    # significant delay for a large document).
    def setHighlight(self, onoff):
        self.hiliter.setDocument(self.nulDoc) # turn off hiliting always
        if onoff:
            self.hiliter.setDocument(self.document())

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
        IMC.needWordCensus = False
        IMC.needMetadataSave = False
        IMC.needBookSave = False

    # Re-implement the parent's keyPressEvent in order to provide some
    # special controls. (Note on Mac, "ctrl-" is "cmd-" and "alt-" is "opt-")
    # ctrl-plus increases the edit font size 1 pt
    # (n.b. ctrl-plus probably only comes from a keypad, we usually just get
    #  ctrl-shift-equals instead of plus)
    # ctrl-minus decreases the edit font size 1 pt
    # ctrl-<n> for n in 1..9 jumps the insertion point to bookmark <n>
    # ctrl-alt-<n> sets bookmark n at the current position
    def keyPressEvent(self, event):
        #print('key {0:x} mod {1:x}'.format(int(event.key()),int(event.modifiers())))
        kkey = int(event.modifiers())+int(event.key())
        # add as little overhead as possible: if it isn't ours, pass it on.
        if kkey in IMC.keysOfInterest : # trusting python to do this quickly
            event.accept() # we handle this one
            if kkey in IMC.findKeys:
                # ^f, ^g, etc. -- just pass them straight to the Find panel
                self.emit(SIGNAL("editKeyPress"),kkey)
            elif (kkey == IMC.ctl_plus) or (kkey == IMC.ctl_minus) \
                or (kkey == IMC.ctl_shft_equal) :
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
            elif kkey in IMC.markKeys : # ^1-9, jump to bookmark
                bkn = kkey - IMC.ctl_1 # make it 0-8
                if self.bookMarkList[bkn] is not None: # if that bookmark is set,
                    self.setTextCursor(self.bookMarkList[bkn]) # jump to it
            elif kkey in IMC.markSetKeys : # ctl-alt-1-9, set a bookmark
                bkn = kkey - IMC.ctl_alt_1 # make it 0-8
                self.bookMarkList[bkn] = self.textCursor()
                self.bookMarkList[bkn].clearSelection() # don't save the selection
                IMC.needMetadataSave = True # need to save metadata
        else: # not in keysOfInterest
            event.ignore()
        # ignored or accepted, pass the event along.
        super(PPTextEditor, self).keyPressEvent(event)
     
    # Implement save: the main window opens the files for output using 
    # QIODevice::WriteOnly, which wipes the contents (contrary to the doc)
    # so we need to write the document and metadata regardless of whether
    # they've been modified. However we avoid rebuilding metadata if we can.        
    def save(self, dataStream, metaStream):
        self.writeDocument(dataStream)
        #self.rebuildMetadata() # update any census that needs it
        self.document().setModified(False)
        self.writeMetadata(metaStream)
        IMC.needMetadataSave = False

    def writeDocument(self,dataStream):
        # writing the file is pretty easy...
        dataStream << self.toPlainText()
        dataStream.flush()

    def writeMetadata(self,metaStream):
        # Writing the metadata takes a bit more work.
        # pageTable goes out between {{PAGETABLE}}..{{/PAGETABLE}}
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
                metaStream << "{0} {1}\n".format(i,self.bookMarkList[i].position())
        metaStream << u"{{/BOOKMARKS}}\n"
        metaStream << u"{{NOTES}}\n"
        d = IMC.notesEditor.document()
        if not d.isEmpty():
            for i in range( d.blockCount() ):
                t = d.findBlockByNumber(i).text()
                if t.startsWith("{{"):
                    t.prepend(u"\xfffd") # Unicode Replacement char
                metaStream << t + "\n"
        metaStream << u"{{/NOTES}}\n"
        if IMC.goodWordList.active() : # have some good words
            metaStream << u"{{GOODWORDS}}\n"
            IMC.goodWordList.save(metaStream)
            metaStream << u"{{/GOODWORDS}}\n"
        if IMC.badWordList.active() : # have some bad words
            metaStream << u"{{GOODWORDS}}\n"
            IMC.badWordList.save(metaStream)
            metaStream << u"{{/GOODWORDS}}\n"
        metaStream.flush()
    
    # Implement load: the main window has the job of finding and opening files
    # then passes QTextStreams ready to read here. If metaStream is None,
    # no metadata file was found and we construct the metadata.
    # n.b. before main calls here, it calls our .clear, hence lists are
    # empty, hiliting is off, etc.
    
    def load(self, dataStream, metaStream, goodStream, badStream):
        self.setPlainText(dataStream.readAll())
        if metaStream is None:
            # load goodwords, badwords, and take census
            if goodStream is not None:
                IMC.goodWordList.load(goodStream)
            if badStream is not None:
                IMC.badWordList.load(badStream)
            self.rebuildMetadata(page=True) # build page table & vocab from scratch
        else:
            self.loadMetadata(metaStream)
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
        sectionRE = QRegExp(
            u"\{\{(PAGETABLE|CHARCENSUS|WORDCENSUS|BOOKMARKS|NOTES|GOODWORDS|BADWORDS)\}\}",
            Qt.CaseSensitive)
        while not metaStream.atEnd() :
            qline = metaStream.readLine().trimmed()
            if qline.isEmpty() : continue # allow blank lines between sections
            if sectionRE.exactMatch(qline) : # section start
                section = sectionRE.cap(1)
                endsec = QString(u"{{/" + section + u"}}")
                if section == u"PAGETABLE":
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
                elif section == u"GOODWORDS" :
                    # not going to bother checking for endsec return,
                    # if it isn't that then we will shortly fail anyway
                    w = IMC.goodWordList.load(metaStream,endsec)
                elif section == u"BADWORDS" :
                    w = IMC.badWordList.load(metaStream,endsec)
                else:
                    # this can't happen; section is text captured by the RE
                    # and we have accounted for all possibilities
                    raise AssertionError, "impossible metadata"
            else:
                pqMsgs.infoMsg(
                    "Unexpected line in metadata: {0}".format(pqMsgs.trunc(qline,20)),
                        "Metadata may be incomplete, suggest quit")
                break

    # rebuild as much of the char/word census and spellcheck as we need to.
    # We could need just a spellcheck, if e.g. the dictionary has changed but
    # the document has not. If page=True is passed this is the first open of
    # a document (anyway, no metadata) we do it all.
    def rebuildMetadata(self,page=False):
        if page or self.document().isModified() :
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
        IMC.needMetadataSave = True
        IMC.needSpellCheck = False
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
            if 0 == i & 0x3f :
                pqMsgs.rollBar(i)
        pqMsgs.endBar()

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
    # or prior to a save) we skip over page separator lines.
    
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
        global reMarkup, qcDash, qcApost, qcLess, qcLbr, qslcLig
        global qsucLig, qsLine, qsDict, i, qcThis, uiCat, inWord
        global uiWordFlags, qsWord, nextAction, parseArray
        IMC.needSpellCheck = True # after a census this is true
        IMC.needMetadataSave = True
        IMC.wordCensus.clear()
        IMC.charCensus.clear()
        # If we are doing pages, it's for load, and the page table has been
        # cleared. If not, we don't want to mess with the page table.
        reLineSep = QRegExp("^-----File:\s*(\d+)\.png---(.+)(-+)$",Qt.CaseSensitive)
        reTrailDash = QRegExp("-+$")
        iFolio = 0 # really, page number
        def GET(): # acquire the next char and category, push action
            global qcThis, uiCat, nextAction, i
            qcThis = qsLine.at(i)
            uiCat = qcThis.category()
            nextAction = parseArray[inWord][uiCat]
        def COUNT1(): # count the current character, advance index
            global qcThis, uiCat, nextAction, i
            IMC.charCensus.count(QString(qcThis),uiCat)
            i += 1
            # since most letters end up here, save one cycle by doing GET now
            # if i is off the end, it's ok: QString.at(toobig) returns 0.
            qcThis = qsLine.at(i)
            uiCat = qcThis.category()
            nextAction = parseArray[inWord][uiCat]
        def COUNTN(n): # census chars of a known-length string e.g. [OE], </i>
            global qcThis, uiCat, qsLine, nextAction, i
            for j in range(n): # i.e. do this n times
                IMC.charCensus.count(QString(qcThis),uiCat)
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
                        pass
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

        pqMsgs.startBar(self.document().blockCount(),"Counting words and chars...")    
        qtb = self.document().begin() # first text block
        if IMC.bookType.startsWith(QString(u"htm")) \
        and qtb.text().startsWith(QString(u"<!DOCTYPE")) :
            while (qtb != self.document().end()) \
            and (not qtb.text().startsWith(QString(u"<body"))) :
                qtb = qtb.next()
        while qtb != self.document().end(): # up to end of document
            qsLine = qtb.text() # text of line as qstring
            if reLineSep.exactMatch(qsLine): # a page separator
                if page : # and we are doing page seps
                    qsfilenum = reLineSep.capturedTexts()[1]
                    qsproofers = reLineSep.capturedTexts()[2]
                    j = reTrailDash.indexIn(qsproofers)
                    if j > 0: # get rid of trailing dashes
                        qsproofers.truncate(j)
                    # proofer names can contain spaces, replace with en-space char
                    qsproofers.replace(QChar(" "),QChar(0x2002))
                    tcursor = QTextCursor(self.document())
                    tcursor.setPosition(qtb.position())
                    iFolio += 1
                    IMC.pageTable.append(
    [tcursor, qsfilenum, qsproofers, IMC.FolioRuleAdd1, IMC.FolioFormatArabic, iFolio]
                                      )
                # else skip over the psep line
            else: # ordinary text line, count chars and words
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
            if (0 == (qtb.blockNumber() & 127)) : #every 128th block
                pqMsgs.rollBar(qtb.blockNumber()) # roll the bar
        pqMsgs.endBar()
# The following are global names referenced from inside the parsing functions
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
