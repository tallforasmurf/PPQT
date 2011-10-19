# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
 A PGDP Post-processing tool in Python and PyQt.
 
 A single document file, bookname.suffix, is edited. A variety of metadata
 is collected the first time a file is opened and is saved in a metadata file,
 bookname.suffix.metadata. Also expected to exist at the same file path
 as the document:
     bookname.suffix
     bookname.suffix.meta (created on first save)
     good_words.txt (optional)
     bad_words.txt (optional)
     pngs, a folder containing scan images named nnn.png
     regexes.txt, optional file of predefined regexes for this book

 The main window is has two panes divided by a splitter. The left pane has
 the text for editing (QTextEdit). The right pane is tabbed and offers a
 variety of views:
 
    Pngs :   a tab showing the image (nnn.png) for the text where the 
             user is editing (insertion point) from the pngs folder.
    
    Find :   a panel with a variety of search/replace controls including
             predefined regex searches (e.g. find poetry markup) and buttons
             that the user can program with regexes (from regexes.txt)
    
    Notes :  a QSimpleTextEdit where the user can keep notes that
             are saved as part of the metadata.

    Pages :  a table of all pages with their scan (.png) numbers, folio
             (pagination) controls, and proofer ids. Maintained from metadata
             after page delimiters are purged.
    
    Chars :  a table of the character census, showing for each its glyph,
             hex value, count, and class (e.g. ascii, utf, windows etc),
             sortable on any column.
    
    Words :  a table of the word census, showing for each its text, count,
             and class info (e.g. all-cap, fails spellcheck, etc), sortable
             by text and count, and filterable on class.
    
    Flow :   a tab offering various controls for text reflow, page delimiter
             removal, and ascii table processing.

    FNote :  a panel with controls related to footnote processing and a table
             of footnotes found with errors indicated.
    
    Html :   a tab offering controls related to Html conversion.
    
    View :   live preview of the (html) document (QWebView)
'''

'''
Acknowledgements and Credits

First to Steve Shulz (Thundergnat) who created and maintained Guiguts,
the program from which we have taken inspiration and lots of methods.

Second to Mark Summerfield for the book "Rapid GUI Developement with PyQt"
without which we couldn't have done this.

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
import sys # for argv, passed to QApplication
import platform # for mac detection

from PyQt4.QtCore import (Qt, QSettings )
from PyQt4.QtGui import ( QApplication )

# Program structure:
# This module imports a series of other modules, one for each major UI widget
# and some for general utility, as follows:
#
#  pqSpell.py defines an interface to Aspell
#
#  pqLists.py defines search list objects used for good_words, bad_words,
#             and for the word and character censuses.
#
#  pqEdit.py  defines the text editor object including all its user
#             interactions and metadata storage.
#
#  pqMain.py  defines the Main window in which everything else is shown.
#
#  pqPngs.py  defines the pngs widget for viewing scanned page images.
#
#  pqNotes.py defines the user-notes widget.
#
#  pqChars.py defines the character census table widget.
#
#  pqWords.py defines the word census table widget.
#
#  pqFind.py  defines the find/replace widget
#
#  pqPages.py defines the page and folio table widget
#
#  pqFlow.py  defines the reflow controls widget
#
#  pqFoots.py defines the footnote manager widget
#
#  pqHtml.py  defines the html conversion manager
#
#  pqView.py  defines the live html preview widget
#
# Some modules have unit-test code that runs if they are executed stand-alone.
# Each module imports whatever classes of PyQt.Qtxx it needs. This causes
# some duplication; we trust Python to not import duplicate code.
#
# Modules need access to each other and to global constants, and this
# is provided by assigning values to an object named IMC, a reference to
# which is stored into each object when it is imported. IMC should be treated
# as read-only by all modules (but there is no enforcement of this).
#
class tricorder():
	def __init__(self):
		pass

IMC = tricorder()

# Constants of interest to multiple modules (think of a header file):
# Word characteristics stored in the word census list:

IMC.WordHasUpper = 0x01
IMC.WordHasLower = 0x02
IMC.WordHasDigit = 0x04
IMC.WordHasHyphen = 0x08
IMC.WordHasApostrophe = 0x10
IMC.WordMisspelt = 0x80

# Folio controls for the Page/folio table

IMC.FolioFormatArabic = 0x00
IMC.FolioFormatUCRom = 0x01
IMC.FolioFormatLCRom = 0x02

IMC.FolioRuleAdd1 = 0x00
IMC.FolioRuleSet = 0x01
IMC.FolioRuleSkip = 0x02

# Controls on the edit word hiliter, queried in the editor and
# set by the Main window menu actions:

IMC.scannoHiliteSwitch = False
IMC.spellingHiliteSwitch = False

# Keystrokes checked by editor and other panels

# In rough order of frequency of use we support:
# ^g and ^G, search again forward/backward,
# ^f start search,
# ^t and ^T replace and search forward/backward,
# ^1-9 bookmarks
# ^F start search with selection
# ^= replace,
# ^-alt-1-9 set bookmarks
# ^+/- zoom also ctrl-shift-equal which is how plus comes in usually
# ^l and ^-alt-l, ^p and ^-alt-p for the Notes panel

IMC.ctl_G = Qt.ControlModifier | Qt.Key_G
IMC.ctl_shft_G = Qt.ShiftModifier | IMC.ctl_G
IMC.ctl_F = Qt.ControlModifier | Qt.Key_F
IMC.ctl_T = Qt.ControlModifier | Qt.Key_T
IMC.ctl_shft_T = Qt.ShiftModifier | IMC.ctl_T
IMC.ctl_1 = Qt.ControlModifier | Qt.Key_1
IMC.ctl_2 = Qt.ControlModifier | Qt.Key_2
IMC.ctl_3 = Qt.ControlModifier | Qt.Key_3
IMC.ctl_4 = Qt.ControlModifier | Qt.Key_4
IMC.ctl_5 = Qt.ControlModifier | Qt.Key_5
IMC.ctl_6 = Qt.ControlModifier | Qt.Key_6
IMC.ctl_7 = Qt.ControlModifier | Qt.Key_7
IMC.ctl_8 = Qt.ControlModifier | Qt.Key_8
IMC.ctl_9 = Qt.ControlModifier | Qt.Key_9
IMC.ctl_shft_F = Qt.ShiftModifier | IMC.ctl_F
IMC.ctl_alt_1 = Qt.AltModifier | IMC.ctl_1
IMC.ctl_alt_2 = Qt.AltModifier | IMC.ctl_2
IMC.ctl_alt_3 = Qt.AltModifier | IMC.ctl_3
IMC.ctl_alt_4 = Qt.AltModifier | IMC.ctl_4
IMC.ctl_alt_5 = Qt.AltModifier | IMC.ctl_5
IMC.ctl_alt_6 = Qt.AltModifier | IMC.ctl_6
IMC.ctl_alt_7 = Qt.AltModifier | IMC.ctl_7
IMC.ctl_alt_8 = Qt.AltModifier | IMC.ctl_8
IMC.ctl_alt_9 = Qt.AltModifier | IMC.ctl_9
IMC.ctl_minus = Qt.ControlModifier | Qt.Key_Minus
IMC.ctl_equal = Qt.ControlModifier | Qt.Key_Equal
IMC.ctl_plus = Qt.ControlModifier | Qt.Key_Plus
IMC.ctl_shft_equal = Qt.ShiftModifier | IMC.ctl_equal
IMC.ctl_L = Qt.ControlModifier | Qt.Key_L
IMC.ctl_alt_L = Qt.AltModifier | IMC.ctl_L
IMC.ctl_P = Qt.ControlModifier | Qt.Key_P
IMC.ctl_alt_P = Qt.AltModifier | IMC.ctl_P
IMC.keysOfInterest = [IMC.ctl_G, IMC.ctl_shft_G, IMC.ctl_F, IMC.ctl_T,
                      IMC.ctl_equal, IMC.ctl_shft_T,
        IMC.ctl_1, IMC.ctl_2, IMC.ctl_3, IMC.ctl_4, IMC.ctl_5,
        IMC.ctl_6, IMC.ctl_7, IMC.ctl_8, IMC.ctl_9,
        IMC.ctl_shft_F, IMC.ctl_alt_1, IMC.ctl_alt_2, IMC.ctl_alt_3,
        IMC.ctl_alt_4,  IMC.ctl_alt_5,  IMC.ctl_alt_6,  IMC.ctl_alt_7,
        IMC.ctl_alt_8,  IMC.ctl_alt_9,
        IMC.ctl_minus, IMC.ctl_plus, IMC.ctl_shft_equal,
        IMC.ctl_L,IMC.ctl_alt_L,IMC.ctl_P,IMC.ctl_alt_P]
IMC.findKeys = [IMC.ctl_G, IMC.ctl_shft_G, IMC.ctl_F, IMC.ctl_shft_F,
                IMC.ctl_T, IMC.ctl_equal, IMC.ctl_shft_T]
IMC.markKeys = [IMC.ctl_1, IMC.ctl_2, IMC.ctl_3, IMC.ctl_4, IMC.ctl_5,
        IMC.ctl_6, IMC.ctl_7, IMC.ctl_8, IMC.ctl_9]
IMC.markSetKeys = [IMC.ctl_alt_1, IMC.ctl_alt_2, IMC.ctl_alt_3,
        IMC.ctl_alt_4,  IMC.ctl_alt_5,  IMC.ctl_alt_6,  IMC.ctl_alt_7,
        IMC.ctl_alt_8,  IMC.ctl_alt_9]
import pqMsgs
pqMsgs.IMC = IMC
# Import the spell-check code and create an object the represents
# the gateway to Aspell:

import pqSpell
pqSpell.IMC = IMC
IMC.aspell = pqSpell.makeAspell()

# pqLists.py implements the badwords, goodwords, and scannos lists
# and provides quick lookup in them.

import pqLists
pqLists.IMC = IMC
IMC.scannoList = pqLists.wordList()
IMC.goodWordList = pqLists.wordList()
IMC.badWordList = pqLists.wordList()
IMC.wordCensus = pqLists.vocabList()
IMC.charCensus = pqLists.vocabList()
IMC.pageTable = []

import pqEdit
pqEdit.IMC = IMC
IMC.editWidget = None # created in pqMain

import pqPngs
pqPngs.IMC = IMC

import pqNotes
pqNotes.IMC = IMC

import pqFind
pqFind.IMC = IMC

import pqChars
pqChars.IMC = IMC

import pqWords
pqWords.IMC = IMC

import pqPages
pqPages.IMC = IMC

import pqFlow
pqFlow.IMC = IMC

import pqMain
pqMain.IMC = IMC

#
# and awayyyyyy we go
# Create the application and sign it with our names so that
# saved settings go in reasonable places
app = QApplication(sys.argv)
app.setOrganizationName("PGDP")
app.setOrganizationDomain("pgdp.org")
app.setApplicationName("PPQT")

# Create a default settings object, which will be stored using
# the app and organization names set just above. In Mac OS it
# goes in ~/Library/Preferences/com.pgdp.org; on Linux, in
# ~/.config/PGDP; on Windows, in the Registry under /Software/PGDP.
IMC.settings = QSettings()

IMC.mainWindow = pqMain.MainWindow() # create the main window (creates all tabs)
IMC.mainWindow.show()
app.exec_()
