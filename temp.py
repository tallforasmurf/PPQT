# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
Implement the find/replace panel. The findPanel class constructor has
the very lengthy task of building and laying out the panel. (The initial
look was worked out using Qt Designer, but we implement the widgets and
layouts manually rather than using the designer output.)

Interactions between this and the Edit widget are as follows: To
implement Find (through the Next and Prior buttons) we just reach into
the editor and get its document and call its find method. When we get a
hit we change the editor's cursor to display it. To replace, we use the
editor's cursor's textInsert method. However, for a regex replace we
have to get the selection out of the editor, prime the regex by
repeating the match, then use a QString replace method, finally put the
altered text back.

The editor traps keyevents and when it sees the search special keys
it emits a signal and passes the keyEvent to us here at editKeyEvent.
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

At the top of the pane is a row of four checkboxes for case, whole-word,
regex, and greedy. Whole-word is ignored for regex (use \b\w+\b), and
greedy is ignored for non-regex.

TODO: do we need a Wrap checkbox and wrap-around search?

Below the checkboxes is the Find lineEdit, which has syntax checking for regex
and turns pink when an invalid regex is being entered. Below that are three
Replace lineEdits and three checkboxes for replace behavior: and-find, in selection,
and ALL! Despite the dramatic checkbox, we pop up a confirmation dialog on All.

Beside each Find and Rep lineEdit we have a combo box that pops up a list
of previous strings from most recent down. The find list is updated on use
of Next or Prior. The Rep lists are updated on use of that Rep. The lists
of strings are saved in the settings on shutdown and restored on startup.

Below the find and replace widgets we have an array of pushbuttons each
of which stores a single find/replace setup and loads it when pressed.
(The idea is that these canned search setups can replace most of the
guiguts special searches, and users can extend them freely.)

The button array contents can be saved to a file or loaded from a file.
The format is one __repr__ string of a python dict, per line. Within the
string the "find" and "rep1/2/3" keys are uuencoded strings, so as not
to have to fret escaping the regex special characters. The Main
window offers a File > Save_regex and File > Load_regex, and handles
selecting and opening the files, calling our saveFind and loadFind
methods with a QTextStream ready to use.
TODO: editKeyEvent
TODO: pqEdit signal
TODO: link signal from main
TODO: replace in selection
TODO: replace all
TODO: saveFind
TODO: loadFInd
TODO: File>Save_finds
TODO: File>Load_finds
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

from urllib import (quote, unquote) # for safely encoding find/rep strings
import pqMsgs
from PyQt4.QtCore import (Qt,
    QRegExp,
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
    QTextDocument,
    QWidget )

UserButtonMax = 25 # how many user buttons to instantiate
UserButtonRow = 5 # how many to put in a row of the grid

class findPanel(QWidget):
    def __init__(self, parent=None):
        super(findPanel, self).__init__(parent)
		# list of previous-string popups: [0] is Find, [1/2/3] is reps
		self.popups = [None,None,None,None]
		# list of rep lineEdits, [0] is none, [1/2/3] is reps
		self.repEdits = [None,None,None,None]
		# list of refs to the  created user buttons
		self.userButtons = []
		# where we keep the find regexp as it is being entered
		self.regexp = QRegExp()
		# Per the Qt doc, we need to create a layout and parent it, that is,
		# add it to its parent layout, before we populate it. So here we
		# create the layouts and parent them. They get local names and will
		# go out of scope when we exit but the chain of parent-child refs 
		# keeps them alive. The organization is:
		# mainLayout
		#   findCheckHbox (4 checkboxes)
		#   findEditHbox  (find popup and lineEdit)
		#   nextPriorHbox ( Next and Prior buttons)
		#   repHolderHbox
		#		repRowsVbox
		#			repRowHbox (sequentially created, holds rep popup and lineEdit)
		#		repChecksVbox (3 checkboxes)
		#	userButtonGrid
		mainLayout = QVBoxLayout()
		self.setLayout(mainLayout)
		# set up the top row of four checkboxes
		findCheckHbox = QHBoxLayout()
		mainLayout.addLayout(findCheckHbox,0)
		self.caseSwitch = QCheckBox(u"Respect &Case")
		self.wholeWordSwitch = QCheckBox(u"Whole &Word")
		self.regexSwitch = QCheckBox(u"&Regex")
		self.greedySwitch = QCheckBox(u"&Greedy")
		findCheckHbox.addWidget(self.greedySwitch,0,Qt.AlignLeft)
		findCheckHbox.addWidget(self.caseSwitch,0,Qt.AlignLeft)
		findCheckHbox.addWidget(self.wholeWordSwitch,0,Qt.AlignLeft)
		findCheckHbox.addWidget(self.regexSwitch,0,Qt.AlignLeft)
		findCheckHbox.addStretch(1) # keep switches compact to the left
		# make a horizontal row of a combobox and the find text lineEdit
		# the custom lineEdit and comboBox classes are defined below.
		findEditHbox = QHBoxLayout()
		mainLayout.addLayout(findEditHbox,0)
		self.findText = findRepEdit()
		self.popups[0] = recentStrings(self.findText)
		findEditHbox.addWidget(self.popups[0])
		findEditHbox.addWidget(self.findText)
		# Connect any find text alteration to the regex-syntax check.
		# Note we are using textChanged which is emitted on user input or
		# when we call setText in userButtonClick
		self.connect(self.findText, SIGNAL("textChanged(QString)"),
					 self.checkFindText )
		self.connect(self.regexSwitch, SIGNAL("stateChanged(int)"),
					 self.checkFindText )
		# Make a horizontal row of the next and prior buttons
		nextPriorHbox = QHBoxLayout()
		mainLayout.addLayout(nextPriorHbox,0)
		self.nextButton = QPushButton(u"&Next")
		self.priorButton = QPushButton(u"&Prior")
		nextPriorHbox.addWidget(self.nextButton,0)
		nextPriorHbox.addWidget(self.priorButton,0)
		nextPriorHbox.addStretch(1) # keep buttons compact left
		# Connect both buttons to doSearch, passing 0 for next, 1 for prior
		self.connect(self.nextButton, SIGNAL("clicked()"),
					 lambda b=0: self.doSearch(b) )
		self.connect(self.priorButton, SIGNAL("clicked()"),
					 lambda b=1: self.doSearch(b) )
		# Set up the rep container layouts and parent them
		repHolderHbox = QHBoxLayout()
		mainLayout.addLayout(repHolderHbox,0)
		repRowsVbox = QVBoxLayout()
		repChecksVbox = QVBoxLayout()
		repHolderHbox.addLayout(repRowsVbox)
		repHolderHbox.addLayout(repChecksVbox)
		# populate the stack of replace checkboxes
		self.andFindSwitch = QCheckBox("&& find")
		self.inSelectionSwitch = QCheckBox("in sel.")
		self.allSwitch = QCheckBox("ALL!")
		repChecksVbox.addStretch(1) # spring at the top
		repChecksVbox.addWidget(self.andFindSwitch,0)
		repChecksVbox.addWidget(self.inSelectionSwitch,0)
		repChecksVbox.addWidget(self.allSwitch,0)
		repChecksVbox.addStretch(1) # spring at the bottom too
		# populate the stack of three replace setups, spacer at bottom
		self.makeRepRow(repRowsVbox,1)
		self.makeRepRow(repRowsVbox,2)
		self.makeRepRow(repRowsVbox,3)
		# put a spacer in the main layout between the replace stuff and user buttons
		mainLayout.addStretch(1)
		# create the grid of user buttons, for now all empty. 
		# Connect the left click signal from any button to our userButtonClick.
		# Connect the signal emitted by a user button on the contextMenu event
		# (left- or ctrl-click) to our userButtonLoad. N.B. to make these 
		# lambdas work it is essential to specify an expression, not a variable
		# name alone, as the parameter.
		userButtonGrid = QGridLayout()
		mainLayout.addLayout(userButtonGrid,0)
		for i in range(UserButtonMax):
			self.userButtons.append(userButton())
			self.connect(self.userButtons[i], SIGNAL("clicked()"),
						 lambda b=i : self.userButtonClick(b) )
			self.connect(self.userButtons[i], SIGNAL("userButtonLoad"),
						 lambda b=i : self.userButtonLoad(b) )
			userButtonGrid.addWidget(self.userButtons[i],
								 int(i/UserButtonRow), int(i%UserButtonRow))
		# ...and there we are!
    
    # Subroutine to make a replace row. Called with the parent layout and the
    # row number. Create a horizontal layout with a combobox, lineEdit,
    # and Repl button. Connect the button to doReplace with a lambda passing 1/2/3.
    
    def makeRepRow(self, parent, repRow):
		# create the edit and then the combobox with its buddy edit
		self.repEdits[repRow] = findRepEdit()
		self.popups[repRow] = recentStrings(self.repEdits[repRow])
		button = QPushButton("Repl")
		button.setMaximumHeight(32)
		self.connect(button, SIGNAL("clicked()"),
					 lambda : self.doReplace(repRow) )
		rowLayout = QHBoxLayout()
		parent.addLayout(rowLayout)
		rowLayout.addWidget(self.repEdits[repRow])
		rowLayout.addWidget(self.popups[repRow])
		rowLayout.addWidget(button)
=	
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

    # Called when either Next or Prior is clicked or when the relevant
    # key events are seen: perform a search. button = 0 for next, 1 for prior
    # N.B. for reference we have these switches:
    # self.caseSwitch self.wholeWordSwitch self.regexSwitch, self.greedySwitch
    def doSearch(self,button):
		# set forward/backward search flag depending on the button clicked
		flags = QTextDocument.FindBackward if button \
			  else QTextDocument.FindFlags(0)
		# any use of the find string means, save it in the pushdown list
		self.popups[0].noteString()
		# start at the end of the present selection
		startTc = IMC.editWidget.textCursor()
		doc = IMC.editWidget.document()
		if self.regexSwitch.isChecked() :
			# Regex search - self.regexp is ready but may not be valid
			if self.regexp.isValid() :
			# valid but need to set case and greedy
			cs = Qt.CaseSensitive if self.caseSwitch.isChecked() \
			   else Qt.CaseInsensitive
			self.regexp.setCaseSensitivity(cs)
			self.regexp.setMinimal(not self.greedySwitch.isChecked())
			findTc = doc.find(self.regexp,startTc,flags)
			else: # invalid regex, tsk tsk
			findTc = QTextCursor() # null cursor, see below
		else:
			# normal string search: finish setting up find flags
			if self.caseSwitch.isChecked() :
			flags |= QTextDocument.FindCaseSensitively
			if self.wholeWordSwitch.isChecked() :
			flags |= QTextDocument.FindWholeWords
			findTc = doc.find(self.findText.text(),startTc,flags)
		# search is done, finish up
		if findTc.isNull() : # search failed
			pqMsgs.beep()
		else: # search succeeded, highlight found
			IMC.editWidget.setTextCursor(findTc)	

    # Called from one of the three replace buttons to do a replace.
    # We replace the current selection (whether or not it is the result of
    # executing a find). If the andFind switch is on, we call doSearch above.
    
    def doReplace(self,repno):
		tc = IMC.editWidget.textCursor()
		if self.regexSwitch.isChecked() : # regex replace is complicated
			found = tc.selectedText()
			found.replace(self.regex, self.repEdits[repno].text())
			tc.insertText(found)
		else:
			tc.insertText(self.repEdits[repno].text())
		if self.andFindSwitch.isChecked() : 
			self.doSearch()

    # Slot for the clicked signal of a userButton. The button number is 
    # passed as an argument via the actual slot, which is a lambda.
    # Move the dictionary fields from the button into the find dialog fields,
    # changing only those that are defined in the button.
    def userButtonClick(self,butnum):
		d = self.userButtons[butnum].udict
		if 'case' in d : self.caseSwitch.setChecked(d['case'])
		if 'word' in d : self.wholeWordSwitch.setChecked(d['word'])
		if 'regex' in d : self.regexSwitch.setChecked(d['regex'])
		if 'greedy' in d : self.greedySwitch.setChecked(d['greedy'])
		if 'andfind' in d : self.andFindSwitch.setChecked(d['andfind'])
		if 'insel' in d : self.inSelectionSwitch.setChecked(d['insel'])
		if 'all' in d : self.allSwitch.setChecked(d['all'])
		if 'find' in d : self.findText.setText(unquote(d['find']))
		if 'rep1' in d : self.repEdits[1].setText(QString(unquote(d['rep1'])))
		if 'rep2' in d : self.repEdits[2].setText(QString(unquote(d['rep2'])))
		if 'rep3' in d : self.repEdits[3].setText(QString(unquote(d['rep3'])))
	
	# Slot for the userButtonLoad signal coming out of a userButton when
	# it is right-clicked. Query the user for a new label for the button
	# and if Cancel is not chosen, load the label and all find data into
	# the dict in the button.
	def userButtonLoad(self,butnum):
		j = butnum + 1
		(ans, ok) = pqMsgs.getStringMsg(u"Loading button {0}".format(j),
							u"Enter a short label for button {0}".format(j) )
		if ans.isNull() or (not ok) : return
		d = self.userButtons[butnum].udict
		d.clear()
		d['label'] = unicode(ans)
		self.userButtons[butnum].setText(ans)
		d['case'] = self.caseSwitch.isChecked()
		d['word'] = self.wholeWordSwitch.isChecked()
		d['regex'] = self.regexSwitch.isChecked()
		d['greedy'] = self.greedySwitch.isChecked()
		d['andfind'] = self.andFindSwitch.isChecked()
		d['insel'] = self.inSelectionSwitch.isChecked()
		d['all'] = self.allSwitch.isChecked()
		if not self.findText.text().isNull() :
			d['find'] = quote(unicode(self.findText.text()))
		if not self.repEdits[1].text().isNull() :
			d['rep1'] = quote(unicode(self.repEdits[1].text()))
		if not self.repEdits[2].text().isNull() :
			d['rep2'] = quote(unicode(self.repEdits[2].text()))
		if not self.repEdits[3].text().isNull() :
			d['rep3'] = quote(unicode(self.repEdits[3].text()))

# We subclass QComboBox to make the recent-string-list pop-ups.
# One change from default, we set the max width to 32; these are
# more like buttons than combo boxes. The associated line edit widget
# is passed and this constructor clips its activated(QString) signal to
# the lineEdit's setText(QString) function.

class recentStrings(QComboBox):
	def __init__(self, myLineEdit, parent=None):
		super(recentStrings, self).__init__(parent)
		self.setMaximumWidth(32)
		self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
		self.setEditable(False)
		self.setMaxCount(10)
		self.buddy = myLineEdit # save ref to associated lineEdit
		self.lastString = QString()
		self.list = QStringList() # clear our list of items
		self.connect(self, SIGNAL("activated(QString)"), self.buddy.setText)
	
	# Called when our associated lineEdit is used, e.g. Next or Repl button.
	# Such use might happen multiple times without changing the string, so
	# bail quick if we've seen this one. When the string is not the same as
	# last time, put it at the head of our list and reload our popup.
	def noteString(self):
		tx = self.buddy.text()
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
			self.addItems(self.list)

# We subclass LineEdit to make our find and replace text widgets.
# It has some special features compared to the usual LineEdit.

class findRepEdit(QLineEdit):
	def __init__(self, parent=None):
		super(findRepEdit, self).__init__(parent)
		monofont = QFont()
		monofont.setStyleStrategy(QFont.PreferAntialias+QFont.PreferMatch)
		monofont.setStyleHint(QFont.Courier+QFont.Monospace)
		monofont.setFamily("DPCustomMono2")
		monofont.setFixedPitch(True) # probably unnecessary
		monofont.setPointSize(14) # nice and big
		self.setAutoFillBackground(True) # allow changing bg color
	
	# Change the background color of this lineEdit
	def setBackground(self,color):
		palette = self.palette()
		palette.setColor(QPalette.Normal,QPalette.Base,QColor(color))
		self.setPalette(palette)
	
	# these lineEdits, same as edit and notes panels, allow changing
	# font size though over a smaller range
	def keyPressEvent(self, event):
		kkey = event.key() + int(event.modifiers()
		if (kkey == IMC.ctl_plus) or (kkey == IMC.ctl_minus) \
		or (kkey == IMC.ctl_shft_equal) :
			event.accept()
			n = (-1) if (kkey == Qt.Key_Minus) else 1
			p = self.fontInfo().pointSize() + n
			if (p > 4) and (p < 25): # don't let's get ridiculous, hmm?
				f = self.font() # so get our font,
				f.setPointSize(p) # change its point size +/-
				self.setFont(f) # and put the font back
		else: # not ctl-+/-
			event.ignore()
		# ignored or accepted, pass the event along.
		super(findRepEdit, self).keyPressEvent(event)
  
# Class of the user-programmable push buttons. Each button can store the values
# of all the fields of the upper part of the panel.
#
# The values are stored in the form of a python dict with these keys:
# 'label'  :'string'     label for the button
# 'case'   : True/False  case switch
# 'word'   : True/False  whole word switch
# 'regex'  : True/False  regex switch
# 'greedy' : True/False  greedy switch
# 'find'   : 'string' with quotes escaped find string
# 'rep1/2/3' : 'string' with quotes escaped rep strings 1/2/3
# 'andfind' : True/False  and then find switch
# 'insel'  : True/False  in selection switch
# 'all'    : True/False  all switch
# The find and rep strings are encoded as for a url to make them safe.
# When the button is clicked, the signal goes to findPanel.userButtonClick
# where the dict values are queried and used to set the fields of the panel.
# The button constructor takes the __repr__ string of a dict as argument
# and converts it to a dict if it can. The requirement is only that it be
# a good syntactic python dict literal and that it have a 'label' key.
# The stored dict can be converted with its __repr__ method to a string
# for saving buttons to a file or to the settings at shutdown.
class userButton(QPushButton):
	def __init__(self, initDict=None, parent=None):
		super(userButton, self).__init__(parent)
		# if a dict string was passed, treat it with suspicion
		self.udict = None
		if initDict is not None: 
			try:
				# execute an assignment - checks for valid python syntax
				exec( 'self.udict = ' + initDict )
				# now make sure it was a dict not a list or whatever
				if not isinstance(self.udict,dict) : 
					raise ValueError
				# and make sure it has a label key
				if not 'label' in self.udict :
					raise ValueError
				# and make sure the value of dict['label'] is a string
				if not ( isinstance(self.udict['label'],str) \
				or isinstance(self.udict['label'],unicode) ):
					raise ValueError
				# all good, go ahead and use it
			except StandardError:
				# some error raised, go to defaults
				self.udict = None
		if self.udict is None : # no dict or bad dict, make minimal dict
			self.udict = { 'label':'(empty)' }
		# one way or 'tother we have a dict
		self.setText(QString(self.udict['label']))

	# trap a right-click or control-click and pass it as a signal to findPanel
	# where it will load our dict from the present find fields, and query the
	# user for a new button label.
	def contextMenuEvent(self,event):
		event.accept()
		self.emit(SIGNAL("userButtonLoad"))
		super(userButton, self).contextMenuEvent(event) # pass it up

if __name__ == "__main__":
    import sys
    from PyQt4.QtGui import (QApplication,QPlainTextEdit)
    class tricorder():
	def __init__(self):
		pass
    app = QApplication(sys.argv) # create an app

    #ubutt = userButton() # no dict
    #ubutt = userButton('{frummage') # bad syntax
    #ubutt = userButton('2 + 3') # not a dict
    #ubutt = userButton('{\'x\':\'y\'}') # good dict no label
    #ubutt = userButton("{ 'label':99 }") # label not a string
    #ubutt = userButton("{ 'label':'what', 'word':True }")
    
    
    IMC = tricorder()
    import pqMsgs
    pqMsgs.IMC = IMC
    IMC.editWidget = QPlainTextEdit()
    doc = '''
    banana
    frog
    bumbershoot
    shooterbumb
    bumbershoot
    frog
    banana
    '''
    IMC.editWidget.setPlainText(doc)
    widj = findPanel()
    IMC.mainWindow = widj
    widj.show()
    app.exec_()