# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *
'''
Implement the (re)Flow panel. On this panel are an array of controls
related to reflowing text, which is only done in the etext, not the HTML.
Generally reflow means arranging the text of each paragraph to fit
in the 75-character line. Complicating this are the special markups developed
for guiguts and one developed by us specifically:

/* .. */   Do not reflow but can be indented by a settable default amount or
           by specific amount specified in /*[n] on the first line. In HTML
           guiguts tries (with poor success) to preserve vertical alignment.

/# .. #/   Reflow within block-quote margins which have a settable default but
           can be given in /#[left.first,right] markup

/P .. P/   Indent by 4 spaces, reflow on a single-line basis as poetry. We add
           support for /P[left.first,right] markup too

/C .. C/   Like the Guiguts /f..f/, which guiguts does not reflow or indent;
           supposedly HTML makes it text-align:center. Typically used for title
           pages etc. We indent the whole by 2 spaces minimum, and center each
           line on col 36 by default, but optionally on the center of the
           longest line, minimizing the width of the centered block.

/$ .. $/   Do not reflow, do not indent. In HTML ??

/L .. L/   Same as /$..$/ in text files; in HTML, treated as unsigned list
           with each nonempty line as one list item.

/X .. X/   Same as /$..$/ in text files; in HTML, wrapped in <pre> 

The reflow markups are always left in place, ensuring that reflow can be
done multiple times.

/T .. T/   Multi-line table markup TBS

/t .. t/   Single-line table markup TBS

The plan is to do with a static markup what guiguts did with the awesome
but difficult-to-use ascii table special effects dialog.

The general algorithm of reflow is two-pass. On the first pass we examine the
document (or selection, no difference) line-by-line from top to bottom. In this
pass we identify each reflow unit, that is, each block of text to be treated.
In open text or block quote, a unit is a paragraph delimited by blank lines.
In poetry, noflow, and centered text, a unit is each single non-empty line.

For each unit we note five items: the first and last text block numbers, the
first-line indent, the left indent, and the right indent (relative to a 75-char
line). The indents of course depend on the type of markup we are in at that
point. All these decisions are made on the first pass and recorded in a list
of tuples, one for each unit/paragraph.

The second pass operates on single units, working from the bottom of the
document or selection, up. This is so changes in the text will not alter
the block numbers of text still to be done. For each unit we form a QTextCursor
for the unit. We pull tokens from the unit text and form a new text as a
QString with the specified indents. Then we assign the reflowed text string
as the text of the cursor, replacing the unflowed text with flowed.

In a "pythonic" move we use a "generator" (co-routine) to produce tokens from
the old text.

'''
import pqMsgs
from PyQt4.QtCore import (Qt, QChar,
    QRegExp,
    QString, QVariant, SIGNAL )
from PyQt4.QtGui import(
    QCheckBox,
    QGridLayout, QHBoxLayout, QVBoxLayout,
    QGroupBox, QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSizePolicy, QSpacerItem,
    QTextBlock, QTextCursor, QTextDocument,
    QWidget )

class flowPanel(QWidget):
    def __init__(self, parent=None):
        super(flowPanel, self).__init__(parent)
        self.stgs = IMC.settings # from which we pull last session's settings
        self.stgs.beginGroup("Flow") # all keys start with Find.
        # Create all subwidgets and lay them out:
        # Per the Qt doc, we need to create a layout and add it to its parent
        # layout before we populate it. So we create layouts with local names,
        # to go out of scope when we exit, but the chain of parent-child refs 
        # keeps them alive. The organization is (See below for more notes)
        # mainLayout is a VBox with a vertical stack of:
        #   indentsVbox
        #      bqiGbox group box "block quote default indents"
        #         bqiHbox
        #            three spinboxes for first, left, right
        #      poiGbox group box "poetry default indents"
        #         poiHbox
        #            three spinboxes for left, right, fold
        #      miscHBox
        #         nfiGbox group box "/*..*/ default indents"
        #            nfiHbox
        #               one spinbox for left
        #         ctrGBox group box "Center /C..C/ on:"
        #            ctrHBox
        #               radio buttons "75" "longest line"
        #   bigHbox
        #      skipGbox group box "Do Not Reflow (skip):"
        #         skipVbox
        #            five checkboxes for Poetry, blockquote, center, special, table
        #      tknVbox
        #         itGbox group box "Count <i> and </i> as:"
        #            itHbox
        #               three radio buttons 0, 1, as-is
        #         boGbox group box "Count <b> and </b> as:"
        #            boHBox
        #               three radio buttons 0, 1, as-is
        #         scGBox group box "Count <sc> and </sc> as:"
        #            scHBox
        #               three radio buttons 0, 1, as-is
        #         ctGBox group box "Center /C..C/ on:"
        #            ctHBox
        #               two radio buttons 75, longest line
        #   doitFrame sunken frame for important buttons
        #      doitHBox
        #         "Reflow Now" [Selection]  [Whole Document]
        #
        # TBS: Possibly other groups of controls from gg text menu
        
        mainLayout = QVBoxLayout() # Main layout is a stack of boxes
        self.setLayout(mainLayout)
        indentsVBox = QVBoxLayout() # box for 3 rows of indents
        mainLayout.addLayout(indentsVBox)
        # block-quote indent row
        bqiGBox = QGroupBox("Block Quote default indents:")
        indentsVBox.addWidget(bqiGBox)
        bqiHBox = QHBoxLayout()
        bqiGBox.setLayout(bqiHBox)
        bqiHBox.addWidget(QLabel("First:"),0)
        self.bqIndent = [None,None,None]
        self.bqIndent[0] = self.makeSpin(0,35,4,u"bqFirst") 
        bqiHBox.addWidget(self.bqIndent[0],0)
        bqiHBox.addWidget(QLabel("Left:"),0)
        self.bqIndent[1] = self.makeSpin(0,35,4,u"bqLeft")
        bqiHBox.addWidget(self.bqIndent[1],0)
        bqiHBox.addWidget(QLabel("Right:"),0)
        self.bqIndent[2] = self.makeSpin(0,35,4,u"bqRight")
        bqiHBox.addWidget(self.bqIndent[2],0)
        bqiHBox.addStretch(1) # compact left
        # poetry indent row
        poiGBox = QGroupBox("Poetry default indents:")
        indentsVBox.addWidget(poiGBox)
        poiHBox = QHBoxLayout()
        poiGBox.setLayout(poiHBox)
        self.poIndent = [None,None,None]
        poiHBox.addWidget(QLabel("First:"),0)
        self.poIndent[0] = self.makeSpin(2,60,2,u"poFirst")
        poiHBox.addWidget(self.poIndent[0],0)
        poiHBox.addWidget(QLabel("Left:"),0)
        self.poIndent[1] = self.makeSpin(2,35,12,u"poLeft")
        poiHBox.addWidget(self.poIndent[1],0)
        poiHBox.addWidget(QLabel("Right:"),0)
        self.poIndent[2] = self.makeSpin(0,35,0,u"poRight")
        poiHBox.addWidget(self.poIndent[2],0)
        poiHBox.addStretch(1)
        # misc row with two groups
        miscHBox = QHBoxLayout()
        indentsVBox.addLayout(miscHBox)
        # no-flow indent
        nfiGBox = QGroupBox("/*..*/ default indent:")
        miscHBox.addWidget(nfiGBox)
        nfiHBox = QHBoxLayout()
        nfiGBox.setLayout(nfiHBox)
        nfiHBox.addWidget(QLabel("Left:"),0)
        self.nfLeftIndent = self.makeSpin(2,35,2,u"nfLeft")
        nfiHBox.addWidget(self.nfLeftIndent,0)
        nfiHBox.addStretch(1)
        # Center choice
        ctrGBox = QGroupBox("Center /C..C/ on:")
        miscHBox.addWidget(ctrGBox)
        ctrHBox = QHBoxLayout()
        ctrGBox.setLayout(ctrHBox)
        self.ctrOn75 = QRadioButton(" 75")
        ctrHBox.addWidget(self.ctrOn75,0)
        self.ctrOnLongest = QRadioButton("longest line+2")
        ctrHBox.addWidget(self.ctrOnLongest,0)
        ctrHBox.addStretch(1)
        bigHBox = QHBoxLayout()
        mainLayout.addLayout(bigHBox)
        # group of block skip checkboxes
        skipGBox = QGroupBox("Do not reflow (skip):")
        bigHBox.addWidget(skipGBox,0)
        skipVBox = QVBoxLayout()
        skipGBox.setLayout(skipVBox)
        self.skipPoCheck = QCheckBox("Poetry /P..P/")
        skipVBox.addWidget(self.skipPoCheck,0)
        self.skipBqCheck = QCheckBox("Block quote /#..#/")
        skipVBox.addWidget(self.skipBqCheck,0)
        self.skipCeCheck = QCheckBox("Center /C..C/")
        skipVBox.addWidget(self.skipCeCheck,0)
        self.skipNfCheck = QCheckBox("No-reflow /*..*/")
        skipVBox.addWidget(self.skipNfCheck,0)
        self.skipTbCheck = QCheckBox("Tables /t, /T")
        skipVBox.addWidget(self.skipTbCheck,0)
        #skipVBox.addStretch(1)
        # group of token-width radio button sets
        tknVBox = QVBoxLayout()
        bigHBox.addLayout(tknVBox)
        itGBox = QGroupBox("Count <i> and </i> as:")
        tknVBox.addWidget(itGBox)
        itHBox = QHBoxLayout()
        itGBox.setLayout(itHBox)
        self.itCounts = self.makeRadioSet(1,"italWidth")
        itHBox.addWidget(self.itCounts[0],0)
        itHBox.addWidget(self.itCounts[1],0)
        itHBox.addWidget(self.itCounts[2],0)
        itHBox.addStretch(1)
        boGBox = QGroupBox("Count <b> and </b> as:")
        tknVBox.addWidget(boGBox)
        boHBox = QHBoxLayout()
        boGBox.setLayout(boHBox)
        self.boCounts = self.makeRadioSet(0,"boldWidth")
        boHBox.addWidget(self.boCounts[0],0)
        boHBox.addWidget(self.boCounts[1],0)
        boHBox.addWidget(self.boCounts[2],0)
        boHBox.addStretch(1)
        scGBox = QGroupBox("Count <sc> and </sc> as:")
        tknVBox.addWidget(scGBox)
        scHBox = QHBoxLayout()
        scGBox.setLayout(scHBox)
        self.scCounts = self.makeRadioSet(0,"scWidth")
        scHBox.addWidget(self.scCounts[0],0)
        scHBox.addWidget(self.scCounts[1],0)
        scHBox.addWidget(self.scCounts[2],0)
        scHBox.addStretch(1)
        tknVBox.addStretch(1)
        # main buttons
        doitGBox = QGroupBox()
        mainLayout.addWidget(doitGBox)
        doitHBox = QHBoxLayout()
        doitGBox.setLayout(doitHBox)
        doitHBox.addWidget(QLabel("Reflow now: "),0)
        self.reflowSelSwitch = QPushButton("Selection")
        doitHBox.addWidget(self.reflowSelSwitch,0)
        self.reflowDocSwitch = QPushButton("Document")
        doitHBox.addWidget(self.reflowDocSwitch,0)
        doitHBox.addStretch(1)        
        mainLayout.addStretch(1)
        self.connect(self.reflowSelSwitch, SIGNAL("clicked()"),self.reflowSelection)
        self.connect(self.reflowDocSwitch, SIGNAL("clicked()"),self.reflowDocument)
        self.itbosc = {'it':1,'bo':0,'sc':2}
        self.updateItBoSc()
        self.stgs.endGroup() # and that's that
        
    # convenience subroutine to make a spinbox recovering its value from
    # the settings.
    def makeSpin(self,lo,hi,df,key):
        sb = QSpinBox()
        sb.setMinimum(lo)
        sb.setMaximum(hi)
        (v,b) = self.stgs.value(QString(key),QVariant(df)).toInt()
        sb.setValue(v)
        return sb
    # convenience subroutine to make a set of 3 radio buttons 0/1/as-is
    # recovering their state from the settings
    def makeRadioSet(self,df,key):
        x = []
        x.append( QRadioButton(" 0") )
        x.append( QRadioButton(" 1") )
        x.append( QRadioButton("as-is") )
        (n,b) = self.stgs.value(QString(key),QVariant(df)).toInt()
        x[n].setChecked(True)
        self.connect(x[0],SIGNAL("toggled(bool)"),self.updateItBoSc)
        self.connect(x[1],SIGNAL("toggled(bool)"),self.updateItBoSc)
        self.connect(x[2],SIGNAL("toggled(bool)"),self.updateItBoSc)
        return x
    # This slot gets called on any change to the "count markup as"
    # button groups and refreshes the itbosc list which is used during reflow.
    # self.itbosc is a dict giving the logical widths for i, b and sc markup,
    # as 0, 1, or as-is (2).
    
    def updateItBoSc(self):
        self.itbosc['it'] = 0 if self.itCounts[0].isChecked() else \
            1 if self.itCounts[1].isChecked() else 2
        self.itbosc['bo'] = 0 if self.boCounts[0].isChecked() else \
            1 if self.boCounts[1].isChecked() else 2
        self.itbosc['sc'] = 0 if self.scCounts[0].isChecked() else \
            1 if self.scCounts[1].isChecked() else 2

    def reflowSelection(self):
        tc = IMC.editWidget.textCursor()
        if tc.hasSelection():
            doc = IMC.editWidget.document()
            topBlock = doc.findBlock(tc.selectionStart())
            endBlock = doc.findBlock(tc.selectionEnd()-1)
            self.theRealReflow(topBlock,endBlock)
        else:
            pqMsgs.warningMsg("No selection to reflow.")
    
    def reflowDocument(self):
        doc = IMC.editWidget.document()
        topBlock = doc.begin()
        endBlock = doc.findBlockByNumber(doc.blockCount()-1)
        self.theRealReflow(topBlock,endBlock)

    # FOR REFERENCE here are the actual data access items:
    # self.bqIndent[0/1/2].value() for first, left, right
    # self.poIndent[0/1/2].value() for first, left, right
    # self.nfLeftIndent.value()
    # self.ctrOn75.isChecked() versus self.ctrOnLongest.isChecked()
    # self.itCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.boCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.scCounts[0/1/2].isChecked() == 0, 1, as-is
    # -- the above 3 are also available as self.itbosc['bo'/'it'/'sc']
    # self.skipPoCheck.isChecked()
    # self.skipBqCheck.isChecked()
    # self.skipNfCheck.isChecked()
    # self.skipCeCheck.isChecked()
    # self.skipTbCheck.isChecked()

    # Reflow proceeds in two passes. The first pass, implemented as 
    # parseText below, scans the text and reduces it to a sequence of
    # "work units. This method is shared with HTML conversion so it
    # produces more data than reflow really needs. A work unit is a dict
    # having these members:
    # 'T' : type of work unit, specifically
    #    'P' paragraph or line to reflow within margins F, L, R
    #    'M' markup of type following starts
    #    '/' markup  of type following ends
    # 'M' : the type of markup starting, in effect, or ending:
    #    ' ' no active markup, open text
    #    '#' block quote
    #    'P' poetry
    #    '*' no-reflow but indent as per UI
    #    'C' no-reflow but center as per UI
    #    'X' no-reflow and leave alone
    #    'U' unordered list by single lines (Guiguts /L)
    #    'W' unordered list by paragraphs
    # 'A' : text block number of start of the unit
    # 'Z' : text block numberof end of the unit
    # 'F', 'L', 'R': the desired First, Left and Right margins for this unit,
    # 'F' and 'R' also apply to single lines
    # 'W' : valid only in a 'T':'/' end of markup unit, the smallest
    # existing indent seen in a *, P, or C markup. All lines of a * or P
    # markup section, or of a C section with "longest line" checked, are
    # indented by F-W, which may be negative.
    # 'B' : the count of blank lines that preceded this unit, used in
    # HTML conversion to detect chapter heads.

    def theRealReflow(self,topBlock,endBlock):
	global tokGen # see wayyyy below us
        unitList = self.parseText(topBlock,endBlock)
        if 0 == len(unitList) :
            return # all-blank? or perhaps an error like unbalanced markup
        #
	# Now do the actual reflowing. unitList has all the paras and single
	# lines to be hacked. Work from end to top. For lines in sections
	# X, *, and C, just adjust the leading spaces. For other sections
	# reflow into new lines. The tokgen function (below) is a generator
	# that returns the next token and its effective length (counting
	# i/b/sc markups as specified in the UI).
        doc = IMC.editWidget.document()
        # In order to have a single undo/redo operation we have to use a
        # single QTextCursor, which is this one:
        tc = IMC.editWidget.textCursor()
        tc.beginEditBlock() # start single undo/redo macro
	topBlockNumber = topBlock.blockNumber()
	endBlockNumber = endBlock.blockNumber()
	pqMsgs.startBar((endBlockNumber - topBlockNumber), "Reflowing the text")
	# To support nesting e.g. /* .. /C .. C/ .. */ we need to save and
	# restore the current least-indent-seen value.
	markupCode = u' '
	markStack = []
	leastIndent = 0
        for u in reversed(range(len(unitList))):
            unit = unitList[u]
	    if unit['T'] == u'/' :
		# end of markup, which we see first because going backwards.
		# push our leastIndent and set it to the new one.
		markStack.append( (leastIndent, markupCode) )
		leastIndent = unit['W']
		markupCode = unit['M']
		continue
	    if unit['T'] == u'M' :
		# start of markup, which we see last; pop our least-indent stack
		(leastIndent, markupCode) = markStack.pop()
		continue
	    # a real unit of lines to process.
	    blockNumberA = unit['A'] # First block of paragraph
	    blockNumberZ = unit['Z'] # ..and last block number
	    # approximately every 16 lines complete, roll the bar
	    if 0x0 == (blockNumberA & 0x0f) :
		pqMsgs.rollBar(endBlockNumber - blockNumberA)
	    # is this a reflow block or not?
	    blockType = unit['M']
	    if blockType == u'X' : 
		continue # don't touch it
	    if (blockType == u'*') or (blockType == u'C') :
		# non-reflow block; adjust leading spaces. F is how many
		# spaces this line has (* section) or needs to center it (C).
		indentAmount = unit['F']
		if blockType == u'*' or \
		   (blockType == u'C' and self.ctrOnLongest.isChecked()) :
		    # reduce that to bring the longest line to the proper
		    # left margin, typically 2 but could be nested deeper.
		    indentAmount = unit['F'] - leastIndent + unit['L']
		# click and drag to select the whole line
		blockA = doc.findBlockByNumber(blockNumberA)
		tc.setPosition(blockA.position()) # click
		tc.setPosition(blockA.position()+blockA.length(),
		               QTextCursor.KeepAnchor) # and draaaag
		# get the text to python land
		lineText = unicode(tc.selectedText())
		# strip leading and trailing spaces, and prepend the number
		# of spaces the line ought to have, and add a newline
		lineText = (u' '*indentAmount)+lineText.strip()+u'\n'
		# put that back in the document replacing the existing line
		tc.insertText(QString(lineText))
		continue # and that's that for this unit
	    # This unit describes a paragraph of one or more lines to reflow.
	    # This includes open text, block quotes, and lines of Poetry.
	    # set up a text cursor that selects the text to be flowed: 
            # set the virtual insertion point after the end of the last line
            blockZ = doc.findBlockByNumber(blockNumberZ)
            tc.setPosition(blockZ.position()+blockZ.length())
	    # drag to select up to the beginning of the first line
            blockA = blockZ if blockNumberA == blockNumberZ \
	           else doc.findBlockByNumber(blockNumberA)
            tc.setPosition(blockA.position(),QTextCursor.KeepAnchor)
            # collect tokens from the selected text and assemble them into
            # lines based on F, L, R, adjusted by W. Collect the marginal
	    # indents and tokens into a QString flowText.
	    F = unit['F']
	    if markupCode == u'P' or markupCode == u'U' :
		F = max(0,F-leastIndent)
	    L = unit['L']
	    if markupCode == u'P' or markupCode == u'U' :
		L = max(0,L-leastIndent)
	    flowText = QString(u' '*F) # start the paragraph with indent F
	    oneSpace = QString(u' ') # one space between tokens
	    leftIndent = QString(u' '*L) # left-indent space
            lineLength = 75 - unit['R']
	    lineLimit = lineLength # how big flow can get before we break it
	    currentLength = F # line space used so far
            for (tok,tl) in tokGen(tc,self.itbosc):
                if lineLimit >= (currentLength + tl): # room for this token
                    flowText.append(tok)
                    flowText.append(oneSpace) # assume there'll be another token
                    currentLength += (tl + 1)
                else: # time to break the line.
                    # replace superfluous space with linebreak code
                    flowText.replace(flowText.size()-1,1,IMC.QtLineDelim)
                    lineLimit = currentLength + lineLength # set new limit
                    flowText.append(leftIndent) # insert left indent
                    flowText.append(tok) # and now the token on a new line
                    flowText.append(oneSpace) # assume there'll be another token
                    currentLength += (L + tl + 1)
            # used up all the tokens, replace the old text with reflowed text
            flowText.replace(flowText.size()-1,1,IMC.QtLineDelim) # terminate last line
            tc.insertText(flowText) # replace selection with reflow
	    # end of for u in reversed range of unitList loop
        pqMsgs.endBar() # wipe out the progress bar
        tc.endEditBlock() # close the single undo/redo macro
	# and that's reflow, folks. Barely 800 lines. pih. easy.

    # subroutine to update the PSW with F L R indent values for markups, either
    # tfrom a list of three values passed in (typically from the UI, but for
    # some markup types, defined literals), or from the optional l[.f][,r]
    # syntax after the markup. Guiguts started this, allowing /#[4.8,2] to mean
    # indent first lines 8, others 4, right 2. We are allowing it all markups
    # just because we can. L == F for single-line markups like /*.
    def getIndents(self,qs,PSW,defaults):
        paramRE = QRegExp("^/\S\s*\[(\d+)(\.\d+)?(\,\d+)?\]")
        tempF = defaults[0]
        tempL = defaults[1]
        tempR = defaults[2]
        if 0 == paramRE.indexIn(qs) : # some params given
            # in the following, since the pattern matched is d+
            # there is no need to check the success boolean on toInt()
            t = paramRE.cap(1) # left - if the regex matched, there is a left
            (tempL, b) = t.toInt()
            t = paramRE.cap(2)
            if not t.isEmpty() : # t has '.d+'
                t.remove(0,1) # drop the leading dot
                (tempF, b) = t.toInt()
            t = paramRE.cap(3)
            if not t.isEmpty() : # t has ',d+'
                t.remove(0,1) # drop the leading comma
            (tempR, b) = t.toInt()
        PSW['F']+=tempF
        PSW['L']+=tempL
        PSW['R']+=tempR
    
    def makeUnit(self,type,PSW,ab,zb):
    	# convenience subroutine just to shorten some code below: return
    	# a unit record based on the PSW, a type code, and start and end blocks.
    	return { 'T':type, 'M':PSW['M'], 'A':ab, 'Z':zb,
                'F':PSW['F'], 'L':PSW['L'], 'R':PSW['R'],
                'W':PSW['W'], 'B':PSW['B']}
   
    def parseText(self,topBlock,endBlock):
	# here we parse a span of text (which may be the whole doc) into a series
	# of work units. Each unit is a dict, described above.
	unitList = []
	# We keep track of the parsing state in a record called PSW (a nostalgic
	# reference to the IBM 360) which is a dict initialized to:
	PSW = { 'S': True, 'Z':None, 'M':' ', 'P':True, 'F':0, 'L':0, 'R':0, 'W':75, 'B':0 }
	# S : scanning: True, looking for a para, or False, collecting a para
	# Z : None, or a QString of the end of the current markup, '#/'
	# M : the code of this markup e.g. u'*'
	# P : True = reflow by paragraphs, False, by single lines as in Poetry
	# F, L, R: current first, left, right indents
	# W, shortest existing indent seen in a no-reflow section
	# B, count of blank lines skipped
	# we allow nesting markups arbitrarily, altho only the nest of
	# /P within /# block quote is really likely or necessary. To keep track
	# of nesting we push the PSW onto this
	stack = []
	# We recognize the start of markup with this RE    
	markupRE = QRegExp("^/(P|#|\\*|C|X|U)")
	# We step through QTextBlocks using the next() method but we take the
	# block numbers to set up the progress bar:
	topBlockNumber = topBlock.blockNumber()
	endBlockNumber = endBlock.blockNumber()
	pqMsgs.startBar((endBlockNumber - topBlockNumber), "Parsing the text")
	#
	# OK here we go with a massive loop over the sequence of lines
	thisBlock = topBlock # current block (text line)
	firstBlockNumber = None # number of first block of a work unit (paragraph)
	while True:
	    # Note the block number which we store in work units
	    thisBlockNumber = thisBlock.blockNumber()
	    # Every 16th line on average roll the progress bar
	    if 0x0f == (thisBlockNumber & 0x0f) :
		pqMsgs.rollBar(thisBlockNumber - topBlockNumber)
	    qs = thisBlock.text() # const(?) ref(?) to text of line
	    if PSW['S'] :
		# not in a paragraph, scanning for data to work on
		if qs.trimmed().isEmpty() :
		    # another blank line, just count it
		    PSW['B'] += 1
		else:
		    # We are looking for work and we found a non-empty line!
			# But: is it text, or a markup?
		    if 0 == markupRE.indexIn(qs):
			# we have found a markup! Save our current state
			stack.append(PSW.copy())
			# Now, figure out which markup it is, and set PSW to suit.
			# Note that PSW['S'] is already True and stays that way
			PSW['M'] = unicode(markupRE.cap(1)) # u'*', u'P' etc
			PSW['Z'] = QString(PSW['M']+u'/')
			unitList.append(self.makeUnit('M',PSW,0,0))
			if PSW['M'] == u'#' :
			    # Start a block quote section
			    PSW['P'] = True # collect paragraphs
			    self.getIndents(qs,PSW,[
			        self.bqIndent[0].value(),
			        self.bqIndent[1].value(),
			        self.bqIndent[2].value()] )
			    # don't care about W
			    PSW['B'] = 0
			elif PSW['M'] == u'P' :
			    # start a poetry section
			    PSW['P'] = False # collect by lines
			    self.getIndents(qs,PSW,[
			        self.poIndent[0].value(),
			        self.poIndent[1].value(),
			        self.poIndent[2].value()] )
			    PSW['W'] = 75
			    # don't care about B
			elif PSW['M'] == u'*' :
			    # start a no-reflow indent section
			    PSW['P'] = False # collect by lines
			    self.getIndents(qs,PSW,[
			        self.nfLeftIndent.value(),
			        self.nfLeftIndent.value(),
			        0] )
			    PSW['W'] = 75
			    # don't care about B
			elif PSW['M'] == u'C' :
			    # start a centering section
			    PSW['P'] = False # collect by lines
			    self.getIndents(qs,PSW,[2,2,0])
			    PSW['W'] = 75
			    # don't care about B
			elif PSW['M'] == u'X' :
			    # start a no-reflow no-indent section
			    PSW['P'] = False # collect by lines
			    PSW['F'] = 0
			    PSW['L'] = 0
			    PSW['R'] = 0
			    # don't care about W or B
			elif PSW['M'] == u'U' :
			    # start a list by single lines
			    PSW['P'] = False # collect by lines
			    self.getIndents(qs,PSW,[2,4,4])
			    PSW['W'] = 75
			    # don't care about B
			else : 
			    # start a list by paragraphs - the only remaining
			    # possibility because the RE only matches these codes.
			    PSW['P'] = True # collect paras
			    self.getIndents(pq,PSW,[2,4,4])
			    PSW['W'] = 75
			    # don't care about B
		    elif PSW['Z'] is not None and qs.startsWith(PSW['Z']):
			# we have found end of markup with no paragraph working
			# document it with an end-markup unit
			unitList.append(self.makeUnit('/',PSW,0,0))
			# and return to what we were doing before the markup
			PSW = stack.pop()
			PSW['B'] = 0
		    else:
			# It is not a markup, so it starts a paragraph
			if PSW['P'] : 
			    # start of a normal paragraph
			    firstBlockNumber = thisBlockNumber
			    PSW['S'] = False # go to other half of the if-stack
			else:
			    # we are not doing paragraphs, e.g. we are in /*
			    # estimate the proper indent for this line.
			    u = self.makeUnit('P',PSW,thisBlockNumber,thisBlockNumber)
			    lineText = unicode(qs) # get text to python-land
			    if PSW['M'] == u'C' : 
				# calculate indent for centered line, at least 2
				# (may be reduced later)
				lineIndent = ( 75-len(lineText.strip()) ) /2
				lineIndent = int( max(2, lineIndent) )
				u['F'] = lineIndent
			    elif PSW['M'] != u'X' : 
				# calculate indent for P, *, L: existing leading
				# spaces plus F (possibly adjusted later)
				lineIndent = len(lineText)-len(lineText.lstrip())
				u['F'] = lineIndent + PSW['F']
			    else :  # indent for X is 0
				lineIndent = 0
				u['F'] = 0
			    PSW['W'] = min(lineIndent,PSW['W'])
			    unitList.append(u)			    
	    else: # PSW['S'] is false
		# we are collecting the lines of a paragraph. Is this line empty?
		# the .trimmed method strips leading and trailing whitespace,
		# so we can detect either all-blank or truly empty lines.
		if qs.trimmed().isEmpty():
		    # we were collecting lines and now have a blank line,
		    # create a work unit for the completed paragraph.
		    unitList.append(
		            self.makeUnit('P',PSW,firstBlockNumber, thisBlockNumber-1))
		    # note the blank line
		    PSW['B'] = 1
		    # go back to scanning for data
		    PSW['S'] = True
		else:
		    # this line is not empty, but, is it data or end-markup?
		    if PSW['Z'] is not None and qs.startsWith(PSW['Z']):
			# we have found the end of the current markup with a para working
			# add a work unit for the paragraph we are in
			unitList.append(
			    self.makeUnit('P',PSW,firstBlockNumber,thisBlockNumber-1))
			# and also put in a work unit for the end of the markup
			unitList.append(self.makeUnit('/',PSW,0,0) )
		        # and return to what we were doing before the markup
		        PSW = stack.pop()
		        PSW['B'] = 0
		    else:
			# just another line of text for this paragraph. we need
			# to note the count of leading spaces to make W right.
			# the only way to get that is to strip them and compare
			# counts. Unfortunately QString doesn't have an lstrip.
			uqs = unicode(qs).lstrip()
			PSW['W'] = min(PSW['W'],qs.size()-len(uqs))
	    # bottom of repeat-until loop, check for end
	    if thisBlock == endBlock :
		# we have processed the last line in the doc or selection
		if not PSW['S'] :
		    # we were collecting a paragraph, finish it
		    unitList.append(
		        self.makeUnit('P',PSW,firstBlockNumber,thisBlockNumber))
		# end the loop
		break
	    # not the last block; move along to the next block
	    thisBlock = thisBlock.next()
	# end of while true loop.
	if len(stack) != 0 :
	    # a markup was not closed
	    msg1 = "Markup end "+unicode(PSW['Z'])+" not seen!"
	    msg2 = "Nothing will be done. Correct and retry."
	    pqMsgs.warningMsg(msg1, msg2)
	    unitList = []
	pqMsgs.endBar()
	return unitList

    # This slot receives the pqMain's shutting-down signal. Stuff all our
    # current UI settings into the settings file.
    def shuttingDown(self):
        stgs = IMC.settings
        stgs.beginGroup("Flow") # all subsequent keys start with Flow.
        stgs.setValue("bqFirst",self.bqIndent[0].value() )
        stgs.setValue("bqLeft",self.bqIndent[1].value() )
        stgs.setValue("bqRight",self.bqIndent[2].value() )
        stgs.setValue("poFirst",self.poIndent[0].value() )
        stgs.setValue("poLeft",self.poIndent[1].value() )
        stgs.setValue("poRight",self.poIndent[2].value() )
        stgs.setValue("nfLeft",self.nfLeftIndent.value() )
        stgs.endGroup()

# tokGen is a generator function that returns the successive tokens from the
# text selected by a text cursor. Each token is returned as a tuple, (tok,tl)
# where tok is a QString and tl is its logical length, which may be less than
# tok.size() when tok contains <i/b/sc> markups. The lengths to use for these are
# passed as a dictionary (from flowpanel.itbosc, which isn't accessible as this
# is a global function, not a method). Note that a multiline selection has
# \u2029 instead of \n, but it comes up as isSpace() anyway so we don't care.
ibsRE = QRegExp("^</?(i|b|sc)>",Qt.CaseInsensitive)
ltChar = QChar(u'<')

def tokGen(tc, itbosc):
    qs = tc.selectedText() # sadly we end up copying every paragraph.
    qs.append(QChar(u' ')) # ensure text ends in space for easier loop control
    i = 0
    while True: # one iteration per token returned
        # n.b. qs.at(qs.size()).isSpace() returns False
        while qs.at(i).isSpace():
            i += 1
        if i >= qs.size() : break # we're done
        tok = QString()
        ll = 0
        while not qs.at(i).isSpace():
            # since markup is < 1% of a doc, no point in applying the ibsRE
            # when it has no chance of matching.
            if qs.at(i) == ltChar :
                # The reason there's a caret in that RE is that we want
                # the search to fail quick, not run on ahead and find the
                # next markup that may be 50 characters down the string.
                # One would think with the CaretAtOffset rule, and a match
                # at offset i, the return would be 0, but it's the offset.
                if i == ibsRE.indexIn(qs,i,QRegExp.CaretAtOffset):
                    x = itbosc[unicode(ibsRE.cap(1))]
                    ll += x if x<2 else ibsRE.matchedLength()
                    tok.append( ibsRE.cap(0) )
                    i += ibsRE.matchedLength()
                else:
                    ll += 1
                    tok.append(ltChar)
                    i += 1
            else:
                ll += 1
                tok.append(qs.at(i))
                i += 1
        # back to spaces, return this token
        yield( (tok, ll) )

if __name__ == "__main__":
    import sys
    from PyQt4.QtCore import (Qt,QFile,QIODevice,QTextStream,QSettings)
    from PyQt4.QtGui import (QApplication,QPlainTextEdit,QFileDialog,QMainWindow)
    import pqIMC
    app = QApplication(sys.argv) # create an app
    IMC = pqIMC.tricorder() # set up a fake IMC for unit test
    IMC.fontFamily = QString("Courier")
    import pqMsgs
    pqMsgs.IMC = IMC
    IMC.editWidget = QPlainTextEdit()
    IMC.editWidget.setFont(pqMsgs.getMonoFont())
    IMC.settings = QSettings()
    widj = flowPanel()
    MW = QMainWindow()
    MW.setCentralWidget(widj)
    pqMsgs.makeBarIn(MW.statusBar())
    MW.show()
    utqs = QString('''

/X
-123456789-123456789-123456789-123456789-123456789-123456789-123456789-123|56789
X/

This is a paragraph of text on
several lines. When building or refreshing its metadata,
PPQT checks all words for spelling. A "bad" word is assumed
to be misspelt; a "good" word is assumed to be correct.
Any word not in those lists is presented to the spell-checker
and noted as correct or misspelt based on the current dictionary.

/#
When building or refreshing its metadata,
PPQT checks all words for spelling. A "bad" word is assumed
to be misspelt; a "good" word is assumed to be correct.
Any word not in those lists is presented to the spell-checker
and noted as correct or misspelt based on the current dictionary.
#/

/C
A
TYPICALLY LONG AND VERBOSE AND TURGID TITLE FOR THE
FIRST PAGE 

BY

AUTHOR TEDIOUS
C/

/P
Twinkle,
  Twinkle,
    Star of mine,
They tell me you are wicked and I believe them, for I have seen your painted women under the gas lamps luring the farm boys.
P/

/U
First
They tell me you are wicked and I believe them, for I have seen your painted women
Third
U/

    ''')
    IMC.editWidget.setPlainText(utqs)
    IMC.mainWindow = widj
    IMC.editWidget.show()
    app.exec_()
