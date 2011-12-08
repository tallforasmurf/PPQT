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
import os # for dict path manipulations
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
#  pqSpell.py defines an interface to some spell-checker
#             (via enchant, typically MySpell)
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
import pqIMC
IMC = pqIMC.tricorder()

# Import each submodule and stick a reference to IMC in it.
import pqMsgs # misc message and font routines
pqMsgs.IMC = IMC

import pqLists # implements ordered lists of words for quick lookup
# instantiate all our lists empty
pqLists.IMC = IMC
IMC.scannoList = pqLists.wordList()
IMC.goodWordList = pqLists.wordList()
IMC.badWordList = pqLists.wordList()
IMC.wordCensus = pqLists.vocabList()
IMC.charCensus = pqLists.vocabList()
IMC.pageTable = []

import pqEdit # the main edit widget plus save and load metadata
pqEdit.IMC = IMC

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

import pqView # html preview
pqView.IMC = IMC

import pqHelp
pqHelp.IMC = IMC

import pqMain # code to create the main window and all menus
pqMain.IMC = IMC

# and awayyyyyy we go:
# Create the application and sign it with our names so that
# saved settings go in reasonable places
app = QApplication(sys.argv)
app.setOrganizationName("PGDP")
app.setOrganizationDomain("pgdp.net")
app.setApplicationName("PPQT")

# Create a default settings object, which will be stored using
# the app and organization names set just above. It is stored in:
# * Mac OS : ~/Library/Preferences/com.pgdp.org
# * Linux : ~/.config/PGDP
# * Windows : in the Registry under /Software/PGDP.
IMC.settings = QSettings()

# Establish what should be a path to our spellcheck dictionary folder "dict"
# We expect the folder of dicts to be at the same level as this executable,
# -- yes, cheesy as heck! -- but we get our path different ways depending
# on whether we are running in development or bundled by pyinstaller.
if hasattr(sys, 'frozen') : # bundled by pyinstaller?
	base = os.path.dirname(sys.executable)
else: # running normally
	base = os.path.dirname(__file__)
IMC.dictPath = os.path.join(base,u"dict")

import pqSpell # Spell-check routines (which use the settings)
pqSpell.IMC = IMC
IMC.spellCheck = pqSpell.makeSpellCheck()

IMC.mainWindow = pqMain.MainWindow() # create the main window and all tabs
IMC.mainWindow.show()
app.exec_()
