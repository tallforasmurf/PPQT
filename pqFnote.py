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
Implement the Footnote managament panel, whose chief feature is a table
of footnotes that is re/built with a Refresh button. Important nomenclature:
A footnote KEY is a symbol that links a REFERENCE to a NOTE.
A Reference
* appears in text but never in column 0,
* has a Key in square brackets with no superfluous spaces, e.g. [A] or [2].
A Note
* begins on a line following its matching reference
* always begins in column 0 with [Footnote k: where k is a Key.
* always ends with a right square bracket at end of line.

It is not required that Keys be unique. (It is normal for most Keys in a PG
text to be proofed as "A" and a few as "B".) However it is expected and required
that (a) the Reference with Key k precedes the Note with the matching Key k,
and (b) Notes with the same Key appear in the same sequence as their references.

A Note may contain a Reference, but Notes may NOT be nested. A Note ref'd from
another Note must be outside the other note. A note may contain square brackets
so long as the contained brackets do not end a line. This is valid:

  Text[A] and more text[A]
  ...
  [Footnote A: this note has[i] a reference.]
  [Footnote A: this is the second note A and runs
  to multiple -- [text in brackets but not at end of line] --
  lines]
  [Footnote i: inner note referenced from A.]
  
After a Refresh, the table has these columns:

Key:        The key symbol from a footnote, e.g. A or i or 1.

Class:      The class of the key, one of:
                ABC     uppercase alpha
                IVX     uppercase roman numeral
                123     decimal
                abc     lowercase alpha
                ivx     lowercase roman numeral
                *\u00A4\u00A5 symbols

Ref Line:   The text block (line) number containing the key, e.g. [A]

Note Line:   The text block number of the matching [Footnote A: if found

Length:    The length in lines of the matched Note

Text:      The opening text of the Note e.g. [Footnote A: This note has...

The example above might produce the following table:

 Key   Class  Ref Line   Note Line   Length   Text
  A     ABC     1535      1570         1      Footnote A: this note has[i..
  A     ABC     1535      1571         3      Footnote A: this is the sec..
  i     ivx     1570      1574         1      Footnote i: inner note refe..

The table interacts as follows.

* Clicking Key jumps the edit text to the Ref line, unless it is on the ref
  line in which case it jumps to the Note line, in other words, click/click
  to cycle between the Ref and the Note.

* Clicking Ref Line jumps the edit text to that line with the Key
(not the whole Reference) selected.

* Clicking Note line jumps the edit text to that line with the Note selected.

* Doubleclicking Class gets a popup list of classes (see Pages Folio Action)
  and the user can select a different class which is noted.

* When a Key or a Note is not matched, its row is pink.

The actual data behind the table is a Python list of dicts where each dict
describes one Key and/or Note (both when they match), with these fields:

'K' :  Key symbol as a QString
'C' :  Key class number
'R' :  QTextCursor with position/anchor selecting the Key in the Ref, or None
'N' :  QTextCursor selecting the Note, or None

If a Reference is found, K has the Key and R selects the Key.
If a Note is found, K has the key and N selects the Note.
When a Ref and a Note are matched, all fields are set.

Note we don't pull out the line numbers but rather get them as needed from the
QTextCursors. This is because Qt keeps the cursors updated as the document
is edited, so edits that don't modify Refs or Notes don't need Refresh to keep
the table current.

When Refresh is clicked, this list of dicts is rebuilt by scanning the whole
document with regexs to find References and Notes, and matching them.
The progress bar is used during this process.

During Refresh, found Keys are assigned to a number class based on their
values expressed as regular expressions:
    Regex               Assumed class
    [IVXLCDM]{1,15}       IVX
    [A-Z]{1,2}            ABC
    [1-9]{1,3}            123
    [ivxlcdm]{1,15}       ivx
    [a-z]{1,2}            abc
    [*\u00a4\u00a7\u00b6\u2020\u20221] symbols *, para, currency, dagger, dbl-dagger

(Note these are NOT unicode-aware. In Qt5 it may be possible to code a regex
to detect any Unicode uppercase, and we can revisit allowing e.g. Keys with
Greek or Cyrillic letters. For now, only latin-1 key values allowed.)

Other controls supplied at the bottom of the panel are:

Renumber Streams: a box with the six Key classes and for each, a popup
giving the choice of renumber stream:

  no renumber
  1,2,..999
  A,B,..ZZ
  I,II,..M
  a,b,..zz
  i,ii,..m

There are five unique number streams, set to 0 at the start of a renumber
operation and incremented before use, and formatted in one of five ways.
The initial settings of classes to streams are:

  123 : 1,2,..999
  ABC : A,B,..ZZ
  IVX : A,B,..ZZ
  abc : a,b,..zz
  ivx : a,b,..zz
  sym : no renumber

A typical book has only ABC keys, or possibly ABC and also ixv or 123 Keys.
There is unavoidable ambiguity between alpha and roman classes. Although an
alpha key with only roman letters is classed as roman, the renumber stream
for roman is initialized to the alpha number stream.

In other words, the ambiguity is resolved in favor of treating all alphas
as alphas. If the user actually wants a roman stream, she can e.g. set
class ivx to use stream i,ii..m. Setting either roman Class to use a
roman Stream causes the alpha class of that case to be set to no-renumber.
Setting an alpha class to use any stream causes the roman stream of that
case to also use the same stream. Thus we will not permit a user to try
to have both an alpha stream AND a roman stream of the same letter case
at the same time.

The Renumber button checks for any nonmatched keys and only shows an error
dialog if any exist. Else it causes all Keys in the table to be renumbered
using the stream assigned to their class. This is a single-undo operation.

A Footnote Section is marked off using /F .. F/ markers (which are ignored by
the reflow code). The Move Notes button asks permission with a warning message.
On OK, it scans the document and makes a list of QTextCursors of the body of
all Footnote Sections. If none are found it shows an error and stops. If the 
last one found is above the last Note in the table, it shows an error and stops.
Else it scans the Notes in the table from bottom up. For each note, if the note
is not already inside a Footnote section, its contents are inserted at the
head of the Footnote section next below it and deleted at the 
original location. The QTextCursor in the table is repositioned.

The database of footnotes built by Refresh and shown in the table is cleared
on the DocHasChanged signal from pqMain, so it has to be rebuilt after any
book is loaded, and isn't saved. We should think about adding the footnote
info to the document metadata, but only if the Refresh operation proves to be
too lengthy to bear.

'''

from PyQt4.QtCore import (
    Qt,
    QAbstractTableModel,QModelIndex,
    QChar, QString, QStringList,
    QRegExp,
    QVariant,
    SIGNAL)
from PyQt4.QtGui import (
    QBrush, QColor,
    QComboBox,
    QItemDelegate,
    QSpacerItem,
    QTableView,
    QGroupBox,
    QHBoxLayout, QVBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextCursor,
    QWidget)
import pqMsgs

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# This code is global and relates to creating the "database" of footnotes.
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# Right, let's get some constants defined globally
# KeyClass_* gives sequential integer values to the classes.
KeyClass_IVX = 0
KeyClass_ABC = 1
KeyClass_ivx = 2
KeyClass_abc = 3
KeyClass_123 = 4
KeyClass_sym = 5
# name strings in KeyClass_* numeric order
KeyClassNames = (
    QString(u'IVX'),
    QString(u'ABC'),
    QString(u'ivx'),
    QString(u'abc'),
    QString(u'123'),
    QString(u'*\u00a4\u00a7') )
# stream names as a QStringList in KeyClass_* numeric order
# (used in comboboxes)
StreamNames = QStringList(QString(u'I,II..M')) << \
    QString(u'A,B,..ZZ') << \
    QString(u'i,ii..m') << \
    QString(u'a,b,..zz') << \
    QString(u'1,2,..999') << \
    QString(u'no renumber')
# class-detecting REs in KeyClass_* numeric order
ClassREs = (
    u'[IVXLCD]{1,15}', # ROMAN to DCCCCLXXXXVIII
    u'[A-Z]{1,2}',     # ALPHA to ZZ (should it be ZZZ?)
    u'[ivxlcd]{1,15}', # roman to whatever
    u'[a-z]{1,2}',     # alpha to zz (?)
    u'\d{1,3}',       # decimal to 999
    u'[\*\u00a4\u00a7\u00b6\u2020\u2021]' # star currency section para dagger dbl-dagger
    )

# The regex for finding a Ref to any possible Key class.
# (This is so pythonic I want to choke...)
RefFinderRE = QRegExp( u'\[(' + u'|'.join(ClassREs) + u')\]' )
# The similar regex for finding the head of a Note of any Key class.
NoteFinderRE = QRegExp( u'\[Footnote\s+(' + u'|'.join(ClassREs) + u')\s*\:' )

# Some notes about QTextCursors. A cursor is connected to a document (our main
# document) and has an anchor and a position. If .anchor() != .position() there
# is a selection. Qt doesn't care which is lower (closer to the top of the doc)
# but we take pains herein that .anchor() < .position(), i.e. the cursor is
# "positioned" at the end of the selection, the anchor at the start.

# Given a QTextCursor that selects a Reference, return its line number.
def refLineNumber(tc):
    if tc is not None:
        return tc.block().blockNumber() # block number for tc.position()
    return None

# Given a QTextCursor that selects a Note, return its line number, which is
# the block number for the anchor, not necessarily that of the position.
def noteLineNumber(tc):
    if tc is not None:
        return tc.document().findBlock(tc.anchor()).blockNumber()
    return None

# Given a QTextCursor that selects a Note, return the number of lines in it.
def noteLineLength(tc):
    if tc is not None:
        return 1 + tc.blockNumber() - \
            tc.document().findBlock(tc.anchor()).blockNumber() 
    return 0

# Given a QString that is a Key, return the class of the Key.
# single-class Regexes based on ClassREs above, tupled with the code.
ClassQRegExps = (
    (KeyClass_IVX, QRegExp(ClassREs[KeyClass_IVX])),
    (KeyClass_ABC, QRegExp(ClassREs[KeyClass_ABC])),
    (KeyClass_123, QRegExp(ClassREs[KeyClass_123])),
    (KeyClass_ivx, QRegExp(ClassREs[KeyClass_ivx])),
    (KeyClass_abc, QRegExp(ClassREs[KeyClass_abc])),
    (KeyClass_sym, QRegExp(ClassREs[KeyClass_sym]))
    )
def classOfKey(qs):
    for (keyclass,regex) in ClassQRegExps:
        if 0 == regex.indexIn(qs):
            return keyclass
    return None

# Given a QTextCursor that selects a Key (as in a Reference)
# return the class of the Key.
def classOfRefKey(tc):
    return classOfKey(tc.selectedText())

# Given a QTextCursor that selects a Note, return the note's key.
# We assume that tc really selects a Note so that noteFinderRE will
# definitely hit so we don't check its return. All we want is its cap(1).
def keyFromNote(tc):
    NoteFinderRE.indexIn(tc.selectedText())
    return NoteFinderRE.cap(1)

# Given a QTextCursor that selects a Note, return the class of its key.
def classOfNoteKey(tc):
    return classOfKey(keyFromNote(tc))

# Given a QTextCursor that selects a Note, return the leading characters,
# truncated at 40 chars, from the Note.
MaxNoteText = 40
def textFromNote(tc):
    qs = QString()
    if tc is not None:
        qs = tc.selectedText()
        if MaxNoteText < qs.size() :
            qs.truncate(MaxNoteText-3)
            qs.append(u'...')
    return qs

# The following is the database for the table of footnotes.
# This is empty on startup and after the DocHasChanged signal, then built
# by the Refresh button.

TheFootnoteList = [ ]

# Make a database item given ref and note cursors as available.
# Note we copy the text cursors so the caller doesn't have to worry about
# overwriting, reusing, or letting them go out of scope afterward.
def makeDBItem(reftc,notetc):
    keyqs = reftc.selectedText() if reftc is not None else keyFromNote(notetc)
    dbg = unicode(keyqs)
    dbg2 = noteLineNumber(notetc)
    dbg1 = refLineNumber(reftc)
    item = {'K': keyqs,
            'C': classOfKey(keyqs),
            'R': QTextCursor(reftc) if reftc is not None else None,
            'N': QTextCursor(notetc) if notetc is not None else None
            }
    return item

# Append a new matched footnote to the end of the database, given the
# cursors for the reference and the note. It is assumed this is called on
# a top-to-bottom sequential scan so entries will be added in line# sequence.

def addMatchedPair(reftc,notetc):
    TheFootnoteList.append(makeDBItem(reftc,notetc))

# insert an unmatched reference into the db in ref line number sequence.
# unmatched refs and notes are expected to be few, so a sequential scan is ok.
def insertUnmatchedRef(reftc):
    item = makeDBItem(reftc,None)
    j = refLineNumber(reftc)
    for i in range(len(TheFootnoteList)):
        if j <= refLineNumber(TheFootnoteList[i]['R']) :
            TheFootnoteList.insert(i,item)
            return
    TheFootnoteList.append(item)
# insert an unmatched note in note line number sequence.
def insertUnmatchedNote(notetc):
    item = makeDBItem(None,notetc)
    j = noteLineNumber(notetc)
    for i in range(len(TheFootnoteList)):
        if j <= noteLineNumber(notetc) :
            TheFootnoteList.insert(i,item)
            return
        TheFootnoteList.append(item)

# Based on the above spadework, do the Refresh operation
def theRealRefresh():
    global TheFootnoteList
    TheFootnoteList = [] # wipe the slate
    doc = IMC.editWidget.document() # get handle of document
    # initialize status message and progress bar
    barCount = doc.characterCount()
    pqMsgs.startBar(barCount * 2,"Scanning for notes and references")
    barBias = 0 
    # scan the document from top to bottom finding References and make a
    # list of them as textcursors. doc.find(re,pos) returns a textcursor
    # that .isNull on no hit.
    listOrefs = []
    findtc = QTextCursor(doc) # cursor that points to top of document
    findtc = doc.find(RefFinderRE,findtc)
    while not findtc.isNull() : # while we keep finding things
        # findtc now selects the whole reference [xx] but we want to only
        # select the key. This means incrementing the anchor and decrementing
        # the position; the means to do this are a bit awkward.
        a = findtc.anchor()+1
        p = findtc.position()-1
        findtc.setPosition(a,QTextCursor.MoveAnchor) #click..
        findtc.setPosition(p,QTextCursor.KeepAnchor) #..and drag
        listOrefs.append(QTextCursor(findtc))
        pqMsgs.rollBar(findtc.position())
        findtc = doc.find(RefFinderRE,findtc) # look for the next
    barBias = barCount
    pqMsgs.rollBar(barBias)
    # scan the document again top to bottom now looking for Notes, and make
    # a list of them as textcursors.
    listOnotes = []
    findtc = QTextCursor(doc) # cursor that points to top of document
    findtc = doc.find(NoteFinderRE,findtc)
    while not findtc.isNull():
        # findtc selects "[Footnote key:" now we need to find the closing
        # right bracket, which must be at the end of its line. We will go
        # by text blocks looking for a line that ends like this]
        pqMsgs.rollBar(findtc.anchor()+barBias)
        while True:
            # "drag" to end of line, selecting whole line
            findtc.movePosition(QTextCursor.EndOfBlock,QTextCursor.KeepAnchor)
            if findtc.selectedText().endsWith(u']') :
                break # now selecting whole note
            if findtc.block() == doc.lastBlock() :
                # ran off end of document looking for ...]
                findtc.clearSelection() # just forget this note, it isn't a note
                break # we could tell user, unterminated note. eh.
            else: # there is another line, step to its head and look again
                findtc.movePosition(QTextCursor.NextBlock,QTextCursor.KeepAnchor)
        if findtc.hasSelection() : # we did find the line ending in ]
            listOnotes.append(QTextCursor(findtc))
        findtc = doc.find(NoteFinderRE,findtc) # find next, fail at end of doc

    # Now, listOrefs is all the References and listOnotes is all the Notes,
    # both in sequence by document position. Basically, merge these lists.
    # For each Ref in sequence, find the first Note with a matching key at
    # a higher line number. If there is one, add the matched pair to the db,
    # and delete the note from its list. If there is no match, copy the
    # ref to a list of unmatched refs (because we can't del from the listOrefs
    # inside the loop over it).
    # This is not an MxN process despite appearances, as (a) most refs
    # will find a match, (b) most matches appear quickly and (c) we keep
    # shortening the list of notes.
    listOfOrphanRefs = []
    for reftc in listOrefs:
        hit = False
        refln = refLineNumber(reftc) # note line number for comparison
        for notetc in listOnotes:
            if 0 == reftc.selectedText().compare(keyFromNote(notetc)) and \
            refln < noteLineNumber(notetc) :
                hit = True
                break
        if hit : # a match was found
            addMatchedPair(reftc,notetc)
            listOnotes.remove(notetc)
        else:
            listOfOrphanRefs.append(reftc)
    # All the matches have been made (in heaven?). If there remain any
    # unmatched refs or notes, insert them in the db as well.
    for reftc in listOfOrphanRefs:
        insertUnmatchedRef(reftc)
    for notetc in listOnotes:
        insertUnmatchedNote(notetc)
    # clear the status and progress bar
    pqMsgs.endBar()

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# This code implements the Fnote table and its interactions.
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

# Implement a concrete table model by subclassing Abstract Table Model.
# The data served is derived from the TheFootnoteList, above.

class myTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super(myTableModel, self).__init__(parent)
        # The header texts for the columns
        self.headerDict = {
            0:"Key", 1:"Class", 2:"Ref line", 3:"Note Line", 4:"Length", 5:"Text"
        }
        # the text alignments for the columns
        self.alignDict = { 0:Qt.AlignCenter, 1: Qt.AlignCenter, 
                           2: Qt.AlignRight, 3: Qt.AlignRight,
                           4: Qt.AlignRight, 5: Qt.AlignLeft }
        # The values for tool/status tips for data and headers
        self.tipDict = { 0: "Actual key text",
                         1: "Assumed class of key for renumbering",
                         2: "Line number of the Reference",
                         3: "First line of the Footnote",
                         4: "Number of lines in the Footnote",
                         5: "Initial text of the Footnote" 
                         }
        # The brushes to painting the background of good and questionable rows
        self.whiteBrush = QBrush(QColor(QString('transparent')))
        self.pinkBrush = QBrush(QColor(QString('lightpink')))
        # Here save the expansion of one database item for convenient fetching
        self.lastRow = -1
        self.lastTuple = ()
        self.brushForRow = QBrush()
        
    def columnCount(self,index):
        if index.isValid() : return 0 # we don't have a tree here
        return 6

    def flags(self,index):
        f = Qt.ItemIsEnabled
        if index.column() ==1 :
            f |= Qt.ItemIsEditable # column 1 *only) editable
        return f
    
    def rowCount(self,index):
        if index.isValid() : return 0 # we don't have a tree here
        return len(TheFootnoteList) # initially 0
    
    def headerData(self, col, axis, role):
        if (axis == Qt.Horizontal) and (col >= 0):
            if role == Qt.DisplayRole : # wants actual text
                return QString(self.headerDict[col])
            elif (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
                return QString(self.tipDict[col])
        return QVariant() # we don't do that, whatever it is
    # This method is called whenever the table view wants to know practically
    # anything about the visible aspect of a table cell. The row & column are 
    # in the index, and what it wants to know is expressed by the role.
    def data(self, index, role ):
        # whatever it wants, we need the row data. Get it into self.lastTuple
        if index.row() != self.lastRow :
            # We assume Qt won't ask for any row outside 0..rowCount-1.
            # We TRUST it will go horizontally, hitting a row multiple times,
            # before going on to the next row.
            r = index.row()
            self.brushForRow = self.whiteBrush
            rtc = TheFootnoteList[r]['R']
            ntc = TheFootnoteList[r]['N']
            if (rtc is None) or (ntc is None):
                self.brushForRow = self.pinkBrush
            self.lastTuple = (
                TheFootnoteList[r]['K'], # key as a qstring
                KeyClassNames[TheFootnoteList[r]['C']], # class as qstring
                QString(unicode(refLineNumber(rtc))) if rtc is not None else QString("?"),
                QString(unicode(noteLineNumber(ntc))) if ntc is not None else QString("?"),
                QString(unicode(noteLineLength(ntc))),
                textFromNote(ntc)
                )
        # Now, what was it you wanted?
        if role == Qt.DisplayRole : # wants actual data
            return self.lastTuple[index.column()] # so give it.
        elif (role == Qt.TextAlignmentRole) :
            return self.alignDict[index.column()]
        elif (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
            return QString(self.tipDict[index.column()])
        elif (role == Qt.BackgroundRole) or (role == Qt.BackgroundColorRole):
            return self.brushForRow
        # don't support other roles
        return QVariant()
 
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# This code creates the Fnote panel and implements the other UI widgets.
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

# Used during renumbering: given an integer, return an upper- or
# lowercase roman numeral. Cribbed from Mark Pilgrim's "Dive Into Python".
romanNumeralMap = (('M',  1000),
                   ('CM', 900),
                   ('D',  500),
                   ('CD', 400),
                   ('C',  100),
                   ('XC', 90),
                   ('L',  50),
                   ('XL', 40),
                   ('X',  10),
                   ('IX', 9),
                   ('V',  5),
                   ('IV', 4),
                   ('I',  1))
def toRoman(n,lc):
    """convert integer to Roman numeral"""
    if not (0 < n < 5000):
        raise OutOfRangeError, "number out of range (must be 1..4999)"
    if int(n) <> n:
        raise NotIntegerError, "decimals can not be converted"
    result = ""
    for numeral, integer in romanNumeralMap:
        while n >= integer:
            result += numeral
            n -= integer
    qs = QString(result)
    if lc : return qs.toLower()
    return qs

class fnotePanel(QWidget):
    def __init__(self, parent=None):
        super(fnotePanel, self).__init__(parent)
        # Here we go making a layout. The outer shape is a vbox.
        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)
        # The following things are stacked inside the vbox.
        # 1, the Refresh button, left-justifed in an hbox.
        refreshLayout = QHBoxLayout()
        self.refreshButton = QPushButton("Refresh")
        refreshLayout.addWidget(self.refreshButton,0)
        refreshLayout.addStretch(1) # stretch on right left-aligns the button
        mainLayout.addLayout(refreshLayout)
        self.connect(self.refreshButton, SIGNAL("clicked()"), self.doRefresh)
        # 2, The table of footnotes, represented as a QTableView that displays
        # our myTableModel.
        self.view = QTableView()
        self.view.setCornerButtonEnabled(False)
        self.view.setWordWrap(False)
        self.view.setAlternatingRowColors(False)
        self.view.setSortingEnabled(False)
        mainLayout.addWidget(self.view,1) # It gets all stretch for the panel
        # create the table (empty just now) and display it
        self.table = myTableModel() # 
        self.view.setModel(self.table)
        # Connect the table view's clicked to our clicked slot
        self.connect(self.view, SIGNAL("clicked(QModelIndex)"), self.tableClick)
        # 3, an hbox containing 3 vboxes each containing 2 hboxes... ok, let's
        # start with 6 comboboxes, one for each class.
        self.pickIVX = self.makeStreamMenu(KeyClass_ABC) # initialize both IVX
        self.pickABC = self.makeStreamMenu(KeyClass_ABC) # ..and ABC to A,B
        self.pickivx = self.makeStreamMenu(KeyClass_abc) # similarly
        self.pickabc = self.makeStreamMenu(KeyClass_abc)
        self.pick123 = self.makeStreamMenu(KeyClass_123)
        self.picksym = self.makeStreamMenu()
        # while we are at it let us connect their signals to the methods
        # that enforce their behavior.
        self.connect(self.pickIVX, SIGNAL("activated(int)"),self.IVXpick)
        self.connect(self.pickABC, SIGNAL("activated(int)"),self.ABCpick)
        self.connect(self.pickivx, SIGNAL("activated(int)"),self.ivxpick)
        self.connect(self.pickabc, SIGNAL("activated(int)"),self.abcpick)
        # Now make 6 hboxes each containing a label and the corresponding
        # combobox.
        hbIVX = self.makePair(KeyClassNames[0],self.pickIVX)
        hbABC = self.makePair(KeyClassNames[1],self.pickABC)
        hbivx = self.makePair(KeyClassNames[2],self.pickivx)
        hbabc = self.makePair(KeyClassNames[3],self.pickabc)
        hb123 = self.makePair(KeyClassNames[4],self.pick123)
        hbsym = self.makePair(KeyClassNames[5],self.picksym)
        # Stack up the pairs in three attractive vboxes
        vbIA = self.makeStack(hbABC,hbIVX)
        vbia = self.makeStack(hbabc,hbivx)
        vbns = self.makeStack(hb123,hbsym)
        # Array them across a charming hbox and stick it in our panel
        hbxxx = QHBoxLayout()
        hbxxx.addLayout(vbIA)
        hbxxx.addLayout(vbia)
        hbxxx.addLayout(vbns)
        hbxxx.addStretch(1)
        mainLayout.addLayout(hbxxx)
        # Finally, the action buttons on the bottom in a frame.
        doitgb = QGroupBox("Actions")
        doithb = QHBoxLayout()
        self.renumberButton = QPushButton("Renumber")
        self.moveButton = QPushButton("Move Notes")
        doithb.addWidget(self.renumberButton,0)
        doithb.addStretch(1)
        doithb.addWidget(self.moveButton)
        doithb.addStretch(1)
        self.htmlButton = QPushButton("HTML Convert")
        doithb.addWidget(self.htmlButton)
        doitgb.setLayout(doithb)
        mainLayout.addWidget(doitgb)
        # and connect the buttons to actions
        self.connect(self.renumberButton, SIGNAL("clicked()"), self.renClick)
        self.connect(self.moveButton, SIGNAL("clicked()"), self.movClick)
        self.connect(self.htmlButton, SIGNAL("clicked()"), self.htmClick)

    def makeStreamMenu(self,choice=5):
        cb = QComboBox()
        cb.addItems(StreamNames)
        cb.setCurrentIndex(choice)
        return cb
    
    def makePair(self,qs,cb):
        hb = QHBoxLayout()
        hb.addWidget(QLabel(qs))
        hb.addWidget(cb)
        hb.addStretch(1)
        return hb
    def makeStack(self,pair1,pair2):
        vb = QVBoxLayout()
        vb.addLayout(pair1)
        vb.addLayout(pair2)
        vb.addStretch(1)
        return vb

    # The slot for a click of the Refresh button. Tell the table model we are
    # changing stuff; then call theRealRefresh; the tell table we're good.
    def doRefresh(self):
        self.table.beginResetModel()
        theRealRefresh()
        self.table.endResetModel()
        self.view.resizeColumnsToContents()
    
    # These slots are invoked when a stream choice is made for an ambiguous
    # class. They ensure that contradictory choices can't be made.

    # If the user sets the IVX stream to the same as the ABC stream, or
    # to no-renumber, fine. Otherwise, she is asserting that she has valid
    # IVX footnote keys, in which case ABC needs to be no-renumber.
    def IVXpick(self,pick):
        if (pick != self.pickABC.currentIndex()) or (pick != 5) :
            self.pickABC.setCurrentIndex(5)
    # If the user sets the ABC stream to anything but no-renumber, she is
    # asserting that there are valid ABC keys in which case, (keys we have
    # classed as) IVX need to use the same stream.
    def ABCpick(self,pick):
        if pick != 5 :
            self.pickIVX.setCurrentIndex(pick)
    # And similarly for lowercase.
    def ivxpick(self,pick):
        if (pick != self.pickabc.currentIndex()) or (pick != 5) :
            self.pickabc.setCurrentIndex(5)
    def abcpick(self,pick):
        if pick != 5 :
            self.pickivx.setCurrentIndex(pick)

    # The slot for a click anywhere in the tableview. If the click is on:
    # * column 0 or 1 (key or class) we jump to the ref line, unless we are on
    #   the ref line in which case we jump to the note line (ping-pong).
    # * column 2 (ref line) we jump to the ref line.
    # * column 3, 4, 5 (note line or note) we jump to the note line.
    def tableClick(self,index):
        r = index.row()
        c = index.column()
        dtc = IMC.editWidget.textCursor()
        rtc = TheFootnoteList[r]['R']
        ntc = TheFootnoteList[r]['N']
        targtc = None
        if c > 2 : # column 3 4 or 5
            targtc = ntc
        elif c == 2 :
            targtc = rtc
        else:
            dln = dtc.blockNumber()
            rln = refLineNumber(rtc) # None, if rtc is
            if dln == rln :
                targtc = ntc
            else:
                targtc = rtc
        if targtc is not None:
            IMC.editWidget.setTextCursor(targtc)
    
    # The slots for the main window's docWill/HasChanged signals.
    # Right now, just clear the footnote database, the user can hit
    # hit refresh when he wants the info. If the refresh proves to be
    # very small performance hit even in a very large book, we could
    # look at doing the refresh automatically after docHasChanged.
    def docWillChange(self):
        self.table.beginResetModel()
    def docHasChanged(self):
        TheFootnoteList = []
        self.table.endResetModel()

    # The slot for the Renumber button
    def renClick(self):
        pass

    # The slot for the Move button
    def movClick(self):
        pass

    # The slot for the HTML button
    def htmClick(self):
        pass
   
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
    widj = fnotePanel()
    MW = QMainWindow()
    MW.setCentralWidget(widj)
    pqMsgs.makeBarIn(MW.statusBar())
    MW.show()
    utqs = QString('''
This is text[A] with footnotes[2].
This is another[DCCCCLXXXXVIII] reference.
This is another[q] reference and[x] another.
A lame symbol[\u00a7] reference.
Ref to unmatched key[yy]
[Footnote A: footnote A which
extends onto 
three lines]
[Footnote zz: orphan note]
[Footnote 2: footnote 2 which has[A] a nested note]
[Footnote A: nested ref in note 2]
[Footnote DCCCCLXXXXVIII: footnote DCCCCLXXXXVIII]
[Footnote q: footnote q]
[Footnote \u00a7: footnote symbol]
    ''')
    IMC.editWidget.setPlainText(utqs)
    IMC.mainWindow = MW
    IMC.editWidget.show()
    app.exec_()