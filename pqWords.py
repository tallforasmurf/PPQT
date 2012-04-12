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
import pqMsgs

from PyQt4.QtCore import (Qt,
                          QAbstractTableModel,QModelIndex,
                          QChar, QString, 
                          QVariant,
                          SIGNAL)
from PyQt4.QtGui import (
    QApplication,
    QCheckBox,
    QComboBox,
    QContextMenuEvent,
    QHBoxLayout,
    QItemSelectionModel,
    QKeyEvent,
    QMenu,
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
        ret = Qt.ItemIsEnabled
        if 0 == index.column():
            ret |= Qt.ItemIsSelectable
        return ret
    
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
        elif (role == Qt.UserRole) and (2 == index.column()):
            # context menu wants the flag bits as int
            (qs,count,flag) = IMC.wordCensus.get(index.row())
            return flag
        # don't support other roles
        return QVariant()
    
    # The data in this table isn't normally editable but if the word is
    # added to goodwords, the flags may be changed -- see the context menu
    # in the view following. In which case the flag field gets changed.
    def setData(self,index,value,role):
        if (role == Qt.UserRole) and (index.column() == 2):
            (flag, b) = value.toInt() # damned qvariants...
            IMC.wordCensus.setflags(index.row(),flag)
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),index,index)
            return True
        return False # dunno about other roles or columns

# Customize a sort/filter proxy by making its filterAcceptsRow method
# test the character in that row against a filter function in the parent.

class mySortFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super(mySortFilterProxy, self).__init__(parent)
        self.panelRef = parent # save pointer to the panel widget
        
    # Get the data from column 2 of row (feature string), and apply
    # parent.filterLambda to it. The model/view abstractions get really thick
    # here: go to the parent for an index to the row/column, then go back to
    # the parent for the data for the display role for that index. Which is
    # supposed to come as a qvariant, but actually comes as a QString.
    def filterAcceptsRow(self, row, parent_index):
        if self.panelRef.listFilter is None:
            qmi = self.panelRef.tableModel.index(row, 2, parent_index)
            dat = self.panelRef.tableModel.data(qmi,Qt.DisplayRole)
            return self.panelRef.filterLambda(unicode(dat))
        else: # filtering on first harmonic or similar
            qmi = self.panelRef.tableModel.index(row, 0, parent_index)
            dat = self.panelRef.tableModel.data(qmi,Qt.DisplayRole)
            return ( unicode(dat) in self.panelRef.listFilter )

# subclass QTableView just so we can install a custom context menu
# for column 0, and intercept ^c to copy a word.
class myTableView(QTableView):
    def __init__(self, parent=None):
        super(myTableView, self).__init__(parent)
        # save ref to panel widget
        self.panelRef = parent 
        self.setFocusPolicy(Qt.ClickFocus)
        # set up stuff used in our context menu
        self.contextIndex = QModelIndex()
        self.contextMenu = QMenu(self)
        addAction = self.contextMenu.addAction("&Add to goodwords")
        simAction = self.contextMenu.addAction("S&imilar words")
        har1Action = self.contextMenu.addAction("&First harmonic")
        har2Action = self.contextMenu.addAction("&Second harmonic")
        self.connect(addAction, SIGNAL("triggered()"), self.addToGW)
        self.connect(simAction, SIGNAL("triggered()"), self.similarWords) 
        self.connect(har1Action, SIGNAL("triggered()"), self.firstHarmonic)
        self.connect(har2Action, SIGNAL("triggered()"), self.secondHarmonic)

    # Reimplement the parent (QTableView) KeyPressEvent in order to trap
    # the ctl/cmd-c key and copy the selected word(s) to the clipboard.
    # BUG: for reasons as yet unknown, the Edit menu in the menubar preempts
    # the cmd-c Qt.Key_Copy signal, even when this widget has the focus.
    # For now we are looking specifically for Key_C with the control modifier
    # which can be entered here by the workaround of SHIFT-CMD-C.
    def keyPressEvent(self, event):
        code = int(event.key())
        mods = int(event.modifiers())
        #print('key {0:X} mod {1:X}'.format(code,mods))
        if (code == Qt.Key_C) and (mods & Qt.ControlModifier) :
            # PyQt4's implementation of QTableView::selectedIndexes() does 
            # not return a QList but rather a Python list of indices.
            lix = self.selectedIndexes()
            if len(lix) : # non-zero selection
                ans = QString()
                for ix in lix :
                    ans.append(
                self.model().data(ix, Qt.DisplayRole).toString()
                            )
                    ans.append(u' ')
                ans.chop(1) # drop final space
                QApplication.clipboard().setText(ans)
    
    # A context menu event means a right-click anywhere, ctrl-click (Mac)
    # or Menu button (Windows). We ignore any such except on column 0,
    # the word. There we pop up our menu.
    def contextMenuEvent(self,event):
        if 0 == self.columnAt(event.x()) :
            # get the index for the datum under the widget-relative position
            self.contextIndex = self.indexAt(event.pos())
            # display the popup menu which needs the global click position
            self.contextMenu.exec_(event.globalPos())

    # This is the slot to receive the context menu choice "Add to goodwords".
    # We are going to play nice with Qt's abstract table model/view. Although
    # we could just reach into IMC.wordCensus, we will get the word and its
    # flags by calling our model's data() method, and if we change the flag,
    # set it by calling our model's setData(). The point is to cause the right
    # signal to be emitted so that the flag column display changes right now.
    # Or maybe just because we like to wrap ourselves up in snuggy layers of
    # abstractions because it makes us feel all ... programmer-y.
    # Oh, a little syntax note. When, in this AbstractTableView object, we need
    # to call our AbstractTableModel, we have to use our inherited method,
    # self.model(). Note the parens. That actually gets us the sort filter
    # proxy but it behaves like a table model so we're all fat and happy.
    # Below, when the wordsPanel widget has to refer to its actual table model
    # it keeps the reference in a property named self.tableModel. No parens!
    def addToGW(self):
        lix = self.selectedIndexes()
        if len(lix) == 1 : # just one selected, presumably the on clicked-on
            qs = self.model().data(lix[0], Qt.DisplayRole).toString()
            mtxt = u'Add {0} to the good-words list?'.format(unicode(qs))
        else :
            mtxt = u'Add {0} words to the good-words list?'.format(len(lix))
        b = pqMsgs.okCancelMsg(mtxt,"This action cannot be undone.")
        if b : # user says do it
            for ix in lix :
                qs = self.model().data(ix, Qt.DisplayRole).toString()
                word = unicode(qs)
                IMC.goodWordList.insert(word)
                # fabricate an index to the flags field of the indexed row
                findex = self.model().index(ix.row(), 2)
                # get flag as an int instead of a fancy char string
                (flag, b) = self.model().data(findex, Qt.UserRole).toInt()
                flag &= 0xfff - IMC.WordMisspelt
                self.model().setData(findex,flag,Qt.UserRole)
                IMC.needMetadataSave = True
        
    # The actual code of First and Second Harmonic. Run through the word list
    # and make a sublist of just the ones that are a Levenshtein distance of 1
    # (first) or 2 (second) from the current word. If there are none, pop up a
    # notice saying so. Otherwise, set the list in the wordsPanel.filterList
    # Then filterAcceptsRow, above, will only accept words in the list.
    def realHarmonic(self,dist):
        qs = self.model().data(self.contextIndex, Qt.DisplayRole).toString()
        word = unicode(qs) # get python string
        wordLen = len(word) # save a few cycles in the test below
        harmList = []
        for i in range(IMC.wordCensus.size()):
            word2 = unicode(IMC.wordCensus.getWord(i))
            if dist >= abs(wordLen - len(word2)): # There's a chance of a match
                if dist >= edit_distance(word,word2): # test it
                    harmList.append(word2) # one hit is on the word itself
        if 1 < len(harmList) : # got at least 1 other
            self.panelRef.listFilter = harmList
            self.panelRef.tableModel.reset()
        else:
            pqMsgs.infoMsg(
        "There are no words in edit distance {0} edit of {1}".format(dist,word)
            )

    def firstHarmonic(self):
        self.realHarmonic(1)
    def secondHarmonic(self):
        self.realHarmonic(2)

    # The slot to receive the context menu choice Similar Words. Like first
    # and second harmonic above, but simpler to process.
    def similarWords(self):
        qch = QChar(u'-')
        qcp = QChar(u"'")
        wordOriginal = self.model().data(self.contextIndex, Qt.DisplayRole).toString()
        word = QString(wordOriginal)
        word.remove(qch)
        word.remove(qcp)
        h1list = []
        for i in range(IMC.wordCensus.size()):
            word1 = IMC.wordCensus.getWord(i)
            word2 = QString(word1) # force a copy!
            word2.remove(qch) # otherwise this would affect the word
            word2.remove(qcp) # in the census list
            if 0 == word.compare(word2,Qt.CaseInsensitive):
                h1list.append(unicode(word1)) # one hit on word itself
        if 1 < len(h1list): # got at least 1 other
            self.panelRef.listFilter = h1list
            self.panelRef.tableModel.reset()
        else:
            pqMsgs.infoMsg("There are no words similar to {0}".format(unicode(wordOriginal)))

# Levenshtein distance computation in Python. At some point we probably
# have to get one coded in C, there is more than one such in pypi. However
# that means installing same on all 3 platforms. For the nonce we go with this.
# The algorithm is is m*n in the lengths of the two strings.
def edit_distance(a, b):
    """
    distance(a, b) -> int.
    Calculates Levenshtein's edit distance between strings "a" and "b".
    Modified for PPQT use from the original Text manipulation utilities
    package at http://bitbucket.org/tarek/texttools
    Author: Tarek Ziade
    """
    # ensure a is the longer string
    if len(a) < len(b):
        return edit_distance(b, a)
    previous_row = xrange(len(b) + 1)
    for i, c1 in enumerate(a):
        current_row = [i + 1]
        for j, c2 in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

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
        self.view = myTableView(self)
        self.view.setCornerButtonEnabled(False)
        self.view.setWordWrap(False)
        self.view.setAlternatingRowColors(True)
        mainLayout.addWidget(self.view,1)
        # Set up the table model/view. Interpose a sort filter proxy
        # between the view and the model.
        self.tableModel = myTableModel()
        self.proxy = mySortFilterProxy(self)
        self.proxy.setSourceModel(self.tableModel)
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
        self.listFilter = None
        # Connect a user-selection in the popup to our filter method.
        self.connect(self.filterMenu, SIGNAL("activated(int)"),self.filter)
        # Connect doubleclicked from our table view to self.findThis
        self.connect(self.view, SIGNAL("doubleClicked(QModelIndex)"), self.findThis)
        # Connect state change in case switch to a slot
        self.connect(self.caseSwitch, SIGNAL("stateChanged(int)"),
                     self.setCase)

    # This slot receives a double-click on the table. Figure out which
    # word it is and get the Find panel set up to search for it. Some words
    # have /dictag, get rid of that before going to the search.
    def findThis(self,qmi):
        if qmi.column() != 0 :
            qmi = qmi.sibling(qmi.row(),0)
        qs = qmi.data(Qt.DisplayRole).toString()
        if qs.contains(QChar(u'/')) :
            qs = qs.split(QChar(u'/'))[0]
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
        self.listFilter = None
        self.tableModel.reset()

    # This slot receives the main window's docWillChange signal.
    # It comes with a file path but we can ignore that.
    def docWillChange(self):
        self.view.setSortingEnabled(False)
        self.tableModel.beginResetModel()

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
        self.tableModel.endResetModel()
        self.setUpTableView()

    # This slot receives the click of the refresh button. Tell the
    # model we are resetting everything so the view will suck up new
    # data. Then call our editor to rebuild the metadata.
    def refresh(self):
        self.view.setSortingEnabled(False)
        self.tableModel.beginResetModel()
        if IMC.editWidget.document().isModified():
            IMC.editWidget.doCensus()
        IMC.editWidget.doSpellcheck()
        self.tableModel.endResetModel()
        self.setUpTableView()

# No separate unit test - too dependent on edit metadata creation
