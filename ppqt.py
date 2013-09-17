# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.2.0" # refer to PEP-0008
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

import os # for dict path manipulations
import sys # for argv, passed to QApplication
import platform # for mac detection
import argparse # for a command-line filename or --version argument

from PyQt4.QtCore import (Qt, QSettings, QString )
from PyQt4.QtGui import ( QApplication, QFont, QFontDatabase )

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
#  pqFnote.py defines the footnote manager widget
#
#  pqHtml.py  defines the html conversion manager
#
#  pqView.py  defines the live html preview widget
#
#  pgHelp.py  displays the program manual (whose text is in pqHelp.html).
# Some modules have unit-test code that runs if they are executed stand-alone.
# Each module imports whatever classes of PyQt.Qtxx it needs. This causes
# some duplication; we trust Python to not import duplicate code.

# Create the Inter-Module Communicator
import pqIMC
IMC = pqIMC.tricorder()

# Collect version and copyright info into one string suitable for the
# argparse version action.
versionstr = 'PPQT Version {0}\n(with PyQt {1} and Qt {2})\n{3}'.format(
    __version__, IMC.version_pyqt, IMC.version_qt, __copyright__)

# Display copyright and version on the console, which may or may not be visible
print(versionstr)

# Pre-parse the argv string. If --version, it displays and exits. If a filename
# is given, it is saved as args.filename. Qt-specific options are ignored.
parser = argparse.ArgumentParser(description='PPQT.')
parser.add_argument('filename', nargs='?', help=u"Name of file to open")
parser.add_argument('--version', action='version', version=versionstr)
args, _ = parser.parse_known_args()

# Create the application, which needs to exist for some of the following
# operations to work, and sign it with our names so that
# saved settings go in reasonable places. QApplication picks Qt args from argv.
app = QApplication(sys.argv)
app.setOrganizationName("PGDP")
app.setOrganizationDomain("pgdp.net")
app.setApplicationName("PPQT")

# Get the message support for diagnostics
import pqMsgs # misc message and font routines
pqMsgs.IMC = IMC

pqMsgs.noteEvent("Getting path to bundled files")
#-- but we get our path different ways depending
# on whether we are running in development or bundled by pyinstaller.
if hasattr(sys, 'frozen') : # bundled by pyinstaller?
    base = os.path.dirname(sys.executable)
else: # running under normal python e.g. from command line or an IDE
    base = os.path.dirname(__file__)
IMC.appBasePath = base

# Establish what should be the path to our spellcheck dictionary folder "dict"
# It, like our "extras" and "fonts" folders are at the same level as the app.

IMC.dictPath = os.path.join(base,u"dict")

# Initialize the font system. We need a monospaced font with clear visual
# separation between 0/O, 1/l, etc, and a good complement of Unicode, with
# at a minimum full support of Greek, Cyrillic and Hebrew. These features are
# found in Liberation Mono, which is free, and by Courier New, which is less
# readable but is bundled in most OSs by default, and by Everson Mono.
# We prefer Liberation Mono, but set that or Courier New as the default font family
# and as our App's default font. pqMain uses it as a default when
# reading the font family name from the saved settings.

pqMsgs.noteEvent("Setting up default font name")

lm_name = QString(u'Liberation Mono')
qfdb = QFontDatabase()
qf = qfdb.font(lm_name,QString(u'Regular'),12)
if qf.family() == lm_name :
    # Lib. Mono is installed in this system, good to go
    IMC.defaultFontFamily = lm_name
else:
    # Let's try to install Lib. Mono. Was it bundled with us?
    fpath = os.path.join(base,u"fonts")
    if os.path.exists(fpath) :
        # It was; add each .ttf in it to the Qt font database
        # We are *assuming* that what's in fonts is Liberation Mono Regular
        # for sure, and optionally other variants like bold.
        for fname in os.listdir(fpath) :
            if fname.endswith(u'.ttf') :
                qfdb.addApplicationFont(QString(os.path.join(fpath,fname)))
        IMC.defaultFontFamily = lm_name
    else :
        # OK, no fonts bundled with us (or they've been removed?)
        IMC.defaultFontFamily = QString(u'Courier New')
IMC.fontFamily = IMC.defaultFontFamily # pqMain may override
# Make the application default be that which we just set
# app.setFont(pqMsgs.getMonoFont()) -- do NOT as it is a bad
# idea to have monospaced menus, titles, etc!

# Import each submodule and stick a reference to IMC into it.

import pqLists # implements ordered lists of words for quick lookup
pqLists.IMC = IMC
# instantiate all our lists empty
IMC.scannoList = pqLists.wordList()
IMC.goodWordList = pqLists.wordList()
IMC.badWordList = pqLists.wordList()
IMC.wordCensus = pqLists.vocabList()
IMC.charCensus = pqLists.vocabList()

import pqPages # page and folio table
pqPages.IMC = IMC
IMC.pageTable = pqPages.pagedb()

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

import pqFlow # text reflow
pqFlow.IMC = IMC

import pqTable # flow's partner in crime, table reflow
pqTable.IMC = IMC

import pqFnote # footnote management
pqFnote.IMC = IMC

import pqView # html preview
pqView.IMC = IMC

import pqHelp # help panel
pqHelp.IMC = IMC

import pqMain # code to create the main window and all menus
pqMain.IMC = IMC

pqMsgs.noteEvent("Done with most imports, opening settings")

# Create a default settings object, or access an existing one. Settings
# are stored using the app and organization names defined just above in:
# * Mac OS : ~/Library/Preferences/com.pgdp.org
# * Linux : ~/.config/PGDP
# * Windows : in the Registry under /Software/PGDP.
IMC.settings = QSettings()

pqMsgs.noteEvent("Creating spellchecker (which loads a dict)")

import pqSpell # Spell-check routines (which use the settings)
pqSpell.IMC = IMC

# create the spellcheck, loading the last-set dictionary
IMC.spellCheck = pqSpell.makeSpellCheck()

pqMsgs.noteEvent("Creating main window...")

# Create the main window and all the tabs in it
IMC.mainWindow = pqMain.MainWindow()
# Display and execute!

IMC.mainWindow.show()

# If we are invoked from a command line and a filename was given,
# try to open it. If there is a problem, for example if the file is
# not found, there will be a popup diagnostic that the user will
# have to dismiss and then we continue as normal.
#
# Useability note: We have considered automatically reopening the
# last-used file on startup. Here would be the point at which to
# trigger that action (if args.filename was empty). Decided against
# that feature because (a) if you want it, it is 2 clicks at the
# top of the recent-files list, and (b) if you don't want it, it's
# a needless delay in startup and (c) if it moved or doesn't exist,
# either it's a gratuitous error message or if you check for existence,
# how far down the recent-files list should you go?
if args.filename:
    IMC.mainWindow.loadFile(args.filename, None)

pqMsgs.noteEvent("Starting the app (event loop)")

app.exec_()