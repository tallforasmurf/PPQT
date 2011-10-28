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
 as bookname.suffix:
     bookname.suffix.meta (created on first save)
     good_words.txt (optional)
     bad_words.txt (optional)
     pngs, a folder containing scan images named nnn.png

 The main window has two panes divided by a splitter. The left pane has
 the text for editing (QPlainTextEdit). The right pane is tabbed and offers a
 variety of panels, each with a specific function:
 
    Pngs :   Shows the scan image (nnn.png) for the text at the insertion point
	     from the pngs folder.
    
    Find :   A variety of search/replace controls including predefined regex
             searches in a user-programmable button array.
    
    Notes :  A QPlainTextEdit where the user can keep notes that are saved as
	     part of the metadata.

    Pages :  A table of all pages with their scan (.png) numbers, folio
             (pagination) controls, and proofer ids. Page boundaries are kept
	     in the metadata after page delimiters are purged.
    
    Chars :  A table of the character census, showing for each its glyph,
             hex value, count, and Unicode class, sortable on any column.
    
    Words :  A table of the word census, showing for each its text, count,
             and class info (all-cap, fails spellcheck, etc), sortable
             by text and count, and filterable on class.
    
    Flow :   Various controls for text reflow, page delimiter removal, and
	     ascii table processing.

    FNote :  Controls related to footnote processing and a table of the
             footnotes found, with errors indicated.
    
    Html :   Controls related to Html conversion.
    
    View :   Live preview of the (html) document (QWebView)
'''

'''
Acknowledgements and Credits

First to Steve Shulz (Thundergnat) who created and maintained Guiguts,
the program from which we have taken inspiration and lots of methods.

Second to Mark Summerfield for the book "Rapid GUI Development with PyQt"
without which we couldn't have done this.
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

import sys # for argv, passed to QApplication
import platform # for mac detection

from PyQt4.QtCore import (Qt, QSettings )
from PyQt4.QtGui import ( QApplication )

# A note on variable names: since we started working from Summerfield's code
# we adopted his use of camelCase names. Later we found out that Python coders
# generally prefer lots_o_under_bars. Too late. CamelCase rules. Global names
# only are initial-cap, others lowerCase.
#
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
#  pqMain.py  defines the Main window in which everything else is shown, and
#             instantiates all the other widgets.
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
#  pqFoot.py defines the footnote manager widget
#
#  pqHtml.py  defines the html conversion manager
#
#  pqView.py  defines the live html preview widget
#
#  pgHelp.py  displays the program manual (whose text is in pqHelp.html).
#
# Some modules have unit-test code that runs if they are executed stand-alone.
# Each module imports whatever classes of PyQt.Qtxx it needs. This causes
# some duplication; we trust Python to not import duplicate code.
#
# Modules need access to each other and to global constants, and this
# is provided by assigning values to an object named IMC, (Inter-Module
# Communicator), a reference to which is stored into each object after it is
# imported, see below.
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
# set by the Main window View menu actions:

IMC.scannoHiliteSwitch = False
IMC.spellingHiliteSwitch = False

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

# Import each submodule and stick a reference to IMC in it.
import pqMsgs # misc message and font routines
pqMsgs.IMC = IMC

import pqSpell # Spell-check routines and gateway to Aspell
pqSpell.IMC = IMC
IMC.aspell = pqSpell.makeAspell()

import pqLists # ordered lists of words for quick lookup
pqLists.IMC = IMC
IMC.scannoList = pqLists.wordList()
IMC.goodWordList = pqLists.wordList()
IMC.badWordList = pqLists.wordList()
IMC.wordCensus = pqLists.vocabList()
IMC.charCensus = pqLists.vocabList()
IMC.pageTable = []

import pqEdit # the main edit widget plus save and load metadata
pqEdit.IMC = IMC
IMC.editWidget = None # instantiated in pqMain

import pqPngs # scan image display
pqPngs.IMC = IMC

import pqNotes # notes
pqNotes.IMC = IMC

import pqFind # find/replace
pqFind.IMC = IMC

import pqChars # character census table
pqChars.IMC = IMC

import pqWords # word census table
pqWords.IMC = IMC

import pqPages # page and folio table
pqPages.IMC = IMC

import pqFlow # text reflow
pqFlow.IMC = IMC

#import pqFoot # footnote management
# pqFoot.IMC = IMC

#import pqHtml # html conversion
# pqHtml.IMC = IMC

# import pqView # html preview
# pqView.IMC = IMC

import pqHelp
pqHelp.IMC = IMC

import pqMain # code for the main window and all menus
pqMain.IMC = IMC

# and awayyyyyy we go:
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

IMC.mainWindow = pqMain.MainWindow() # create the main window and all tabs
IMC.mainWindow.show()
app.exec_()
