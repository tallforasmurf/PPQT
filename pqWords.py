# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
Implement the Word Census panel. At the top a row with a Refresh button on
the left, a case-sensitivity checkbox next, and a filter combobox on the right.
Below, a table with three columns:
* Word, the text of the word 
* Count, the number times it appears in the document
* Features, the various flag values translated to letters:
    - WordHasUpper: A or dash
    - WordHasLower: a or dash
    - WordHasDigit: 9 or dash
    - WordHasHyphen: h or dash
    - WordHasApostrophe: p or dash
    - WordMisspelt: X or dash

The table is implemented using a Qt AbstractTableView, SortFilterProxyModel,
and AbstractTableModel. The AbstractTableModel is subclassed to implement
fetching data from the IMC.wordCensus list. The AbstractTableModel is used
as-is, but the SortFilterProxyModel is subclassed to provide the filtering
mechanism. Filters for various flag combinations are implemented as 
lambda expressions on the flag value of the word. When the user selects a
row in the popup, we change the filter lambda and reset the model, forcing
all rows to be re-fetched.

The main windows DocWillChange and DocHasChanged signals are accepted
and used to warn the model of impending changes in metadata.
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

from PyQt4.QtCore import (Qt,
                          QAbstractTableModel,QModelIndex,
                          QChar, QString, 
                          QVariant,
                          SIGNAL)
from PyQt4.QtGui import (
    QCheckBox,
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
# The data served is derived from the word census prepared in the editor.
class myTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super(myTableModel, self).__init__(parent)
        # The header texts for the columns
        self.headerDict = { 0:"Word", 1:"Count", 2:"Features" }
        # the text alignments for the columns
        self.alignDict = { 0:Qt.AlignLeft, 1: Qt.AlignRight, 2: Qt.AlignHCenter }
        # The values for tool/status tips for data and headers
        self.tipDict = { 0: "Word text",
                         1: "Number of occurrences",
        2: "A:uppercase a:lowercase 9:digit h:hyphen p:apostrophe X:misspelt" }

    def columnCount(self,index):
        if index.isValid() : return 0 # we don't have a tree here
        return 3 # word, count, features
    
    def flags(self,index):
        return Qt.ItemIsEnabled
    
    def rowCount(self,index):
        if index.isValid() : return 0 # we don't have a tree here
        return IMC.wordCensus.size() # initially 0
    
    def headerData(self, col, axis, role):
        if (axis == Qt.Horizontal) and (col >= 0):
            if role == Qt.DisplayRole : # wants actual text
                return QString(self.headerDict[col])
            elif (role == Qt.ToolTipRole) or (role == Qt.StatusTipRole) :
                return QString(self.tipDict[col])
        return QVariant() # we don't do that
    
    def data(self, index, role ):
        if role == Qt.DisplayRole : # wants actual data
            (qs,count,flag) = IMC.wordCensus.get(index.row())
            if 0 == index.column():
                return qs
            elif 1 == index.column():
                return count
            else:
                features = 'A' if flag & IMC.WordHasUpper else '-'
                features += 'a' if flag & IMC.WordHasLower else '-'
                features += '9' if flag & IMC.WordHasDigit else '-'
                features += 'h' if flag & IMC.WordHasHyphen else '-'
                features += 'p' if flag & IMC.WordHasApostrophe else '-'
                features += 'X' if flag & IMC.WordMisspelt else '-'
                return QString(features)
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
        
    # Get the data from column 2 of row (feature string), and apply
    # parent.filterLambda to it. The model/view abstractions get really thick
    # here: go to the parent for an index to the row/column, then go back to
    # the parent for the data for the display role for that index. Which is
    # supposed to come as a qvariant, but actually comes as a QString.
    def filterAcceptsRow(self, row, parent_index):
        qmi = self.parent.model.index(row, 2, parent_index)
        dat = self.parent.model.data(qmi,Qt.DisplayRole)
        return self.parent.filterLambda(unicode(dat))
   
class wordsPanel(QWidget):
    def __init__(self, parent=None):
        super(wordsPanel, self).__init__(parent)
        # Do the layout: refresh button and filter popup at the top,
        # with a table below.
        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)
        topLayout = QHBoxLayout()
        mainLayout.addLayout(topLayout,0)
        self.refreshButton = QPushButton("Refresh")
        self.caseSwitch = QCheckBox(u"Respect &Case")
        self.caseSwitch.setChecked(True) # proxy defaults to case-sensitive
        self.filterMenu = QComboBox()
        topLayout.addWidget(self.refreshButton,0)
        topLayout.addWidget(self.caseSwitch,0)
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
        # 1 : UPPERCASE - show only all-cap words
        # 2 : lowercase - only all-lowercase words
        # 3 : mIxEdcase - words with mixed case
        # 4 : numbers - all-digit words
        # 5 : alnumeric - words with digits and letters
        # 6 : hyphenated - words with hyphens
        # 7 : apostrophes - words with apostrophes
        # 8 : misspelt - words with misspellings
        self.filterMenu.addItem(QString(u"All"))
        self.filterMenu.addItem(QString(u"UPPERCASE"))
        self.filterMenu.addItem(QString(u"lowercase"))
        self.filterMenu.addItem(QString(u"mIxEdcase"))
        self.filterMenu.addItem(QString(u"numbers"))
        self.filterMenu.addItem(QString(u"alnumeric"))
        self.filterMenu.addItem(QString(u"hyphenated"))
        self.filterMenu.addItem(QString(u"apostrophes"))
        self.filterMenu.addItem(QString(u"misspelt"))
        # The filters refer to these properties, called with the feature string
        self.lambdaAll = lambda S : True
        self.lambdaUpper = lambda S : S[:3] == u'A--'
        self.lambdaLower = lambda S : S[:3] == u'-a-'
        self.lambdaMixed = lambda S : S[:2] == u'Aa' # allow digits
        self.lambdaNumber = lambda S : S[:3] == u'--9'
        self.lambdaAlnum = lambda S : S[2] == u'9' and S[:2] != u'--'
        self.lambdaHyphen = lambda S : S[3] == u'h'
        self.lambdaApostrophe = lambda S : S[4] == u'p'
        self.lambdaMisspelt = lambda S : S[5] == u'X'
        self.filterLambda = self.lambdaAll # initially All
        # Connect a user-selection in the popup to our filter method.
        self.connect(self.filterMenu, SIGNAL("activated(int)"),self.filter)
        # Connect doubleclicked from our table view to self.findThis
        self.connect(self.view, SIGNAL("doubleClicked(QModelIndex)"), self.findThis)
        # Connect state change in case switch to a slot
        self.connect(self.caseSwitch, SIGNAL("stateChanged(int)"),
                     self.setCase)

    # This slot receives a double-click on the table. Figure out which
    # word it is and get the Find panel set up to search for it.
    def findThis(self,qmi):
        if qmi.column() != 0 :
            qmi = qmi.sibling(qmi.row(),0)
        qs = qmi.data(Qt.DisplayRole).toString()
        IMC.findPanel.censusFinder(qs)

    # This slot receives a change of the respect case checkbox. Set the
    # case sensitivity of the sort proxy model accordingly.
    def setCase(self, state):
        self.proxy.setSortCaseSensitivity(
            Qt.CaseSensitive if state else Qt.CaseInsensitive )

    # this slot gets the activated(row) signal from the combo-box.
    # Based on the row, set self.filterLambda to a lambda that will
    # accept or reject a given QChar value.
    def filter(self,row):
        if row == 1 : self.filterLambda = self.lambdaUpper
        elif row == 2 : self.filterLambda = self.lambdaLower
        elif row == 3 : self.filterLambda = self.lambdaMixed
        elif row == 4 : self.filterLambda = self.lambdaNumber
        elif row == 5 : self.filterLambda = self.lambdaAlnum
        elif row == 6 : self.filterLambda = self.lambdaHyphen
        elif row == 7 : self.filterLambda = self.lambdaApostrophe
        elif row == 8 : self.filterLambda = self.lambdaMisspelt
        else : self.filterLambda = self.lambdaAll
        self.model.reset()

    # This slot receives the main window's docWillChange signal.
    # It comes with a file path but we can ignore that.
    def docWillChange(self):
        self.view.setSortingEnabled(False)
        self.model.beginResetModel()

    # Subroutine to reset the visual appearance of the table view,
    # invoked on table reset because on instantiation we have no table.
    def setUpTableView(self):
        self.view.sortByColumn(0,Qt.AscendingOrder)
        #self.view.resizeColumnsToContents()
        self.view.setColumnWidth(0,200)
        self.view.setColumnWidth(1,50)
        self.view.horizontalHeader().setStretchLastSection(True)
        #self.view.resizeRowsToContents()
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
        self.view.setSortingEnabled(False)
        self.model.beginResetModel()
        IMC.editWidget.rebuildMetaData()
        self.model.endResetModel()
        self.setUpTableView()

# No separate unit test - too dependent on edit metadata creation
