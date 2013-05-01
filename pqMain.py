# must precede anything except #comments, including the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.02.0" # refer to PEP-0008
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

'''
Create the main window and lay it out with a splitter,
editor on the left, tabs on the right. Create menus and menu actions.
Most of this is based on code from Summerfield's book, without which not.

'''
 # used in detecting encodings of ambiguous files
import io 
from chardet.universaldetector import UniversalDetector

from PyQt4.QtCore import ( pyqtSignal, Qt,
    QFile, QFileInfo, QDir,
    QIODevice, QPoint, QRegExp, QSize,
    QSettings,
    QString, QStringList,
    QTextStream,
    QVariant,
    SIGNAL, SLOT)

from PyQt4.QtGui import (
    QAction,
    QFileDialog,
    QFont, QFontDialog, QFontInfo,
    QFrame,
    QKeySequence,
    QMainWindow, QMenu, QMenuBar,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextCursor)

import pqEdit
import pqPngs
import pqMsgs
import pqNotes
import pqFind
import pqChars
import pqWords
import pqPages
import pqFlow
import pqFnote
import pqView
import pqHelp
# -------------------------------------------------------------------------#
#
# The parent module begins execution by instantiating one of these.
# In this __init__ we create the main window and all the panels in it.
#
class MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        IMC.mainWindow = self # give other panels our address during init
        # -----------------------------------------------------------------
        # Set up the file paths and related stuff used by our methods:
        #  * IMC.bookPath is the full path to the current document; when
        #    IMC.bookPath.isEmpty() there is no current document.
        IMC.bookPath = QString()
        #  * IMC.bookDirPath is the leading part of bookFile, used to
        #    look for pngs, goodwords etc, and to start open/save dialogs.
        #    (also used in pqView as the URL basepath for image lookup)
        IMC.bookDirPath = QString()
        #  * IMC.bookType is the file suffix, for those who care.
        IMC.bookType = QString()
        #  * self.buttonDirPath is the default directory start for opening
        #    or saving user Find buttons. Initialize to our extras directory.
        self.buttonDirPath = QString(IMC.appBasePath + u"/extras/" )
        #  * character detector object used when opening an ambiguous file
        self.charDetector = None # instantiated when first needed
        self.utfEncoding = QString(u'UTF-8') # handy consts
        self.ltnEncoding = QString(u'ISO-8859-1')
        #  * IMC.saveEncoding is the encoding ID as a python string
        IMC.saveEncoding = unicode(self.utfEncoding)
        # Recall a scannoPath if we had one, else get a default empty QString
        # See closeEvent() below for how this and other settings are saved.
        self.scannoPath = IMC.settings.value("main/scannoPath",
                                             QString()).toString()
        # If we had a scannoPath, try to load it.
        if not self.scannoPath.isEmpty() :
            
            # +++++++ Temp O'Rary +++++
            pqMsgs.noteEvent("..Loading scanno file")
            
            self.scannoLoad()
        # Recall the setting of the scanno hilite switch and adjust for whether
        # we were able to load the recalled file.
        IMC.scannoHiliteSwitch = IMC.settings.value("main/scannoSwitch",
                        False).toBool() and (not self.scannoPath.isEmpty())
        # n.b. we leave the spellcheck switch initialized False because we
        # have no file loaded.
        # -----------------------------------------------------------------
        # Recall a user-selected font if any:
        IMC.fontFamily = IMC.settings.value("main/fontFamily", IMC.defaultFontFamily).toString()
        (IMC.fontSize,junk) = IMC.settings.value("main/fontSize",12).toInt()
        # -----------------------------------------------------------------
        # Create the editor for the left-hand pane. Put a reference in the
        # IMC for other modules to use in calling edit members. Hook up the
        # signal for document-modification-state-change to our slot where
        # we set the document title bar status flag, and the signal for 
        # text change for where we note a change of text.
        
        pqMsgs.noteEvent("..creating edit panel")

        self.editor = pqEdit.PPTextEditor(self,IMC.fontSize)
        IMC.editWidget = self.editor # let other modules access edit methods
        self.connect(self.editor, SIGNAL("modificationChanged(bool)"),
                     self.ohModificationChanged)
        self.connect(self.editor, SIGNAL("textChanged()"),
                     self.ohTextChanged)
        # -----------------------------------------------------------------
        # Format the window as a split between an editor and a tab array
        # to hold all the other panels.
        self.tabSet = QTabWidget()
        self.hSplitter = QSplitter(Qt.Horizontal)
        self.hSplitter.addWidget(self.editor)
        self.hSplitter.addWidget(self.tabSet)
        self.setCentralWidget(self.hSplitter)
        # -----------------------------------------------------------------
        # Populate the tab set with the different panel objects:
        #
        # 1. Create the pngs display and connect it to the editors
        # cursor-move signal and our doc-has-changed and shut-down signals.
        #
        
        pqMsgs.noteEvent("..creating Pngs panel")

        IMC.pngPanel = pqPngs.pngDisplay()
        self.tabSet.addTab(IMC.pngPanel, u"Pngs")
        self.connect(self.editor, SIGNAL("cursorPositionChanged()"),
                        IMC.pngPanel.newPosition)
        self.connect(self, SIGNAL("docHasChanged"), IMC.pngPanel.newFile)
        self.connect(self, SIGNAL("shuttingDown"), IMC.pngPanel.shuttingDown)
        #
        # 2. Create the notes panel editor.
        #
        
        pqMsgs.noteEvent("..creating Notes panel")
        
        IMC.notesEditor = pqNotes.notesEditor()
        self.tabSet.addTab(IMC.notesEditor, u"Notes")
        #
        # 3. Create the find panel and connect it to the editor's ^f keypress
        # signal and our doc-has-changed and shut-down signals.

        pqMsgs.noteEvent("..creating Find panel")
        
        IMC.findPanel = pqFind.findPanel()
        self.tabSet.addTab(IMC.findPanel, u"Find")
        self.connect(self.editor, SIGNAL("editKeyPress"),
                     IMC.findPanel.editKeyPress)
        self.connect(self, SIGNAL("shuttingDown"), IMC.findPanel.shuttingDown)
        self.connect(self, SIGNAL("docHasChanged"), IMC.findPanel.docHasChanged)   
        #
        # 4. Create Char Census panel and give it both the doc-has-changed
        # and the preceding doc-will-change signals (but not shutdown).

        pqMsgs.noteEvent("..creating Chars panel")
        
        self.charPanel = pqChars.charsPanel()
        self.tabSet.addTab(self.charPanel, u"Char")
        self.connect(self, SIGNAL("docWillChange"), self.charPanel.docWillChange)
        self.connect(self, SIGNAL("docHasChanged"), self.charPanel.docHasChanged)   
        #
        # 5. Create Word Census Panel and give it signals.

        pqMsgs.noteEvent("..creating Words panel")
        
        self.wordPanel = pqWords.wordsPanel()
        self.tabSet.addTab(self.wordPanel, u"Word")
        self.connect(self, SIGNAL("docWillChange"), self.wordPanel.docWillChange)
        self.connect(self, SIGNAL("docHasChanged"), self.wordPanel.docHasChanged)   
        #
        # 6. Create Pages Panel and give it signals.

        pqMsgs.noteEvent("..creating Pages panel")
        
        self.pagePanel = pqPages.pagesPanel()
        self.tabSet.addTab(self.pagePanel, u"Pages")
        self.connect(self, SIGNAL("docWillChange"), self.pagePanel.docWillChange)
        self.connect(self, SIGNAL("docHasChanged"), self.pagePanel.docHasChanged)
        #
        # 7. Create the Flow panel. It only gets the shutdown signal, which it 
        # uses to save all its user settings.

        pqMsgs.noteEvent("..creating Flow panel")
        
        
        self.flowPanel = pqFlow.flowPanel()
        self.tabSet.addTab(self.flowPanel, u"Flow")
        self.connect(self, SIGNAL("shuttingDown"), self.flowPanel.shuttingDown)
        #
        # 8. Create the Footnote Panel which gets both sides of doc-changed
        # to clear its table.

        pqMsgs.noteEvent("..creating Fnote panel")
        
        self.fnotePanel = pqFnote.fnotePanel()
        self.tabSet.addTab(self.fnotePanel, u"Fnote")
        self.connect(self, SIGNAL("docWillChange"), self.fnotePanel.docWillChange)
        self.connect(self, SIGNAL("docHasChanged"), self.fnotePanel.docHasChanged)   
        #
        # 9. Create the html Preview Panel - it's simple, needs no signals

        pqMsgs.noteEvent("..creating View panel")
        
        self.pvwPanel = pqView.htmlPreview()
        self.tabSet.addTab(self.pvwPanel, u"Pvw")
        #
        # 10. Lastly, the Help panel:

        pqMsgs.noteEvent("..creating Help panel")
        
        
        self.helpPanel = pqHelp.helpDisplay()
        self.tabSet.addTab(self.helpPanel, u"Help")
        # We could now do either self.tabSet.setCurrentIndex(1) to make the
        # pngs panel current, but that seems to happen by default. Or, we 
        # could at shutdown save the last-set tab index and restore it?
        #
        # ------------------------------------------------------------------
        # Now set up the bottom of the window: status, line#, and progress bar.
        #

        pqMsgs.noteEvent("..completing main window")
        
        status = self.statusBar()
        status.setSizeGripEnabled(False)
        # Create the line number widget. The widget definition is in pqMsgs.
        # It gets the cursor movement signal from the editor, obviously.
        # status.addWidget puts it at the extreme left, effectively "under"
        # the permanent status message area, which may sometimes overlay it.
        self.lnum = pqMsgs.lineLabel()
        self.connect(self.editor, SIGNAL("cursorPositionChanged()"),
                        self.lnum.cursorMoved)
        status.addPermanentWidget(self.lnum)
        # Create the progress bar in our status bar, in pqMsgs because that
        # is where are all the routines to run it. It adds at  the extreme right.
        pqMsgs.makeBarIn(status)
        #
        # -----------------------------------------------------------------
        # Get our window geometry from the settings file and set it, restoring
        # the last-set window size and splitter position.
        self.resize(IMC.settings.value("main/size",
                                       QVariant(QSize(800,600))).toSize() )
        self.move(IMC.settings.value("main/position",
                                       QPoint(100, 100)).toPoint() )
        self.hSplitter.restoreState(
                            IMC.settings.value("main/splitter").toByteArray() )
        #
        # -----------------------------------------------------------------
        # Tell the editor to clear itself in order to initialize everything
        # related to the document.
        self.editor.clear()
        #
        # -----------------------------------------------------------------
        # Put a message in our status bar for 5 seconds.
        status.showMessage("Ready", 5000)

        pqMsgs.noteEvent("..setting up menus")
        
        #
        # -----------------------------------------------------------------
        # Set up the menu actions, then create menus to invoke them.
        # 
        # Create actions for the File menu. All are parented by the main window.
        # Their shortcuts are always active.
        fileNewAction = self.createAction("&New...", None, self.fileNew,
                QKeySequence.New, "Clear to an empty state")
        fileOpenAction = self.createAction("&Open...", None, 
                lambda : self.fileOpen(None),
                QKeySequence.Open, "Open a book and its metadata")
        fileOpenWithUTF = self.createAction("Open UTF-8", None,
                lambda : self.fileOpen(u'UTF-8'),
                None, "Open a book encoded UTF-8")
        fileOpenWithLTN = self.createAction("Open Latin-1", None,
                lambda : self.fileOpen(u'ISO-8859-1'),
                None, "Open a book encoded ISO-8859-1")
        fileOpenWithWIN = self.createAction("Open CP1252", None,
                lambda : self.fileOpen(u'CP1252'),
                None, "Open a book encoded Windows CP1252")
        fileOpenWithMAC = self.createAction("Open MacRoman", None,
                lambda : self.fileOpen(u'macintosh'),
                None, "Open a book encoded Mac Roman")
        fileSaveAction = self.createAction("&Save", None, self.fileSave,
                QKeySequence.Save, "Save the book and metadata")
        fileSaveAsAction = self.createAction("Save &As...", None,
                self.fileSaveAs, QKeySequence.SaveAs,
                "Save the book under a new name")
        fileScannosAction = self.createAction("Scannos...", None,
                self.scannoOpen, None, "Read list of likely scannos")
        fileButtonLoadAction = self.createAction("Load Find Buttons...", None,
                self.buttonLoad, None, "Read user-defined buttons in Find Panel")
        fileButtonSaveAction = self.createAction("Save Find buttons...", None,
                self.buttonSave, None, "Save user-defined buttons in Find Panel")
        fileQuitAction = self.createAction("&Quit", None, self.close,
                QKeySequence.Quit, "Close the application")
        # -----------------------------------------------------------------
        # Create the File menu but don't populate it yet. We do that on the
        # fly, adding recent files to it. Save the prepared actions as tuples
        # for convenient use when it is time to populate the menu.
        self.fileMenu = self.menuBar().addMenu("&File")
        # actions preceding the open with encoding submenu
        self.fileMenuActions1 = (fileNewAction, fileOpenAction)
        self.openWithMenu = QMenu("Open With Encoding")
        self.openWithMenu.addAction(fileOpenWithUTF)
        self.openWithMenu.addAction(fileOpenWithLTN)
        self.openWithMenu.addAction(fileOpenWithWIN)
        self.openWithMenu.addAction(fileOpenWithMAC)
        # actions following the open with encoding submenu
        self.fileMenuActions2 = (fileSaveAction, fileSaveAsAction,
                                 fileScannosAction, fileButtonLoadAction,
                                 fileButtonSaveAction, None, fileQuitAction)
        # Recall our list of recently-opened files from saved settings.
        self.recentFiles = IMC.settings.value("main/recentFiles",
                            QVariant(QVariant.StringList)).toStringList()
        # When the File menu is about to be opened, update its contents
        # with the actions and files above.
        self.connect(self.fileMenu, SIGNAL("aboutToShow()"),
                     self.updateFileMenu)
        # Update the file menu one time explicitly so that the accelerator
        # keys will work the first time before the menu has been displayed.
        self.updateFileMenu()
        # -----------------------------------------------------------------
        # Create actions for the Edit menu. Direct cut/copy/paste to the
        # inherited methods of the QPlainTextEdit object. Direct the ones
        # we implement (ToUpper etc) to methods provided by our edit class.
        # All these menu actions are parented to the editor, so their shortcuts
        # can supposedly be preempted by other widgets e.g. Notes, Words.
        editCopyAction = self.createAction("&Copy", self.editor,
            self.editor.copy, QKeySequence.Copy,
            "Copy selection to clipboard")
        editCutAction = self.createAction("Cu&t", self.editor,
            self.editor.cut, QKeySequence.Cut,
            "Cut selection to clipboard")
        editPasteAction = self.createAction("&Paste", self.editor,
            self.editor.paste, QKeySequence.Paste,
            "Paste clipboard at selection")
        editToUpperAction = self.createAction("to&Upper", None,
            self.editor.toUpperCase, QKeySequence(Qt.Key_U+Qt.CTRL),
            "Make selected text UPPERCASE")
        editToLowerAction = self.createAction("to&Lower", None,
            self.editor.toLowerCase, QKeySequence(Qt.Key_L+Qt.CTRL),
            "Make selected text lowercase")
        editToTitleAction = self.createAction("toT&itle", None,
            self.editor.toTitleCase, QKeySequence(Qt.Key_I+Qt.CTRL),
            "Make Selected Text Titlecase")
        # There may perhaps be some more edit actions, e.g. ex/indent
        # -----------------------------------------------------------------
        # Create and populate the Edit menu.
        editMenu = self.menuBar().addMenu("&Edit")
        self.addActions(editMenu,
            (editCopyAction, editCutAction, editPasteAction,
             None, editToUpperAction, editToLowerAction, editToTitleAction))
        # -----------------------------------------------------------------
        # Create actions for the View menu: toggle choices for spell and
        # scanno hilighting. We keep references to these because we
        # need to query and alter their toggle status.
        # Also in View, the dict and font choices, mainly because
        # there was no other place to put them. Make a Tools menu?
        # These are parented by the main window so always the same.
        self.viewScannosAction = self.createAction("Sca&nnos", None,
                self.viewSetScannos, None, "Toggle scanno hilight",
                True, "toggled(bool)")
        self.viewSpellingAction = self.createAction("S&pelling", None,
                self.viewSetSpelling, None, "Toggle spellcheck hilight",
                True, "toggled(bool)")
        self.viewFontAction = self.createAction("&Font...", None,
                self.viewFont, None, "Open font selection dialog")
        self.viewDictAction = self.createAction("&Dictionary...", None,
                self.viewDict, None, "Open dictionary selection dialog")
        # -----------------------------------------------------------------
        # Create and populate the View menu
        viewMenu = self.menuBar().addMenu("&View")
        self.addActions(viewMenu, (self.viewScannosAction,
                                   self.viewSpellingAction,
                                   self.viewFontAction,
                                   self.viewDictAction))
        self.viewScannosAction.setChecked(IMC.scannoHiliteSwitch)

    # ---------------------------------------------------------------------
    # This convenience function, lifted from Summerfield's examples, 
    # encapsulates the boilerplate of creating a menu action. (We are not
    # using a toolbar nor using icons in the menus, so those arguments
    # from his version are omitted.) Arguments are:
    #
    # text = text of the menu item, e.g. "Save &As" (ampersand designates the
    #    windows accelerator key for that item, s.b. unique in any menu)
    #
    # parent = the parent widget or None to indicate "this main window"
    #    When a parent (usually, the editor) is given, the action is also
    #    given shortCutContext of Qt.WidgetShortcut, which is supposed to 
    #    mean other widgets can use the same shortcut for their own actions.
    #
    # slot = target of a signal emitted by this action, see also signal
    #
    # shortcut = standard key sequence, preferably from QKeySequence, or an
    #    app-unique sequence
    #
    # tip = text of a tooltip that flashes in the status bar when the menu
    #     
    # checkable = whether the item has an on/off state (like View>Scannos)
    #
    # signal = signature of the signal emitted by this action. The slot and
    #     signal work together to say, upon this action send signal to slot.
    #
    def createAction(self, text, parent, slot=None, shortcut=None,
                     tip=None, checkable=False, signal="triggered()"):
        # create the action with a parent as specified
        if parent is None :
            # give this action self, i.e. the main window, as parent
            action = QAction(text, self)
        else :
            # give this action the specified parent and make it apply to that
            action = QAction(text, parent)
            action.setShortcutContext(Qt.WidgetShortcut)
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            self.connect(action, SIGNAL(signal), slot)
        if checkable:
            action.setCheckable(True)
        return action

    # -----------------------------------------------------------------
    # Another Summerfield convenience: populate a given menu (target) with 
    # a list of QActions. In the list None means "separator here".
    def addActions(self, target, actions):
        for action in actions:
            if action is None:
                target.addSeparator()
            else:
                target.addAction(action)

    # -----------------------------------------------------------------
    # This slot is entered on the File menu signal aboutToShow. Quick like
    # a bunny, populate the menu with the prepared actions and with the 
    # current list of previously-opened files. Point the file name menu items
    # at the recentFile() function. Hard to believe, but all this executes
    # every time you click on "File".
    def updateFileMenu(self):
        self.fileMenu.clear()
        # add all our file actions except the last, Quit, to the menu
        self.addActions(self.fileMenu, self.fileMenuActions1)
        self.fileMenu.addMenu(self.openWithMenu)
        self.addActions(self.fileMenu, self.fileMenuActions2[:-1])
        current = None if IMC.bookPath.isEmpty() else IMC.bookPath
        # make a list of recent files, excluding the current one and
        # any that might have been deleted meantime.
        current = None if IMC.bookPath.isEmpty() else IMC.bookPath
        recentFiles = QStringList()
        for fname in self.recentFiles:
            if fname != current and QFile.exists(fname):
                recentFiles.append(fname)
        # ...if there are any, put them in the menu between separators
        if not recentFiles.isEmpty():
            self.fileMenu.addSeparator()
            fnum = 0
            for fname in recentFiles:
                # extract the basename from the full file path
                base = QFileInfo(fname).fileName()
                # note &# gives a windows underscored digit accelerator
                # BTW, this is why we limit the list to 9 entries.
                menuString = "&{0} {1}".format(fnum + 1, base)
                action = QAction(menuString, self)
                # store the file path as the value of the action
                action.setData(QVariant(fname))
                # connect the action to our loadFile
                self.connect(action, SIGNAL("triggered()"),
                             self.recentFile)
                self.fileMenu.addAction(action)
                fnum += 1
        # and put the Quit action at the end of the menu
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.fileMenuActions2[-1])

    # -----------------------------------------------------------------
    # Set the main window's windowModified status, based on whether
    # the edited doc has been modified or if any metadata has changed.
    # IMC.needMetadataSave is set by pqNotes, pqPages, and pqWords and
    # cleared in pqEdit. Setting windowModified true in Mac OS sets the
    # modified dot in the red close gumdrop, and on other platforms, 
    # displays an asterisk after the filename in the titlebar.
    #
    # On the non-mac platforms, we have to avoid caling setWindowModified()
    # when there is no asterisk in the window title, because it produces
    # an annoying message on the console.
    def setWinModStatus(self):
        if self.windowTitle().contains(u'*') :
            self.setWindowModified(
    self.editor.document().isModified() | (0 != IMC.needMetadataSave)
                            )        
    # Slot to receive the modificationChanged signal from the main editor.
    # This signal only comes when the document goes from unmodified to 
    # modified, or the reverse (on ^z). It does not come on every text change,
    # only on the first text change.
    def ohModificationChanged(self,newValue):
        if not newValue : # doc is, has become, unchanged
            IMC.staleCensus &= (0xff ^ IMC.staleCensusAcquired)
        self.setWinModStatus()
    # Slot to receive the textChanged signal from the editor. This comes
    # very frequently, like every edit keystroke. So be quick.
    def ohTextChanged(self):
        IMC.staleCensus |= IMC.staleCensusAcquired
        IMC.editCounter += 1

    # -----------------------------------------------------------------
    # Called by a tab that wants to be visible (currently only the Find panel
    # responding to ^f in the editor), make the calling widget visible
    def makeMyPanelCurrent(self,widg):
        self.tabSet.setCurrentWidget(widg)

    # -----------------------------------------------------------------
    # Called from the View menu, these functions set the hilighting switches
    # The state of the menu toggle is passed as a parameter.
    def viewSetScannos(self, toggle):
        if toggle : # switch is going on,
            # Do we have a scanno file? If not, remind the user to give one.
            if self.scannoPath.isEmpty():
                self.scannoOpen()
        willDoIt = (toggle) and (not self.scannoPath.isEmpty())
        self.viewScannosAction.setChecked(willDoIt)
        IMC.scannoHiliteSwitch = willDoIt
        self.editor.setHighlight(IMC.scannoHiliteSwitch or IMC.spellingHiliteSwitch)   
    
    def viewSetSpelling(self, toggle):
        willDoIt = (toggle) and (IMC.wordCensus.size()>0)
        self.viewSpellingAction.setChecked(willDoIt)
        IMC.spellingHiliteSwitch = willDoIt
        self.editor.setHighlight(IMC.scannoHiliteSwitch or IMC.spellingHiliteSwitch)
    
    # -----------------------------------------------------------------
    # Handle View>Font... by throwing up a QFontDialog initialized with an
    # available monospaced family and the last-chosen font size. Store the
    # user's choice of family and size in the IMC and install it in the Editors.
    def viewFont(self):
        if IMC.fontFamily is None:
            # first time after installation
            IMC.fontFamily = IMC.defaultFontFamily
        defont = QFont(IMC.fontFamily, IMC.fontSize)
        (refont,ok) = QFontDialog.getFont(defont, self,
                        QString("Choose a monospaced font"))
        if ok:
            finf = QFontInfo(refont) # get actual info as chosen
            IMC.fontFamily = finf.family() # remember the family
            IMC.fontSize = finf.pointSize() # remember the chosen size
            IMC.editWidget.setFont(refont) # tell the editor
            IMC.notesEditor.setFont(refont) # tell the notes editor

    # -----------------------------------------------------------------
    # This is the action for View > Dictionary... 
    # Get the current dictionary tag from the spell checker (e.g. "en_US")
    # and the list of available languages. Throw up a dialog with a popup
    # menu, and if the user clicks ok, set a new main dictionary.
    def viewDict(self):
        qsl = IMC.spellCheck.dictList()
        if qsl.count() : # then we know about some dicts
            qsl.sort() # put the list in order
            qsmt = IMC.spellCheck.mainTag if IMC.spellCheck.isUp() else u'(none)'
            # get the index of the current main dict tag, if any
            current = qsl.indexOf(qsmt)
            if current < 0 : # appears there isn't a current main dict
                current = 0 # so don't spec which item to make current
            # The explanatory label is needlessly wordy to force the dialog
            # to be wide enough to display the full title o_o
            (qs,b) = pqMsgs.getChoiceMsg("Select Default Dictionary",
                    "The currently selected language is "+unicode(qsmt),
                    qsl, current)
            if b: # user clicked OK
                IMC.spellCheck.setMainDict(qs)
                IMC.needSpellCheck = True
        else:
            pqMsgs.warningMsg("No dictionaries are known!",
                              "Check console window for error messages?")

    # -----------------------------------------------------------------
    #
    # CODE RELATED TO DOCUMENT/FILE OPERATIONS: NEW, OPEN, SAVE [AS]
    # also load scanno file and load/save Find buttons.
    #
    # -----------------------------------------------------------------

    # -----------------------------------------------------------------
    # Called from File>Save (as) and File>Open, stuff the current bookpath
    # onto the front of the list of recent files, and drop the oldest one
    # to limit the list to 9 entries. This uses a QStringList (not a python
    # list). What's being saved is full file-path strings. We have to be
    # careful to take QString(fname) so as to get a copy, not just a ref.
    def addRecentFile(self, fname):
        if fname is None:
            return
        if not self.recentFiles.contains(fname):
            # it is not a dup, so add it at the end
            self.recentFiles.prepend(QString(fname))
            while self.recentFiles.count() > 9:
                # note dammit, QStringList is *supposed* to inherit removeLast()
                # from QList, also .size() -- neither is true. Instead it has
                # a .count() method, and does have removeAt, so that is how
                # we drop the oldest items from the list.
                self.recentFiles.removeAt(self.recentFiles.count()-1)

    # -----------------------------------------------------------------
    # Called from Quit, New, and Open to make sure the current file is saved.
    # Query the user with a modal dialog if the file is dirty, and if the
    # answer is "yes, save it" invoke the save action. Return True only if
    # it is safe to proceed with Quit/New/Open.
    def ohWaitAreWeDirty(self):
        if self.editor.document().isModified() \
        or (0 != IMC.needMetadataSave) :
            if IMC.documentHash != IMC.metaHash :
                # the doc and meta didn't match and user is now trying to
                # use New, Quit or Open -- just let that go ahead.
                return True
            # The doc and meta did match and there's been editing.
            reply = QMessageBox.question(self,
                            "There are unsaved changes!",
                            "Save the book and metadata first?",
                            QMessageBox.Yes|QMessageBox.No|
                            QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return False
            elif reply == QMessageBox.Yes:
                return self.fileSave()
        return True
    
    # -----------------------------------------------------------------
    # Infer the correct I/O codec for a file based on the filename.suffix
    # and, for input files and only when necessary, based on file contents. 
    # Return a name string accepted by QTextStream.setCodec(), or None if
    # the codec cannot be determined.
    #
    # The input is a QFileInfo for the file of interest, a QFileInfo for
    # its .meta file if there is one (a null QFileInfo if none), and a boolean
    # forInput = True if the file is being loaded, not saved.
    #
    # PG wants etexts to be suffixed .txt regardless of their encoding!
    # It is optional to end the filename with -u[tf[8]] to indicate UTF or
    # -l[tn[1]] to indicate Latin-1. Without that flag it could be US-ASCII,
    # ISO-8859-1, UTF-8 or UTF-16 or who knows what.
    #
    # We look for the name-flags first. Then, if the suffix is .htm[l] and
    # the file is for input, we look in the first 1024 bytes for a charset=
    # parameter and if found, return what that says. Otherwise, HTML defaults
    # to UTF-8, per the W3 standards website.
    #
    # Then we look for some file suffixes that PG does not support, but which
    # are convenient for local uses:
    #  .ltn -- "ISO 8859-1"  when you know that's what you have or want
    #  .utf or .utx -- "UTF-8"  convenient for good_words and scanno files.
    #  .win -- "cp1252"      for input only, when you know that's what you got
    #  .mac -- "macintosh"   for input only, when you know that's what you got
    #
    # Failing all that (no flag in the name, suffix is .txt or unknown), if the
    # file is for input, open it in python as a byte stream and feed up to 4k
    # of it to the chardet package. If it comes up >= 90% confidence, return
    # that string. Else return None.
    
    def inferTheCodec(self, fileInfo, metaInfo, forInput):
        # the quickest and easiest test is for a -u or -l flag in the filename.
        fileName = fileInfo.fileName() # const QString name
        utfRE = QRegExp(u'-(u|utf|utf8)\.')
        if utfRE.indexIn(fileName) > -1 :
            return self.utfEncoding # filename ends in -u[tf[8]]. 
        ltnRE = QRegExp(u'-(l|ltn|ltn1)\.')
        if ltnRE.indexIn(fileName) > -1 :
            return self.ltnEncoding # filename ends in -l[tn[1]]
        # if the file was saved by us there is a .meta file. Somewhere in the
        # first few lines of that should be {{ENCODING FOOBAR}}. If we find
        # that, return FOOBAR.
        if forInput and metaInfo.exists() :
            (mStream, mHandle) = self.openSomeFile(
                metaInfo.absoluteFilePath(), QIODevice.ReadOnly, 'UTF-8' )
            if mStream is not None :
                metaRE = QRegExp(u'''\{\{ENCODING ([\w\-\_\d]+)\}\}''')
                mqs = mStream.read(512)
                mHandle.close()
                if metaRE.indexIn(mqs) > -1 :
                    return metaRE.cap(1)
        # Alright let's look at file suffixes, starting with htm[l]
        fileSuffix = fileInfo.suffix()
        if fileSuffix == 'htm' or fileSuffix == 'html' or fileSuffix == 'xml':
            # The HTML 4, 5, and XHTML standards say page files should be UTF-8
            # and if not, must have a charset= or encoding= parameter within
            # the first 1024 bytes, eg: <?xml version="1.0" encoding="UTF-8"?>
            # <meta charset="UTF-8"> <meta... content="text/html;charset=UTF-8">
            # So now look for that either on disk (forInput) or in memory.
            if forInput :
                # html file on disk: read 1K of it (as UTF which includes ascii)
                (htmStream, htmHandle) = self.openSomeFile(
                    fileInfo.absoluteFilePath(), QIODevice.ReadOnly, self.utfEncoding )
                if htmStream is None :
                    return None # couldn't open it, as forInput it fails
                htmqs = htmStream.read(1024) # grab first 1K
                htmHandle.close()
            else :
                # html file in memory. get access to its first 1K from the
                # editor document.
                doc = IMC.editWidget.document()
                tc = QTextCursor(doc)
                tc.setPosition(0)
                tc.setPosition(min(1024,doc.characterCount()),
                               QTextCursor.KeepAnchor)
                htmqs = tc.selectedText()
            # The encoding names are specified to be from the IANA registry
            # (http://www.iana.org/assignments/character-sets) which shows that
            # there are no names with embedded spaces. So the regex can use
            # a space, quote or > as a terminal marker.
            htmRE = QRegExp(u'''(charset|encoding)\s*=\s*['"]?([\w\-\_\d]+)[;'">\s]''')
            if htmRE.indexIn(htmqs) > -1 :
                    return unicode(htmRE.cap(2))
            # no charset parameter seen. Return the W3 standard encoding for HTML.
            return self.utfEncoding 
        # OK, look for useful suffixes PG doesn't support but we do.
        if fileSuffix == u'utf' or fileSuffix == u'utx' :
            return self.utfEncoding
        if fileSuffix == u'ltn' :
            return self.ltnEncoding
        if fileSuffix == u'win' :
            return QString(u'cp1252')
        if fileSuffix == u'mac' :
            return QString(u'macintosh')
        # Unhelpful file name and suffix. If this is an output file we can 
        # infer nothing more so let's default to UTF8.
        if not forInput :
            return self.utfEncoding
        # The file is supposed to exist, so let us grab some of it as raw
        # bytes, shove it into the decoder and see if it can tell anything.
        if self.charDetector is None : # first time this session
            self.charDetector = UniversalDetector() # create bulky object
        self.charDetector.reset() # reset detector
        try:
            pyfile = io.open(unicode(fileInfo.absoluteFilePath()),'rb')
        except:
            return None # didn't open, can't tell encoding
        # file is open, read some of it and decode it.
        self.charDetector.feed(pyfile.read(4096))
        pyfile.close()
        result = self.charDetector.close()
        if ('confidence' in result) : # detector is working
            if result['confidence'] > 0.85 : # detector is confident
                return QString(result['encoding'])
        # The detector isn't confident and neither are we.
        return None

    # -----------------------------------------------------------------
    # Take care of opening any file for input or output, with appropriate
    # error messages. Input is:
    # the complete file path as a QString,
    # the open mode, either QIODevice.ReadOnly or QIODevice.WriteOnly, and
    # the id string for the codec.
    # Allow for an input file that doesn't exist (as a convenience to 
    # loadFile, which uses this code to test for it). Return a tuple:
    #   on success, (handle of the open QTextStream, handle of the file)
    #   on failure, (None, None)
    def openSomeFile(self, path, mode, codec):
        filehandle = QFile(path)
        if mode == QIODevice.ReadOnly :
            if not filehandle.exists() or codec is None:
                return (None, None)
        if mode == QIODevice.WriteOnly :
            # need to add this to get crlf line-ends on Windows
            mode |= QIODevice.Text
        try:
            if not filehandle.open(mode):
                raise IOError
            streamhandle = QTextStream(filehandle)
            streamhandle.setCodec(codec)
        except (IOError, OSError), e:
            pqMsgs.warningMsg(
                "Cannot open {0}".format(unicode(path)),
                unicode(filehandle.errorString())
            )
            filehandle.close()
            return (None, None)
        return (streamhandle, filehandle)

    # -----------------------------------------------------------------
    # This is the target of a File menu action based on the name of a previous
    # file. Get the path from the user data field of the event. Make sure we
    # save a modified doc. That done, call loadFile().
    def recentFile(self):
        action = self.sender() # QObject method for the invoking action of a slot
        if isinstance(action, QAction): # it was an action not something else?
            # we stored the file path as the action data, see updateFileMenu(),
            # which only lists files that existed as of the time the menu was
            # about to display, i.e. seconds ago. So assume it's there still.
            fname = action.data().toString()
            if not self.ohWaitAreWeDirty():
                return # dirty doc & user said cancel or save failed
            else:
                self.loadFile(fname, None)
    
    # -----------------------------------------------------------------
    # This is the action slot for the File>Open and File>Open With Encoding
    # menu commands. (Actually, the slots for the five 'triggered' signals are
    # lambdas that call this with the appropriate encoding parameter.)
    # An encoding id is passed when known, or None.
    # Make sure to save a working file. Ask the user for a file.
    # The starting directory for the dialog is the folder for the current book,
    # or '.' if there is none. If a path is selected, pass it to loadFile().
    def fileOpen(self, encoding = None):
        if not self.ohWaitAreWeDirty():
            return False # dirty doc & user said cancel, or save failed
        startdir = (QString(".") if IMC.bookPath.isEmpty() else IMC.bookPath)
        msg = "PPQT - choose a book file to open"
        if encoding is not None :
            msg = "PPQT - choose book encoded {0} to open".format(encoding)
        bookname = QFileDialog.getOpenFileName(self,msg,startdir)
        if not bookname.isEmpty(): # user selected a file, we are "go"
            self.loadFile(bookname, encoding)
            self.addRecentFile(IMC.bookPath)
    
    # -----------------------------------------------------------------
    # Heart of opening a document: called by way of the File menu actions
    # Open, Open With Encoding, and recent-file-name. Each passes the path
    # to the book and the encoding when known. Locate the book file and its
    # associated .meta, good_words, and bad_words files. Learn or infer the
    # proper codec for each. Open them as text streams. Finally, pass the
    # streams to the Edit module for actual loading.
    #
    # We use the Qt file API because it is convenient and platform-independent.
    # The Python io module is pretty nearly as nice, but QFileInfo is a very
    # convenient way to learn about a file, and QDir a great way to get names,
    # without any platform dependency. NB: QFile(None).exist() ==> False
    
    def loadFile(self, path, encoding):
        bookInfo = QFileInfo(path)
        # Note the complete path to the book directory. note the difference:
        # bookInfo.absoluteFilePath includes the filename, absolutePath 
        # is only the path through the directory.
        bookPath = bookInfo.absoluteFilePath()
        bookDirPath = bookInfo.absolutePath()
        bookDir = QDir(bookDirPath)
        # find the .meta file if it exists.
        metaInfo = QFileInfo(QString(unicode(bookPath) + u'.meta'))
        # Get the encoding if we weren't told it
        if encoding is None:
            encoding = self.inferTheCodec(bookInfo,metaInfo,True)
        if encoding is None: # cannot infer an encoding
            pqMsgs.warningMsg(
                u'Cannot guess the encoding of '+unicode(bookInfo.fileName()),
                u'Please change the name or use File>Open With Encoding')
            return
        # If we don't have a .meta file, find the good_words and bad_words files.
        goodwordsEncoding = None
        goodwordsPath = None
        badwordsEncoding = None
        badwordsPath = None
        if not metaInfo.exists() :
            # Locate these without requiring particular suffixes. Set the dir
            # object to sort the list by suffix, reversed, so if there is more
            # than one of that name, we will get good_words.utf before .bak.
            # Filter is good_words*.* so we find good_words-utf.txt
            bookDir.setFilter(QDir.Files | QDir.Readable)
            bookDir.setSorting(QDir.Type | QDir.Reversed)
            bookDir.setNameFilters( QStringList( QString( u'good_words*.*') ) )
            listOfFiles = bookDir.entryList()
            if listOfFiles.count() > 0 : # at least one good_words*.*
                goodwordsPath = bookDir.absoluteFilePath(listOfFiles[0]) # the alpha-last one
                goodwordsEncoding = self.inferTheCodec(
                    QFileInfo(goodwordsPath),QFileInfo(),True)
            bookDir.setNameFilters( QStringList( QString( u'bad_words*.*') ) )
            listOfFiles = bookDir.entryList()
            if listOfFiles.count() > 0 : # at least one bad_words*.*
                badwordsPath = bookDir.absoluteFilePath(listOfFiles[0]) # the alpha-last one\
                badwordsEncoding = self.inferTheCodec(
                    QFileInfo(badwordsPath),QFileInfo(),True)
        # OK we have all the ducks in a row, get serious about this.
        (bookStream, bookHandle) = self.openSomeFile(
                    bookInfo.absoluteFilePath(), QIODevice.ReadOnly, encoding)
        # If the book file, at least, opened, we can proceed.
        if bookStream is not None :
            self.setWindowTitle("PPQT - loading...")
            (metaStream, metaHandle) = self.openSomeFile(
                    metaInfo.absoluteFilePath(), QIODevice.ReadOnly, "UTF-8")
            (goodStream, goodHandle) =self.openSomeFile(
                    goodwordsPath, QIODevice.ReadOnly, goodwordsEncoding)
            (badStream, badHandle) = self.openSomeFile(
                    badwordsPath, QIODevice.ReadOnly, badwordsEncoding)
            # emit signal to any panels that care before the edit window changes.
            self.emit(SIGNAL("docWillChange"),bookPath)
            # tell the editor to clear itself in preparation for loading.
            self.editor.clear()
            IMC.notesEditor.clear()
            try:
                self.editor.load(bookStream, metaStream, goodStream, badStream)
                self.setWindowTitle(u"PPQT - {0}[*]".format(bookInfo.fileName()))
                IMC.bookDirPath = bookDirPath
                IMC.bookPath = bookPath
                IMC.bookType = bookInfo.suffix()
                # if the encoding is Latin-1, save as that. Any other, use UTF
                if encoding == self.ltnEncoding :
                    IMC.bookSaveEncoding = encoding
                else :
                    IMC.bookSaveEncoding = self.utfEncoding
            except (IOError, OSError), e:
                pqMsgs.warningMsg(u"Error during load: {0}".format(e))
                self.setWindowTitle(u"PPQT - new file[*]")
            finally:
                bookHandle.close()
                if metaStream is not None : metaHandle.close()
                if goodStream is not None : goodHandle.close()
                if badStream is not None : badHandle.close()
                self.emit(SIGNAL("docHasChanged"),bookPath)
                self.setWinModStatus() # notice if metadata changed
        # else: we didn't get a book file, so nothing has changed, the editor
        # was not cleared and the window title hasn't changed.

    # -----------------------------------------------------------------
    # File > New comes here. Check for a modified file, then tell the editor
    # to clear, and clear our filepath info.
    def fileNew(self):
        if not self.ohWaitAreWeDirty():
            return False # dirty doc & user said cancel or save failed
        self.emit(SIGNAL("docWillChange"),QString())
        # the following clears IMC.needMetadataSave etc
        self.editor.clear()
        IMC.notesEditor.clear()
        self.emit(SIGNAL("docHasChanged"),QString())
        IMC.documentHash = ''
        IMC.metaHash = ''
        IMC.bookPath = QString()
        IMC.bookDirPath = QString()
        IMC.bookType = QString()
        IMC.bookSaveEncoding = QString(u'UTF-8')
        self.setWindowTitle("PPQT - new file[*]")
        self.setWinModStatus() # notice if metadata changed

    # -----------------------------------------------------------------
    # For either Save or Save-As, check for a mismatch between the metadata file
    # and the document file. Normally there is none and we return True.
    def doHashesMatch(self):
        if IMC.documentHash == IMC.metaHash :
            return True
        # There is a mismatch; this would have been detected and warned about when
        # the file was opened but the user ignored that and now wants to save.
        # Get one last confirmation. Result of okCancelMsg is True if "OK" clicked.
        return pqMsgs.okCancelMsg(u"The document and metadata files do not match!",
                               u"Are you sure you want to save this book?")
        
    # -----------------------------------------------------------------
    # File>Save clicked, or this is called from ohWaitAreWeDirty() above.
    # If we don't know a bookFile we must be working on a New, so call Save As
    # (which will recurse to here after it gets a file path).
    # Otherwise, try to open bookFile and bookFile+".meta" for writing,
    # and pass them to the editor to do the save. Trap any errors it gets.
    def fileSave(self):
        if IMC.bookPath.isEmpty():
            return self.fileSaveAs()
        # Test for mismatched doc/meta situation
        if not self.doHashesMatch() :
            return False # mismatch, and user thought better of save
        bookInfo = QFileInfo(IMC.bookPath)
        metaInfo = QFileInfo(QString(unicode(IMC.bookPath) + u'.meta'))
        bookEncoding = self.inferTheCodec(bookInfo,metaInfo,False)
        if bookEncoding is None :
            bookEncoding = IMC.bookSaveEncoding
        if (0 != self.utfEncoding.compare(bookEncoding,Qt.CaseInsensitive)) \
        and (0 != self.ltnEncoding.compare(bookEncoding,Qt.CaseInsensitive)) :
            if pqMsgs.okCancelMsg(
                u'Cannot save to {0} encoding'.format(bookEncoding),
                u'Click OK to save in UTF-8') :
                bookEncoding = QString(self.utfEncoding)
            else :
                return False
        (bookStream, bfh) = self.openSomeFile(bookInfo.absoluteFilePath(),
                    QIODevice.WriteOnly, bookEncoding )
        (metaStream, mfh) = self.openSomeFile(metaInfo.absoluteFilePath(),
                    QIODevice.WriteOnly, self.utfEncoding)
        if (bookStream is not None) and (metaStream is not None) :
            try:
                IMC.bookSaveEncoding = bookEncoding
                # the following clears IMC.needMetadataSave and the document
                # modified flags in edit and notes documents, as well as
                # triggering setWinModStatus above.
                self.editor.save(bookStream, metaStream)
                retval = True # success
                self.addRecentFile(IMC.bookPath)
                self.setWinModStatus() # notice if metadata changed
            except (IOError, OSError), e:
                QMessageBox.warning(self, "Error on output: {0}".format(e))
                retval = False
            finally:
                bfh.close()
                mfh.close()
        return retval

    # -----------------------------------------------------------------
    # File>Save As is basically a wrapper on File>Save. Get a path & name.
    # QFileDialog allows a "filter" string to filter filetypes but we don't
    # apply it.
    
    def fileSaveAs(self):
        # Test for mismatched doc/meta situation
        if not self.doHashesMatch() :
            return False # mismatch, and user thought better of save
        startPath = QString(".") if IMC.bookDirPath.isEmpty() else IMC.bookDirPath
        savename = QFileDialog.getSaveFileName(self,
                "Save book text As", startPath)
        if not savename.isEmpty():
            finf = QFileInfo(savename)
            IMC.bookPath= finf.absoluteFilePath()
            IMC.bookDirPath = finf.absolutePath()
            IMC.bookType = finf.suffix()
            self.setWindowTitle("PPQT - {0}[*]".format(finf.fileName()))
            # with file path set up, we can go on to the real Save
            return self.fileSave()
        # oops, user cancelled out of the dialog
        return False
    
    # -----------------------------------------------------------------
    # File>Scanno clicked. Ask the user for a file to open and if one is given,
    # store it as self.scannoPath, open it, and use it to load IMC.scannoList.
    # If we know a scannoPath, use that as the starting directory.
        
    def scannoOpen(self):
        startdir = (QString(".") if self.scannoPath.isEmpty() else self.scannoPath)
        sfname = QFileDialog.getOpenFileName(self,
                "PPQT - choose a list of common scannos",
                startdir)
        if not sfname.isEmpty(): # user selected a file, we are "go"
            self.scannoPath = sfname
            self.scannoLoad()

    # -----------------------------------------------------------------
    # Called during initialization to load a scanno file from the settings,
    # and from scannoOpen. Check that the scannoPath exists (probably, but
    # perhaps the file was moved or deleted between sessions). Determine
    # its file encoding. Clear the list so as not to get the superset of old
    # and new lists (doh!). Turn off the hilites if they are on, so as not
    # to leave residual purple marks (doh!). Load the list.
    # If the hilites were on, turn them back on to show new words.
    
    def scannoLoad(self):
        scanno_sw = IMC.scannoHiliteSwitch
        if scanno_sw : # highlighting is on
            # regardless of whether we can open the file, clear scannos now
            self.viewSetScannos(False) # turn it off
            IMC.scannoList.clear() # clear out the list
        scannoInfo = QFileInfo(self.scannoPath)
        scannoCodec = self.inferTheCodec(scannoInfo,QFileInfo(),True)
        if scannoCodec is None :
            # can't get the encoding (v. unlikely), just silently steal away
            IMC.scannoHilitSwitch = False # make sure switch is off
            return
        # Could get the encoding, so try to open it.
        (sh, fh) = self.openSomeFile(self.scannoPath, QIODevice.ReadOnly, scannoCodec)
        if sh is not None:
            IMC.scannoList.load(sh)
            fh.close()
            # new list is loaded,
            if scanno_sw : # if highlighting was on,
                self.viewSetScannos(True) # turn it on again
        else:
            if scanno_sw :
                IMC.scannoHilitSwitch = False # make sure switch is off

    # -----------------------------------------------------------------
    # File> Load Find Buttons clicked. Ask the user for a file to open and
    # if one is given, get its codec and open it. Pass the text stream to the
    # Find panel loadUserButtons method. Start the search in the last-used
    # button file folder, defaulting to our /extras (self.buttonDirPath).
    
    def buttonLoad(self):
        startPath = self.buttonDirPath
        bfName = QFileDialog.getOpenFileName(self,
                "PPQT - choose a file of saved user button definitions",
                startPath)
        if not bfName.isEmpty(): # a file was chosen
            bfInfo = QFileInfo(bfName)
            bfCodec = self.inferTheCodec(bfInfo,QFileInfo(),True)
            # if no codec inferred, very unlikely, just silently do nothing
            (buttonStream, fh) = self.openSomeFile(bfName,
                                        QIODevice.ReadOnly, bfCodec)
            if buttonStream is not None:
                IMC.findPanel.loadUserButtons(buttonStream)
                fh.close()
                # after successful use, update start path for saving
                self.buttonDirPath = bfInfo.path()

    # -----------------------------------------------------------------
    # File> Save Find Buttons clicked. Ask the user for a file to open.
    # If one is given, determine its coded, and open it for output and
    # pass the stream to the Find panel saveUserButtons method.
    def buttonSave(self):
        startPath = self.buttonDirPath
        bfName = QFileDialog.getSaveFileName(self,
                "Save user-defined buttons as:", startPath)
        if not bfName.isEmpty():
            bfInfo = QFileInfo(bfName)
            bfCodec = self.inferTheCodec(bfInfo,QFileInfo(),False)
            if bfCodec is None : # pooh, default to UTF
                bfCodec = self.utfEncoding
            (buttonStream, fh) = self.openSomeFile(bfName,
                                        QIODevice.WriteOnly, bfCodec)
            if buttonStream is not None:
                IMC.findPanel.saveUserButtons(buttonStream)
                fh.close()
                # after successful use, update start path for saving
                self.buttonDirPath = bfInfo.path()                

    # -----------------------------------------------------------------
    # reimplement QWidget::closeEvent() to check for a dirty file and save it.
    # Then save our current geometry, list of recent files, etc.
    # Finally emit the shuttingDown signal so other widgets can do the same.
    def closeEvent(self, event):
        if not self.ohWaitAreWeDirty() :
            # user clicked cancel on the save your file? dialog
            event.ignore() # as you were...
            return
        # file wasn't dirty, or is now saved
        # Let any modules that care, write to settings.
        self.emit(SIGNAL("shuttingDown"))
        IMC.settings.setValue("main/size",self.size())
        IMC.settings.setValue("main/position", self.pos())
        IMC.settings.setValue("main/splitter", self.hSplitter.saveState() )
        IMC.settings.setValue("main/recentFiles", self.recentFiles)
        IMC.settings.setValue("main/scannoPath", self.scannoPath)
        IMC.settings.setValue("main/scannoSwitch",IMC.scannoHiliteSwitch)
        IMC.settings.setValue("main/fontFamily",IMC.fontFamily)
        IMC.settings.setValue("main/fontSize",IMC.fontSize)
        IMC.spellCheck.terminate() # shut down spellcheck
        event.accept() # pass it up the line
    