# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
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
Implement a Page database, a table with one row of metadata for each
scanned page image and the following columns:
0 A QTextCursor positioned at the first char of the page

1 The scan image filename without the .png suffix, typically
  but not necessarily a decimal string

2 A list of proofer name strings (some may be '')

3 Folio format, one of:
    IMC.FolioFormatArabic, IMC.FolioFormatUCRom, IMC.FolioFormatLCRom

4 Folio action, one of:
    IMC.FolioRuleAdd1, IMC.FolioRuleSet, IMC.FolioRuleSkip, IMC.FolioRuleSame

5 Folio value, 1-n or -1 for a Skipped folio

6 Folio display string, a QString like "5" or "xiv", or "" for skipped

The table is initialized by pqEdit reading metadata or actual page
separator lines. It is built in page sequence. The table is queried
by the Page Display (below) or by pqPngs to display page and folio values.

Based on the page table as a model, the Pages tab displays page
data to the user and allows editing folio information and inserting
folio strings into the document.

The table is implemented using a QAbstractTableView and QAbstractTableModel.
(Unlike the Char and Word panels we do not interpose a sort proxy; we build
the table in sequence and do not allow sorting of it.)
Columns are presented as follows:
0: Image scan number from 0 to n
1: Folio format: Same, Arabic, ROMAN, roman
2: Folio action: Add 1 Skip Set-to
3: Folio display value
4: proofers as a comma-delimited list

The AbstractTableModel is subclassed to provide user interactions:
* Doubleclicking column 0 causes the editor to reposition to that page
* A custom data delegate on col. 1 allows the user to change formats
* A custom data delegate on col. 2 allows the user to change commands
* A custom data delegate on col. 3 allows setting the folio as a spinbox
  -- setting the folio changes col. 2 to "set @" command

An Update button on the top row triggers a recalculation of the folios
based on the current formats, commands and values.

A text field and an Insert button allows inserting a string of text
at the cursor position of every page. "%f" in the  inserted string is
replaced with the formatted folio value on each insert.

The main windows DocWillChange and DocHasChanged signals are accepted
and used to warn the model of impending changes in metadata.
'''


from PyQt4.QtCore import (Qt,
                          QAbstractTableModel,QModelIndex,
                          QChar, QString,
                          QVariant,
                          SIGNAL)
from PyQt4.QtGui import (
    QComboBox,
    QItemDelegate,
    QSpacerItem,
    QTableView,
    QHBoxLayout, QVBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextCursor,
    QWidget)
import pqMsgs

# The following is from Mark Pilgrim's "Dive Into Python" slightly
# modified to return a QString and for upper or lower-case.
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
    if (0 < n < 5000) and int(n) == n :
        result = ""
        for numeral, integer in romanNumeralMap:
            while n >= integer:
                result += numeral
                n -= integer
    else : # invalid number, don't raise an exception
        result = "!!!!"
    qs = QString(result)
    if lc : return qs.toLower()
    return qs

# The table database, another (sigh) singleton class, but a class so we
# can put a handle to it in IMC.pageTable.
class pagedb(object):
    def __init__(self):
        # Each row might be a dict, which would make for clearer code, but
        # there might be 250 - 1000 of these; so many dicts each with its key hash.
        # So let's pretend we are coding in C...
        self._TheDB = []
        self._Cursor = 0 # the text cursor
        self._Scan = 1 # the scan filename
        self._Proofers = 2 # ['foo', 'bar'...]
        self._Fofor = 3 # folio format
        self._Foact = 4 # folio action
        self._Foval = 5 # folio integer
        self._Fodis = 6 # folio display
        self.clear()
    # Called from pqEdit
    def clear(self):
        self._TheDB = []
        self._last_format = None
        self._last_value = 0
        self._explict_formats = set()

    def size(self):
        return len(self._TheDB)

    # Return the various values. Using "getter" methods rather than
    # permitting callers to put grubby fingers into the database.
    def getCursor(self, index) :
        # Return the cursor that points to this page as maintained by Qt
        return self._TheDB[index][self._Cursor]
    def getScan(self, index) :
        # Return the name of the image file as qstring - a copy
        # of the qstring so if the caller messes with it, the change
        # will not appear in the db.
        return QString(self._TheDB[index][self._Scan])
    def getProoferList(self, index) :
        # return the proofers as a list of python strings, some null
        # (used by pqMain to export GG)
        return self._TheDB[index][self._Proofers]
    def getProoferString(self, index) :
        # Return proofers as a nicely formatted list
        return QString( ', '.join(self._TheDB[index][self._Proofers]) )
    def getActualFormat(self, index) :
        # Return the format code which may (most likely is) (same)
        return self._TheDB[index][self._Fofor]
    def getFormat(self, index) :
        # Return the format code, resolving (same) to the next higher
        # explicit format. We are sure there is at least one explicit
        # format because we require row 0 to not be (same).
        fcode = self._TheDB[index][self._Fofor]
        if fcode == IMC.FolioFormatSame :
            nearest_explicit = 0
            for an_index in self._explict_formats :
                if (an_index > nearest_explicit) and (an_index < index) :
                    nearest_explicit = an_index
            fcode = self._TheDB[nearest_explicit][self._Fofor]
        return fcode
    def getAction(self, index) :
        return self._TheDB[index][self._Foact]
    def getValue(self, index) :
        return self._TheDB[index][self._Foval]
    def getDisplay(self, index) :
        return QString(self._TheDB[index][self._Fodis])
    # Change the format code - called by the format code delegate
    # refresh the value display string immediately
    def setFormat(self, index, fcode):
        self._TheDB[index][self._Fofor] = fcode
        if fcode != IMC.FolioFormatSame :
            # explicit format, add to set of explicit rows
            self._explict_formats.add(index)
        else :
            # changing to (same), remove from set if it is in there
            self._explict_formats.discard(index)
        self._TheDB[index][self._Fodis] = self.formatFolio(index)
    # Change the action code - called by the action delegate.
    # Since setting the action to skip affects the display, redo the display.
    def setAction(self, index, action) :
        self._TheDB[index][self._Foact] = action
        self._TheDB[index][self._Fodis] = self.formatFolio(index)
    # Change the value - called by the folio delegate and the Update loop
    # Keep the display string in step.
    def setValue(self, index, number) :
        self._TheDB[index][self._Foval] = number
        self._TheDB[index][self._Fodis] = self.formatFolio(index)
    # Set the cursor position - called from the insert operation to correct
    # cursor position after insert
    def setPosition(self, index, number) :
        self._TheDB[index][self._Cursor].setPosition(number)

    # Return the properly formatted folio value as a QString, based on the
    # format code and action code of that row.
    def formatFolio(self, index):
        if self.getAction(index) != IMC.FolioRuleSkip :
            fcode = self.getFormat(index)
            number = self.getValue(index)
            if fcode == IMC.FolioFormatArabic :
                return QString(repr(number))
            else : # upper or lowercase roman
                return toRoman(number, fcode == IMC.FolioFormatLCRom)
        else : # skipped row
            return QString()

    # Called from pqEdit with the important bits from an actual psep line like
    # -----File: 0002.png---\joe\sam\bertha\\fred
    # This is brand-new metadata so assign Arabic, Set-to, 1 to the first row
    # and assign (same), Add 1, n to all the others.
    def loadPsep(self, tc, qsFile, qs_proofers) :
        # Little-known Python fact: in a string \b (like the start of \bertha above)
        # actually stands for the BEL code, \x08. Hence we cannot take the PGDP
        # proofer string into Python and split it on \, we would get "sam\x08ertha"
        # from the above example. So first use QString.replace \ with comma.
        # Also drop the leading \ to avoid a null list item.
        qs_proofers = qs_proofers.remove(0,1)
        qs_proofers = qs_proofers.replace(QChar(u'\\'),QChar(u','))
        proofers = unicode(qs_proofers).split(',') # list of names
        new_row = [tc, QString(qsFile), proofers, 0, 0, 0, 0]
        if self.size() :
            # not the first row in an empty DB
            new_row[self._Fofor] = IMC.FolioFormatSame
            new_row[self._Foact] = IMC.FolioRuleAdd1
        else : # size of 0: first row
            new_row[self._Fofor] = IMC.FolioFormatArabic
            new_row[self._Foact] = IMC.FolioRuleSet
            self._explict_formats.add(0) #initialize set to one member
        self._TheDB.append(new_row)
        index = self._last_value
        self._last_value += 1
        self.setValue(index, self._last_value) # also updates display value

    # Called from pqEdit while writing the metadata file to return a given
    # page table row as a qstring suitable for the metadata file.
    # For compatibility with old files we turn the proofer list back to
    # backlash delimiters and convert (same) formats to actual formats.
    # Because we know that index increases 0..n we can keep track of the last
    # explicit format seen and not have to go through self.getFormat().
    def metaStringOut(self, index) :
        row = self._TheDB[index]
        fcode = row[self._Fofor]
        if fcode == IMC.FolioFormatSame :
            fcode = self._last_format
        else :
            # not ditto, note latest real format
            self._last_format = fcode
        pos = row[0].position() # get position from textcursor
        fn = unicode(row[1]) # image file name as python
        proofers = '\\'+'\\'.join(row[2]) # proofers back to old style
        ret = "{0} {1} {2} {3} {4} {5}\n".format(pos, fn, proofers, row[self._Foact], fcode, row[self._Foval] )
        return QString(ret)

    # Process a metadata string like the one created just above (but possibly
    # from a legacy .meta file). This only happens while building a new page table
    # from a .meta file, so make a new row and append it. Convert sequences of
    # duplicate formats to (same).
    def metaStringIn(self, qline) :
        parts = unicode(qline).split(' ')
        tc = QTextCursor(IMC.editWidget.document())
        tc.setPosition(int(parts[0]))
        # see comments on proofer string in loadPsep above.
        qs_proofers = QString(parts[2])
        qs_proofers = qs_proofers.remove(0,1)
        qs_proofers = qs_proofers.replace(QChar(u'\\'),QChar(u','))
        proofers = unicode(qs_proofers).split(',')
        row = [tc, QString(parts[1]), proofers, 0, 0, 0, 0]
        index = self.size() # index of row to be
        row[self._Foact] = int(parts[3])
        fcode = int(parts[4])
        if fcode != self._last_format :
            # either row 0 and self._last_format is None, or a change of format
            self._last_format = fcode
            # put index of row we are about to add, into set of explicit formats
            self._explict_formats.add(self.size())
        else :
            fcode = IMC.FolioFormatSame
        row[self._Fofor] = fcode
        self._TheDB.append(row)
        self.setValue(index, int(parts[5]) ) # also updates display

# These are global items so that both the table model and the custom delegates
# can access them.

ActionItems = [ QString("Add 1"), QString("Set to n"), QString("Skip folio") ]
FormatItems = [ QString("Arabic"), QString("ROMAN"), QString("roman"), QString("(same)") ]

# Implement a concrete table model by subclassing Abstract Table Model.
# The data served is derived from the page separator table prepared as
# metadata in the editor.
class myTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super(myTableModel, self).__init__(parent)
        # The header texts for the columns
        self.headerDict = { 0:"Scan#", 1:"Format", 2:"Action", 3:"Folio", 4:"Proofers" }
        # the text alignments for the columns
        self.alignDict = { 0:Qt.AlignRight, 1: Qt.AlignLeft,
                           2: Qt.AlignLeft, 3: Qt.AlignRight, 4: Qt.AlignLeft }
        # The values for tool/status tips for data and headers
        self.tipDict = { 0: "Scan image (file) number",
                         1: "Folio numeric format",
                         2: "Folio action: skip, set, +1",
                         3: "Folio (page) number",
                         4: "Proofer user-ids" }

    def columnCount(self,index):
        if index.isValid() : return 0 # we don't have a tree here
        return 5

    def flags(self,index):
        f = Qt.ItemIsEnabled
        if (index.column() >=1) and (index.column() <= 3) :
            f |= Qt.ItemIsEditable # cols 1-3 editable
        return f

    def rowCount(self,index):
        if index.isValid() : return 0 # we don't have a tree here
        return IMC.pageTable.size() # initially 0

    def headerData(self, col, axis, role):
        if (axis == Qt.Horizontal) and (col >= 0):
            if role == Qt.DisplayRole : # wants actual text
                return QString(self.headerDict[col])
            elif (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
                return QString(self.tipDict[col])
        return QVariant() # we don't do that

    def data(self, index, role ):
        if role == Qt.DisplayRole : # wants actual data
            c = index.column()
            r = index.row()
            if c == 0:
                return IMC.pageTable.getScan(r) # qstring of file #
            elif c == 1:
                return FormatItems[IMC.pageTable.getActualFormat(r)] # name for format code
            elif c == 2:
                return ActionItems[IMC.pageTable.getAction(r)] # name for action code
            elif c == 3: # return folio formatted per rule
                return IMC.pageTable.getDisplay(r)
            elif c == 4:
                return IMC.pageTable.getProoferString(r)
            else: return QVariant()
        elif (role == Qt.TextAlignmentRole) :
            return self.alignDict[index.column()]
        elif (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
            return QString(self.tipDict[index.column()])
        # don't support other roles
        return QVariant()

    # Called when the update button is clicked, run through the page table
    # and reset folio values based on the folio rules.
    def updateFolios(self):
        self.beginResetModel()
        folio = 0
        fmt = None
        for i in range(IMC.pageTable.size()):
            action = IMC.pageTable.getAction(i)
            if action == IMC.FolioRuleAdd1 :
                folio += 1
                IMC.pageTable.setValue(i, folio)
            elif action == IMC.FolioRuleSet :
                folio = IMC.pageTable.getValue(i)
            else : # FolioRuleSkip
                assert action == IMC.FolioRuleSkip
                IMC.pageTable.setValue(i, -1)
        self.endResetModel()
        IMC.needMetadataSave |= IMC.pagePanelChanged
        IMC.mainWindow.setWinModStatus()

# A quick summary of WTF a custom delegate is: an object that represents a
# type of data when an instance of that type needs to be displayed or edited.
# The delegate must implement 3 methods:
# createEditor() returns a widget that the table view will position in the
#    table cell to act as an editor;
# setEditorData() initializes the editor widget with data to display;
# setModelData() is called when editing is complete, to store possibly
#    changed data back to the model.

# Implement a custom data delegate for column 1, format code
# Our editor is a combobox with the four choices in it (or three,
# on row 0 where "Same" is not permitted).
class formatDelegate(QItemDelegate):
    def createEditor(self, parent, style, index):
        if index.column() != 1 : return None
        cb = QComboBox(parent)
        # Add choices but not "(same)" on row 0
        cb.addItems(FormatItems[:4 if index.row() else 3])
        return cb
    def setEditorData(self,cb,index):
        v = IMC.pageTable.getFormat(index.row())
        cb.setCurrentIndex(v)
    def setModelData(self,cb,model,index):
        IMC.pageTable.setFormat(index.row(), cb.currentIndex())
        IMC.needMetadataSave |= IMC.pagePanelChanged
        IMC.mainWindow.setWinModStatus()

# Implement a custom delegate for column 2, folio action.
# The editor is a combobox with the three choices in it.
class actionDelegate(QItemDelegate):
    def createEditor(self, parent, style, index):
        if index.column() != 2 : return None
        cb = QComboBox(parent)
        cb.addItems(ActionItems)
        return cb
    def setEditorData(self,cb,index):
        v = IMC.pageTable.getAction(index.row())
        cb.setCurrentIndex(v)
    def setModelData(self,cb,model,index):
        IMC.pageTable.setAction(index.row(),cb.currentIndex())
        IMC.needMetadataSave |= IMC.pagePanelChanged
        IMC.mainWindow.setWinModStatus()

# Implement a custom delegate for column 3, the folio value,
# as a spinbox - why not, likely only small adjustments are needed.
# When the folio value changes, the View calls setModelData. Since
# the user has set the folio, make sure the action for that row is Set@
class folioDelegate(QItemDelegate):
    def createEditor(self, parent, style, index):
        if index.column() != 3 : return None
        sb = QSpinBox(parent)
        sb.setMaximum(2000)
        return sb
    def setEditorData(self,sb,index):
        sb.setValue(IMC.pageTable.getValue(index.row()))
    def setModelData(self,sb,model,index):
        IMC.pageTable.setValue(index.row(), sb.value() )
        IMC.pageTable.setAction(index.row(), IMC.FolioRuleSet )
        IMC.needMetadataSave |= IMC.pagePanelChanged


class pagesPanel(QWidget):
    def __init__(self, parent=None):
        super(pagesPanel, self).__init__(parent)
        # The layout is very basic, the table with an Update button.
        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)
        hlayout = QHBoxLayout()
        self.updateButton = QPushButton("Update")
        self.insertText = QLineEdit()
        self.insertText.setFont(pqMsgs.getMonoFont())
        self.insertButton = QPushButton("Insert")
        hlayout.addWidget(self.updateButton,0)
        hlayout.addWidget(self.insertText,1) # text gets all available room
        hlayout.addWidget(self.insertButton,0)
        mainLayout.addLayout(hlayout)
        self.view = QTableView()
        self.view.setCornerButtonEnabled(False)
        self.view.setWordWrap(False)
        self.view.setAlternatingRowColors(True)
        self.view.setSortingEnabled(False)
        self.c1Delegate = formatDelegate()
        self.view.setItemDelegateForColumn(1,self.c1Delegate)
        self.c2Delegate = actionDelegate()
        self.view.setItemDelegateForColumn(2,self.c2Delegate)
        self.c3Delegate = folioDelegate()
        self.view.setItemDelegateForColumn(3,self.c3Delegate)
        mainLayout.addWidget(self.view,1)
        # Set up the table model/view.
        self.model = myTableModel()
        self.view.setModel(self.model)
        # Connect the double-clicked signal of the view
        self.connect(self.view, SIGNAL("doubleClicked(QModelIndex)"),
                    self.goToRow)
        # Connect the update button to the model's update method
        self.connect(self.updateButton, SIGNAL("clicked()"),self.model.updateFolios)
        # Connect the insert button to our insert method
        self.connect(self.insertButton, SIGNAL("clicked()"),self.insertMarkers)

    # This slot receives a double-click from the table view,
    # passing an index. If the click is in column 0, the scan number,
    # get the row; use it to get a text cursor from the page table
    # and make that the editor's cursor, thus moving to the top of that page.
    # Double-click on cols 1-3 initiates editing and maybe someday a
    # doubleclick on column 5 will do something with the proofer info.
    def goToRow(self,index):
        if index.column() == 0:
            tc = IMC.pageTable.getCursor(index.row())
            IMC.editWidget.setTextCursor(tc)
            IMC.editWidget.setFocus(Qt.TabFocusReason)

    # This slot receives the main window's docWillChange signal.
    # It comes with a file path but we can ignore that.
    def docWillChange(self):
        self.model.beginResetModel()

    # Subroutine to reset the visual appearance of the table view,
    # invoked on table reset because on instantiation we have no table.
    def setUpTableView(self):
        # Header text is supplied by the table model headerData method
        # Here we are going to set the column widths of the first 4
        # columns to a uniform 7 ens each based on the current font.
        # However, at least on Mac OS, the headers are rendered with a
        # much smaller font than the data, so we up it by 50%.
        hdr = self.view.horizontalHeader()
        pix = hdr.fontMetrics().width(QString("9999999"))
        hdr.resizeSection(0,pix)
        hdr.resizeSection(3,pix)
        pix += pix/2
        hdr.resizeSection(1,pix)
        hdr.resizeSection(2,pix)
        self.view.resizeColumnToContents(4)

    # This slot receives the main window's docHasChanged signal.
    # Let the table view populate with all-new metadata (or empty
    # data if the command was File>New).
    def docHasChanged(self):
        self.model.endResetModel()
        self.setUpTableView()

    # On the Insert button being pressed, make some basic sanity checks
    # and get user go-ahead then insert the given text at the head of
    # every page.
    def insertMarkers(self):
        # Copy the text and if it is empty, complain and exit.
        qi = QString(self.insertText.text())
        if qi.isEmpty() :
            pqMsgs.warningMsg("No insert text specified")
            return
        # See how many pages are involved: all the ones that aren't marked skip
        n = 0
        for i in range(IMC.pageTable.size()):
            if IMC.pageTable.getAction(i) != IMC.FolioRuleSkip :
                n += 1
        if n == 0 : # page table empty or all rows marked skip
            pqMsgs.warningMsg("No pages to give folios to")
            return
        m = "Insert this string at the top of {0} pages?".format(n)
        b = pqMsgs.okCancelMsg(QString(m),pqMsgs.trunc(qi,35))
        if b :
            # Convert any '\n' in the text to the QT line delimiter char
            # we do this in the copy so the lineEdit text doesn't change
            qi.replace(QString(u'\\n'),QString(IMC.QtLineDelim))
            # get a cursor on the edit document
            tc = QTextCursor(IMC.editWidget.textCursor())
            tc.beginEditBlock() # start single undoable operation
            # Working from the end of the document backward, go to the
            # top of each page and insert the string
            for i in reversed( range( IMC.pageTable.size() ) ) :
                if IMC.pageTable.getAction(i) != IMC.FolioRuleSkip :
                    # Note the page's start position and set our work cursor to it
                    pos = IMC.pageTable.getCursor(i).position()
                    tc.setPosition(pos)
                    # Make a copy of the insert string replacing %f with this folio
                    f = IMC.pageTable.getDisplay(i)
                    qf = QString(qi)
                    qf.replace(QString(u'%f'),f,Qt.CaseInsensitive)
                    tc.insertText(qf)
                    # The insertion goes in ahead of the saved cursor position so now
                    # it points after the inserted string. Put it back where it was.
                    IMC.pageTable.setPosition(i, pos)
            tc.endEditBlock() # wrap up the undo op


if __name__ == "__main__":
    def setWinModStatus():
        print(IMC.needMetadataSave)
    import sys
    from PyQt4.QtGui import (QApplication,QFileDialog,QMainWindow,QPlainTextEdit, QTextCursor)
    from PyQt4.QtCore import (QFile, QTextStream, QString, QRegExp)
    app = QApplication(sys.argv) # create the app
    import pqIMC
    IMC = pqIMC.tricorder()
    import pqMsgs
    pqMsgs.IMC = IMC
    IMC.fontFamily = QString(u"Courier")
    IMC.editWidget = QPlainTextEdit()
    IMC.pageTable = pagedb()
    widj = pagesPanel()
    MW = QMainWindow()
    IMC.mainWindow = MW
    MW.setCentralWidget(widj)
    MW.setWinModStatus = setWinModStatus
    MW.show()
    fn = QFileDialog.getOpenFileName(None,"Select a Test Book")
    print(fn)
    fh = QFile(fn)
    if not fh.open(QFile.ReadOnly):
        raise IOError, unicode(fh.errorString())
    stream = QTextStream(fh)
    stream.setCodec("UTF-8")
    IMC.editWidget.setPlainText(stream.readAll()) # load the editor doc
    widj.docWillChange()
    # Code from pqEdit to parse a doc by lines and extract page seps.
    reLineSep = QRegExp(u'-----File: ([^\\.]+)\\.png---((\\\\[^\\\\]*)+)\\\\-*',Qt.CaseSensitive)
    qtb = IMC.editWidget.document().begin() # first text block
    IMC.pageTable.clear()
    while qtb != IMC.editWidget.document().end(): # up to end of document
        qsLine = qtb.text() # text of line as qstring
        if reLineSep.exactMatch(qsLine): # a page separator
            qsfilenum = reLineSep.capturedTexts()[1]
            qsproofers = reLineSep.capturedTexts()[2]
            # proofer names can contain spaces, replace with en-space char
            qsproofers.replace(QChar(" "),QChar(0x2002))
            tcursor = QTextCursor(IMC.editWidget.document())
            tcursor.setPosition(qtb.position())
            IMC.pageTable.loadPsep(tcursor, qsfilenum, qsproofers)
        # ignore non-seps
        qtb = qtb.next()
    widj.docHasChanged()
    app.exec_()
