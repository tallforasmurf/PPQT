# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.01.0" # refer to PEP-0008
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
Implement the Page table, based on IMC.pageTable, and allow inserting
Folio strings in the document. The actual data is a simple Python list of lists,
each member having:

0: a QTextCursor positioned before the first character of the page
    -- text cursors are updated by their document as the text changes
1: the file number (digits preceding ".png") as a QString
2: the proofer-name section as a QString, possibly with extra hyphens
3: the current folio rule or action, one of:
    IMC.FolioRuleAdd1, IMC.FolioRuleSet, IMC.FolioRuleSkip
4: the current folio format, one of:
    IMC.FolioFormatArabic, IMC.FolioFormatUCRom, IMC.FolioFormatLCRom
    Question: do we need UCAlpha/LCAlpha formats?
5: the current folio value
As initially created (when a book is first read), every folio 
tuple is Add1, Arabic, and a sequential number.

The table is implemented using a Qt AbstractTableView, and AbstractTableModel.
(Unlike the Char and Word panels we do not interpose a sort proxy; we build
the table in sequence and do not allow sorting of it.) The AbstractTableModel
is subclassed to implement fetching data from the IMC.pageTable list.
Columns are presented as follows:
0: Page (i.e. scan or row) number from 0 to n
1: Folio format: Arabic ROMAN roman
2: Folio action: Add 1 Skip Set-to
3: Folio value
4: proofer string 

The AbstractTableModel is subclassed to provide user interactions:
* Doubleclicking any row causes the editor to reposition to that page
* A custom data delegate on col. 1 allows the user to change formats
* A custom data delegate on col. 2 allows the user to change commands
* A custom data delegate on col. 3 allows setting the folio as a spinbox
  -- setting the folio changes col. 2 to "set @" command

An update button on the top row triggers a recalculation of the folios
based on the current formats, commands and values.

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

# These are global items so that both the table model and the custom delegates
# can access them.

ActionItems = [QString("Add 1"),QString("Set to n"),QString("Skip folio")]
FormatItems = [QString("Arabic"),QString("ROMAN"), QString("roman")]

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
    if not (0 < n < 5000):
        raise ValueError, "number out of range (must be 1..4999)"
    if int(n) <> n:
        raise TypeError, "decimals can not be converted"
    result = ""
    for numeral, integer in romanNumeralMap:
        while n >= integer:
            result += numeral
            n -= integer
    qs = QString(result)
    if lc : return qs.toLower()
    return qs

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
        # translation of folio actions and formats to text
        self.lastRow = -1
        self.lastTuple = (None,None,None,None,None,None)
        
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
        return len(IMC.pageTable) # initially 0
    
    def headerData(self, col, axis, role):
        if (axis == Qt.Horizontal) and (col >= 0):
            if role == Qt.DisplayRole : # wants actual text
                return QString(self.headerDict[col])
            elif (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
                return QString(self.tipDict[col])
        return QVariant() # we don't do that
    
    def data(self, index, role ):
        if role == Qt.DisplayRole : # wants actual data
            if index.row() != self.lastRow :
                self.lastTuple = IMC.pageTable[index.row()]
            c = index.column()
            if c == 0:
                return self.lastTuple[1] # qstring of file #
            elif c == 1:
                return FormatItems[self.lastTuple[4]] # name for format code
            elif c == 2:
                return ActionItems[self.lastTuple[3]] # name for action code
            elif c == 3: # return folio formatted per rule
                if self.lastTuple[5] >= 0 : # not being skipped
                    if self.lastTuple[4] == IMC.FolioFormatArabic :
                        return QString("{0}".format(self.lastTuple[5]))
                    else:
                        return toRoman(self.lastTuple[5],
                                       self.lastTuple[4] == IMC.FolioFormatLCRom)
                else:
                    return QString(" ")
            elif c == 4:
                return self.lastTuple[2]
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
        f = 0
        for i in range(len(IMC.pageTable)):
            r = IMC.pageTable[i][3]
            if r == IMC.FolioRuleAdd1 :
                f += 1
                IMC.pageTable[i][5] = f
            elif r == IMC.FolioRuleSet :
                f = IMC.pageTable[i][5]
            elif r == IMC.FolioRuleSkip :
                IMC.pageTable[i][5] = -1
            else:
                raise Error
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
# Our editor is a combobox with the three choices in it.
class formatDelegate(QItemDelegate):
    def createEditor(self, parent, style, index):
        if index.column() != 1 : return None
        cb = QComboBox(parent)
        cb.addItems(FormatItems)
        return cb
    def setEditorData(self,cb,index):
        v = IMC.pageTable[index.row()][4]
        cb.setCurrentIndex(v)
    def setModelData(self,cb,model,index):
        IMC.pageTable[index.row()][4] = cb.currentIndex()
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
        v = IMC.pageTable[index.row()][3]
        cb.setCurrentIndex(v)
    def setModelData(self,cb,model,index):
        IMC.pageTable[index.row()][3] = cb.currentIndex()
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
        return sb
    def setEditorData(self,sb,index):
        sb.setValue(IMC.pageTable[index.row()][5])
    def setModelData(self,sb,model,index):
        IMC.pageTable[index.row()][5] = sb.value()
        IMC.pageTable[index.row()][3] = IMC.FolioRuleSet
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
            tc = IMC.pageTable[index.row()][0]
            IMC.editWidget.setTextCursor(tc)
    
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
        for i in range(len(IMC.pageTable)):
            if IMC.pageTable[i][3] != IMC.FolioRuleSkip :
                n += 1
        if n == 0 : # page table empty or all rows marked skip
            pqMsgs.warningMsg("No pages to give folios to")
            return
        m = "Insert this string at the top of {0} pages?".format(n)
        b = pqMsgs.okCancelMsg(QString(m),pqMsgs.trunc(qi,35))
        if b :  
            # Convert any '\n' in the text to the QT line delimiter char
            # we do this in the copy so the lineEdit text doesn't change
            dbg = unicode(qi)
            qi.replace(QString(u'\\n'),QString(IMC.QtLineDelim))
            dbg = unicode(qi)
            # get a cursor on the edit document
            tc = QTextCursor(IMC.editWidget.textCursor())
            tc.beginEditBlock() # start single undoable operation
            # Working from the end of the document backward, go to the
            # top of each page and insert the string
            for i in reversed(range(len(IMC.pageTable))) :
                page = IMC.pageTable[i]
                if page[3] is not IMC.FolioRuleSkip :
                    # set our text cursor to that page's start
                    tc.setPosition(page[0].position())
                    # update our string with the current folio
                    if page[4] == IMC.FolioFormatArabic :
                        f = QString(u"{0}".format(page[5]))
                    else:
                        f = toRoman(page[5], page[4] == IMC.FolioFormatLCRom)
                    qf = QString(qi)
                    qf.replace(QString(u'%f'),f,Qt.CaseInsensitive)
                    tc.insertText(qf)
            tc.endEditBlock() # wrap up the undo op


# Unit test code fairly elaborate due to learning curve for delegates

if __name__ == "__main__":
    import sys
    from PyQt4.QtGui import (QApplication,QFileDialog,QPlainTextEdit, QTextCursor)
    from PyQt4.QtCore import (QFile, QTextStream, QString, QRegExp)
    app = QApplication(sys.argv) # create the app
    import pqIMC
    IMC = pqIMC.tricorder()
    import pqMsgs
    pqMsgs.IMC = IMC
    IMC.fontFamily = QString(u"Courier")
    IMC.editWidget = QPlainTextEdit()
    IMC.pageTable = []
    widj = pagesPanel()
    IMC.mainWindow = widj
    widj.show()
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
    reLineSep = QRegExp("^-----File:\s*(\d+)\.png---(.+)(-+)$",Qt.CaseSensitive)
    reTrailDash = QRegExp("-+$")
    iFolio = 0 # really, page number
    qtb = IMC.editWidget.document().begin() # first text block
    while qtb != IMC.editWidget.document().end(): # up to end of document
        qsLine = qtb.text() # text of line as qstring
        if reLineSep.exactMatch(qsLine): # a page separator
            qsfilenum = reLineSep.capturedTexts()[1]
            qsproofers = reLineSep.capturedTexts()[2]
            # proofer names can contain spaces, replace with en-space char
            qsproofers.replace(QChar(" "),QChar(0x2002))
            j = reTrailDash.indexIn(qsproofers)
            if j > 0: # get rid of trailing dashes
                qsproofers.truncate(j)
            tcursor = QTextCursor(IMC.editWidget.document())
            tcursor.setPosition(qtb.position())
            iFolio += 1
            IMC.pageTable.append(
    [tcursor, qsfilenum, qsproofers, IMC.FolioRuleAdd1, IMC.FolioFormatArabic, iFolio]
                                      )
        # ignore non-seps
        qtb = qtb.next()
    widj.docHasChanged()
    app.exec_()
