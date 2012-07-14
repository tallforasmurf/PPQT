# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "0.1.0" # refer to PEP-0008
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
Implement the (re)Flow panel. On this panel are an array of controls
related to reflowing the ASCII etext, and buttons for HTML conversion.

ASCII reflow means arranging the text of each paragraph to fit in the standard
75-character line. Complicating this are the special markups pioneered by
Guiguts and supported here with somewhat different syntax:

/Q .. Q/   Reflow within block-quote margins, with default margins from the
           control on the panel but which can be set using /Q F:nn L:nn R:nn
	   in the opening markup line.

/U .. U/   Unsigned list, treated identically to /Q F:2 L:4 but allows
           explicit F:/L:/R: options as well.

/* .. */   Do not reflow but can be indented by a settable default amount or
           by specific amount specified in /* L:nn on the first line.

/P .. P/   Indent by 2 spaces, reflow on a single-line basis as poetry. Default
           margins from the controls but we add /P F:nn L:nn R:nn support.

/C .. C/   Like the Guiguts /f..f/, which guiguts does not reflow or indent.
           Typically used for title pages etc. We indent the whole by 2 spaces
	   minimum, and center each line on col 36 by default, but optionally
	   on the center of the longest line, minimizing the width.

/X .. X/   Do not reflow, do not indent.

/R .. R/   Right-aligned text, something missing from Guiguts, convenient
	   signatures and letter heads.

/T .. T/   Single-line table markup

/TM .. T/  Multi-line table markup. These allow more complex table options
           which are documented in pqTable.

The reflow markups are always left in place, ensuring that reflow can be
done multiple times.

The general algorithm of reflow is two-pass. On the first pass we examine the
document (or selection, no difference) line-by-line from top to bottom. In this
pass we identify each reflow unit, that is, each block of text to be treated.
In open text, /Q, and /U, a unit is a paragraph delimited by blank lines.
In other markups a unit is each single non-empty line. Empty lines are counted
but otherwise ignored.

For each unit we note several items: the first and last text block numbers;
the first-line indent, left indent, and right indent (relative to a 75-char
line); the count of blank lines preceding.. The indents of course depend on
the type of markup we are in at that point. All these decisions are made on
the first pass and recorded in a list of dicts, one for each unit/paragraph.

The second pass operates on single units, working from the bottom of the
document or selection, up. This is so changes in the text will not alter
the block numbers of text still to be done. For each unit we pull tokens from
the unit text and form a new text as a QString with the specified indents.
Then we insert the reflowed text string to replace the original line(s).
All updates are done with one QTextCursor set up for a single undo "macro".

In a "pythonic" move we use a "generator" (co-routine) to produce tokens from
the old text.

'''
import pqMsgs
import pqTable
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
        #         "Reflow Now" [Selection]  [Document]
	#   htmlFrame sunken frame for two more buttons
	#      htmlHBox
	#         "HTML Convert" [Selection]  [Document]
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
        self.skipBqCheck = QCheckBox("Block quote /Q..Q/")
        skipVBox.addWidget(self.skipBqCheck,0)
        self.skipCeCheck = QCheckBox("Center /C..C/")
        skipVBox.addWidget(self.skipCeCheck,0)
        self.skipNfCheck = QCheckBox("No-reflow /*..*/")
        skipVBox.addWidget(self.skipNfCheck,0)
        self.skipTbCheck = QCheckBox("Tables /T..T/")
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
        # reflow action buttons
        doitGBox = QGroupBox()
        mainLayout.addWidget(doitGBox)
        doitHBox = QHBoxLayout()
        doitGBox.setLayout(doitHBox)
        doitHBox.addWidget(QLabel("Reflow now: "),0)
        self.reflowSelSwitch = QPushButton("Selection")
        doitHBox.addWidget(self.reflowSelSwitch,0)
        self.reflowDocSwitch = QPushButton("Document")
        doitHBox.addWidget(self.reflowDocSwitch,0)
        doitHBox.addStretch(1) # compress to the left
	# html action buttons
        htmlGBox = QGroupBox()
        mainLayout.addWidget(htmlGBox)
        htmlHBox = QHBoxLayout()
        htmlGBox.setLayout(htmlHBox)
        htmlHBox.addWidget(QLabel("HTML Convert: "),0)
        self.htmlSelSwitch = QPushButton("Selection")
        htmlHBox.addWidget(self.htmlSelSwitch,0)
        self.htmlDocSwitch = QPushButton("Document")
        htmlHBox.addWidget(self.htmlDocSwitch,0)
        htmlHBox.addStretch(1)   # compress to the left     
        mainLayout.addStretch(1) # make compact to the top
        self.connect(self.reflowSelSwitch, SIGNAL("clicked()"),self.reflowSelection)
        self.connect(self.reflowDocSwitch, SIGNAL("clicked()"),self.reflowDocument)
        self.itbosc = {'i':1,'b':0,'sc':2}
        self.updateItBoSc()
        self.connect(self.htmlSelSwitch, SIGNAL("clicked()"),self.htmlSelection)
        self.connect(self.htmlDocSwitch, SIGNAL("clicked()"),self.htmlDocument)
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
        self.itbosc['i'] = 0 if self.itCounts[0].isChecked() else \
            1 if self.itCounts[1].isChecked() else 2
        self.itbosc['b'] = 0 if self.boCounts[0].isChecked() else \
            1 if self.boCounts[1].isChecked() else 2
        self.itbosc['sc'] = 0 if self.scCounts[0].isChecked() else \
            1 if self.scCounts[1].isChecked() else 2

    # FOR REFERENCE here are the actual data access items in the UI:
    # self.bqIndent[0/1/2].value() for first, left, right
    # self.poIndent[0/1/2].value() for first, left, right
    # self.nfLeftIndent.value()
    # self.ctrOn75.isChecked() versus self.ctrOnLongest.isChecked()
    # self.itCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.boCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.scCounts[0/1/2].isChecked() == 0, 1, as-is
    # -- the above 3 are also available as self.itbosc['b'/'i'/'sc']
    # self.skipPoCheck.isChecked()
    # self.skipBqCheck.isChecked()
    # self.skipNfCheck.isChecked()
    # self.skipCeCheck.isChecked()
    # self.skipTbCheck.isChecked()

    # These slots receive the clicked signal of the action buttons
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

    def htmlSelection(self):
        tc = IMC.editWidget.textCursor()
        if tc.hasSelection():
            doc = IMC.editWidget.document()
            topBlock = doc.findBlock(tc.selectionStart())
            endBlock = doc.findBlock(tc.selectionEnd()-1)
            self.theRealHTML(topBlock,endBlock)
        else:
            pqMsgs.warningMsg("No selection to convert.")
    
    def htmlDocument(self):
        doc = IMC.editWidget.document()
        topBlock = doc.begin()
        endBlock = doc.findBlockByNumber(doc.blockCount()-1)
        self.theRealHTML(topBlock,endBlock)

    # Reflow proceeds in two passes. The first pass is common to Reflow and
    # to HTML, and is implemented as parseText below. It scans the text and
    # reduces it to a sequence of "work units." A work unit is a dict
    # having these members:
    # 'T' : type of work unit, specifically
    #    'P' paragraph or line to reflow within margins F, L, R
    #    'M' markup of type noted next begins with this line
    #    '/' markup of type noted next ends with this line
    # 'M' : the type of markup starting, in effect, or ending:
    #    ' ' no active markup, open text
    #    'Q' block quote
    #    'F' like Q but zero indents
    #    'P' poetry
    #    '*' no-reflow but indent as per UI
    #    'C' no-reflow but center as per UI
    #    'X' no-reflow and leave alone
    #    'U' unordered list by paragraphs
    #    'R' right-aligned by lines
    #    'T' single or multiline table
    # 'A' : text block number of start of the unit
    # 'Z' : text block number of end of the unit
    # 'F', 'L', 'R': the desired First, Left and Right margins for this unit,
    # 'W' : in a paragraph ('T':'P'), the smallest actual indent thus far
    #       in the unit; in end of markup ('T':'/') the smallest in the unit.
    # 'K' : in a line of a poem ('T':'P' && 'M':'P'), an empty QString or
    #       the poem line number as a decimal digits.
    # seen in a *, P, or C markup. Lines of a * or P markup, or C markup with
    # "longest line" checked, are indented by F-W (which may be negative) thus
    # removing any existing indent installed from a previous reflow.
    # 'B' : the count of blank lines that preceded this unit, used in Table
    # to detect row divisions and in HTML conversion to detect chapter heads
    # or Poetry stanzas.

    def theRealReflow(self,topBlock,endBlock):
	global tokGen # see wayyyy below this code down at the end
	# Parse the text into work units
        unitList = self.parseText(topBlock,endBlock)
        if 0 == len(unitList) :
            return # all-blank? or perhaps an error like unbalanced markup
	# Now do the actual reflowing. unitList has all the paras and single
	# lines to be hacked. Work from end to top. For lines in sections
	# R, P, *, and C, just adjust the leading spaces. Skip over X, and
	# pass Tables to a separate module. For nonmarkup, Q and U sections
	# reflow paragraphs into new lines. The tokgen function (below) is a
	# generator that returns the next token and its effective length
	# (counting i/b/sc markups as specified in the UI).
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
		# end of markup, which we see first because of going backwards.
		# push our leastIndent and set it to the new one.
		markStack.append( (leastIndent, markupCode) )
		leastIndent = unit['W']
		markupCode = unit['M']
		if markupCode == u'T':
		    # bottom of a table section, not its start
		    tableBottomIndex = u
		continue
	    if unit['T'] == u'M' :
		# start of markup, which we see last in our backward scan
		if markupCode == u'T' :
		    # top of a table section; pass the table work units to
		    # pqTable.tableReflow, which will do the needful.
		    pqTable.tableReflow(tc,doc,unitList[u:tableBottomIndex+1])
		# and emerge from this markup block
		(leastIndent, markupCode) = markStack.pop()
		continue
	    # neither end of markup, so: a real unit of lines to process.
	    blockNumberA = unit['A'] # First block of paragraph
	    blockNumberZ = unit['Z'] # ..and last block number
	    # approximately every 16 lines complete, roll the bar
	    if 0x0 == (blockNumberA & 0x0f) :
		pqMsgs.rollBar(endBlockNumber - blockNumberA)
	    # is this a reflow block or not?
	    if markupCode == u'X' or markupCode == u'T':
		# line of /X or /F which we skip, or /T which we defer
		continue # don't touch it
	    if (markupCode == u'*') or (markupCode == u'C') or (markupCode == u'R') :
		# non-reflow block; adjust leading spaces. F is how many
		# spaces this line has (* section) or needs to align it (C, R).
		indentAmount = unit['F']
		if markupCode == u'*' or \
		(markupCode == u'C' and self.ctrOnLongest.isChecked()) :
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
	    # This includes open text, block quotes, lists, and lines of Poetry.
	    # set up a text cursor that selects the text to be flowed: 
            # set the virtual insertion point after the end of the last line
            blockZ = doc.findBlockByNumber(blockNumberZ)
	    if blockZ != doc.lastBlock():
		tc.setPosition(blockZ.position()+blockZ.length())
	    else:
		tc.setPosition(blockZ.position()+blockZ.length()-1)
	    # drag to select up to the beginning of the first line
            blockA = blockZ if blockNumberA == blockNumberZ \
	           else doc.findBlockByNumber(blockNumberA)
            tc.setPosition(blockA.position(),QTextCursor.KeepAnchor)
            # collect tokens from the selected text and assemble them into
            # lines based on F, L, R, adjusted by W. Collect the marginal
	    # indents and tokens into a QString flowText.
	    F = unit['F']
	    L = unit['L']
	    if markupCode == u'P' :
		# pull Poetry lines back out if they had previously indented
		# for example if they had previously been reflowed
		F = max(0,F-leastIndent)
		L = max(0,L-leastIndent)
	    flowText = QString(u' '*F) # start the paragraph with indent F
	    oneSpace = QString(u' ') # one space between tokens
	    leftIndent = QString(u' '*L) # left-indent space
            lineLength = 75 - unit['R']
	    lineLimit = lineLength # how big flow can get before we break it
	    currentLength = F # line space used so far
	    wholeLineLength = 0 # length of whole lines accumulated
            for (tok,tl) in tokGen(tc,self.itbosc):
                if lineLimit >= (currentLength + tl): # room for this token
                    flowText.append(tok)
                    flowText.append(oneSpace) # assume there'll be another token
                    currentLength += (tl + 1)
                else: # time to break the line.
                    lineLimit = currentLength + lineLength # set new limit
                    # replace superfluous space with linebreak code
                    flowText.replace(currentLength-1,1,IMC.QtLineDelim)
                    flowText.append(leftIndent) # insert new left indent
                    flowText.append(tok) # and now the token on a new line
                    flowText.append(oneSpace) # assume there'll be another token
                    currentLength += (L + tl + 1)
            # used up all the tokens of this paragraph or line. If this was a
	    # line of a poem, and it ended with a line number, push that out
	    flowText.chop(1) # drop superfluous final space
	    if markupCode == u'P' and (not unit['K'].isEmpty()) :
		# there was a line number seen on this poem line
		available = lineLimit - currentLength
		if available < 1 :
		    # not room to put a second space ahead of the 
		    # line number, which we must do to maintain the ability
		    # to recognize a line number.
		    pqMsgs.warningMsg(
		        u'Poem line number does not fit in line length',
		        u'Near line {0}'.format(blockNumberA)  )
		    available = 1 # so push it past the limit by 1
		insertPoint = currentLength - unit['K'].size() - 1
		flowText.insert(insertPoint,b' '*available)
		
	    # replace the old text with reflowed text
            flowText.append(IMC.QtLineDelim) # terminate last line
	    tc.insertText(flowText) # replace selection with reflow
	    # end of for u in reversed range of unitList loop
        pqMsgs.endBar() # wipe out the progress bar
        tc.endEditBlock() # close the single undo/redo macro
	# and that's reflow, folks. Barely 800 lines. pih. easy.

    # This is the text parser used by theRealReflow and theRealHTML.
    # Parse a span of text lines into work units, as documented above.
    # We keep track of the parsing state in a record called PSW (a nostalgic
    # reference to the IBM 360), a dict with these members:
    # S : scanning: True, looking for a para, or False, collecting a para
    # Z : None, or a QString of the end of the current markup, e.g. 'P/'
    # M : the code of this markup e.g. u'Q'
    # P : True = reflow by paragraphs, False, by single lines as in Poetry
    # F, L, R: current first, left, right indents
    # W, shortest existing indent seen in a no-reflow section
    # B, count of blank lines skipped ahead of this line/para
    # K, poem line number when seen
    # Many of these items get copied into each work unit.
    # 
    # We permit nesting markups pretty much arbitrarily (nothing can nest
    # inside /X or /T however). In truth only the nest of /P or /R inside
    # /Q block quote is really likely. To keep track of nesting we push the
    # PSW onto a stack when entering a markup, and pop it on exit.
    def parseText(self,topBlock,endBlock):
	unitList = []
	PSW = { 'S': True, 'Z':None, 'M':' ', 'P':True, 'F':0, 'L':0, 'R':0, 'W':75, 'B':0}
	stack = []
	# We recognize the start of markup with this RE    
	markupRE = QRegExp(u'^/(P|Q|\\*|C|X|F|U|R|T)')
	# We recognize a poem line number with this RE: at least 2 spaces,
	# then decimal digits followed by the end of the line. Note: because
	# we apply to a line as qstring we can use the $ for end of line
	poemNumberRE = QRegExp(u' {2,}(\d+) *$')
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
			PSW['M'] = unicode(markupRE.cap(1)) # u'Q', u'P' etc
			PSW['Z'] = QString(PSW['M']+u'/') # endmark, 'Q/' etc
			# make a start-markup work unit for this line
			unitList.append(self.makeUnit('M',PSW,thisBlockNumber,thisBlockNumber))
			PSW['B'] = 0 # clear the blank-line-before count
			if PSW['M'] == u'Q' and (not self.skipBqCheck.isChecked()) :
			    # Enter a block quote section
			    PSW['P'] = True # collect paragraphs
			    self.getIndents(qs,PSW,self.bqIndent[0].value(),
			    self.bqIndent[1].value(), self.bqIndent[2].value() )
			    # don't care about W
			elif PSW['M'] == u'F' : # footnote section
			    PSW['P'] = True # collect paragraphs
			    PSW['F'] = 0 # with 0 margins
			    PSW['L'] = 0
			    PSW['R'] = 0
			    # don't care about W
			elif PSW['M'] == u'P' and (not self.skipPoCheck.isChecked()) :
			    # Enter a poetry section
			    PSW['P'] = False # collect by lines
			    self.getIndents(qs,PSW, self.poIndent[0].value(),
			        self.poIndent[1].value(), self.poIndent[2].value() )
			    PSW['W'] = 75 # initialize to find shortest indent
			elif PSW['M'] == u'*' and (not self.skipNfCheck.isChecked()) :
			    # Enter a no-reflow indent section
			    PSW['P'] = False # collect by lines
			    self.getIndents(qs,PSW,self.nfLeftIndent.value(),
			        self.nfLeftIndent.value(), 0 )
			    PSW['W'] = 75 # initialize to find shortest indent
			elif PSW['M'] == u'C' and (not self.skipCeCheck.isChecked()) :
			    # Enter a centering section
			    PSW['P'] = False # collect by lines
			    self.getIndents(qs,PSW,2,2,0)
			    PSW['W'] = 75 # initialize to find shortest indent
			elif PSW['M'] == u'X' :
			    # Enter a no-reflow no-indent section
			    PSW['P'] = False # collect by lines
			    PSW['F'] = 0
			    PSW['L'] = 0
			    PSW['R'] = 0
			    # don't care about W
			elif PSW['M'] == u'U' :
			    # Enter a list markup
			    PSW['P'] = True # collect by paragraphs
			    self.getIndents(qs,PSW,2,4,4)
			    # don't care about W
			elif PSW['M'] == u'R' :
			    # Enter a right-aligned section
			    PSW['P'] = False # collect by lines
			    self.getIndents(qs,PSW,0,0,0)
			    # don't care about W
			elif PSW['M'] == u'T' :
			    # start a table section /T or /TM
			    PSW['P'] = False # collect by lines
			    # table will fit in current F and R values
			else : 
			    # one of the sections is being skipped: consume
			    # lines until we see the end of the section.
                            while thisBlock.next() != endBlock:
                                thisBlock = thisBlock.next()
                                if thisBlock.text().startsWith(PSW['Z']) :
				    thisBlock = thisBlock.previous()
				    break     
		    # markupRE did not hit, not starting a markup. Ending one?
		    elif PSW['Z'] is not None and qs.startsWith(PSW['Z']):
			# we have found end of markup with no paragraph working
			# document it with an end-markup unit
			unitList.append(self.makeUnit('/',PSW,thisBlockNumber,thisBlockNumber))
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
			    # we are not doing paragraphs, we are in /C, /P etc
			    # create a work unit to describe this line
			    u = self.makeUnit('P',PSW,thisBlockNumber,thisBlockNumber)
			    lineText = unicode(qs) # get text to python-land
			    if PSW['M'] == u'C' : 
				# calculate indent for centered line, at least 2
				# (may be reduced later)
				lineIndent = ( 75-len(lineText.strip()) ) /2
				lineIndent = int( max(2, lineIndent) )
				u['F'] = lineIndent
			    elif PSW['M'] == u'R' :
				# calculate indent for right-aligned line
				lineIndent = max(0, (75-len(lineText.strip()))-PSW['R'])
				u['F'] = lineIndent
			    elif PSW['M'] == u'P' or PSW['M'] == u'*': 
				# calculate indent for P or *: existing leading
				# spaces plus F (possibly adjusted later)
				lineIndent = len(lineText)-len(lineText.lstrip())
				u['F'] = lineIndent + PSW['F']
				# look for and save poem line number (if this is
				# not a poem it will be ignored)
				if 0 < poemNumberRE.indexIn(qs):
				    u['K'] = QString(poemNumberRE.cap(1))
			    else :  # indent for X is 0, for T is ignored
				lineIndent = 0
				u['F'] = 0
			    PSW['W'] = min(lineIndent,PSW['W']) # note shortest indent
			    unitList.append(u)			    
			    PSW['B'] = 0
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
			unitList.append(self.makeUnit('/',PSW,thisBlockNumber,thisBlockNumber) )
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

    # subroutine to update the PSW with F L R indent values for markups, either
    # from a list of three numbers passed in (which would typically come from
    # the UI, but for some markup types, defined literals), or from the optional
    # F:n L:n R:n syntax after the markup.
    def getIndents(self, qs, PSW, dfltF, dfltL, dfltR):
	F_RE = QRegExp(u' F\\w*:(\\d+)')
	L_RE = QRegExp(u' L\\w*:(\\d+)')
	R_RE = QRegExp(u' R\\w*:(\\d+)')
	tempF = dfltF
	if -1 < F_RE.indexIn(qs) : # we see F:n, capture it
	    (tempF, b) = F_RE.cap(1).toInt()
	tempL = dfltL
	if -1 < L_RE.indexIn(qs) : # don't have to check the success boolean
	    (tempL, b) = L_RE.cap(1).toInt()
	tempR = dfltR
	if -1 < R_RE.indexIn(qs) : # .. we know cap(1) is only digits
	    (tempR, b) = R_RE.cap(1).toInt()
	# Add the captured or default value into the PSW -- adding because
	# this markup may be nested in another.
	PSW['F']+=tempF
        PSW['L']+=tempL
        PSW['R']+=tempR
    
    def makeUnit(self,type,PSW,ab,zb):
    	# convenience subroutine just to shorten some code: return
    	# a unit record based on the PSW, a type code, and start and end blocks.
    	return { 'T':type, 'M':PSW['M'], 'A':ab, 'Z':zb,
                'F':PSW['F'], 'L':PSW['L'], 'R':PSW['R'],
                'W':PSW['W'], 'B':PSW['B'], 'K':QString() }

    # Do HTML conversion. Use the textParse method to make a list of units.
    # Process the list of units from bottom up, replacing as we go:
    #  Q/   -->   </div>
    #  /Q   -->   <div class='blockquote'>
    #  R/   -->   </div>
    #  /R   -->   <div class='ralign'>
    #  U/   -->   </ul>
    #  /U   -->   <ul>
    #  P/   -->   </div></div>
    #  /P   -->   <div class='poetry'><div class='stanza'>
    #  T/   -->   </table>
    #  /T[M] -->  <table>
    #  /F  -->  <div class='footnotes'>
    #  F/  -->  </div>
    #  */, X/, C/  --> </pre>
    #  /*, /X, /C  --> <pre>
    # <tb> --> <hr /> (no classname, so set your CSS for this as default case)
    #
    # We "enter" a markup at its end (Q/, T/, etc) and on entering push the
    # prior markup type. Within a markup we insert bookend texts around each
    # work unit based on the markup:
    #  Q/, R/, and open code: <p> and </p>
    #  U/ : <li> and </li>
    #  P/ : <span class="iX"> and </span><br /> where "iX" is based on F-W
    #  */, X/, C/, and T/ -- None
    # On seeing T/ we note the unit number ending the table; on /T[M] we pass
    # the slice of table units from /T to T/ to pqTable.tableHTML.
    # The B, preceding blank lines, value of a work unit is used as follows:
    # With poetry, B>0 means inserting </div><div class='stanza'>
    # In open text, B==4 means using <h2> and </h2> as paragraph bookends;
    # but B==2 when the next-higher unit has B!=4 means use <h3> and </h3>
    # Globals bookendA, etc are below.
    #
    # Note on inserting bookends and other markup: QTextBlock.length() does
    # include the line-delim at the end of the block. We include our own
    # line-delim inserting bookendA, so <p>, <li> etc go on a line alone,
    # and also on bookendZ, which goes after the existing line-delim and
    # gets one of its own as well, thus <p>\n ... text \N</p>\n where 
    # \N represents the existing line-delim.
    
    def theRealHTML(self,topBlock,endBlock):
	# This is a serious one-time-only operation for the whole document.
	# Get user buy-in if it's more than half the document.
	doc = IMC.editWidget.document()
	topBlockNumber = topBlock.blockNumber()
	endBlockNumber = endBlock.blockNumber()
	if (doc.blockCount()/2) < (endBlockNumber - topBlockNumber) :
	    yn = pqMsgs.okCancelMsg(
	        QString(u"HTML Conversion is a big deal: OK?"),
	        QString(U"Inspect result carefully before saving; ^Z to undo")
	        )
	    if not yn : return
	# Parse the text into work units
	unitList = IMC.flowPanel.parseText(topBlock,endBlock)
	if 0 == len(unitList) :
	    return # all-blank? or perhaps an error like unbalanced markup
	# In order to have a single undo/redo operation we have to use a
	# single QTextCursor, namely this one:
	tc = IMC.editWidget.textCursor()
	tc.beginEditBlock() # start single undo/redo macro
	pqMsgs.startBar((endBlockNumber - topBlockNumber), "Converting markup to HTML")
	# keep track of the current markup code and allow nesting
	markupCode = u' ' # state: open text; no markup active
	markStack = []
	qtb = QString(u'<tb>')
	qdiva = QString(u'<div')
	qdivz = QString(u'</div')
	# process units from last to first
	for u in reversed(range(len(unitList))):
	    unit = unitList[u]
	    unitBlockA = doc.findBlockByNumber(unit['A'])
	    unitBlockZ = unitBlockA if unit['A'] == unit['Z'] \
	                    else doc.findBlockByNumber(unit['Z'])
	    if 0x0 == (unit['A'] & 0x0f) :
		pqMsgs.rollBar(endBlockNumber - unit['A'])
	    if unit['T'] == 'P' :
		# This is a paragraph (or line) of text (i.e. not markup)
		# Select bookend strings based on the current markup context.
		bA = bookendA[markupCode]
		bZ = bookendZ[markupCode]
		if bA is not None:
		    # not in * or C or T or X, so collecting paragraphs. However,
		    # this could be a <tb> by itself, valid in these contexts.
		    if unit['A'] == unit['Z'] \
		       and unitBlockA.text().startsWith(qtb) :
			# Convert <tb>: in other cases we insert markup, we do
			# not replace the text. To continue that pattern
			# we just insert bookends that provide an <hr> and also
			# comment out the <tb> but retain it.
			bA = u'<hr /> <!-- '
			bZ = U' -->'
		    elif markupCode == ' ': # or, if len(markStack)==0
			# this is open text, check for headers
			if (unit['B'] == 2) and (u) and (unitList[u-1]['B'] != 4):
			    # two-line blank not at top of reflow selection and
			    # not following a head-2, make a head-3
			    bA = bookendA['3']
			    bZ = bookendZ['3']
			if unit['B'] == 4 : # four-line blank, make head-2
			    bA = bookendA['2']
			    bZ = bookendZ['2']
		    elif markupCode == 'P':
			# line of poetry, bA is <span class="i{0:02d}">
			# we have to, one, modify bA for the indent,
			F = int((unit['F']-2)/2) # number of nominal ems
			if F : # some nonzero indent dd
			    bA = bA.format(F) # class="idd"
			else : # no indent, default span
			    bA = u'<span>'
			# Then, two, look for a stanza break preceding this line
			if unit['B'] > 0: # some blank lines preceded
			    bA = u'</div><div class="stanza">\u2029' + bA
			# And, three, look for a poem line number and wrap
			# it in <span class='linenum'>..<span>. Note this is
			# the only place we have to actually modify the text.
			if not unit['K'].isEmpty() :
			    tc.setPosition(unitBlockZ.position()+unitBlockZ.length()-1)
			    tc.insertText(bookendLZ)
			    tc.setPosition(
    unitBlockZ.position()+unitBlockZ.length()-(1+len(bookendLZ)+unit['K'].size())
			                           )
			    tc.insertText(bookendLA)
		    bA = QString(bA)
		    # Minimal check for user error of re-marking, and 
		    # over-marking divs (spans are ok)
		    if not unitBlockA.text().startsWith(bA) \
		    and not unitBlockA.text().startsWith(qdiva) \
		    and not unitBlockA.text().startsWith(qdivz) :
			bA.append(IMC.QtLineDelim)
			bZ = QString(bZ)
			bZ.append(IMC.QtLineDelim)
			# insert bookends from bottom up to not invalidate #A
			tc.setPosition(unitBlockZ.position()+unitBlockZ.length())
			tc.insertText(bZ)
			tc.setPosition(unitBlockA.position())
			tc.insertText(bA)
		# end of unit type P bookending all paras not in C/*/X markup    
	    elif unit['T'] == '/' :
		# this is an end-markup line such as Q/, so we are entering a
		# new markup. Push the current markup code and set the new.
		markStack.append(markupCode)
		markupCode = unit['M']
		# replace the markup line contents with the markup close HTML.
		# Note in ASCII we never look past the x/ so there can be
		# comments there, but for HTML we should wipe the whole line.
		mzs = QString(markupZ[markupCode])
		mzs.append(IMC.QtLineDelim)
		tc.setPosition(unitBlockA.position()+unitBlockA.length()) # click
		tc.setPosition(unitBlockA.position(),QTextCursor.KeepAnchor) # drag 
		tc.insertText(mzs)
		# Note unit at the bottom of a table markup
		if markupCode == 'T':
		    tableBottom = u
	    else : # unit['T'] = 'M' we would assert
		# this is a start-markup such as /Q or /T. If the latter, 
		# process it.
		if markupCode == 'T':
		    pqTable.tableHTML(tc,doc,unitList[u : tableBottom+1])
		    # pqTable writes its own <table> string
		else:
		    # Overwrite the markup line with the openmarkup HTML.
		    mza = QString(markupA[markupCode])
		    mza.append(IMC.QtLineDelim)
		    mza.prepend(IMC.QtLineDelim)
		    tc.setPosition(unitBlockA.position()+unitBlockA.length()) # click
		    tc.setPosition(unitBlockA.position(),QTextCursor.KeepAnchor) # drag 
		    tc.insertText(mza)
		# Exit this markup
		markupCode = markStack.pop()
        tc.endEditBlock() # close the single undo/redo macro
        pqMsgs.endBar() # wipe out the progress bar
    
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

    # ============= end of the class definition of flowPanel!! ========

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

# Opening and closing bookends for theRealHTML indexed by active markup code.
# These are Python strings rather than QStrings mainly so the P string
# can have a format code.
bookendA = {
            ' ':u'<p>',
            'Q':u'<p>',
            'R':u'<p>',
            'P':u'<span class="i{0:02d}">', # indent filled in
            'U':u'<li>',
            'T':None,
            'F':u'<p>',
            'X':None,
            'C':None,
            '*':None,
            '2':u'<h2>',
            '3':u'<h3>'
            }
bookendZ = {
            ' ':u'</p>',
            'Q':u'</p>',
            'R':u'</p>',
            'P':u'</span><br />',
            'U':u'</li>',
            'T':None,
            'F':u'</p>',
            'X':None,
            'C':None,
            '*':None,
            '2':u'</h2>',
            '3':u'</h3>'
            }
# bookend markup for poem line number
bookendLA = u"<span class='linenum'>"
bookendLZ = u"</span>"
# Similarly, markup open/close strings indexed by markup code letter
markupA = {
            ' ':None,
            'Q':u'<div class="blockquote">',
            'R':u'<div class="ralign">',
            'P':u'<div class="poetry"><div class="stanza">',
            'U':u'<ul>',
            'T':u'<table>',
            'F':u"<div class='footnotes'>",
            'X':u'<pre>',
            'C':u'<pre>',
            '*':u'<pre>'
            }
markupZ = {
            ' ':None,
            'Q':u'</div>',
            'R':u'</div>',
            'P':u'</div></div>',
            'U':u'</ul>',
            'T':u'</table>',
            'F':u'</div>',
            'X':u'</pre>',
            'C':u'</pre>',
            '*':u'</pre>'
            }

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
    import pqTable
    pqTable.IMC = IMC
    IMC.editWidget = QPlainTextEdit()
    IMC.editWidget.setFont(pqMsgs.getMonoFont())
    IMC.settings = QSettings()
    widj = flowPanel()
    IMC.flowPanel = widj
    MW = QMainWindow()
    MW.setCentralWidget(widj)
    pqMsgs.makeBarIn(MW.statusBar())
    MW.show()
    utqs = QString('''
/U
Edit Flow to skip /F..F/ in ascii reflow

Edit Flow to handle /F..F/ in html convert

U/

This lengthy quote is the unit-test document. It contains representative
samples of all the reflow markup types. This is a sample of an open paragraph
to be reflowed.

<tb>

The types of reflow markup are as follows, which is an example of a list. The list
for ascii reflow is exactly like a block quote with FLR of 2,4,4, which exdents
the first line. You can of course specify different FLR values. In HTML the
List section is converted to a <ul> markup.

The following are the markups that reflow by paragraphs, like open text but with
different margin values.

/U
Poetry markup is done with /P..P/. It allows FLR values with defaults coming
from the UI spinboxes.

Block quote is done with /Q..Q/. It takes FLR with defaults from the UI.

Lists are done with /U..U/.
U/

/Q F:8 L:6 R:12
The following markups are not reflowed by paragraphs, but rather are
treated as single lines.

/R
--David Hume, 1789
R/

Q/

/P F:2 R:10 L:8
Here are our thoughts, voyagers' thoughts,
Here not the land, firm land, alone appears, may then by them be said,
The sky o'erarches here, we feel the undulating deck beneath our feet,
We feel the long pulsation, ebb and flow of endless motion,
The tones of unseen mystery, the vague and vast suggestions of the briny world, the liquid-flowing syllables,  5
The perfume, the faint creaking of the cordage, the melancholy rhythm,
The boundless vista and the horizon far and dim are all here,
And this is ocean's poem.

Then falter not O book, fulfil your destiny,
You not a reminiscence of the land alone,   10
You too as a lone bark cleaving the ether, purpos'd I know not whither, yet ever full of faith,
Consort to every ship that sails, sail you!
Bear forth to them folded my love, (dear mariners, for you I fold it here in every leaf;)
Speed on my book! spread your white sails my little bark athwart the  imperious waves,
Chant on, sail on, bear o'er the boundless blue from me to every sea,      315
This song for mariners and all their ships.
P/

/X
-123456789-123456789-123456789-123456789-123456789-123456789-123456789-123|56789
X/

/T  single line table
Line numero uno   99.95
Deux Dos Due     165.56
T/

/T T(W:50) 2(A:R)  single line table width col 2 aligned right
Line numero uno   99.95
Deux Dos Due     165.56
T/

/TM T(W:60) 2(W:10 A:R) multiline table typical TOC
Introduction   1

Preface  5

This Is the Title of Chapter One    7

The Title of Chapter Two, in which
Doris Gets Her Offs.       25

Index   299
T/

/TM TABLE(TOP:'-' WIDTH:30 SIDE:'|') COL(B:'-' S:'|')
------------------------------------------
|cell | cell |  now si the time for all |
|one  | two  |  good parties to end     |
------------------------------------------
|row 2 cell | @ | some more exciting     |
|    @      | @ |  prose |
------------------------------------------
T/

/T T(W:30) 1(A:L) 2(A:C) 3(A:R)
@  @  @
T/

    ''')
    IMC.editWidget.setPlainText(utqs)
    IMC.mainWindow = widj
    IMC.editWidget.show()
    app.exec_()
