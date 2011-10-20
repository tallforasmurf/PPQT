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
           can be given in /#[first.left,right] markup

/P .. P/   Indent by 4 spaces, reflow on a single-line basis as poetry. We add
           support for /P[first.left,right] markup too

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
        self.poIndent[0] = self.makeSpin(2,60,12,u"poFirst")
        poiHBox.addWidget(self.poIndent[0],0)
        poiHBox.addWidget(QLabel("Left:"),0)
        self.poIndent[1] = self.makeSpin(2,35,2,u"poLeft")
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
        self.skipCeCheck = QCheckBox("Center /f..f/")
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
        self.itbosc = {'i':1,'b':0,'sc':2}
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
        self.itbosc['i'] = 0 if self.itCounts[0].isChecked() else \
            1 if self.itCounts[1].isChecked() else 2
        self.itbosc['b'] = 0 if self.boCounts[0].isChecked() else \
            1 if self.boCounts[1].isChecked() else 2
        self.itbosc['sc'] = 0 if self.scCounts[0].isChecked() else \
            1 if self.scCounts[1].isChecked() else 2

    def reflowSelection(self):
        tc = IMC.editWidget.textCursor()
        if tc.hasSelection():
            doc = IMC.editWidget.document()
            topBlock = doc.findBlock(tc.selectionStart())
            endBlock = doc.findBlock(tc.selectionEnd())
            self.theRealReflow(topBlock,endBlock)
        else:
            pqMsgs.warningMsg("No selection to reflow.")
    
    def reflowDocument(self):
        doc = IMC.editWidget.document()
        topBlock = doc.begin()
        endBlock = doc.findBlockByNumber(doc.blockCount()-1)
        self.theRealReflow(topBlock,endBlock)

    # FOR REFERENCE here are the actual data access items:
    # self.bqIndent[0/1/2].value() for First, left, right
    # self.poIndent[0/1/2].value() for Fold, left, right
    # self.nfLeftIndent.value()
    # self.ctrOn75.isChecked() versus self.ctrOnLongest.isChecked()
    # self.itCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.boCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.scCounts[0/1/2].isChecked() == 0, 1, as-is
    # self.skipPoCheck.isChecked()
    # self.skipBqCheck.isChecked()
    # self.skipNfCheck.isChecked()
    # self.skipCeCheck.isChecked()
    # self.skipTbCheck.isChecked()

    # The parameters here are the first QTextBlock (==logical line) to be
    # processed and the final block to be processed: 1st and last lines of a
    # selection or of the whole document. The process is two-pass.
    # In the first pass we make a list of units where each unit is a tuple,
    #  ( starting-block#, ending-block#, first-, left-, right-indent)
    # In pass 1 we reduce all issues such as block quote, poetry, no-flow,
    # and centering to just these 5 items. For a normal paragraph a tuple
    # might be (a, z, 0, 0 ,0). For a block quote, (a, z, 4, 4, 4). For a
    # line of poetry, (a, a, 4, 24, 4) where the first and only line
    # is indented 4 but if it folds to a second physical line it is indented 24.
    # For a 30-character line being centered on 75, (a, a, 19, 19, 0), where
    # the start at 19 will center it on column 34.
    # We only recognize reflow markers such as /P at the start of a paragraph,
    # hence the rule that the markers must be preceded by a blank line. (The
    # blank line after the closing marker is not essential.)
    # We allow arbitrarily nested reflow markers -- tho only /# /P P/ #/ is
    # expected or useful -- but the mechanism is the same for all so why not.
    # The current scan state is represented by these variables:
    # S : state is either: 1, looking for data, or 0, collecting data
    # Z : an endmark to watch for, e.g. "#/"
    # C : True when centering (effectively, Z=="C/") else False
    # P : True = reflow by paragraphs, False, by single lines as in Poetry
    # F, L, R: current first, left, right indents

    def theRealReflow(self,topBlock,endBlock):
        ulist = [] # list of unit tuples
        markupRE = QRegExp("^/(P|#|\*|C|X|L|\$)")
        topBlockNumber = topBlock.blockNumber()
        endBlockNumber = endBlock.blockNumber()
        pqMsgs.startBar(2 * (endBlockNumber - topBlockNumber), "Reflowing text")
        # establish normal starting state: collecting normal paragraphs
        (S, Z, C, P, F, L, R) = (True, None, False, True, 0,0,0 )
        stack = [] # pushdown stack of states
        tb = topBlock # current block (text line) in loop
        fbn = None # number of first block of reflow unit
        while True:
            tbn = tb.blockNumber()
            if 0 == (tbn & 0x3f) :
                pqMsgs.rollBar(tbn - topBlockNumber)
            qs = tb.text().trimmed() # careful, trims both back AND front
            if S : # looking for data
                if not qs.isEmpty(): # non-blank line: data? markup?
                    if 0 == markupRE.indexIn(qs): # markup.
                        M = markupRE.cap(1)
                        if M == "#" and (not self.skipBqCheck.isChecked()): # block quote
                            stack.append( (S, Z, C, P, F, L, R) )
                            # S is already True
                            Z = QString("#/")
                            C = False # not centering
                            P = True # collect paras
                            (F, L, R) = self.getIndents(self.bqIndent,qs,F,L,R)
                        elif M == "P" and (not self.skipPoCheck.isChecked()): # poetry
                            stack.append( (S, Z, C, P, F, L, R) )
                            # S is already True
                            Z = QString("P/")
                            P = False # collect single lines
                            C = False # not centering
                            (F, L, R) = self.getIndents(self.poIndent,qs,F,L,R)
                        elif M == "*" and (not self.skipNfCheck.isChecked()) : # noflow
                            stack.append( (S, Z, C, P, F, L, R) )
                            # S is already True
                            Z = QString("*/")
                            C = False # not centering
                            P = False # collect by lines
                            (F, L, R) = self.getIndents(self.nfLeftIndent,qs,F,F,0)
                        elif M == "C" and (not self.skipCeCheck.isChecked()): # center
                            stack.append( (S, Z, C, P, F, L, R) )
                            # S is already True
                            Z = QString("C/")
                            C = True # centering
                            P = False # by lines
                            F += 2 # minimum 2-space indent on centered
                            L = F
                            R = 0
                        else: # /$, /X, /L or we are skipping this markup
                            M.append("/") # make endmarkup eg $/
                            while tb.next() != endBlock:
                                tb = tb.next()
                                if tb.text().startsWith(M) : break                            
                    else: # text
                        if Z is not None and qs.startsWith(Z) :
                            # end of a markup and no para working
                            (S, Z, C, P, F, L, R) = stack.pop()
                        else:
                            if P : # collecting paragraphs
                                fbn = tbn # first line of a para
                                S = False # now collecting
                            else : # single-line mode, line is a unit
                                if not C : # /* or /P -- for these, the
                                    # leading spaces count! Add them to F.
                                    txt = unicode(tb.text()).rstrip()
                                    ldgspaces = len(txt) - qs.size()
                                    ulist.append( (tbn, tbn, F+ldgspaces, L, R) )
                                else: # Centering, only stripped len matters
                                    x = max(4,75-qs.size())/2
                                    ulist.append( (tbn, tbn, int(x), 0, 0) )
                else:
                    pass # blank line, keep looking
            else: # collecting lines of a para
                if qs.isEmpty() : # blank line, ends para
                    ulist.append( (fbn, tbn-1, F, L, R) )
                    S = True # now looking
                else : # non-blank line: more data? or end markup?
                    if (Z is not None) and qs.startsWith(Z):
                        # end of current markup
                        ulist.append( (fbn, tbn-1, F, L, R) )
                        (S, Z, C, P, F, L, R) = stack.pop()
            # bottom of repeat-until loop, check for end
            if tb == endBlock : # we have processed the last line to do
                break
            tb = tb.next()
        # and now for phase 2. ulist has all the paras and single lines
        # to be hacked. Work our way from end to top. The tokgen function
        # is a generator (co-routine) that returns the next token and its
        # effective length (counting i/b/sc markups as specified in the ui).
        doc = IMC.editWidget.document()
        tc = IMC.editWidget.textCursor()
        progress = endBlockNumber - topBlockNumber
        for u in reversed(range(len(ulist))):
            (fbn,lbn,F,L,R) = ulist[u]
            if 0 == (fbn & 0x1f) :
                pqMsgs.rollBar(progress + (endBlockNumber - fbn))
            # set up a text cursor that selects the text to be flowed
            ltb = doc.findBlockByNumber(lbn)
            tc.setPosition(ltb.position()+ltb.length())
            ftb = ltb if fbn == lbn else doc.findBlockByNumber(fbn)
            tc.setPosition(ftb.position(),QTextCursor.KeepAnchor)
            # make that visible in the edit window
            IMC.editWidget.setTextCursor(tc)
            # collect tokens from this cursor's selection and assemble
            # them in lines based on F, L, R.
            lbr = QString(u'\u2029')
            linelen = 75 - R
            limit = linelen
            spc1 = QString(u' ')
            spcL = QString(u' '*L)
            space = QString(u' '*F)
            flow = QString()
            for (tok,tl) in tokGen(tc,self.itbosc):
                flow.append(space)
                if (flow.size() + tl) <= limit :
                    flow.append(tok)
                    space = spc1
                else : # time to break
                    flow.append(lbr)
                    limit = flow.size() + linelen
                    flow.append(spcL)
                    flow.append(tok)
            # used up all the tokens, replace
            flow.append(lbr) # terminate the last line
            tc.insertText(flow)   
        pqMsgs.endBar()

    # subroutine of finding /# or /P markups. Get the F L R values for poetry
    # or block quote from one of two sources: either the list of three
    # spinboxes in the UI, or from the optional [ [f.] [l,] r ] syntax after
    # the markup. Guiguts started this, allowing /#[8.4,4] to mean, indent
    # first lines 8, others 4, right 4. We are allowing it on /P as well, just
    # because we can... Add the results to the existing f, l, r to allow for nesting.
    def getIndents(self,uiList,qs,F,L,R):
        paramRE = QRegExp("^/\S\s*\[(\d+\.)?(\d+,)?(\d+)\]")
        tempF = uiList[0].value()
        tempL = uiList[1].value()
        tempR = uiList[2].value()
        if 0 == paramRE.indexIn(qs) : # some params given
            t = paramRE.cap(1)
            if not t.isEmpty() : #t = nn.
                t.chop(1) # drop the .
                (tempF, b) = t.toInt()
            t = paramRE.cap(2)
            if not t.isEmpty() : # t = nn,
                t.chop(1) # drop the ,
                (tempR, b) = t.toInt()
            (tempL, b) = paramRE.cap(3).toInt()
        return (F+tempF, L+tempL, R+tempR)
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
# is a global function, not a method). Not that a multiline selection has
# \u2029 instead of \n, but it comes up as isSpace() anyway so we don't care.
ibsRE = QRegExp("^</?(i|b|sc)>",Qt.CaseInsensitive)
ltChar = QChar(u'<')

def tokGen(tc, itbosc):
    qs = tc.selectedText() # sadly we end up copying every paragraph.
    qs.append(QChar(u' ')) # ensure text ends in space for easier loop control
    i = 0
    while True: # one iteration per token returned
        # qs.at(qs.size()).isSpace() -> False
        while qs.at(i).isSpace():
            i += 1
        if i >= qs.size() : break # we're done
        tok = QString()
        ll = 0
        while not qs.at(i).isSpace():
            # since markup is < 1% of a doc, no point in applying the ibsRE
            # when it has no chance of matching:
            if qs.at(i) == ltChar :
                if 0 == ibsRE.indexIn(qs,i,QRegExp.CaretAtOffset):
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
    import sys
    from PyQt4.QtCore import (Qt,QFile,QIODevice,QTextStream,QSettings)
    from PyQt4.QtGui import (QApplication,QPlainTextEdit,QFileDialog)
    class tricorder():
        def __init__(self):
            pass
    app = QApplication(sys.argv) # create an app
    IMC = tricorder() # set up a fake IMC for unit test
    import pqMsgs
    pqMsgs.IMC = IMC
    IMC.editWidget = QPlainTextEdit()
    IMC.settings = QSettings()
    widj = flowPanel()
    widj.show()
    utname = QFileDialog.getOpenFileName(widj,
                "UNIT TEST DATA FOR FLOW", ".")
    utfile = QFile(utname)
    if not utfile.open(QIODevice.ReadOnly):
        raise IOError, unicode(utfile.errorString())
    utstream = QTextStream(utfile)
    utstream.setCodec("UTF-8")
    utqs = utstream.readAll()
    IMC.editWidget.setPlainText(utqs)
    IMC.mainWindow = widj
    IMC.editWidget.show()
    app.exec_()
