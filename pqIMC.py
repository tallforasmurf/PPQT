# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *
'''
How, in a multi-module Python source, do you give different modules
references to objects created in other modules? Also how do you share
constant values that should be defined in one place, as with a C header?
This is our answer, the Inter Module Communicator. Just an object into
which we stuff every attribute that needs to be used from more than
one module. Might be a kludge, might be very clever.

The ppqt module stuffs a reference to IMC into every module it imports,
thus they all refer to the one instance.
'''

__version__ = "0.1.0" # refer to PEP-0008
__author__  = "David Cortesi"
__copyright__ = "Copyright 2011, David Cortesi"
__maintainer__ = "?"
__email__ = "tallforasmurf@yahoo.com"
__status__ = "first-draft"
__license__ = '''
Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0)
http://creativecommons.org/licenses/by-nc-sa/3.0/
'''
from PyQt4.QtCore import (Qt,QChar)
#
# Stupid star trek reference here.
#
class tricorder():
    def __init__(self):
        # Document/file status variables: more than a simple "dirty" flag.
        # needSpellCheck when a word census has been done, or when a 
        # different main dictionary is selected. Cleared when a spellcheck is
        # done, e.g. from the Refresh button in the Word panel.
        self.needSpellCheck = False
        # needMetadataSave when: a bookmark is set, the Notes panel is edited,
        # a word is added to goodwords, or we do a spellcheck or a word census.
        # Note this can be true when needBookSave is false. Cleared on Save
        # Save-As or New.
        self.needMetadataSave = False
        # Note that the equivalent switch "needDocumentSave" is kept by the
        # QTextDocument as IMC.editWidget.document().isModified() -- we rely on
        # that because it tracks the undo/redo actions and knows if the user
        # has backed out all changes or not.

        # These values are used in forming the word classification
        # flag for words in the word census. Prepared in the census
        # in pqEdit, referenced in pqWord.
        self.WordHasUpper = 0x01
        self.WordHasLower = 0x02
        self.WordHasDigit = 0x04
        self.WordHasHyphen = 0x08
        self.WordHasApostrophe = 0x10
        self.WordMisspelt = 0x80
        # These values are used to encode folio controls for the
        # Page/folio table. Initialized in pqEdit when opening a new file,
        # used in pqWord and pqHtml.        
        self.FolioFormatArabic = 0x00
        self.FolioFormatUCRom = 0x01
        self.FolioFormatLCRom = 0x02
        self.FolioRuleAdd1 = 0x00
        self.FolioRuleSet = 0x01
        self.FolioRuleSkip = 0x02
        # Controls on the edit syntax hiliter, queried in the editor and
        # set by the Main window View menu actions:
        self.scannoHiliteSwitch = False
        self.spellingHiliteSwitch = False
        # Pointers initialized in ppqt, filled in in pqEdit,
        # and referenced everywhere else
        self.settings = None # QSettings for global save/restore app values
        self.dictPath = None # path to folder where we look for dictionaries
        self.scannoList = None # list loaded from a scannos file for hiliting
        self.goodWordList = None # good words
        self.badWordList = None # bad words
        self.wordCensus = None # census of words (tokens actually)
        self.charCensus = None # census of characters
        self.pageTable = None # list of page separators 
        self.currentPageIndex = None # index into page table for current page
        self.currentPageNumber = None # qstring e.g. "002" of png file
        self.editWidget = None # main QPlainTextEdit set up in pqMain
        self.spellCheck = None # spellcheck object from pqSpell
        self.mainWindow = None # ref to main window
        # Pointers initialized in pqMain to various major objects
        self.bookPath = None # path to book file
        self.bookType = None # book file suffix used to detect .hmt(l)
        self.fontFamily = None # last-chosen font
        self.pngPanel = None # ref to Pngs panel
        self.notesEditor = None # ref to Notes panel
        self.findPanel = None # ref to Find panel
        self.statusBar = None # ref to status bar of main window
        self.progressBar = None # ref to progress bar in status bar
        # constant value for the line-delimiter used by QPlainTextEdit
        self.QtLineDelim = QChar(0x2029)
        # Keystrokes checked by editor and other panels that monitor KeyEvent signals.
        # In rough order of frequency of use, we support:
        # ^g and ^G, search again forward/backward,
        # ^f start search,
        # ^t and ^T replace and search forward/backward,
        # ^1-9 bookmarks
        # ^F start search with selection
        # ^= replace,
        # ^-alt-1-9 set bookmarks
        # ^+/- zoom also ctrl-shift-equal which is how plus comes in usually
        # ^l and ^-alt-l, ^p and ^-alt-p for the Notes panel
        # Define these in a way easy to check in a keyEvent slot, and also put
        # them in python lists for quick lookup.
        self.ctl_G = Qt.ControlModifier | Qt.Key_G
        self.ctl_shft_G = Qt.ShiftModifier | self.ctl_G
        self.ctl_F = Qt.ControlModifier | Qt.Key_F
        self.ctl_T = Qt.ControlModifier | Qt.Key_T
        self.ctl_shft_T = Qt.ShiftModifier | self.ctl_T
        self.ctl_1 = Qt.ControlModifier | Qt.Key_1
        self.ctl_2 = Qt.ControlModifier | Qt.Key_2
        self.ctl_3 = Qt.ControlModifier | Qt.Key_3
        self.ctl_4 = Qt.ControlModifier | Qt.Key_4
        self.ctl_5 = Qt.ControlModifier | Qt.Key_5
        self.ctl_6 = Qt.ControlModifier | Qt.Key_6
        self.ctl_7 = Qt.ControlModifier | Qt.Key_7
        self.ctl_8 = Qt.ControlModifier | Qt.Key_8
        self.ctl_9 = Qt.ControlModifier | Qt.Key_9
        self.ctl_shft_F = Qt.ShiftModifier | self.ctl_F
        self.ctl_alt_1 = Qt.AltModifier | self.ctl_1
        self.ctl_alt_2 = Qt.AltModifier | self.ctl_2
        self.ctl_alt_3 = Qt.AltModifier | self.ctl_3
        self.ctl_alt_4 = Qt.AltModifier | self.ctl_4
        self.ctl_alt_5 = Qt.AltModifier | self.ctl_5
        self.ctl_alt_6 = Qt.AltModifier | self.ctl_6
        self.ctl_alt_7 = Qt.AltModifier | self.ctl_7
        self.ctl_alt_8 = Qt.AltModifier | self.ctl_8
        self.ctl_alt_9 = Qt.AltModifier | self.ctl_9
        self.ctl_minus = Qt.ControlModifier | Qt.Key_Minus
        self.ctl_equal = Qt.ControlModifier | Qt.Key_Equal
        self.ctl_plus = Qt.ControlModifier | Qt.Key_Plus
        self.ctl_shft_equal = Qt.ShiftModifier | self.ctl_equal
        self.ctl_L = Qt.ControlModifier | Qt.Key_L
        self.ctl_alt_L = Qt.AltModifier | self.ctl_L
        self.ctl_P = Qt.ControlModifier | Qt.Key_P
        self.ctl_alt_P = Qt.AltModifier | self.ctl_P
        self.keysOfInterest = [self.ctl_G, self.ctl_shft_G, self.ctl_F, self.ctl_T,
                              self.ctl_equal, self.ctl_shft_T,
                self.ctl_1, self.ctl_2, self.ctl_3, self.ctl_4, self.ctl_5,
                self.ctl_6, self.ctl_7, self.ctl_8, self.ctl_9,
                self.ctl_shft_F, self.ctl_alt_1, self.ctl_alt_2, self.ctl_alt_3,
                self.ctl_alt_4,  self.ctl_alt_5,  self.ctl_alt_6,  self.ctl_alt_7,
                self.ctl_alt_8,  self.ctl_alt_9,
                self.ctl_minus, self.ctl_plus, self.ctl_shft_equal,
                self.ctl_L,self.ctl_alt_L,self.ctl_P,self.ctl_alt_P]
        self.findKeys = [self.ctl_G, self.ctl_shft_G, self.ctl_F, self.ctl_shft_F,
                        self.ctl_T, self.ctl_equal, self.ctl_shft_T]
        self.markKeys = [self.ctl_1, self.ctl_2, self.ctl_3, self.ctl_4, self.ctl_5,
                self.ctl_6, self.ctl_7, self.ctl_8, self.ctl_9]
        self.markSetKeys = [self.ctl_alt_1, self.ctl_alt_2, self.ctl_alt_3,
                self.ctl_alt_4,  self.ctl_alt_5,  self.ctl_alt_6,  self.ctl_alt_7,
                self.ctl_alt_8,  self.ctl_alt_9]
