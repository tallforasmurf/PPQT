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
Implement the Character Census panel. At the top a row with a Refresh
button on the left and a filter combobox on the right. Below, a table
with five columns:
* Glyph, the character 
* Value, the character's unicode value in hex
* Count, the number times it appears in the document
* Entity, the HTML named or numeric entity value
* Category, the QChar.category() in words.
The table is implemented using a Qt AbstractTableView, SortFilterProxyModel,
and AbstractTableModel. The AbstractTableModel is subclassed to implement
fetching data from the IMC.charCensus list. The AbstractTableModel is used
as-is, but the SortFilterProxyModel is subclassed to provide the filtering
mechanism. Filters for not-7-bit and not-Latin-1 are implemented as 
lambda expressions on the QChar from column 0. When the user selects a
row in the popup, we change the filter lambda and reset the model, forcing
all rows to be re-fetched.

The main window's DocWillChange and DocHasChanged signals are accepted
and used to warn the model of impending changes in metadata.
'''

from PyQt4.QtCore import (Qt,
                          QAbstractTableModel,QModelIndex,
                          QChar, QString, 
                          QVariant,
                          SIGNAL)
from PyQt4.QtGui import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QSortFilterProxyModel,
    QSpacerItem,
    QTableView,
    QVBoxLayout,
    QHeaderView,
    QWidget)

# Implement a concrete table model by subclassing Abstract Table Model.
# The data served is derived from the character census prepared as 
# metadata in the editor.
class myTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super(myTableModel, self).__init__(parent)
        # The header texts for the columns
        self.headerDict = { 0:"Glyph", 1:"Value",
                            2:"Count", 3:"Entity", 4:"Unicode Category" }
        # the text alignments for the columns
        self.alignDict = { 0:Qt.AlignHCenter, 1: Qt.AlignRight,
                           2:Qt.AlignRight, 3: Qt.AlignLeft, 4:Qt.AlignLeft }
        # The values for tool/status tips for data and headers
        self.tipDict = { 0: "Character glyph",
                         1: "Unicode value in hex",
                         2: "Number of occurrences",
                         3: "HTML/XML Entity code",
                         4: "Unicode category" }
        # The strings that interpret a QChar.category value
        self.catDict = {  0: "NoCategory",
                          1: "Mark_NonSpacing", 2: "Mark_SpacingCombining",
                          3: "Mark_Enclosing", 4: "Number_DecimalDigit",
                          5: "Number_Letter", 6: "Number_Other",
                          7: "Separator_Space", 8: "Separator_Line",
                          9: "Separator_Paragraph", 10: "Other_Control",
                         11: "Other_Format", 12: "Other_Surrogate",
                         13: "Other_PrivateUse", 14: "Other_NotAssigned",
                         15: "Letter_Uppercase", 16: "Letter_Lowercase",
                         17: "Letter_Titlecase", 18: "Letter_Modifier",
                         19: "Letter_Other", 20: "Punctuation_Connector",
                         21: "Punctuation_Dash", 22: "Punctuation_Open",
                         23: "Punctuation_Close", 24: "Punctuation_InitialQuote",
                         25: "Punctuation_FinalQuote", 26: "Punctuation_Other",
                         27: "Symbol_Math", 28: "Symbol_Currency",
                         29: "Symbol_Modifier", 30: "Symbol_Other"
                         }

    def columnCount(self,index):
        if index.isValid() : return 0 # we don't have a tree here
        return 5 # glyph, hex, count, entity, category
    
    def flags(self,index):
        return Qt.ItemIsEnabled
    
    def rowCount(self,index):
        if index.isValid() : return 0 # we don't have a tree here
        return IMC.charCensus.size() # initially 0
    
    def headerData(self, col, axis, role):
        if (axis == Qt.Horizontal) and (col >= 0):
            if role == Qt.DisplayRole : # wants actual text
                return QString(self.headerDict[col])
            elif (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
                return QString(self.tipDict[col])
        return QVariant() # we don't do that
    
    def data(self, index, role ):
        if role == Qt.DisplayRole : # wants actual data
            (qs,count,flag) = IMC.charCensus.get(index.row())
            ui = qs.at(0).unicode() # gets an integer
            uu = unicode(qs)[0] # gets a uchar
            if 0 == index.column():
                return qs
            elif 1 == index.column():
                return QString("0x{0:04x}".format(ui))
            elif 2 == index.column():
                return count
            elif 3 == index.column():
                if uu in IMC.namedEntityDict :
                    return QString("&"+IMC.namedEntityDict[uu]+";")
                else:
                    return QString("&#{0:d};".format(ui))
            else:
                return QString(self.catDict[int(flag)])
        elif (role == Qt.TextAlignmentRole) :
            return self.alignDict[index.column()]
        elif (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
            return QString(self.tipDict[index.column()])
        # don't support other roles
        return QVariant()

# Customize a sort/filter proxy by making its filterAcceptsRow method
# test the character in that row against a filter function in the parent.

class mySortFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super(mySortFilterProxy, self).__init__(parent)
        self.parent = parent # save pointer to the panel widget
        
    # Get the data from column 0 of row, and apply the lambda in
    # parent.filterLambda to it. The model/view abstractions get really thick
    # here: go to the parent for an index to the row/column, then go back to
    # the parent for the data for the display role for that index. Which is
    # supposed to come as a qvariant, but actually comes as a QString, from
    # which we take the first (and only) qchar.
    def filterAcceptsRow(self, row, parent_index):
        qmi = self.parent.model.index(row, 0, parent_index)
        dat = self.parent.model.data(qmi,Qt.DisplayRole)
        return self.parent.filterLambda(dat.at(0))
   
class charsPanel(QWidget):
    def __init__(self, parent=None):
        super(charsPanel, self).__init__(parent)
        # Do the layout: refresh button and filter popup at the top,
        # with a table below.
        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)
        topLayout = QHBoxLayout()
        mainLayout.addLayout(topLayout,0)
        self.refreshButton = QPushButton("Refresh")
        self.filterMenu = QComboBox()
        topLayout.addWidget(self.refreshButton,0)
        topLayout.addStretch(1)
        topLayout.addWidget(self.filterMenu,0)
        self.view = QTableView()
        self.view.setCornerButtonEnabled(False)
        self.view.setWordWrap(False)
        self.view.setAlternatingRowColors(True)
        mainLayout.addWidget(self.view,1)
        # Set up the table model/view. Interpose a sort filter proxy
        # between the view and the model.
        self.model = myTableModel()
        self.proxy = mySortFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.view.setModel(self.proxy)
        # Hook up the refresh button clicked signal to refresh below
        self.connect(self.refreshButton, SIGNAL("clicked()"),self.refresh)
        # Populate the filter popup with rows:
        # 0 : All - no filter
        # 1 : not 7-bit - show only things not in the 7-bit code
        # 2 : not Latin-1 - show only things outside Latin-1
        self.filterMenu.addItem(QString(u"All"))
        self.filterMenu.addItem(QString(u"\u00ac"+u" 7-bit"))
        self.filterMenu.addItem(QString(u"\u00ac"+u" Latin-1"))
        # The filters refer to these properties, called with a QChar C
        self.lambdaAll = lambda C : True
        self.lambdaNotAscii = lambda C : (C.unicode() < 32) or (C.unicode() > 126)
        self.lambdaNotLatin = lambda C : (C.toLatin1() == b'\x00')
        self.filterLambda = self.lambdaAll
        # Connect a user-selection in the popup to our filter method.
        self.connect(self.filterMenu, SIGNAL("activated(int)"),self.filter)
        # Connect doubleclicked from our table view to self.findThis
        self.connect(self.view, SIGNAL("doubleClicked(QModelIndex)"), self.findThis)

    # This slot receives a double-click on the table. Figure out which
    # character it is and get the Find panel set up to search for it.
    def findThis(self,qmi):
        rep = None
        if qmi.column() == 3 :
            # doubleclick in entity column, put entity in the replace field
            rep = qmi.data(Qt.DisplayRole).toString()
        if qmi.column() != 0 :
            # get reference to column 0
            qmi = qmi.sibling(qmi.row(),0)
        qs = qmi.data(Qt.DisplayRole).toString()
        IMC.findPanel.censusFinder(qs,rep)

    # this slot gets the activated(row) signal from the combo-box.
    # Based on the row, set self.filterLambda to a lambda that will
    # accept or reject a given QChar value.
    def filter(self,row):
        if row == 1 : self.filterLambda = self.lambdaNotAscii
        elif row == 2 : self.filterLambda = self.lambdaNotLatin
        else : self.filterLambda = self.lambdaAll
        self.model.reset()

    # This slot receives the main window's docWillChange signal.
    # It comes with a file path but we can ignore that.
    def docWillChange(self):
        #self.view.setSortingEnabled(False)
        self.model.beginResetModel()

    # Subroutine to reset the visual appearance of the table view,
    # invoked on table reset because on instantiation we have no table.
    # Bump up the width of column 0 because when it sets it to its contents
    # there isn't room for the header plus the sort triangle
    def setUpTableView(self):
        #self.view.sortByColumn(0,Qt.AscendingOrder)
        self.view.resizeColumnsToContents()
        self.view.setColumnWidth(0,20+self.view.columnWidth(0))
        self.view.setColumnWidth(2,8+self.view.columnWidth(2))
        self.view.setColumnWidth(3,20+self.view.columnWidth(3))
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.resizeRowsToContents()
        self.view.setSortingEnabled(True)
        
    # This slot receives the main window's docHasChanged signal.
    # Let the table view populate with all-new metadata (or empty
    # data if the command was File>New).
    def docHasChanged(self):
        self.model.endResetModel()
        self.setUpTableView()

    # This slot receives the click of the refresh button. Tell the
    # model we are resetting everything so the view will suck up new
    # data. Then call our editor to rebuild the metadata.
    def refresh(self):
        #self.view.setSortingEnabled(False)
        self.model.beginResetModel()
        IMC.editWidget.rebuildMetadata()
        self.model.endResetModel()
        self.setUpTableView()

if __name__ == "__main__":
    import sys
    from PyQt4.QtCore import (Qt,QFile,QIODevice,QTextStream)
    from PyQt4.QtGui import (QApplication,QFileDialog)
    import pqIMC
    IMC = pqIMC.tricorder() # create inter-module communicator
    app = QApplication(sys.argv) # create an app
    import pqMsgs
    pqMsgs.IMC = IMC
    import pqLists
    IMC.charCensus = pqLists.vocabList()
    W = charsPanel() # create the widget with the table view and model
    W.show()
    utname = QFileDialog.getOpenFileName(W,
                "UNIT TEST DATA FOR CHARS", ".")
    utfile = QFile(utname)
    if not utfile.open(QIODevice.ReadOnly):
        raise IOError, unicode(utfile.errorString())

    W.docWillChange()
    
    utstream = QTextStream(utfile)
    utstream.setCodec("UTF-8")
    utqs = utstream.readAll()
    for i in range(utqs.count()):
        qc = utqs.at(i)
        cat = qc.category()
        IMC.charCensus.count(QString(qc),cat)

    W.docHasChanged()
    app.exec_()
