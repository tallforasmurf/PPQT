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
This rather complex module contains the code for the Reflow UI panel as
well as the code to actually perform ASCII reflow (except tables) and
HTML conversion (including tables). It is structured as follows.

class flowPanel implements the UI with its numerous buttons and spinners.
The class definition also contains the following members which could (maybe
should) be global rather than class members:

parseText scans the text and detects all markups, preparing a list
of work units, one per paragraph or formatted line. This list of work
units is used by theRealReflow to direct reflow, also by pqTable to
direct table reflow, and by theRealHTML to direct HMTL conversion.

theRealReflow controls the process of reflow of a selection or the document.
It calls parseText then converts each unit returned by the parser according
to its markup.

the RealHTML control the process of HTML conversion of a selection or document.
It calls parseText then wraps each returned unit in appropriate markup.

Down at the bottom, global gnuWrap performs optimal reformatting of a single
paragraph, using the Knuth algorithm as copied from the Gnu Core Utilities
"fmt" utility code.

In the pqTable module, tableReflow and tableHTML do ASCII and HTML conversion
of tables, based on the work units found by parseText.

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
        #            three spinboxes for first, left, right
        #      miscHBox
        #         txwGbox group box "Text widths"
        #            oplHBox
        #               one spinbox for optimal text line size
        #            mxlHbox
        #               one spinbox for max text line size
        #         ctrGBox group box "Center /C..C/ on:"
        #            ctrHBox
        #               radio buttons "Para max" "Longest line"
        #         nfiGbox group box "/*..*/ default indents"
        #            nfiHbox
        #               one spinbox for left
        #   bigHbox
        #      skipGbox group box "Do Not Reflow (skip):"
        #         skipVbox
        #            five checkboxes for Poetry, blockquote, center, no-flow, table
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
        #               two radio buttons doc, self
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
        # misc row with three groups
        miscHBox = QHBoxLayout()
        indentsVBox.addLayout(miscHBox)
        # Max and optimal para widths: two spinners
        txwGBox = QGroupBox("Text widths:")
        miscHBox.addWidget(txwGBox)
        txwHBox = QHBoxLayout() # row of two spinners
        mxlHBox = QHBoxLayout() # max width spinner box
        mxlHBox.addWidget(QLabel("Max:"),0)
        self.maxParaWidth = self.makeSpin(32,80,75,u"mxWidth")
        mxlHBox.addWidget(self.maxParaWidth,0)
        mxlHBox.addStretch(1)
        oplHBox = QHBoxLayout() # optimum width spinner box
        oplHBox.addWidget(QLabel("Opt:"),0)
        self.optParaWidth = self.makeSpin(32,80,72,u"optWidth")
        oplHBox.addWidget(self.optParaWidth,0)
        oplHBox.addStretch(1)
        txwHBox.addLayout(oplHBox,0)
        txwHBox.addLayout(mxlHBox,0)
        txwHBox.addStretch(1)
        txwGBox.setLayout(txwHBox)
        self.connect(self.maxParaWidth,SIGNAL("valueChanged(int)"),self.checkMaxWidth)
        # Center choice
        ctrGBox = QGroupBox("Center /C..C/ on:")
        miscHBox.addWidget(ctrGBox)
        ctrHBox = QHBoxLayout()
        ctrGBox.setLayout(ctrHBox)
        self.ctrOnDoc = QRadioButton("doc")
        self.ctrOnDoc.setChecked(True) # should get these from stgs
        ctrHBox.addWidget(self.ctrOnDoc,0)
        self.ctrOnSelf = QRadioButton("self")
        self.ctrOnSelf.setChecked(False)
        ctrHBox.addWidget(self.ctrOnSelf,0)
        ctrHBox.addStretch(1)
        bigHBox = QHBoxLayout()
        mainLayout.addLayout(bigHBox)
        # no-flow indent
        nfiGBox = QGroupBox("/*..*/ default indent:")
        miscHBox.addWidget(nfiGBox)
        nfiHBox = QHBoxLayout()
        nfiGBox.setLayout(nfiHBox)
        nfiHBox.addWidget(QLabel("Left:"),0)
        self.nfLeftIndent = self.makeSpin(2,35,2,u"nfLeft")
        nfiHBox.addWidget(self.nfLeftIndent,0)
        nfiHBox.addStretch(1)
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
        self.skipIsChecked = {'P':self.skipPoCheck.isChecked,
                              'Q':self.skipBqCheck.isChecked,
                              'C':self.skipCeCheck.isChecked,
                              '*':self.skipNfCheck.isChecked,
                              'T':self.skipTbCheck.isChecked,
                              'R':lambda : False,
                              'X':lambda : False,
                              'U':lambda : False,
                              'F':lambda : False }
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

    # This slot gets called on any change to the max para width spinbox,
    # and just makes sure that the optimal box never is greater.
    def checkMaxWidth(self,i):
        if i < self.optParaWidth.value() :
            self.optParaWidth.setValue(i)

    # FOR REFERENCE here are the actual data access items in the UI:
    # self.bqIndent[0/1/2].value() for first, left, right
    # self.poIndent[0/1/2].value() for first, left, right
    # self.maxParaWidth.value() for paragraph wrap max & default table width
    # self.optParaWidth.value() for paragraph wrap
    # self.nfLeftIndent.value()
    # self.ctrOnDoc.isChecked() versus self.ctrOnSelf.isChecked()
    # self.itCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.boCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.scCounts[0/1/2].isChecked() == 0, 1, as-is
    # -- the above 3 are also available as self.itbosc['b'/'i'/'sc']
    # The following are set by the user to skip different kinds of markup:
    # self.skipPoCheck.isChecked()
    # self.skipBqCheck.isChecked()
    # self.skipNfCheck.isChecked()
    # self.skipCeCheck.isChecked()
    # self.skipTbCheck.isChecked()
    # For ease of access, the self.skipIsChecked dict contains references
    # to the .isChecked member of each keyed by the markup code letter.

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

    '''
ASCII reflow means arranging the text of each paragraph to fit in a limited
line width, usually 72 characters. Complicating this are the special markups
pioneered by Guiguts and supported here with somewhat different syntax:

/Q .. Q/   Reflow within block-quote margins, with default margins from the
           control on the panel but which can be set using /Q F:nn L:nn R:nn
	   in the opening markup line.

/U .. U/   Unsigned list, treated identically to /Q F:2 L:4 but allows
           explicit F:nn L:nn R:nn options as well.

/* .. */   Do not reflow, but indent by a settable default amount, or
           by specific amount specified in L:nn on the first line.

/P .. P/   Indent by 2 spaces, reflow on a single-line basis as poetry. Default
           margins from the controls, but allows F:nn L:nn R:nn override.

/C .. C/   Do not reflow but center each line. Typically used for title pages
           and the like. Indent the whole by 2 spaces minimum; center each line
	   on col 36 by default, but optionally on the center of the longest
	   line, minimizing the width.

/X .. X/   Do not reflow, do not indent.

/R .. R/   Right-aligned text, convenient for signatures and letterheads.

/T .. T/   Single-line table markup

/TM .. T/  Multi-line table markup. These allow more complex table options
           which are documented in pqTable.

The reflow markups are always left in place, ensuring that reflow can be
done multiple times.

The general algorithm of reflow is two-pass. On the first pass we examine the
document (or selection, no difference) line-by-line from top to bottom. In this
pass we identify each reflow unit, that is, each block of text to be treated.
In open text, /Q, and /U, a unit is a paragraph delimited by blank lines.
In other markups a unit is a single non-empty line. Empty lines are counted
but otherwise ignored.

For each unit we note several items: the first and last text block numbers;
the first-line indent, left indent, and right indent on the maximum line, and
the count of blank lines preceding. The indents of course depend on
the type of markup we are in at that point. All these decisions are made on
the first pass and recorded in a list of dicts, one for each unit.

The second pass operates on the units, working from the bottom of the
document or selection, up. This is so changes in the text will not alter
the block numbers of text still to be done. For each unit we pull tokens from
the unit text and form a new text as a QString with the specified indents.
Then we insert the reflowed text string to replace the original line(s).
All updates are done with one QTextCursor set up for a single undo "macro".

The reflow work unit produced by parseText below is a dict with these members:
    'T' : type of work unit, specifically
        'P' paragraph or line to reflow within margins F, L, R
        'M' markup of type noted next begins with this line
        '/' markup of type noted next ends with this line
    'M' : the type of markup starting, in effect, or ending:
        ' ' no active markup, open text
        'Q' block quote
        'F' like Q but zero indents
        'P' poetry
        '*' no-reflow but indent as per UI
        'C' no-reflow but center as per UI
        'X' no-reflow and leave alone
        'U' unordered list by paragraphs
        'R' right-aligned by lines
        'T' single or multiline table
    'A' : text block number of start of the unit
    'Z' : text block number of end of the unit
    'F', 'L', 'R': the desired First, Left and Right margins for this unit,
    'W' : in start of markup ('T'='M'), the max par width for reference mainly
        in the table module; in a paragraph ('T'='P'), the smallest actual indent
	thus far seen in the unit; in end of markup ('T'='/') the smallest indent
	seen in the unit. Lines of a * or P markup, or C markup with "center on
	doc" checked, are indented by F-W (which may be negative) thus removing
	any existing indent installed from a previous reflow.
    'K' : in a line of a poem ('T':'P' && 'M':'P'), an empty QString or
	the poem line number as a QString of decimal digits.
    'B' : the count of blank lines that preceded this unit, used in Table
	to detect row divisions, and in HTML conversion to detect chapter heads
        or Poetry stanza breaks.
    '''

    def theRealReflow(self,topBlock,endBlock):
        global optimalWrap
        # Parse the text into work units
        unitList = self.parseText(topBlock,endBlock)
        if 0 == len(unitList) :
            return # all-blank? or perhaps an error like unbalanced markup
        # Now do the actual reflowing. unitList has all the paras and single
        # lines to be hacked. Work from end to top.
        doc = IMC.editWidget.document()
        # In order to have a single undo/redo operation we have to use a
        # single QTextCursor, which is this one:
        tc = QTextCursor(IMC.editWidget.textCursor())
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
                    tableBottomIndex = u # note bottom extent of a Table section
                continue
            if unit['T'] == u'M' :
                # start of markup, which we see last in our backward scan
                if markupCode == u'T' :
                    # top of a table section; pass the table work units to
                    # pqTable.tableReflow, which will do the needful.
                    pqTable.tableReflow(tc,doc,unitList[u:tableBottomIndex+1])
                # Whatever type, emerge from this markup block
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
                # line of /X which we skip, or /T which we defer
                continue # don't touch it
            if (markupCode == u'*') or (markupCode == u'C') or (markupCode == u'R') :
                # For lines in /*, /C and /R, just adjust the leading spaces.
                # F is how many spaces this line has (/*) or needs (/C, /R).
                indentAmount = unit['F']
                if markupCode == u'*' or \
                   (markupCode == u'C' and self.ctrOnSelf.isChecked()) :
                    # reduce that to bring the longest line to the proper
                    # left margin, typically 2 but could be nested deeper.
                    indentAmount = unit['F'] - leastIndent + unit['L']
                # Click and drag to select the whole line, "dragging" right to left
                # so as to work with markPageBreaks below. Note blockA.lenth()
                # includes the linedelim at the end of the line.
                blockA = doc.findBlockByNumber(blockNumberA)
                tc.setPosition(blockA.position()+blockA.length()) # click..
                tc.setPosition(blockA.position(),QTextCursor.KeepAnchor) # ..and draaaag
                # get the selected text as a QString and mark it up for
                # page breaks. 98% of the time, listOfBreaks will be []
                flowText = tc.selectedText()
                listOfBreaks = markPageBreaks(tc,flowText)
                # strip leading and trailing spaces, and prepend the number
                # of spaces the line ought to have, and add a newline
                flowText = flowText.trimmed()
                flowText = flowText.prepend(QString(u' '*indentAmount))
                flowText = flowText.append(IMC.QtLineDelim)
                # Remove any pagebreak marker and note correct pagebreak positions
                unmarkPageBreaks(tc,flowText,listOfBreaks)
                # put the text back in the document replacing the existing line,
                # this horks any pagebreak cursor that fell in that line.
                tc.insertText(flowText)
                # Fix up a page break cursor.
                fixPageBreaks(listOfBreaks)
                continue # and that's that for this unit
            # This unit describes a paragraph of one or more lines to reflow.
            # This includes paras of open text, /Q, and /U, and lines of /P.
            # set up a text cursor that selects the text to be flowed: First,
            # set the virtual insertion point after the end of the last line,
            blockZ = doc.findBlockByNumber(blockNumberZ)
            block_len = blockZ.length() - (0 if blockZ != doc.lastBlock() else 1)
            tc.setPosition(blockZ.position() + block_len)
            # then drag to select up to the beginning of the first line.
            # Note the result of this is that tc.position < tc.anchor.
            blockA = blockZ if blockNumberA == blockNumberZ \
                else doc.findBlockByNumber(blockNumberA)
            tc.setPosition(blockA.position(),QTextCursor.KeepAnchor)
            if markupCode == u'P' :
                # pull Poetry lines back out if they were previously indented
                # for example if they had previously been reflowed
                unit['F'] = max(0, unit['F'] - leastIndent)
                unit['L'] = max(0, unit['L'] - leastIndent)
            # At this point the text to be flowed is defined by tc.position()
            # and tc.anchor. Get a QString view of that text.
            flowText = tc.selectedText()
            # Record the indices of any page break cursors that point within
            # that text, and insert ZWNJ characters at the breaks.
            # This is moved out of line for readability and for access from pqTable.
            listOfBreaks = markPageBreaks(tc,flowText)
            # Optimal paragraph wrap is quite lengthy, I'm pulling the code
            # out of line for readability.
            flowText = optimalWrap(flowText,unit,
                                   self.optParaWidth.value(),
                                   self.maxParaWidth.value(),
                                   self.itbosc)
            # flowText now has all the tokens of this paragraph or line,
            # including a poem line number if present, appropriately divided
            # by space and linebreak characters. It may have ZWNJ page break marks.
            # Now remove those ZWNJs and update the listOfBreaks with new positions.
            unmarkPageBreaks(tc,flowText,listOfBreaks)
            # Insert the modified text into the document. This horks the pageTable
            # cursors but we will repair them.
            tc.insertText(flowText) # replace selection with reflowed text
            fixPageBreaks(listOfBreaks)
        # end of "for u in reversed range of unitList" loop
        # Clear the progress bar from the status area
        pqMsgs.endBar()
        # Close the single undo/redo macro
        tc.endEditBlock()
        # Reposition the document cursor at the top of the reflowed section,
        # because otherwise on reflow document it ends up in the weeds at the end.
        IMC.editWidget.textCursor().setPosition(topBlock.position())
        # and that's reflow, folks.

    # This is the text parser used by theRealReflow and theRealHTML.
    # Parse a span of text lines into work units, as documented above.
    # We keep track of the parsing state in a record called PSW (a nostalgic
    # reference to the IBM 360), a dict with these members:
    # S : scanning: True, looking for a para, or False, collecting a para
    # Z : None, or a QString of the end of the current markup, e.g. 'P/'
    # M : the code of this markup e.g. u'Q'
    # P : True = reflow by paragraphs, False, by single lines as in /P, /*, etc.
    # F, L, R: current first, left, right indents
    # W, shortest existing indent seen in a no-reflow section
    # B, count of blank lines skipped ahead of this line/para
    # K, poem line number when seen
    # Most of these status items get copied into the work units we produce.
    #
    # We permit nesting markups pretty much arbitrarily (nothing can nest
    # inside /X or /T however). In truth only the nest of /P or /R inside
    # /Q block quote is really likely. To keep track of nesting we push the
    # PSW onto a stack when entering a markup, and pop it on exit.
    def parseText(self,topBlock,endBlock):
        unitList = []
        PSW = {'S': True, 'Z':None, 'M':' ', 'P':True, 'F':0, 'L':0, 'R':0, 'W':72, 'B':0}
        PSW['W'] = self.maxParaWidth.value()
        stack = []
        # We recognize the start of markup with this RE
        markupRE = QRegExp(u'^/(P|Q|\\*|C|X|F|U|R|T)')
        # We recognize a poem line number with this RE: at least 2 spaces,
        # then decimal digits followed by the end of the line. Note: because
        # we apply to a line as qstring we can use the $ for end of line. We
        # capture any trailing spaces (not \s which would catch \n as well)
        # so that the HTML conversion gets the right length calculation.
        poemNumberRE = QRegExp(u' {2,}(\d+ *)$')
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
            if PSW['S'] : # state of not in a paragraph, scanning for work.
                if qs.trimmed().isEmpty() :
                    # another blank line, just count it
                    PSW['B'] += 1
                else:
                    # We are looking for work and we found a non-empty line!
                    # But: is it text, or a markup?
                    if 0 == markupRE.indexIn(qs):
                        # We have found a markup! Save our current state.
                        # Note that PSW['S'] is True and stays that way
                        stack.append(PSW.copy())
                        # Note the markup type and prepare its end-flag compare value.
                        PSW['M'] = unicode(markupRE.cap(1)) # u'Q', 'P', 'T' etc
                        PSW['Z'] = QString(PSW['M']+u'/') # endmark, 'Q/', 'P/' etc
                        if not self.skipIsChecked[PSW['M']]() :
                            # We are processing this type of markup
                            # make a start-markup work unit for this line
                            if PSW['M'] == u'Q' : # Enter a block quote section
                                PSW['P'] = True # collect paragraphs
                                self.getIndents(qs,PSW,self.bqIndent[0].value(),
                                                self.bqIndent[1].value(),
                                                self.bqIndent[2].value() )
                            elif PSW['M'] == u'U' : # Enter a list markup
                                PSW['P'] = True # collect by paragraphs
                                self.getIndents(qs,PSW,2,4,4)
                            elif PSW['M'] == u'P' : # Enter a poetry section
                                PSW['P'] = False # collect by lines
                                self.getIndents(qs,PSW, self.poIndent[0].value(),
                                                self.poIndent[1].value(),
                                                self.poIndent[2].value() )
                                PSW['W'] = self.maxParaWidth.value() # initialize to find shortest indent
                            elif PSW['M'] == u'R' : # Enter a right-aligned section
                                PSW['P'] = False # collect by lines
                                self.getIndents(qs,PSW,0,0,0)
                            elif PSW['M'] == u'*' : # Enter a no-reflow indent section
                                PSW['P'] = False # collect by lines
                                self.getIndents(qs,PSW,0,self.nfLeftIndent.value(),0)
                                PSW['W'] = self.maxParaWidth.value() # initialize to find shortest indent
                            elif PSW['M'] == u'C' : # Enter a centering section
                                PSW['P'] = False # collect by lines
                                self.getIndents(qs,PSW,2,2,0)
                                PSW['W'] = self.maxParaWidth.value() # initialize to find shortest indent
                            elif PSW['M'] == u'X' : # Enter a no-reflow no-indent section
                                PSW['P'] = False # collect by lines
                                PSW['F'] = 0 # use zero margins
                                PSW['L'] = 0
                                PSW['R'] = 0
                            elif PSW['M'] == u'T' : # start a table section /T or /TM
                                PSW['P'] = False # collect by lines
                                PSW['L'] += 2 # table indent of 2 over current L
                                PSW['W'] = self.maxParaWidth.value() # save line width
                            else : # assert PSW['M'] == u'F'  # Enter footnote section
                                PSW['P'] = True # collect paragraphs
                                PSW['F'] = 0 # with 0 margins
                                PSW['L'] = 0
                                PSW['R'] = 0
                                # don't care about W
                            unitList.append(self.makeUnit('M',PSW,thisBlockNumber,thisBlockNumber))
                            PSW['B'] = 0 # clear the blank-line-before count
                        else : # markup of this type is to be skipped: consume lines
                            # until we see the end of the section, then pop the stack.
                            # Should we not see the closing mark the stack will be
                            # unbalanced and an error will be issued.
                            while thisBlock.next() != endBlock:
                                thisBlock = thisBlock.next()
                                if thisBlock.text().startsWith(PSW['Z']) :
                                    PSW = stack.pop()
                                    PSW['B'] = 0
                                    break
                    # markupRE did not see a match, so not starting a markup.
                    # Perhaps we are ending one?
                    elif PSW['Z'] is not None and qs.startsWith(PSW['Z']):
                        # we have found end of markup with no paragraph working
                        # document it with an end-markup unit
                        unitList.append(self.makeUnit('/',PSW,thisBlockNumber,thisBlockNumber))
                        # and return to what we were doing before the markup
                        PSW = stack.pop()
                        PSW['B'] = 0
                    else:
                        # Neither open nor close markup, so: a paragraph
                        if PSW['P'] :
                            # collecting by paras, note start of one
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
                                lineIndent = ( self.maxParaWidth.value()-len(lineText.strip()) ) /2
                                lineIndent = int( max(2, lineIndent) )
                                u['F'] = lineIndent
                            elif PSW['M'] == u'R' :
                                # calculate indent for right-aligned line
                                lineIndent = max(0, (self.maxParaWidth.value()-len(lineText.strip()))-PSW['R'])
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
            else: # PSW['S'] is false, ergo we are collecting lines of a
                # paragraph. Is this line empty (ending a para)?
                # The .trimmed method strips leading and trailing whitespace,
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
                        # we have found the end of the current markup with a
                        # paragraph in progress. Add a work unit for the
                        # paragraph we are in...
                        unitList.append(
                            self.makeUnit('P',PSW,firstBlockNumber,thisBlockNumber-1))
                        # ..and put in a work unit for the end of the markup
                        unitList.append(self.makeUnit('/',PSW,thisBlockNumber,thisBlockNumber) )
                        # ..and return to what we were doing before the markup
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

    '''
    Do HTML conversion. Use the textParse method to make a list of units.
    Process the list of units from bottom up, replacing as we go. Unlike reflow
    where the markup codes are retained to use again, here we replace the codes
    with HTML markup as follows:
    /Q   -->   <div class='blockquote'>
    Q/   -->   </div>
    /R   -->   <div class='ralign'>
    R/   -->   </div>
    /U   -->   <ul>
    U/   -->   </ul>
    /P   -->   <div class='poem'><div class='stanza'>
    P/   -->   </div></div>
    /T, /TM -->  <table>
    T/   -->   </table>
    /F  -->  <div class='footnotes'>
    F/  -->  </div>
    /*, /X, /C  --> <pre>
    */, X/, C/  --> </pre>
    <tb> --> <hr /> (no classname, so set your CSS for this as default case)

    We "enter" a markup at its end (Q/, T/, etc) and on entering push the
    prior markup type. WITHIN a markup we insert bookend texts around each
    work unit (paragraph or line) based on the active markup:
    /Q, /R, /F and open code: <p> and </p>
    /U : <li> and </li>
    /P : <span class="iX"> and </span><br /> where "iX" is based on F-W
    /*, /X, /C, and /T -- None
    On seeing T/ we note the unit number ending the table; on /T[M] we pass
    the slice of table units from /T to T/ to pqTable.tableHTML.
    The B (preceding blank lines) value of a work unit is used as follows:
    With poetry, B>0 means inserting </div><div class='stanza'>
    In open text, B==4 means using <h2> and </h2> as paragraph bookends;
    but B==2 when the next-higher unit has B!=4 means use <h3> and </h3>
    The bookend strings are globals, see below.

    Note on inserting bookends and other markup: QTextBlock.length() does
    include the line-delim at the end of the block. We include our own
    line-delim inserting bookendA, so <p>, <li> etc go on a line alone,
    and also on bookendZ, which goes after the existing line-delim and
    gets one of its own as well, thus <p>\\n ... text \\N</p>\\n where
    \\N represents the existing line-delim.
    '''
    def theRealHTML(self,topBlock,endBlock):
        # This being a serious one-time-only operation, get user authorization
        # for more than a page worth of data.
        doc = IMC.editWidget.document()
        topBlockNumber = topBlock.blockNumber()
        endBlockNumber = endBlock.blockNumber()
        if (endBlockNumber - topBlockNumber) > 50 :
            yn = pqMsgs.okCancelMsg(
                QString(u"HTML Conversion is a big deal: OK?"),
                QString(U"Inspect result carefully before saving; ^Z to undo")
            )
            if not yn : return
        # Parse the text into work units
        unitList = self.parseText(topBlock,endBlock)
        if 0 == len(unitList) :
            return # all-blank? or perhaps an error like unbalanced markup
        # Pre-parse the work unit list from the top down in order to identify
        # Chapters and Subheads. For Chapter heads we adopt the same rule as
        # Guiguts, which is different from the PGDP Formatting Guidelines:
        # a Chapter Title is a paragraph of one or more adjacent lines,
        # preceded by 4 empty lines and followed by at least 1 empty line.
        # A Subhead is preceded by 2 blank lines and followed by 1, and does not
        # immediately follow a Chapter head. This avoids the ambiguity implicit
        # in the Formatting Guidelines definition; however, it also means you
        # cannot code a Subhead immediately following a Chapter title. Something
        # else has to come between them, or fix it by hand later.
        #
        # Run through the work list and implement the above rules by changing
        # the 'M' of ' ' to a '2' or a '3' for Chapter and Subhead.
        final_unit_index = len(unitList)-1 # index of last unit
        u = 0 # gotta do old-fashioned loop control, bleagh
        m = 0 # markup depth
        while u <= final_unit_index :
            unit = unitList[u]
            if (m == 0) and (unit['T'] == 'P') :
                # paragraph in open text (not in markup)
                if unit['B'] == 4 :
                    # Starting a chapter
                    unit['M'] = '2' # poof, you're a chapter title paragraph
                elif (unit['B'] == 2) and (u > 0) and (unitList[u-1]['M'] != '2') :
                    # para w/ 2 blank lines before, not following a chapter,
                    unit['M'] = '3' # is a subhead
                else :
                    # unit not properly spaced for chapter or subhead, leave alone.
                    pass
            else:
                # starting, or continuing inside, a markup
                if unit['T'] == 'M' :
                    m += 1 # entering a markup, skip until out of it
                if unit['T'] == '/' :
                    m -= 1 # exiting a markup, maybe start checking again
            u += 1

        # In order to have a single undo/redo operation we have to use a
        # single QTextCursor, namely this one:
        tc = QTextCursor(IMC.editWidget.textCursor())
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
                # Which for open text is a <p>..</p>.
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
                    elif unit['M'] == '3' :
                        # Paragraph marked as subhead in initial scan
                        bA = bookendA['3']
                        bZ = bookendZ['3']
                    elif unit['M'] == '2' :
                        # Paragraph marked as single-unit chapter head
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
                    if not (bA.size() and unitBlockA.text().startsWith(bA) ) \
                       and not unitBlockA.text().startsWith(qdiva) \
                       and not unitBlockA.text().startsWith(qdivz) :
                        bA.append(IMC.QtLineDelim)
                        bZ = QString(bZ)
                        bZ.append(IMC.QtLineDelim)
                        # insert bookends from bottom up to not invalidate #A
                        block_len = unitBlockZ.length() - (0 if unitBlockZ != doc.lastBlock() else 1)
                        tc.setPosition(unitBlockZ.position() + block_len)
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
                block_len = unitBlockA.length() - (0 if unitBlockA != doc.lastBlock() else 1)
                tc.setPosition(unitBlockA.position() + block_len) # click
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
                    #print('tc {0}:{1} gets {2}'.format(
                    #    tc.position(), tc.anchor(), markupA[markupCode] ) )
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
        stgs.setValue("mxWidth",self.maxParaWidth.value() )
        stgs.setValue("optWidth",self.optParaWidth.value() )
        stgs.endGroup()

    # ============= end of the class definition of flowPanel!! ========

# Opening and closing bookends for theRealHTML indexed by active markup code.
# These are Python strings rather than QStrings mainly so the P string
# can have a format code. They are out here global just for neatness.
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
    'P':u'<div class="poem"><div class="stanza">',
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

# These subroutines of theRealReflow are out of line for readability.

# markPageBreaks receives a cursor and a qstring copy of its selection.
# For this we assume that the selection was made by "dragging" left to right,
# i.e. tc.position < tc.anchor.
# Find any page-break cursor in IMC.pageTable whose position is >= tc.position
# and < tc.anchor. Create and return a list of those breaks in the form
# [ [i,p]...] where i is the pageTable index and p its current position.
# Also, inject \u200C ZWNJ at the position of each pagebreak.

def markPageBreaks(tc,ft):
    pbl = []
    A = tc.position()
    Z = tc.anchor()
    # Use bisect-right to find the highest page table entry <= Z
    # (ToDo: we could optimize this based on the knowledge that reflow works
    # backward through the document and just do a sequential search back
    # from the last-noted page break, saving the full search for the initial call.)
    # (OTOH in a 500pp book the below loops at most 8 times. So K.I.S.S.)
    hi = IMC.pageTable.size()
    lo = 0
    while lo < hi:
        mid = (lo + hi)//2
        if Z < IMC.pageTable.getCursor(mid).position(): hi = mid
        else: lo = mid+1
    # the pagebreak cursor at lo-1 is the greatest <= Z. If it is also
    # >A then we need to note it and maybe the one(s) preceding it.
    while True :
        lo -= 1
        if lo < 0 :
            break # second or later iteration (on first, if pageTable is empty)
        P = IMC.pageTable.getCursor(lo).position()
        if P < A :
            break # will often happen on first iteration
        pbl.append([lo,P])
        ft.insert(P-A, IMC.ZWNJ)
    return pbl

# unmarkPageBreaks receives the original cursor, whose position is the base
# offset of the text, the reflowed text string, and the list prepared
# by markPageBreaks. It finds and delete the ZWNJs, and updates the position
# values in the pagebreak list.

def unmarkPageBreaks(tc,ft,pbl):
    P = tc.position() # base offset of the text
    for i in reversed(range(len(pbl))) :
        j = ft.indexOf(IMC.ZWNJ)
        pbl[i][1] = P + j
        ft.remove(j,1)

# fixPageBreaks takes a list of pageTable indices and new position values
# and updates those cursors. Presumably text hs been changed that would
# invalidate those cursors, but if not, no harm done.

def fixPageBreaks(pbl):
    for [i,p] in pbl:
        IMC.pageTable.setPosition(i,p)

# tokGen is a generator function that returns the successive tokens from the
# text selected by a text cursor. Each token is returned as a tuple, (tok,tl)
# where tok is a QString and tl is its logical length, which may be less than
# tok.size() when tok contains <i/b/sc> markups.

# Unlike the tokenization in pqEdit, which is focussed on isolating
# "words" that can be spell-checked, a "token" for reflow purposes is a
# unit that should not be broken at end of line, nor should it have spaces
# gratuitously inserted. The following line has just one token!
#    <span class='foo'><sc><b><i lang='de_DE'>sprechen</i></b></sc></span>
# The obvious problems are: we want to give </?(i|b|sc)> their logical
# lengths (0, 1, or as-is from the Flow panel controls), and two, the
# spaces in "<span class" and "<i lang" mustn't break the token.

# The flowText input is almost always a multiline selection; it has
# \u2029 instead of \n, but the regexes treat that as \s, so we don't care.
# The Zero Width Non-Joiner, \u200C, may appear in a token to mark the
# position of a page-break. \u200C is a nonspace; however its logical width
# should be recorded as zero. Note it is possible to have 2 page breaks
# with nothing between, falling inside one paragraph.

# A token or part thereof consists of:
# * some contiguous non-space things that don't include '<'
#   -- which is a word, the overwhelmingly most common thing we see
re_word = '''([^<\s]+)'''
# * an HTML start tag
re_start_tag = '''(<(\w+)([^>]*)>)'''
# * an HTML end tag OR
re_end_tag = '''(</(\w+)>)'''
# * or a stupid "<" as part of the text.
re_less = '''(<)'''

reParts = QRegExp('|'.join([re_word,re_start_tag,re_end_tag,re_less]))
# When reParts hits on a start-tag, cap(3) is the tag.
# When it hits on an end-tag, cap(6) is the tag. Other matches,
# those captures are null.

def tokGen(flowText, itbosc):
    global reParts
    j = 0 # index of where to scan for next token-part
    j = reParts.indexIn(flowText,j) # find the first part
    while j >= 0 : # once around per token returned
        token = QString()
        tok_len = 0
        k = j # prime the inner loop for once around at least
        while k == j : # while finding adjacent parts
            part = QString(reParts.cap(0)) # copy the entire part
            part_len = part.size() # physical length of part
            k = j + part_len # index of next part, if adjacent
            tag = reParts.cap(3) # tag value of HTML start-tag
            if tag.isEmpty() : # not a start-tag
                tag = reParts.cap(6) # perhaps a close-tag?
            if not tag.isEmpty() : # an HTML tag, but is it i, b, or sc?
                adjust = 2 # assume as-is length
                if unicode(tag) in itbosc :
                    adjust = itbosc[unicode(tag)] # 0, 1, or 2==as-is
                if adjust < 2 :
                    part_len = adjust # treat the markup as size 0 or 1
            else: # not an <i/b/sc> element, so
                part_len -= part.count(IMC.ZWNJ) # deduct Zero-width-non-joiners
            token.append(part)
            tok_len += part_len
            j = reParts.indexIn(flowText, k)
        yield (token, tok_len)

# Optimal paragraph wrap. After considerable research, including reading
# the original Knuth&Plass paper (Software: Practice and Experience, 1981)
# and looking at several implementations in various languages online I finally
# found readable C code in the fmt utility in the Gnu Core Utilities. The
# following is a slavish copy of the fmt_paragraph() function in that.
#
# Input is the text cursor selecting the paragraph text and the itbosc dict,
# which get handed to tokGen (above). Also input is the optimal and max line
# lengths from the UI spinners, and the work unit from which we get the F/L/R
# values and, sometimes, a poem line number.
# This RE matches the last/only line of a poem with a line number.
poemLastLineRE = QRegExp(u'\u2029?(.+)( \d+)\u2029$')
def optimalWrap(flowText,unit,optimum,maximum,itbosc):
    global tokGen
    # Set up the "too much" cost factor
    SquareRootOfInfinity = 32767
    Infinity = SquareRootOfInfinity * SquareRootOfInfinity

    # In Gnu fmt, the paragraph is read into a list of structs but this can
    # be seen as a table, with each struct a row and its members, columns.
    # Here we make the same table using parallel lists. If reading the C code,
    # the "struct word" members map as follows:
    # const char *text -- T[j] as a QString from tokgen
    # int length       -- W[j] logical token length from tokgen
    # int line_length  -- L[j] length of line starting from here
    # COST best_cost   -- C[j] cost of line of length L[j]
    # WORD *next_break -- P[j] index of first T[j] of following line
    # Struct members space, paren, period, punct and final are not maintained.
    # Gnu fmt uses the convention that dot-space-space ends a sentence, so it
    # can distinguish sentence-ending periods from abbreviation periods. PG
    # does not use this convention (too bad!) so we can't detect end of a
    # sentence and accordingly the related cost calculations can't be done.

    T = []
    W = []
    grossLen = 0
    for (tok,ll) in tokGen(flowText,itbosc) :
        T.append(tok)
        W.append(ll)
        grossLen += ll
    N = len(T) # valid tokens are 0..N-1
    # Set up spacing: The line length is the allowed line size minus the
    # left- and right-indents if any.
    LOptimum = optimum - unit['L'] - unit['R']
    LMaximum = maximum - unit['L'] - unit['R']
    # firstIndentDiff is the difference between the first-line indent and the
    # other lines. The standard indent is accounted for in LOptimum/LMaximum
    # and implemented during output. The first line can be indented or exdented
    # relative to it, and this difference is set up in T[0] and W[0]
    firstIndentDiff = unit['F'] - unit['L']
    if (N == 1) or (LMaximum >= (grossLen + (N - 1) + unit['F'])) :
        # There is but one token (any length), or the sum of tokens fits in
        # the first line, so just put it all together now.
        flowText = QString(u' '*unit['F'])
        for tok in T :
            flowText.append(tok)
            flowText.append(QChar(u' '))
        flowText.append(IMC.QtLineDelim)
    else :
        # There is a need to split tokens across lines, using gnuWrap.
        W[0] += firstIndentDiff # W[0] could conceivably be 0 or negative - problem?
        C = (N+1)*[0] # the Costs column; C[N] is a sentinel
        W.append(maximum*2) # ..as is W[N] (recall, tokens are 0..N-1)
        P = (N+1)*[N] # the next-word link column
        L = (N+1)*[0] # The length-from-here column
        scanPtr = N-1 # start with last word, work backwards
        while True : # for (start = word_limit - 1; start >= word; start--)
            bestCost = Infinity
            testPtr = scanPtr
            currentLen = W[testPtr]
            while True : # do{...} while(len < maxwidth)
                testPtr += 1 # this goes to N on first iteration
                # "consider breaking before testPtr" : bringing line_cost() inline
                thisCost = 0
                if testPtr != N:
                    thisCost = LOptimum - currentLen
                    thisCost *= 10
                    thisCost = int(thisCost * thisCost)
                    if P[testPtr] != N :
                        n = (currentLen - L[testPtr])/2
                        thisCost += int(n * n)
                thisCost += C[testPtr]
                if thisCost < bestCost : # possible break point
                    bestCost = thisCost
                    P[scanPtr] = testPtr
                    L[scanPtr] = currentLen
                currentLen += 1 + W[testPtr] # picks up LMaximum when testPtr==N
                if currentLen >= LMaximum : break
            # end inner do-while
            # we don't try to implement base_cost() which penalizes short widows
            # and orphans, encourages breaks after sentences and right parens,
            # and so forth, all because we can't detect ends of sentences.
            C[scanPtr] = bestCost # + base_cost(scanPtr)
            if scanPtr == 0 : break # all done
            scanPtr -= 1
        # end main for-loop
        # prepare the output as a string of lines with proper indents.
        firstIndent = QString(u' '*unit['F'])
        leftIndent = QString(u' '*unit['L']) # left-indent space for lines 2-m
        oneSpace = QString(u' ') # one space between tokens
        flowText = QString()
        indent = firstIndent
        # Each line extends from T[a] to T[z-1]
        a = 0
        while True : # do until z == N
            spacer = indent
            z = P[a]
            while a < z :
                flowText.append(spacer)
                flowText.append(T[a])
                a += 1
                spacer = oneSpace
            flowText.append(IMC.QtLineDelim)
            indent = leftIndent
            if z == N : break
            a = z
    # At this point we have a single line or multiple lines in flowText.
    # If this is a line of poetry and if it had a line number at the end,
    # we need to insert spaces to slide that last token out. Typically poetry
    # lines don't get folded but it can happen, so we have to isolate the
    # last of what is probably only one line but might now be 2 or even more.
    if unit['M'] == u'P' and (not unit['K'].isEmpty()) :
        # there was a line number seen on this poem line. It will have been
        # token T[N-1] and is now at the end of the line with one space.
        # We need to insert spaces to right-justify the number against LMaximum
        # inserting at least 1 space so we can recognize it on another reflow.
        z = poemLastLineRE.indexIn(flowText) # assert z == 0
        # cap(1).size() is text preceding the number; cap(2).size() is the
        # size of the number and its preceding one space.
        a = poemLastLineRE.cap(1).size() # length of text preceding number
        z = poemLastLineRE.cap(2).size() # length of space+nnn
        available = LMaximum - a - z
        if available < 1 :
            # not room to put in space, space, line number
            pqMsgs.warningMsg(
                u'Poem line number overflows line length',
                u'Line number is' + unicode(poemLastLineRE.cap(2))
            )
            available = 1
        flowText.insert(flowText.size()-z-1, QString(u' '*available))

    return flowText

if __name__ == "__main__":
    import sys
    from PyQt4.QtCore import (Qt,QFile,QIODevice,QTextStream,QSettings)
    from PyQt4.QtGui import (QApplication,QPlainTextEdit,QFileDialog,QMainWindow)
    import pqIMC
    app = QApplication(sys.argv) # create an app
    IMC = pqIMC.tricorder() # set up a fake IMC for unit test
    IMC.fontFamily = QString("Courier")
    IMC.QtLineDelim = QChar(0x2029)
    import pqPages
    pqPages.IMC = IMC
    IMC.pageTable = pqPages.pagedb()
    import pqMsgs
    pqMsgs.IMC = IMC
    import pqTable
    pqTable.IMC = IMC
    IMC.editWidget = QPlainTextEdit()
    IMC.editWidget.setFont(pqMsgs.getMonoFont())
    IMC.settings = QSettings()
    widj = flowPanel()
    MW = QMainWindow()
    MW.setCentralWidget(widj)
    pqMsgs.makeBarIn(MW.statusBar())
    MW.show()
    utqs = QString('''



Chapter Goddam Head

Chapter goddam well continues

and more


First para of chapter


Subhead

Text after subhead

/C
a
little
centered section
C/

/*
                    starry
                    starry
    night
*/

/X
123456789-123456789-123456789-123456789-123456789-123456789-123456789-123|56789
X/

/Q F:8 L:6 R:12
The following markups are not reflowed by paragraphs, but rather are
treated as single lines.

/R
--David Hume, 1789
R/

Q/

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
123456789-123456789-123456789-123456789-123456789-123456789-123456789-123|56789
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

/F

F/''')
    IMC.editWidget.setPlainText(utqs)
    IMC.mainWindow = widj
    IMC.editWidget.show()
    app.exec_()