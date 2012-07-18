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
Implement the find/replace panel. The findPanel class constructor has
the very lengthy task of building and laying out the panel. (The initial
look was worked out using Qt Designer, but we implement the widgets and
layouts manually rather than using the designer's unreadable output.)

Widget Design for the Find UI

At the top of the pane is a row of five checkboxes for case, whole-word,
in-selection, regex, and greedy. Whole-word is ignored for regex (use \b\w+\b),
and greedy is ignored for non-regex.

Below the checkboxes is the Find lineEdit, which has syntax checking for regex
and turns pink when an invalid regex is being entered. Below that are four
buttons that trigger a search: Next Prior and First Last. Next/Prior initiate
a search beginning at the present edit cursor going forward/back.

First/Last are my original contribution to the editing field: other editors
have similar abilities but not presented this way. First initiates a search
from the top of the document (or selection), Last initiates one from the end
of the document (or selection). These also implement the in-selection switch;
the selection boundaries are only sampled and noted when First/Last is clicked.
This eliminates the uncertainty about "which selection" is meant. Once you use
First/Last, you can use Next/Prior and Replace freely within the bounds set
by First/Last. Also the presence of First/Last pretty well eliminates the need
for a wrap-mode switch or wrap-around search.

The five switches, find text, and four buttons comprise the find area. Below are
three Replace lineEdits and three checkboxes for replace behavior: &Next, &Prior
and ALL! &Next and &Prior cause a replace to be followed by search-forward or
backward respectively.

Despite the dramatic checkbox name ALL!, on a replace with ALL checked we first
search the whole document or selection and make a list of found cursors. Then we
pop up a confirmation query saying how many replacements will be done. This also
is original; most editors show you the count of replacments after the fact, not
before. Replace all is a single undo-redo event. See also note below.

Beside the Find lineEdit, and beside each Rep lineEdit, we have a combo box that
pops up a list of previous strings from most recent down. The find list is
updated on use of any search button. The Rep lists are updated on use of that
Rep. The lists of strings are saved in the settings on shutdown and
restored on startup.

Editor Keystrokes

The editor widget traps keyevents and when it sees the search special keys
it emits a signal and thereby passes the keyEvent to us here at editKeyEvent.
Supported search keys are:
    ctrl-f        Shift focus to the Find pane
    ctrl-shift-f  Load selection into Find text and focus in Find pane
    ctrl-g        Find next (of whatever is in the find lineEdit)
    ctrl-shift-g  Find previous (ditto)
    ctrl-=        Replace selection with Rep-1 text
    ctrl-t        Replace selection with Rep-1 and find next
    ctrl-shift-t  Replace selection with Rep-1 and find prior

n.b. I can't find any standard for Windows or Unix search keys, so these are
based on the Mac standard and BBEdit's.

User Buttons

Below the find and replace widgets we have an array of pushbuttons each
of which stores a single find/replace setup and loads it when pressed.
The button setups can be set by the user and are saved in the settings from
session to session. The buttons can also be saved to utf-8 text files and
reloaded later. A number of complex searches are distributed in the "extras"
folder for performing specific post-processing jobs. It is hoped that over
time, users will add more or better ones.

Each userButton stores the various find/replace widget values as a Python dict.
The dict for a button can be loaded from the present UI widgets by right-click;
a left-click dumps the values into the widgets. The format for a settings string
or for a button in a file is one __repr__ string of a python dict. When loading
a button, we have python compile the string and verify it is only a literal,
thus preventing any possible code-injection via this route.

Implementing Simple Find/Replace

To implement Find we access the editor's QTextDocument. For a non-regex find
we call the document's find() method. When this succeeds we change the editor's
cursor to select the match, so the user can see it. For non-regex replace,
we use the editor's cursor's textInsert() method to replace the current
selection with a string.

Implementing Regex Find/Replace

The target user population both understands and depends heavily on regex 
find/replace. Unfortunately to implement an adequate regex find we have to
work around a crippling restriction in the QTextDocument.find() method: it will
not search across a textblock (line) boundary! Hence it can never match to
a pattern of \n, or match text on either side of \n, and that kills all 
kinds of critical uses. The QTextDocument.find() also has the problem that it
takes the regex as a "const" argument, meaning it will never update the 
regex's captured-text values! The eliminates any chance of doing a Replace with
substitution of found substrings \1 etc.

The only way to do useful regex find is with a QRegExp.indexIn(QString) method,
and the only way to do regex replacement with substitution of \n is via a
QString.replace(QRegExp) method. So we kludge.

When the find is a regex, we get const access to the QTextDocument's content
within the search bounds in the form of a QString, and apply QRegExp.indexIn
(for Next) or QRegExp.lastIndexIn (for Prior). When the search succeeds we get
the bounds of the matched text and set the editor's cursor to select that.

For replacement when the find was a regex, we copy the current selected text
(which we ASSUME is the text that matched the same regex) -- out of the
editor as a QString; apply QString.replace(regex); and textInsert() the
altered text back.

This works great for most cases, but it introduces three serious issues. One,
in the edit document, there is no actual \n; end of line is \u2029, the Unicode
paragraph sep character. We do this substitution ('\u2029' in place of '\n')
invisibly on the user's regex pattern for find and also on the replace
pattern string, before we use them.

Two, doing search over a span of text as a single QString means that the ^ and
$ pattern assertions only match at the start and end of the find range, never
at a logical line-end. Effectively ^ and $ are useless. A partial workaround is
to use literal \n searches, but they don't match at the start/end of the
document! Conceivably we could invisibly replace '$' with '(?=\0x2029)',
a non-capturing lookahead, but (a) there would still be no equivalent for '^'
because Qt4 doesn't support lookbehind assertions, and (b) the user might
already have used a lookahead in the pattern and you can't have two.

Speaking of lookahead brings us to serious issue #3: when the search pattern
contains a lookahead at the end (very handy & useful), the text that matches
the lookahead expression is not included in the matched text which is then
selected in the editor. But on replace, if we re-apply the regex to only
the current selection, there will be no match, because the lookahead text
isn't there! The sign of the problem is that a search succeeds, but replacement
does nothing at all.

One fix tried is to extend the copied text a few extra characters beyond the
selection, so that IF the regex ends with a lookahead of reasonable length, it
will find a match when re-applied. This turns out to be a bad idea because
QString.replace(regex) replaces ALL matches, and a regex without a trailing
lookahead applied to an extended selection, can replace more than the original
match. Also there is no limit to the amount of text a lookahead could match,
so there would remain regexs that could hit this problem no matter how much
extra text is provided.

The kludge with the fewest gotchas is to copy the find regex and delete from
it any trailing lookahead before using it to do the replace. The regex sans
lookahead should still match to the text it matched with lookahead. It may
be possible to think of a regex that, without its lookahead, will find a
SHORTER match than it did with lookahead, but I can't think of one.

Qt 5 is supposed to offer much improved regex support with both lookahead and
lookbehind and the whole design will have to be revisited then. Possibly the
only answer will be to copy the whole goddam search range into Python and
use relib.

Replace ALL! Constraint

When searching to make a list of matches for replace-all we restart each
search immediately after the previous hit-string. This precludes overlapping
hits during replace-all, even though overlapping hits ARE possible when doing
manual replace with &Next set. The reason is that overlapping hits (a) could
be a black hole of recursion for certain regexes, and (b) would imply doing
overlapping replacements with probably very strange results.
'''


from urllib import (quote, unquote) # for safely encoding find/rep strings
import pqMsgs
import ast

from PyQt4.QtCore import (Qt,
    QChar, QRegExp,
    QString, QStringList,
    SIGNAL, SLOT )
from PyQt4.QtGui import(
    QCheckBox, QComboBox, QColor,
    QFont,
    QGridLayout, QHBoxLayout, QVBoxLayout,
    QLineEdit,
    QPalette,
    QPushButton,
    QSizePolicy, QSpacerItem,
    QTextCursor, QTextDocument,
    QUndoStack,
    QWidget )

UserButtonMax = 24 # how many user buttons to instantiate
UserButtonRow = 4 # how many to put in a row of the grid

class findPanel(QWidget):
    def __init__(self, parent=None):
        super(findPanel, self).__init__(parent)
        stgs = IMC.settings # from which we pull stuff
        stgs.beginGroup("Find") # all keys start with Find.
        # list of previous-string popups: [0] is Find, [1/2/3] is reps
        self.popups = [None,None,None,None]
        # list of rep lineEdits, [0] is none, [1/2/3] is reps - see class below
        self.repEdits = [None,None,None,None]
        # list of refs to the  created user buttons
        self.userButtons = []
        # where we keep the find regexp as it is being entered
        self.regexp = QRegExp()
        self.regexp.setPatternSyntax(QRegExp.RegExp2)
        # regex to search a regex pattern for a trailing lookahead
        self.lookAheadFinder = QRegExp(u'\(\?[\!\=][^)]+\)$')
        # Search boundary positions set on First/Last. Boundary has to be set
        # as a textcursor so it will update as document changes length.
        self.rangeTop = None
        self.rangeBot = None
        self.setFullRange() # sets to full document, which is null right now
        # Flags for when find or rep has been loaded from a user button (and
        # hence shouldn't be saved in the popup menu)
        self.userLoad = [False, False, False, False]
        # Create all subwidgets and lay them out:
        # Per the Qt doc, we need to create a layout and parent it, that is,
        # add it to its parent layout, before we populate it. So here we
        # create the layouts and parent them. They get local names and will
        # go out of scope when we exit but the chain of parent-child refs 
        # keeps them alive. The organization is:
        # mainLayout holds a vertical stack of:
        #   findCheckHbox (5 checkboxes)
        #   findEditHbox  (find popup and lineEdit)
        #   nextPriorHbox ( Next/Prior First/Last buttons)
        #   repHolderHbox holds
        #    repRowsVbox holds
        #        repRowHbox (three copies, rep popup and lineEdit)
        #        repChecksVbox (2 checkboxes)
        #   userButtonGrid
        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)
        # set up the top row of four checkboxes
        findCheckHbox = QHBoxLayout()
        mainLayout.addLayout(findCheckHbox,0)
        self.caseSwitch = QCheckBox(u"Respect &Case")
        self.wholeWordSwitch = QCheckBox(u"Whole &Word")
        self.inSelSwitch = QCheckBox(u"In &Sel'n")
        self.regexSwitch = QCheckBox(u"&Regex")
        self.greedySwitch = QCheckBox(u"&Greedy")
        findCheckHbox.addWidget(self.caseSwitch,0,Qt.AlignLeft)
        findCheckHbox.addWidget(self.wholeWordSwitch,0,Qt.AlignLeft)
        findCheckHbox.addWidget(self.inSelSwitch,0,Qt.AlignLeft)
        findCheckHbox.addWidget(self.regexSwitch,0,Qt.AlignLeft)
        findCheckHbox.addWidget(self.greedySwitch,0,Qt.AlignLeft)
        findCheckHbox.addStretch(1) # keep switches compact to the left
        # connect stateChanged of inSelSwitch to a slot to clear range
        self.connect(self.inSelSwitch, SIGNAL("stateChanged(int)"),
                     self.inSelChange)
        # make a horizontal row of a combobox and the find text lineEdit
        # the custom lineEdit and comboBox classes are defined below.
        findEditHbox = QHBoxLayout()
        mainLayout.addLayout(findEditHbox,0)
        self.findText = findRepEdit()
        self.repEdits[0] = self.findText
        self.popups[0] = recentStrings(self.findText,
                    stgs.value("findList",QStringList()).toStringList() )
        findEditHbox.addWidget(self.popups[0])
        findEditHbox.addWidget(self.findText)
        # Connect any type of find text alteration to the regex-syntax check
        # using the textChanged signal.
        self.connect(self.findText, SIGNAL("textChanged(QString)"),
                                     self.checkFindText )
        self.connect(self.regexSwitch, SIGNAL("stateChanged(int)"),
                                     self.checkFindText )
        # Connect user change in the find text to note a user change
        self.connect(self.findText, SIGNAL("textEdited(QString)"),
                                lambda : self.userEditedText(0) )
        # Make a horizontal row of the finding buttons
        nextPriorHbox = QHBoxLayout()
        mainLayout.addLayout(nextPriorHbox,0)
        self.nextButton = QPushButton(u"&Next")
        self.priorButton = QPushButton(u"&Prior")
        self.firstButton = QPushButton(u"Firs&t")
        self.lastButton = QPushButton(u"&Last")
        nextPriorHbox.addWidget(self.nextButton,0)
        nextPriorHbox.addWidget(self.priorButton,0)
        nextPriorHbox.addStretch(1) # keep n/p buttons left, f/l right
        nextPriorHbox.addWidget(self.firstButton,0)
        nextPriorHbox.addWidget(self.lastButton,0)
        # Connect four buttons to doSearch, passing 0-3 button number
        self.connect(self.nextButton, SIGNAL("clicked()"),
                                     lambda b=0: self.doSearch(b) )
        self.connect(self.priorButton, SIGNAL("clicked()"),
                                     lambda b=1: self.doSearch(b) )
        self.connect(self.firstButton, SIGNAL("clicked()"),
                                     lambda b=2: self.doSearch(b) )
        self.connect(self.lastButton, SIGNAL("clicked()"),
                                     lambda b=3: self.doSearch(b) )
        # Connect the returnPressed of find text to the click slot of 
        # the Next button - so return in the text looks for the next instance
        # of that text -- the natural expectation of the find box.
        self.connect(self.findText, SIGNAL("returnPressed()"),
                                self.nextButton, SLOT("click()") )
        # Set up the rep container layouts and parent them
        repHolderHbox = QHBoxLayout()
        mainLayout.addLayout(repHolderHbox,0)
        repRowsVbox = QVBoxLayout()
        repChecksVbox = QVBoxLayout()
        repHolderHbox.addLayout(repRowsVbox)
        repHolderHbox.addLayout(repChecksVbox)
        # populate the stack of replace checkboxes
        self.andNextSwitch = QCheckBox("&&Next")
        self.andPriorSwitch = QCheckBox("&&Prior")
        # Need to make those 2 mutually exclusive - cannot use a QButtonGroup
        # because it doesn't permit the both-off state once one is checked.
        self.connect(self.andNextSwitch, SIGNAL("stateChanged(int)"),
                     self.andNext)
        self.connect(self.andPriorSwitch, SIGNAL("stateChanged(int)"),
                     self.andPrior)
        self.allSwitch = QCheckBox("ALL!")
        repChecksVbox.addStretch(1) # spring at the top
        repChecksVbox.addWidget(self.andNextSwitch,0)
        repChecksVbox.addWidget(self.andPriorSwitch,0)
        repChecksVbox.addSpacing(24) # little space since insel moved to top
        repChecksVbox.addWidget(self.allSwitch,0)
        repChecksVbox.addStretch(1) # spring at the bottom too
        # populate the stack of three replace setups, spacer at bottom
        stgs.beginReadArray("rep")
        self.makeRepRow(repRowsVbox,1,stgs)
        self.makeRepRow(repRowsVbox,2,stgs)
        self.makeRepRow(repRowsVbox,3,stgs)
        stgs.endArray()
        # put a spacer in the main layout between the replace stuff and user buttons
        mainLayout.addStretch(1)
        # create the grid of user buttons with values restored from settings. 
        # Connect the left click signal from any button to our userButtonClick.
        # Connect the signal emitted by a user button on the contextMenu event
        # (left- or ctrl-click) to our userButtonLoad. N.B. to make these 
        # lambdas work it is essential to specify an expression, not a variable
        # name alone, as the parameter.
        userButtonGrid = QGridLayout()
        mainLayout.addLayout(userButtonGrid,0)
        stgs.beginReadArray("userButton")
        for i in range(UserButtonMax):
            stgs.setArrayIndex(i)
            dict = unicode(stgs.value(
            "dict",QString("{u'label':u'(empty)',u'tooltip':u'Undefined button'}")
                ).toString())
            btn = userButton(unquote(dict))
            self.userButtons.append(btn)
            self.connect(self.userButtons[i], SIGNAL("clicked()"),
                                lambda b=i : self.userButtonClick(b) )
            self.connect(self.userButtons[i], SIGNAL("userButtonLoad"),
                                lambda b=i : self.userButtonLoad(b) )
            userButtonGrid.addWidget(self.userButtons[i],
                                int(i/UserButtonRow), int(i%UserButtonRow))
        stgs.endArray()
        # ...and there we are!
        stgs.endGroup() # end group "Find."
    
    # Subroutine to make a replace row. Called with the parent layout and the
    # row number. Create a horizontal layout with a combobox, lineEdit,
    # and Repl button. Connect the button to doReplace with a lambda passing 1/2/3.
    # Create lambda (nameless) functions to act as the slots for two signals.
    # The lambda for textEdited passes the row number so the function knows which
    # popup to use. The lambda for clicked() passes not only the row number but
    # also the then-current state of the and-find and all switches, so that the
    # doReplace method can be called as a subroutine elsewhere.
    
    def makeRepRow(self, parent, repRow, stgs):
        # create the edit and then the combobox with its buddy edit
        stgs.setArrayIndex(repRow)
        self.repEdits[repRow] = findRepEdit()
        self.popups[repRow] = recentStrings(self.repEdits[repRow],
                        stgs.value("List",QStringList()).toStringList() )
        self.connect(self.repEdits[repRow], SIGNAL("textEdited(QString)"),
                                     lambda : self.userEditedText(repRow) )
        button = QPushButton("Repl")
        button.setMaximumHeight(32)
        self.connect(button, SIGNAL("clicked()"),
            lambda : self.doReplace(repRow,
                    self.andNextSwitch.isChecked(),
                    self.andPriorSwitch.isChecked(),
                    self.allSwitch.isChecked()) )
        rowLayout = QHBoxLayout()
        parent.addLayout(rowLayout)
        rowLayout.addWidget(self.popups[repRow])
        rowLayout.addWidget(self.repEdits[repRow])
        rowLayout.addWidget(button)

    # Called when the find text changes OR the state of the regexSwitch
    # changes: if regex is on, get the find text as a regex and if it
    # has bad syntax, turn the background of the find text pink. As a side
    # effect, whenever Next/Prior is hit, self.regex has the current regex.
    # n.b. the textEdited signal passes a QString but we ignore it.
    def checkFindText(self):
        col = "white"
        if self.regexSwitch.isChecked():
            self.regexp = QRegExp(self.findText.text())
            if not (self.regexp.isValid()) :
                col = "pink"
        self.findText.setBackground(col) # see below

    # Called from the textEdited signal of any of the findRepEdits, meaning
    # the user has changed something in the contents. All we do here is clear
    # the userLoad flag in case it was on. This means that if that field
    # is used, it should be saved in its popup.
    def userEditedText(self,repno):
        self.repEdits[repno].userLoad = False

    # Slots for the statusChanged signal from the &Next and &Prior buttons.
    # Make sure that if one comes on, the other is, or goes, off.
    def andNext(self,state):
        if state : # &Next is now on
            if self.andPriorSwitch.isChecked() :
                self.andPriorSwitch.setChecked(False)
    def andPrior(self,state):
        if state : # &Next is now on
            if self.andNextSwitch.isChecked() :
                self.andNextSwitch.setChecked(False)

    # Slot for the stateChanged signal from the in Sel'n switch.
    # If it has been cleared, set full search range.
    def inSelChange(self,state):
        if not state:
            self.setFullRange()

    # Subroutine to set the search range cursors to the full document.
    # Make each a copy of the document's cursor, not merely a ref to it.
    def setFullRange(self):
        self.rangeTop = QTextCursor(IMC.editWidget.textCursor())
        self.rangeTop.movePosition(QTextCursor.Start)
        self.rangeBot = QTextCursor(IMC.editWidget.textCursor())
        self.rangeBot.movePosition(QTextCursor.End)

    # Slot for the docHasChanged signal out of pqMain. Reset our text
    # boundary to the whole document and clear the In Sel'n button if on.
    # The signal passes a file path string but we ignore it.
    def docHasChanged(self):
        self.setFullRange() # sets rangeTop and rangeBot
        self.inSelSwitch.setChecked(False)
        
    # The heart of search, pulled out for use from replace-all (and 
    # potentially, but not yet, from pqNotes and pqHelp). Takes a
    # textDocument, a starting textcursor based on that document. Returns a
    # find textCursor whose selection is null if no-match, else selects the
    # found text. Depends on the values of self.regexp, self.regexSwitch,
    # self.caseSwitch, self.greedySwitch and self.wholeWordSwitch.
    def realSearch(self, doc, startTc, backward = False):
        if not self.regexSwitch.isChecked() :
            # normal string search: apply the QTextDocument.find() method
            # passing our Case, whole word and direction flags
            flags = QTextDocument.FindBackward if backward \
                  else QTextDocument.FindFlags(0)
            if self.caseSwitch.isChecked() :
                flags |= QTextDocument.FindCaseSensitively
            if self.wholeWordSwitch.isChecked() :
                flags |= QTextDocument.FindWholeWords
            findTc = doc.find(self.findText.text(),startTc,flags)
        else:
            # Regex search! See notes in prologue.
            findTc = QTextCursor(startTc) # null cursor says no-match
            findTc.clearSelection() # probably not necessary
            if self.regexp.isValid() :
                # valid regex: if it contains \n replace with \u2029
                pats = self.regexp.pattern()
                pats.replace(QString("\\n"),IMC.QtLineDelim)
                self.regexp.setPattern(pats)
                # set case and greedy switches in QRegExp
                self.regexp.setCaseSensitivity(
                    Qt.CaseSensitive if self.caseSwitch.isChecked() \
                    else Qt.CaseInsensitive)
                self.regexp.setMinimal(not self.greedySwitch.isChecked())
                # set up workTc selecting all possible text to search, based
                # on the direction of the search.
                workTc = QTextCursor(startTc) # workTc points to start of range
                # Set a cursor to select all text in the searchable range. We
                # do this by "dragging" from startTc's position to the end
                # of the range. See note in doSearch below, about overlapping finds.
                if backward :
                    workTc.setPosition(self.rangeTop.position(),QTextCursor.KeepAnchor)
                else:
                    workTc.setPosition(self.rangeBot.position(),QTextCursor.KeepAnchor)
                # apply the regex to that text as a QString, getting an index
                # to the left end of a hit, and also priming self.regex.cap(n)
                # for replacements.
                if backward : 
                    fpos = self.regexp.lastIndexIn(workTc.selectedText())
                else:
                    fpos = self.regexp.indexIn(workTc.selectedText())
                # if we have a hit, create a cursor that spans it.
                if fpos > -1:
                    findTc = QTextCursor(startTc)
                    findTc.setPosition(workTc.selectionStart()+fpos)
                    findTc.movePosition(QTextCursor.Right,
                                        QTextCursor.KeepAnchor,
                                        self.regexp.matchedLength())
        return findTc

    # called with a find-match cursor to see if it is valid, i.e. if it
    # is in the selection bounds.
    def validHit(self,findTc):
        if findTc.hasSelection(): # found something
            if (findTc.selectionStart() >= self.rangeTop.position()) \
            and (findTc.selectionEnd() <= self.rangeBot.position()) :
                return True # match inside range
                # else - not in rage, fall through and return false
        return False # null selection: no hit
    
    # Called when any of the search buttons is clicked or when the relevant
    # key events are seen. Button number passed is 0 for next, 1 for prior,
    # 2 for first, 3 for last. Hence odd=backward, >1 means limit.
    # These switches modify searching: self.caseSwitch self.wholeWordSwitch
    # self.inSelSwitch, self.regexSwitch, self.greedySwitch
    # The boundaries have to be textCursors we might not have made them yet..
    def doSearch(self,button):
        doc = IMC.editWidget.document()
        editTc = QTextCursor(IMC.editWidget.textCursor())
        # if this is the first/last button set the boundaries based on inSelSwitch.
        if button & 0x02 :
            if self.inSelSwitch.isChecked() : # in selection
                if editTc.hasSelection() : # non-empty selection
                    self.rangeTop.setPosition(editTc.selectionStart())
                    self.rangeBot.setPosition(editTc.selectionEnd())
                else : # empty selection, complain and exit
                    pqMsgs.infoMsg(u"No selection!",
                u"Clear in-sel'n flag or select text range for find/replace")
                    return
            else : # inSel not checked, range is entire document
                self.setFullRange()
            startTc = self.rangeBot if (button & 0x01) else self.rangeTop
        else :
            # Not First/Last, so set start to current edit cursor. Left to itself,
            # QTextDocument will start a forward search at selectionEnd,
            # and a backward search at selectionStart, in other words, assuming
            # that editTc's selection is the result of a previous find, it
            # never allows the next find to overlap with the previous one.
            # Tentatively we will override this, and permit overlapping finds.
            # If the current cursor has a selection, make a forward find start
            # at selectionStart+1 and a backward one at selectionStart-1.
            # (If it has no selection, just start where it points.) This may
            # seem counterintuitive, but the find always tries to match from the
            # starting position forward, and on failure, advances one char either
            # forward or backward and tries again. Work it out on paper, you'll see.
            startTc = editTc
            if startTc.hasSelection():
                if button & 0x01 : # backward
                    startTc.setPosition(editTc.selectionStart()-1)
                else: # forward
                    startTc.setPosition(editTc.selectionStart()+1)
        # Perform a search but first, save it in the pushdown list
        self.popups[0].noteString()
        findTc = self.realSearch(doc, startTc, button&0x01)
        # search is done, finish up: set the visible cursor in the edit window
        # to the found text, and throw the focus over there too.
        if self.validHit(findTc): # got a hit and in-bounds
            IMC.editWidget.setTextCursor(findTc)
            IMC.editWidget.setFocus(Qt.TabFocusReason)
        else:
            pqMsgs.beep()

    # Called from one of the three replace buttons or from an edit keystroke
    # to do a replace. We replace the current selection. Arguments are 
    # the number of the replace field (1-3), and the truth of and-next,
    # and-prior, and rep-all switches. When a Replace button is clicked,
    # these values are sampled by the lambda that is the signal slot,
    # so repno is the button number 1/2/3, and the next three args are
    # the checked status of the interface buttons. 
    #
    # When called from editKeyPress below, representing an edit keystroke,
    # the args are always 1, f/t, f/t, false. 
    #
    # This code also depends on self.regexSwitch, self.regexp, and the
    # replace[repno] text field.
    #
    # Following the replace we need to adjust the edit cursor position.
    # Qt's default on .insertText is to clear the selection and leave
    # the cursor after the last inserted char. We recreate the selection
    # by "dragging" backwards to the starting position.
    # See also comments in the Prolog about regex replace.
    
    def doReplace(self,repno,andNext=False,andPrior=False, doAll=False):
        self.popups[repno].noteString() # any use gets pushed on the popup list
        tc = IMC.editWidget.textCursor() # reference to the edit cursor
        p = tc.selectionStart()
        if not doAll : # one-shot replace
            if self.regexSwitch.isChecked() :
                # make a copy of the current find regexp including its latest
                # settings of case-sensitive and minimal.
                qrex = QRegExp(self.regexp)
                # Find out if it has a trailing lookahead and if so, delete it.
                lookp = self.lookAheadFinder.indexIn(qrex.pattern())
                if lookp > -1 : # there is one
                    qpat = self.regexp.pattern() # get the pattern
                    qpat.truncate(lookp)  # truncate the "(?=asdf)"
                    qrex.setPattern(qpat) # put modified pattern back
                # Get the currently-selected text as a QString ref
                qs = tc.selectedText() # get selection as QString
                # Copy the user's replace string and change \n to psep
                qrep = QString(self.repEdits[repno].text())
                qrep.replace(QString("\\n"),IMC.QtLineDelim)
                # perform the replacement!
                qs.replace(qrex,qrep)
                tc.insertText(qs) # put the updated text back in the doc.
            else: # plain replace, just update the selection with new text
                tc.insertText(self.repEdits[repno].text())
            # QTextEdit leaves the cursor at the end of insert;
            # "drag" backward to reselect the inserted text
            tc.setPosition(p,QTextCursor.KeepAnchor)
            if andNext : 
                self.doSearch(0) # Next button
            if andPrior :
                self.doSearch(1) # Prior button
        else: # replace all!
            # For replace all we assume the bounds were set by a prior First
            # button. We loop doing finds from the top boundary until no-match,
            # saving a text cursor representing each hit.
            hits = []
            doc = IMC.editWidget.document()
            findTc = self.realSearch(doc,self.rangeTop,False)
            while self.validHit(findTc):
                # we have a match, save a copy of the textCursor that
                # describes it -- in LIFO order, note.
                hits.insert(0,QTextCursor(findTc))
                # do the next search from the end of the previous match.
                findTc.setPosition(findTc.selectionEnd())
                findTc = self.realSearch(doc,findTc,False)
            if 0 == len(hits):
                pqMsgs.beep()
                return
            # We have at least 1 hit, ask the user for permission to fire.
            m1 = pqMsgs.trunc(self.findText.text(),25)
            qrep = QString(self.repEdits[repno].text()) # copy replace string
            m2 = pqMsgs.trunc(qrep,25)
            if pqMsgs.okCancelMsg(
            "Replace {0} occurrences of {1}\nwith {2} ?".format(len(hits),m1,m2)
            ) :
                # user says ok do it. In order to make it one undoable operation
                # we have to use a single textCursor for all. We use findTc
                # and we transfer the position of each hit into it with moves.
                findTc = QTextCursor(doc)
                findTc.beginEditBlock() # start undoable operation
                if self.regexSwitch.isChecked():
                    # for regex we support replacing \\n so update rep string
                    qrep.replace(QString("\\n"),IMC.QtLineDelim)
                    # and get rid of a trailing lookahead in the regex
                    qrex = QRegExp(self.regexp)
                    # Find out if it has a trailing lookahead and if so, delete it.
                    lookp = self.lookAheadFinder.indexIn(qrex.pattern())
                    if lookp > -1 : # there is one
                        qpat = self.regexp.pattern() # get the pattern
                        qpat.truncate(lookp)  # truncate the "(?=asdf)"
                        qrex.setPattern(qpat) # put modified pattern back
                # The hits were stored in LIFO order, so this loop applies them
                # from the end of the document up, keeping later positions valid.
                for tc in hits:
                    # transfer the selection of this match to findTc
                    findTc.setPosition(tc.selectionEnd(),QTextCursor.MoveAnchor)
                    findTc.setPosition(tc.selectionStart(),QTextCursor.KeepAnchor)
                    if not self.regexSwitch.isChecked():
                        # simple replace: insert the changed text over it.
                        findTc.insertText(qrep)
                    else :
                        # get the selected text as a string and do regex repl
                        qs = findTc.selectedText()
                        qs.replace(qrex, qrep)
                        findTc.insertText(qs)
                findTc.endEditBlock()
                # clear the All! after successful op
                self.allSwitch.setChecked(False)

    # Slot for the editKeyPress signal from the edit panel. The key is
    # passed as an int in IMC.findKeys. Do the right thing based on it.
    # See notes in pqIMC.py where the key values are set up.
    def editKeyPress(self,kkey):
        if   kkey == IMC.ctl_G : self.doSearch(0) # ^g == Next
        elif kkey == IMC.ctl_shft_G : self.doSearch(1) # ^G == Prior
        elif kkey == IMC.ctl_F : # ^f == focus to Find panel
            if not self.isVisible() :
                IMC.mainWindow.makeMyPanelCurrent(self) 
            self.findText.setFocus() # get keyboard focus to find string
        elif kkey == IMC.ctl_shft_F : # ^F == focus to find with selection
            self.findText.setText(IMC.editWidget.textCursor().selectedText())
            if not self.isVisible() :
                IMC.mainWindow.makeMyPanelCurrent(self)
            self.findText.setFocus() # get keyboard focus to the find string    
        elif kkey == IMC.ctl_equal : # ^= == replace and no movement
            self.doReplace(1,False,False,False)
        elif kkey == IMC.ctl_T : # ^t == replace and find next
            self.doReplace(1, True, False, False)
        elif kkey == IMC.ctl_shft_T : # ^T == replace and find backward
            self.doReplace(1, False, True, False)
        else:
            pqMsgs.beep() # should not occur

    # public method for use by the Char and Word census panels. When a
    # row is double-clicked, throw the char/word into the find text and 
    # bring the find panel to the front. Char panel sometimes passes a
    # replace string, and Words sometimes wants a regex search.
    def censusFinder(self,qs,repl=None,rex=False):
        self.findText.setText(qs)
        self.regexSwitch.setChecked(rex)
        if repl is not None:
            self.repEdits[1].setText(rep)
        if not self.isVisible() :
            IMC.mainWindow.makeMyPanelCurrent(self) 
        self.findText.setFocus() # get keyboard focus to find string
        self.findText.userLoad = True # don't save it in the pushdown list

    # Slot for the clicked signal of a userButton. The button number is 
    # passed as an argument via the actual slot, which is a lambda.
    # Move the dictionary fields from the button into the find dialog fields,
    # Clear any controls not defined in the button.
    def userButtonClick(self,butnum):
        d = self.userButtons[butnum].udict
        self.caseSwitch.setChecked(False)
        if 'case' in d : self.caseSwitch.setChecked(d['case'])
        self.wholeWordSwitch.setChecked(False)
        if 'word' in d : self.wholeWordSwitch.setChecked(d['word'])
        self.inSelSwitch.setChecked(False)
        if 'insel' in d : self.inSelSwitch.setChecked(d['insel'])
        self.regexSwitch.setChecked(False)
        if 'regex' in d : self.regexSwitch.setChecked(d['regex'])
        self.greedySwitch.setChecked(False)
        if 'greedy' in d : self.greedySwitch.setChecked(d['greedy'])
        self.andNextSwitch.setChecked(False)
        if 'andnext' in d : self.andNextSwitch.setChecked(d['andnext'])
        self.andPriorSwitch.setChecked(False)
        if 'andprior' in d : self.andPriorSwitch.setChecked(d['andprior'])
        self.allSwitch.setChecked(False)
        if 'all' in d : self.allSwitch.setChecked(d['all'])
        self.findText.setText(QString())
        if 'find' in d :
            self.findText.setText(d['find'])
            self.findText.userLoad = True
        self.repEdits[1].setText(QString())
        if 'rep1' in d :
            self.repEdits[1].setText(QString(d['rep1']))
            self.repEdits[1].userLoad = True
        self.repEdits[2].setText(QString())
        if 'rep2' in d :
            self.repEdits[2].setText(QString(d['rep2']))
            self.repEdits[2].userLoad = True
        self.repEdits[3].setText(QString())
        if 'rep3' in d :
            self.repEdits[3].setText(QString(d['rep3']))
            self.repEdits[3].userLoad = True
    
    # Slot for the userButtonLoad signal coming out of a userButton when
    # it is right-clicked. Query the user for a new label for the button
    # and if Cancel is not chosen, load the label and all find data into
    # the dict in the button.
    def userButtonLoad(self,butnum):
        d = self.userButtons[butnum].udict
        prep = None
        if d['label'] != u'(empty)':
            prep = d['label']
        j = butnum + 1
        (ans, ok) = pqMsgs.getStringMsg(u"Loading button {0}".format(j),
                        u"Enter a short label for button {0}".format(j),
                        prep)
        if not ok : # Cancel was clicked, make no change
            return
        if ans.isEmpty(): # null label means, clear button
            self.userButtons[butnum].udict = {u'label':u'(empty)',u'tooltip':u'Undefined button'}
            self.userButtons[butnum].setText(QString(u'(empty)'))
            self.userButtons[butnum].setToolTip(QString(u'Undefined button'))
            return
        d.clear()
        d['label'] = unicode(ans)
        self.userButtons[butnum].setText(ans)
        self.userButtons[butnum].setToolTip(ans) # wipe out "Undefined button" tip
        d['case'] = self.caseSwitch.isChecked()
        d['word'] = self.wholeWordSwitch.isChecked()
        d['regex'] = self.regexSwitch.isChecked()
        d['greedy'] = self.greedySwitch.isChecked()
        d['andnext'] = self.andNextSwitch.isChecked()
        d['andprior'] = self.andPriorSwitch.isChecked()
        d['insel'] = self.inSelSwitch.isChecked()
        d['all'] = self.allSwitch.isChecked()
        if not self.findText.text().isNull() :
            d['find'] = unicode(self.findText.text())
        if not self.repEdits[1].text().isNull() :
            d['rep1'] = unicode(self.repEdits[1].text())
        if not self.repEdits[2].text().isNull() :
            d['rep2'] = unicode(self.repEdits[2].text())
        if not self.repEdits[3].text().isNull() :
            d['rep3'] = unicode(self.repEdits[3].text())

    # Slot for the "shuttingDown" signal out of pqMain. Save the Find and
    # Replace popup stacks, and the current userButton values, to the
    # settings file. Here we use url quote to protect the special chars
    # in the find-button-dicts because we aren't sure the settings file
    # is always unicode.
    def shuttingDown(self):
        stgs = IMC.settings
        stgs.beginGroup("Find") # all subsequent keys start with Find.
        stgs.setValue("findList",self.popups[0].list)
        stgs.beginWriteArray("rep") # keys will be Find.rep.#.List
        for i in range(1,4): # that's 1, 2, 3
            stgs.setArrayIndex(i)
            stgs.setValue("List",self.popups[i].list)
        stgs.endArray()
        stgs.beginWriteArray("userButton") # keys Find.userButton.#.dict
        for i in range(UserButtonMax):
            stgs.setArrayIndex(i)
            stgs.setValue("dict",
                QString(quote(self.userButtons[i].udict.__repr__())) )
        stgs.endArray() 
        stgs.endGroup() # end of Find/xxx group

    # Method for pqMain to call to cause saving of userbuttons.
    # The saved value is a python dict literal with __repr__ strings as
    # values. The file is encoded UTF-8 (whether or not the user supplies the
    # right suffix), because the find/rep strings can be any characters.

    def saveUserButtons(self,stream):
        numStr = u"{0}: {{ " # first line is button# : { \t key : value
        openStr = u"\t{0} : {1}"
        sepStr = u",\n\t{0} : {1}" # subsequent lines are ,\n\t key : value
        endStr = u"\n}\n\n"
        stream << u"# every backslash witin a string must be doubled! \n"
        for i in range(UserButtonMax):
            d = self.userButtons[i].udict
            if d['label'] != "(empty)" :
                stream << numStr.format(i)
                puncStr = openStr
                for key in sorted(d.keys()):
                    stream << puncStr.format(key.__repr__(), d[key].__repr__())
                    puncStr = sepStr
                stream << endStr

    # method for pqMain to call to cause loading of all userbuttons
    # from a text file. See above for format. See userButton.loadDict
    # for validation. However, for just a touch of user-friendliness, we
    # do not require the dict to be on a single line, instead we read and
    # collect up to the right brace.
    # n.b. the comparison u"}" == qss.at(x) will fail because a string cannot
    # match a QChar. Or so it seems. You can do u"}" == qss[x], or what we do here.
    def loadUserButtons(self,stream):
        leadingBit = QRegExp("^\s*(\d+)\s*:\s*\{")
        stopper = QChar(u"}")
        while not stream.atEnd():
            qs = stream.readLine().trimmed()
            dbg = unicode(qs)
            if 0 == leadingBit.indexIn(qs) :
                (bn,ok) = leadingBit.cap(1).toInt() # just the digits
                if bn == 99: # code for, highest (empty) one
                    for i in range(UserButtonMax-1,-1,-1) : # go from low to hi
                        if self.userButtons[i].udict['label'] == '(empty)' :
                            bn = i
                            break
                    # if loop ends with no hit, bn remains 99
                if (bn >= 0) and (bn < UserButtonMax):
                    qss = qs.right((qs.size()-leadingBit.cap(0).size())+1)
                    while True:
                        if stopper == qss.at(qss.size()-1):
                            break
                        if stream.atEnd():
                            qss.append(stopper)
                        else:
                            qss.append(u" ")
                            qss.append(stream.readLine().trimmed())
                    btn = self.userButtons[bn]
                    btn.loadDict(unicode(qss)) # always sets label
                    btn.setText(btn.udict['label'])
                    if 'tooltip' in btn.udict:
                        btn.setToolTip(QString(btn.udict['tooltip']))
                # else not valid index to start - ignore it
            # else doesn't start with n: - maybe blank line? anyway skip it
        # end of file

# We subclass QComboBox to make the recent-string-list pop-ups.
# One change from default, we set the max width to 32; these are
# more like buttons than combo boxes. The associated line edit widget
# is passed and this constructor clips its activated(QString) signal to
# the lineEdit's setText(QString) function.

class recentStrings(QComboBox):
    def __init__(self, myLineEdit, oldList=None, parent=None):
        super(recentStrings, self).__init__(parent)
        self.setMaximumWidth(32)
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.setEditable(False)
        self.setMaxCount(10)
        self.buddy = myLineEdit # save ref to associated findRepEdit
        self.lastString = QString()
        if oldList is not None:
            self.list = oldList
            self.addItems(self.list)
        else:
            self.list = QStringList() # clear our list of items
        self.connect(self, SIGNAL("activated(QString)"), self.buddy.setText)
    
    # Called when our associated lineEdit is used, e.g. Next or Repl button.
    # Such use might happen multiple times without changing the string, so
    # bail quick if we've seen this one. When the string is not the same as
    # last time, put it at the head of our list and reload our popup.
    def noteString(self):
        if self.buddy.userLoad : return # don't save userButton load in popup
        tx = self.buddy.text() # text now in associated lineEdit
        if 0 != self.lastString.compare(tx) : # changed since last time
            self.lastString = tx # skip it if the button is hit again
            # look for tx in the current list, if we find it, delete it
            # so we can put it at the front again. n.b. range(0) is a null list.
            for i in range(self.list.count()):
                if 0 == tx.compare(self.list[i]): 
                    self.list.removeAt(i) # get rid of it
                    break
            # we are sure tx is not now in the list, so prepend it. If that 
            # pushes the count past max, the oldest is dropped.
            self.list.prepend(tx)
            self.clear() # empty the displayed list
            self.addItems(self.list) # refresh displayed list
    
# We subclass LineEdit to make our find and replace text widgets.
# It has some special features compared to the usual LineEdit.

class findRepEdit(QLineEdit):
    def __init__(self, parent=None):
        super(findRepEdit, self).__init__(parent)
        self.setFont(pqMsgs.getMonoFont(11,False))
        self.setAutoFillBackground(True) # allow changing bg color
        self.userLoad = False # not loaded from a userButton
    
    # Change the background color of this lineEdit
    def setBackground(self,color):
        palette = self.palette()
        palette.setColor(QPalette.Normal,QPalette.Base,QColor(color))
        self.setPalette(palette)
    
    # these lineEdits, same as edit and notes panels, allow changing
    # font size though over a smaller range
    def keyPressEvent(self, event):
        kkey = event.key() + int(event.modifiers())
        if kkey in IMC.zoomKeys :
            event.accept()
            n = (-1) if (kkey == IMC.ctl_minus) else 1
            p = self.fontInfo().pointSize() + n
            if (p > 4) and (p < 25): # don't let's get ridiculous, hmm?
                f = self.font() # so get our font,
                f.setPointSize(p) # change its point size +/-
                self.setFont(f) # and put the font back
        else: # not ctl-+/-, pass to parent widget
            event.ignore()
            super(findRepEdit, self).keyPressEvent(event)

# Class of the user-programmable push buttons. Each button can store the values
# of all the fields of the upper part of the panel.
#
# The values are stored in the form of a python dict with these keys:
# 'label'  : 'string'    label for the button
# 'tooltip': 'string'    tooltip for the button, can be longer than the label
# 'case'   : True/False  case switch
# 'word'   : True/False  whole word switch
# 'insel'  : True/False  in selection switch
# 'regex'  : True/False  regex switch
# 'greedy' : True/False  greedy switch
# 'find'   : 'string' with quotes escaped find string
# 'rep1/2/3' : 'string' with quotes escaped rep strings 1/2/3
# 'andnext' : True/False  &Next replace switch
# 'andprior' : True/False  &Prior replace switch
# 'all'    : True/False replace all switch
# The find and rep strings are encoded as for a url so that backslashes
# and quotes don't mess up the dict literal values.
#
# When the button is clicked, the signal goes to findPanel.userButtonClick
# where the dict values stored in the clicked button are queried and used
# to set the fields of the panel.
#
# The button constructor takes the __repr__ string of a dict as argument
# and converts it to a dict if it can. The requirement is only that it be
# a good syntactic python dict literal and that it have a 'label' key.
# The stored dict can be converted with its __repr__ method to a string
# for saving buttons to a file or to the settings at shutdown.
class userButton(QPushButton):
    def __init__(self, initDict=None, parent=None):
        super(userButton, self).__init__(parent)
        self.setContextMenuPolicy(Qt.PreventContextMenu) # we handle right-click
        # if a dict string was passed, treat it with suspicion
        self.udict = None
        self.loadDict(initDict) # creates at least a minimal dict with a label
        self.setText(QString(self.udict['label']))
        if 'tooltip' in self.udict:
            self.setToolTip(QString(self.udict['tooltip']))

    # trap a right-click or control-click and pass it as a signal to findPanel
    # where it will load our dict from the present find fields, and query the
    # user for a new button label. n.b. originally we used contextMenuEvent to
    # generate this signal which should be the same, but it elicited some funny
    # behavior from Qt so we went to plain mouseReleaseEvent.
    def mouseReleaseEvent(self,event):
        if 2 == int(event.button()) : # right- or control-click
            event.accept()
            self.emit(SIGNAL("userButtonLoad"))
        else : # not a right-click, pass it to parent widget
            event.ignore()
            super(userButton, self).mouseReleaseEvent(event)

    # Subroutine to load this button's values from a )ython string that purports
    # to be the Python source of a dictionary, such as is created by
    # findPanel.userButtonLoad() above, and saved in the settings in
    # findPanel.shutDown(), and saved by File>Save Find Buttons.
    # This is called on button creation, or when doing File> Load Find Buttons
    # from a file. Since it might come from a user-edited file, we treat it with
    # grave suspicion. We require it to be a valid Python literal form of a
    # a dict type having a 'label':'string' entry. We do not check other
    # entries, and in fact you could sneak in bad stuff e.g. 'andnext':'foobar'
    # which would only cause an error message to the console when the button
    # is clicked.
    def loadDict(self,dictrepr):
        try:
            # validate dictrepr as being strictly a literal dictionary: ast
            # will throw ValueError if it isn't a good literal and only a literal,
            # thus avoiding possible code injection. The compiler chokes on 
            # literal tabs so replace tabs with spaces.
            okdict = ast.literal_eval(dictrepr.replace(u'\t',u' '))
            # now make sure it was a dict not a list or whatever
            if not isinstance(okdict,dict) : 
                raise ValueError
            # and make sure it has a label key
            if not 'label' in okdict :
                raise ValueError
            # and make sure the value of dict['label'] is a string
            if not ( isinstance(okdict['label'],str) \
                    or isinstance(okdict['label'],unicode) ):
                raise ValueError
            # all good, go ahead and use it
            self.udict = okdict
        except StandardError:
            # some error raised, go to minimum default
            self.udict = { 'label':'(empty)', 'tooltip':'Undefined button' }
    
if __name__ == "__main__":
    import sys
    from PyQt4.QtCore import (Qt,QSettings)
    from PyQt4.QtGui import (QApplication,QPlainTextEdit)
    import pqIMC
    IMC = pqIMC.tricorder()
    app = QApplication(sys.argv) # create an app

    #ubutt = userButton() # no dict
    #ubutt = userButton('{frummage') # bad syntax
    #ubutt = userButton('2 + 3') # not a dict
    #ubutt = userButton('{\'x\':\'y\'}') # good dict no label
    #ubutt = userButton("{ 'label':99 }") # label not a string
    #ubutt = userButton("{ 'label':'what', 'word':True }")
    
    import pqMsgs
    pqMsgs.IMC = IMC
    IMC.editWidget = QPlainTextEdit()
    doc = '''
banana
frog
99 bed bedsitter embedded
bumbershoot
shooterbumb
bumbershoot
frog
banana
    '''
    IMC.fontFamily = QString("Courier")
    IMC.settings = QSettings()
    IMC.editWidget.setPlainText(doc)
    widj = findPanel()
    IMC.mainWindow = widj
    widj.show()
    app.exec_()
