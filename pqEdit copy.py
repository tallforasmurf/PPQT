# must precede anything except #comments, including the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
Define our editor, which acts as the Model in a Model-view-controller design.
The editor (of necessity) holds the document and (for convenience) all its
related metadata, and provides it to the various other views.

The editor is a small modification of QPlainTextEdit, because QTextEdit is
oriented to rich-text and html docs and QPlainTextEdit is meant for flat
texts organized as lines. The base Qt editor is a modern one with full unicode
support and all the standard editing actions, including drag-n-drop and
undo/redo stacks, and graceful vertical and horizontal scrolling as the
window changes size.

The following properties are accessible to other code:
     .document()        QTextDocument being edited and its props, e.g.
         .document().isModified, .document().isEmpty, .document().lineCount
     .pageTable       table of pages, png#s, and folio controls
     .bookMarks       list of positions (textCursors) of user bookmarks
     .wordCensus      all words and their counts (can be stale)
     .charCensus      all characters and their counts (ditto)

In initializing the editor we make sure it is using a monospaced font,
preferably DPCustomMono2, which any of our users should have installed.
We also add with keystroke commands as follows:
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
# The edit code below instantiates this object and keeps addressability to it.
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
	# platform's spellcheck underline style. An option woudl be to
	# specify QTextCharFormat.WaveUnderline style so it would be the
	# same on all platforms.
        self.misspeltFormat = QTextCharFormat()
        self.misspeltFormat.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        self.misspeltFormat.setUnderlineColor(QColor("red"))
    
    # The linked QPlainTextEdit calls this function for each text line before
    # displaying it. (It is highly economical, only calling with small bits of
    # text actually modified.) Still it behoovesus to be as quick as possible.
    def highlightBlock(self, text):
	# quickly bail when nothing to do
	if text.length() == 0 : return
        if (IMC.scannoHiliteSwitch or IMC.spellingHiliteSwitch) :
	    # find each word in the text and test it against our lists
	    i = self.wordMatch.indexIn(text,0) # first word if any
	    while i >= 0:
		l = self.wordMatch.matchedLength()
		w = self.wordMatch.capturedTexts()[0] # word as qstring
		# In this we assume that all words in the scanno file are valid
		# words. Only non-scannos can be flagged as spelling errors.
		if IMC.scannoHiliteSwitch: # we are checking for scannos:
		    if IMC.scannoList.check(unicode(w)):
			self.setFormat(i,l,self.scannoFormat)
		if IMC.spellingHiliteSwitch: # we are checking spelling:
		    # words in the bad_words are automatically misspelt, also
		    # words that were seen as misspelt by Aspell when the file
		    # was loaded or the word-census was refreshed.
		    if (IMC.badWordList.check(unicode(w))) \
		    or (IMC.wordCensus.getFlag(w) & IMC.WordMisspelt):
			self.setFormat(i,l,self.misspeltFormat)
		i = self.wordMatch.indexIn(text,i+l) # advance to next word

# Define the editor as a subclass of QPlainTextEdit. Only one object of this
# class is created (in ppqt_main). fontsize arg will be recalled from
# a prior session and passed in when object is created in main window.

class PPTextEditor(QPlainTextEdit):
    # Initialize the editor on creation.
    def __init__(self, parent=None, fontsize=12 ):
        super(PPTextEditor, self).__init__(parent)
        # Do not allow line-wrap; horizontal scrollbar appears when required.
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
	# make sure when we jump to a line, it goes to the window center
	self.setCenterOnScroll(True)
        # Get specifically DPCustomMono2 if we can, and if not, ensure
        # that we have a genuine monospaced font.
        monofont = QFont()
        monofont.setStyleStrategy(QFont.PreferAntialias+QFont.PreferMatch)
        monofont.setStyleHint(QFont.Courier+QFont.Monospace)
        monofont.setFamily("DPCustomMono2")
        monofont.setFixedPitch(True) # probably unnecessary
        monofont.setPointSize(fontsize)
        if not monofont.exactMatch():
	    pqMsgs.infoMsg("Font DPCustomMono2 not available, using {0}".format(QFontInfo(monofont).family()) )
        self.setFont(monofont)
        # establish our "syntax" highlighter object, but link it to an empty
	# QTextDocument. We will redirect it to our actual document after we 
	# have loaded it and the metadata, as it relies on metadata.
	self.nulDoc = QTextDocument()
        self.hiliter = wordHighLighter(self.nulDoc)
        # all the metadata lists will be initialized when clear() is called

    # switch on or off our text-highlighting. By switching the highlighter
    # to a null document we remove highlighting; by switching it back to
    # the real document, we cause re-highlighting of everything.
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
            [None, None, None, None, None, None, None, None, None, ]
        IMC.pageTable = []
        IMC.goodWordList.clear()
        IMC.badWordList.clear()
        IMC.wordCensus.clear()
        IMC.charCensus.clear()
	IMC.notesEditor.clear()
	IMC.pngPanel.clear()

    # Re-implement the parent's keyPressEvent in order to provide some
    # special controls. Note on Mac, "ctrl-" is "cmd-" and "alt-" is "opt-"
    # ctrl-plus increases the edit font size 1 pt
    # (n.b. ctrl-plus probably only comes from a keypad, we usually just get
    #  ctrl-shift-equals instead of plus)
    # ctrl-minus decreases the edit font size 1 pt
    # ctrl-<n> for n in 1..9 jumps the insertion point to bookmark <n>
    # ctrl-alt-<n> sets bookmark n at the current position
    def keyPressEvent(self, event):
        # add as little overhead as possible: if it isn't ours, pass it on.
	kkey = int(event.modifiers())+int(event.key())
	if kkey in IMC.keysOfInterest : # trusting python to do this quickly
	    event.accept() # we handle this one
	    if kkey in IMC.findKeys: # ^f, ^g, etc.
		self.emit(SIGNAL("editKeyPress"),kkey)
            elif (kkey == IMC.ctl_plus) or (kkey == IMC.ctl_minus) \
	    or (kkey == IMC.ctl_shft_equal) :
                # n.b. the self.font and setFont methods are from QWidget
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
		if self.bookMarkList[bkn] is not None: # and one is set,
		    self.setTextCursor(self.bookMarkList[bkn])
	    elif kkey in IMC.markSetKeys : # ctl-alt-1-9, set a bookmark
		bkn = kkey - IMC.ctl_alt_1 # make it 0-8
		self.bookMarkList[bkn] = self.textCursor()
		self.bookMarkList[bkn].clearSelection() # forget any selection
		self.document().setModified(True) # need to save metadata
        else: # not in keysOfInterest
            event.ignore()
        # ignored or accepted, pass the event along.
        super(PPTextEditor, self).keyPressEvent(event)
     
    # Implement save: the main window opens the files for output and passes
    # us text streams ready to write.
    
    def save(self, dataStream, metaStream):
	# writing the file is pretty easy...
        dataStream << self.toPlainText()
	dataStream.flush()
	# Writing the metadata takes a bit more work.
	self.rebuildMetaData() # first pick up any new chars or words
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
	metaStream.flush()
	# TODO if wordTable widget allows adding to good_ or bad_words, have
	# to have dirty switches, and open in Main and and write them here
    
    # Implement load: the main window has the job of finding and opening files
    # then passes QTextStreams ready to read here. If metaStream is None,
    # no metadata file was found and we construct the metadata.
    # n.b. before main calls here, it calls our .clear, hence lists are
    # empty, hiliting is off, etc.
    
    def load(self, dataStream, metaStream, goodStream, badStream):
        self.setPlainText(dataStream.readAll())
        if goodStream is not None:
            self.goodWordList.load(goodStream)
        if badStream is not None:
            self.badWordList.load(badStream)
        if metaStream is None:
            self.rebuildMetaData(page=True) # build page table & vocab from scratch
        else:
	    self.loadMetaData(metaStream)
	# restore hiliting if the user wanted it.
	self.setHighlight(IMC.scannoHiliteSwitch or IMC.spellingHiliteSwitch)
	
    # load page table & vocab from the .meta file as a stream.
    # n.b. QString has a split method we could use but instead
    # we take the input line to a Python u-string and split it. For
    # the word/char census we have to take the key back to a QString.
    def loadMetaData(self,metaStream):
	sectionRE = QRegExp(
            u"\{\{(PAGETABLE|CHARCENSUS|WORDCENSUS|BOOKMARKS|NOTES)\}\}",
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
			tup = (tc, parts[1], parts[2], int(parts[3]), int(parts[4]), int(parts[5]) )
			IMC.pageTable.append(tup)
			qline = metaStream.readLine()
		    continue
		elif section == u"CHARCENSUS":
		    qline = metaStream.readLine()
		    while (not qline.startsWith(endsec)) and (not qline.isEmpty()):
			# can't just .split the char census, the first
			# char is the char and it can be a space.
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
		else:
		    pqMsgs.infoMsg(
		        "Unknown metadata section: {0}".format(section),
		        "Metadata may be incomplete, suggest quit")
		    break
	    else:
		pqMsgs.infoMsg(
	            "Unexpected line in metadata: {0}".format(qline.left(20)),
	                "Metadata may be incomplete, suggest quit")
		break

    # Scan the successive lines of the document and build our metadata.
    # Qt obligingly supplies each line as a QTextBlock. We examine the line
    # to see if it is a page separator. If so we build a page table entry.
    # If not, we scan its characters taking the char and word counts.
    
    # This function is called from the Char and Word tabs, or from save above,
    # to refresh the metadata, but they call with page=False; we should NEVER
    # build the page table from scratch except on the very first load.
    
    # In scanning words, we assume that this is a properly proofed document
    # with no broken words at end of line. We collect internal hyphens as
    # part of the word ("mother-in-law") but not at end of word ("help----"
    # or (go--and soon--). Similarly we collect internal apostrophes
    # ("it's", "hadn't" are words) but not apostrophes at ends ("'Twas" is
    # parsed as Twas, "students' work" as students work). This is because
    # there seems to be no way to distinguish the case of "'Twas brillig"
    # ('Twas as a word) from "'That's Amore' was a song" ('That's is not).
    # Accepting internal hyphens and apostrophes requires a one-char lookahead
    # which is only done when those are seen within a word. The lookahead is
    # made simpler because a QString.at(too-large-index) does not raise an
    # error but obliging returns 0x0.
    # We collect alphanumeric words like 3d or p66, and incidentally collect
    # all-digit number tokens but those are not stored in the vocabulary list.
        
    # TODO : figure out how to include words with [oe] ligatures (which will
    # probably entail using a FSM for this process)

    def rebuildMetaData(self,page=False):
	IMC.charCensus.clear()
	IMC.wordCensus.clear()
        psepPat = QRegExp("^-----File:\s*(\d+)\.png---(.+)(-+)$",Qt.CaseSensitive)
	qcdash = QChar("-")
	qcpost = QChar("'")
        folio = 0
	qtb = self.document().begin() # first text block
	pqMsgs.startBar(self.document().blockCount(),"Building metadata")
        while qtb != self.document().end(): # up to end of document
            qline = qtb.text() # text of line as qstring
            if psepPat.exactMatch(qline): # a page separator
                if page : # and we are doing page seps
                    qsfilenum = psepPat.capturedTexts()[1]
                    qsproofers = psepPat.capturedTexts()[2]
		    # proofer names can contain spaces, bleagh
		    # TODO consider using unicode 8288, word-joiner
		    qsproofers.replace(QChar(" "),QChar("_"))
                    tcursor = QTextCursor(self.document())
                    tcursor.setPosition(qtb.position())
                    folio += 1
                    IMC.pageTable.append(
    (tcursor, qsfilenum, qsproofers, IMC.FolioRuleAdd1, IMC.FolioFormatArabic, folio)
                                      )
                # else skip over the psep line
            else: # ordinary text line, count chars and words
                i = 0
                inword = False
                qword = QString()
                wflags = 0
                while i < qline.size():
		    # Get next character and count it
                    qc = qline.at(i)
                    cat = qc.category()
                    IMC.charCensus.count(QString(qc),cat)
                    # Use character value to locate & analyze words
                    wf = 0 # will be nonzero if qc can begin/continue a word
                    if cat == QChar.Letter_Lowercase : wf = IMC.WordHasLower
                    elif cat == QChar.Letter_Uppercase : wf = IMC.WordHasUpper
                    elif cat == QChar.Number_DecimalDigit : wf = IMC.WordHasDigit
                    elif ( (qc == qcdash ) or (qc == qcpost ) ) and inword:
			# dash/apostrophe in a word, look ahead one char
			lacat = qline.at(i+1).category()
			if (lacat == QChar.Letter_Lowercase) \
			or (lacat == QChar.Letter_Uppercase):
			    wf = IMC.WordHasHyphen if (qc == qcdash) \
		            else IMC.WordHasApostrophe
                    if inword:
                        if wf : # continuing a word
                            qword.append(qc)
                            wflags |= wf
                        else : # qc is first char following word
			    IMC.wordCensus.count(qword,wflags) # count it
                            inword = False
                            qword.clear()
                    else:
                        if wf : # qc is first char of new word
                            qword.append(qc)
                            wflags = wf
                            inword = True
                    i += 1
                if inword : # line ends with a word, not unsurprising
                    IMC.wordCensus.count(qword,wflags)
            qtb = qtb.next() # next textblock == next line
	    if (0 == (qtb.blockNumber() & 127)) : #every 128th block
		pqMsgs.rollBar(qtb.blockNumber()) # roll the bar
	# ok we have stored all words of all lines. Go through vocabulary and
        # check the spelling -- it would be a big waste of time to check
        # the spelling of every word as it was read.
        if IMC.aspell.isUp() :
            for i in range(IMC.wordCensus.size()):
                (qword, cnt, wflags) = IMC.wordCensus.get(i)
                if not IMC.aspell.check(qword):
                    wflags |= IMC.WordMisspelt
                    IMC.wordCensus.setflags(i,wflags)
		#print("{0} word: {1} flag: x{2:x}".format(i,qword,wflags))
	pqMsgs.endBar()
