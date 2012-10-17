# must precede anything except #comments, including the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.0.0" # refer to PEP-0008
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
Create the main window and lay it out with a splitter,
editor on the left, tabs on the right. Create menus and menu actions.
Most of this is based on code from Summerfield's book, without which not.

'''
from PyQt4.QtCore import ( pyqtSignal, Qt,
    QFile, QFileInfo, QDir,
    QIODevice, QPoint, QSize,
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
    QMainWindow,QMenuBar,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget)

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
        #  * self.bookFile is the full path to the current document; when
        #    bookFile.isEmpty() there is no current document.
        self.bookFile = QString()
        #  * IMC.bookPath is the leading part of bookFile, used to
        #    look for pngs, goodwords etc, and to start open/save dialogs.
        self.bookPath = QString()
        IMC.bookPath = self.bookPath # for use in other modules
        #  * IMC.bookType is the file suffix, for those who care.
        IMC.bookType = QString()
        # Recall a scannoPath if we had one, else get a default empty QString
        # See closeEvent() below for how this and other settings are saved.
        self.scannoPath = IMC.settings.value("main/scannoPath",
                                             QString()).toString()
        # If we had a scannoPath, try to load it.
        if not self.scannoPath.isEmpty() : self.scannoLoad()
        # Recall the setting of the scanno hilite switch and adjust for whether
        # we were able to load the recalled file.
        IMC.scannoHiliteSwitch = IMC.settings.value("main/scannoSwitch",
                        False).toBool() and (not self.scannoPath.isEmpty())
        # n.b. we leave the spellcheck switch initialized False because we
        # have no file loaded.
        # -----------------------------------------------------------------
        # Recall a user-selected font if any:
        IMC.fontFamily = IMC.settings.value("main/fontFamily",
                                      QString("DejaVu Sans Mono")).toString()
        (IMC.fontSize,junk) = IMC.settings.value("main/fontSize",12).toInt()
        # -----------------------------------------------------------------
        # Create the editor for the left-hand pane. Put a reference in the
        # IMC for other modules to use in calling edit members. Hook up the
        # signal for document-modification-state-change to our slot where
        # we set the document title bar status flag.
        self.editor = pqEdit.PPTextEditor(self,IMC.fontSize)
        IMC.editWidget = self.editor # let other modules access edit methods
        self.connect(self.editor, SIGNAL("modificationChanged(bool)"),
                     self.ohModificationChanged)
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
        IMC.pngPanel = pqPngs.pngDisplay()
        self.tabSet.addTab(IMC.pngPanel, u"&Pngs")
        self.connect(self.editor, SIGNAL("cursorPositionChanged()"),
                        IMC.pngPanel.newPosition)
        self.connect(self, SIGNAL("docHasChanged"), IMC.pngPanel.newFile)
        self.connect(self, SIGNAL("shuttingDown"), IMC.pngPanel.shuttingDown)
        #
        # 2. Create the notes panel editor.
        #
        IMC.notesEditor = pqNotes.notesEditor()
        self.tabSet.addTab(IMC.notesEditor, u"No&tes")
        #
        # 3. Create the find panel and connect it to the editor's ^f keypress
        # signal and our doc-has-changed and shut-down signals.
        IMC.findPanel = pqFind.findPanel()
        self.tabSet.addTab(IMC.findPanel, u"&Find")
        self.connect(self.editor, SIGNAL("editKeyPress"),
                     IMC.findPanel.editKeyPress)
        self.connect(self, SIGNAL("shuttingDown"), IMC.findPanel.shuttingDown)
        self.connect(self, SIGNAL("docHasChanged"), IMC.findPanel.docHasChanged)   
        #
        # 4. Create Char Census panel and give it both the doc-has-changed
        # and the preceding doc-will-change signals (but not shutdown).
        self.charPanel = pqChars.charsPanel()
        self.tabSet.addTab(self.charPanel, u"&Char")
        self.connect(self, SIGNAL("docWillChange"), self.charPanel.docWillChange)
        self.connect(self, SIGNAL("docHasChanged"), self.charPanel.docHasChanged)   
        #
        # 5. Create Word Census Panel and give it signals.
        self.wordPanel = pqWords.wordsPanel()
        self.tabSet.addTab(self.wordPanel, u"&Word")
        self.connect(self, SIGNAL("docWillChange"), self.wordPanel.docWillChange)
        self.connect(self, SIGNAL("docHasChanged"), self.wordPanel.docHasChanged)   
        #
        # 6. Create Pages Panel and give it signals.
        self.pagePanel = pqPages.pagesPanel()
        self.tabSet.addTab(self.pagePanel, u"&Pages")
        self.connect(self, SIGNAL("docWillChange"), self.pagePanel.docWillChange)
        self.connect(self, SIGNAL("docHasChanged"), self.pagePanel.docHasChanged)
        #
        # 7. Create the Flow panel. It only gets the shutdown signal, which it 
        # uses to save all its user settings.
        self.flowPanel = pqFlow.flowPanel()
        self.tabSet.addTab(self.flowPanel, u"Fl&ow")
        self.connect(self, SIGNAL("shuttingDown"), self.flowPanel.shuttingDown)
        #
        # 8. Create the Footnote Panel which gets both sides of doc-changed
        # to clear its table.
        self.fnotePanel = pqFnote.fnotePanel()
        self.tabSet.addTab(self.fnotePanel, u"F&note")
        self.connect(self, SIGNAL("docWillChange"), self.fnotePanel.docWillChange)
        self.connect(self, SIGNAL("docHasChanged"), self.fnotePanel.docHasChanged)   
        #
        # 9. Create the html Preview Panel - it's simple, needs no signals
        self.pvwPanel = pqView.htmlPreview()
        self.tabSet.addTab(self.pvwPanel, u"P&vw")
        #
        # 10. Lastly, the Help panel:
        self.helpPanel = pqHelp.helpDisplay()
        self.tabSet.addTab(self.helpPanel, u"&Help")
        # We could now do either self.tabSet.setCurrentIndex(1) to make the
        # pngs panel current, but that seems to happen by default. Or, we 
        # could at shutdown save the last-set tab index and restore it?
        #
        # ------------------------------------------------------------------
        # Now set up the bottom of the window: status, line#, and progress bar.
        #
        status = self.statusBar()
        status.setSizeGripEnabled(False)
        # Create the progress bar in our status bar, in pqMsgs because that
        # is where are all the routines to run it.
        pqMsgs.makeBarIn(status)
        # Create the line number widget. The widget definition is in pqMsgs.
        # It gets the cursor movement signal from the editor, obviously.
        self.lnum = pqMsgs.lineLabel()
        self.connect(self.editor, SIGNAL("cursorPositionChanged()"),
                        self.lnum.cursorMoved)
        self.connect(self.lnum, SIGNAL("returnPressed()"), self.lnum.moveCursor)
        status.insertPermanentWidget(0,self.lnum)
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
        #
        # -----------------------------------------------------------------
        # Set up the menu actions, then create menus to invoke them.
        # 
        # Create actions for the File menu. All are parented by the main window.
        # Their shortcuts are always active.
        fileNewAction = self.createAction("&New...", None, self.fileNew,
                QKeySequence.New, "Clear to an empty state")
        fileOpenAction = self.createAction("&Open...", None, self.fileOpen,
                QKeySequence.Open, "Open a book and its metadata")
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
        # fly, adding recent files to it. Save the prepared actions as a tuple
        # for convenient use when it is time to populate the menu.
        self.fileMenu = self.menuBar().addMenu("&File")
        self.fileMenuActions = (fileNewAction, fileOpenAction,
                fileSaveAction, fileSaveAsAction, fileScannosAction,
                fileButtonLoadAction, fileButtonSaveAction, None, 
                fileQuitAction)
        # Recall our list of recently-opened files from saved settings.
        self.recentFiles = IMC.settings.value("main/recentFiles",
                            QVariant(QVariant.StringList)).toStringList()
        # When the File menu is about to be opened, update its contents
        # with the actions and files above.
        self.connect(self.fileMenu, SIGNAL("aboutToShow()"),
                     self.updateFileMenu)
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
        editToUpperAction = self.createAction("to&Upper", self.editor,
            self.editor.toUpperCase, QKeySequence(Qt.Key_U+Qt.CTRL),
            "Make selected text UPPERCASE")
        editToLowerAction = self.createAction("to&Lower", self.editor,
            self.editor.toLowerCase, QKeySequence(Qt.Key_L+Qt.CTRL),
            "Make selected text lowercase")
        editToTitleAction = self.createAction("toT&itle", self.editor,
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
                action.setShortcutContext(Qt.WidgetShortcut)

    # -----------------------------------------------------------------
    # This slot is entered on the File menu signal aboutToShow. Quick like
    # a bunny, populate the menu with the prepared actions and with the 
    # current list of previously-opened files. Point the file name menu items
    # at the recentFile() function. Hard to believe, but all this executes
    # every time you click on "File".
    def updateFileMenu(self):
        self.fileMenu.clear()
        # add all our file actions except the last, Quit, to the menu
        self.addActions(self.fileMenu, self.fileMenuActions[:-1])
        current = None if self.bookFile.isEmpty() else self.bookFile
        # make a list of recent files, excluding the current one and
        # any that might have been deleted meantime.
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
        self.fileMenu.addAction(self.fileMenuActions[-1])

    # -----------------------------------------------------------------
    # Set the main window's windowModified status, based on whether
    # the edited doc has been modified or if any metadata has changed.
    # IMC.needMetadataSave is set by pqNotes, pqPages, and pqWords and
    # cleared in pqEdit. Setting windowModified true in Mac OS sets the
    # modified dot in the red close gumdrop, and on other platforms, 
    # displays an asterisk after the filename in the titlebar.
    def setWinModStatus(self):
        self.setWindowModified(
            self.editor.document().isModified() | IMC.needMetadataSave
                            )        
    # Slot to receive the modificationChanged signal from the main editor.
    def ohModificationChanged(self,newValue):
        self.setWinModStatus()

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
            IMC.fontFamily = pqMsgs.getMonoFont()
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
            qsmt = IMC.spellCheck.mainTag if IMC.spellCheck.isUp() else u'(none)'
            # The explanatory label is needlessly wordy to force the dialog
            # to be wide enough to display the full title o_o
            (qs,b) = pqMsgs.getChoiceMsg("Select Default Dictionary",
                    "The currently selected language is "+unicode(qsmt), qsl)
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
        or IMC.needMetadataSave:
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
    # Choose the correct I/O codec based on the file suffix of current doc.
    # Return a name string accepted by QTextStream.setCodec().
    # .txt, .ltn, .asc -- "latin1"
    # .win -- "cp1252"
    # .mac -- "macintosh"
    # .utf -- "UTF-8"
    # We depend on the user to know the encoding of an input file, and the
    # desired encoding of an output file. On input we convert anything to
    # unicode, with incorrect substitutions if the wrong codec is chosen.
    # On output, any document chars that cannot be represented in the target
    # codec will be written as "?"s. No errors are raised in either case.
    # (In particular we have no way to enforce 7-bit ascii output. Qt does
    # not provide such a codec. You must use "latin1" but ensure that no
    # chars >127 are in the file; see the character census view.)
    # TODO: File submenu "Open with encoding" > list of encodings would be
    # a good addition.
    
    def codecFromFileSuffix(self, path=None):
        fp = (self.bookFile if path is None else path)
        sfx = QFileInfo(fp).suffix()
        if sfx == u"utf" : return "UTF-8"
        if sfx == u"win" : return "cp1252"
        if sfx == u"mac" : return "macintosh"
        if sfx == u"isr" : return "cp1255"
        if sfx == u"cyr" : return "cp1251"
        if sfx == u"kir" : return "KOI8-R"
        if sfx == u"kiu" : return "KOI8-U"
        return "latin1" # for .txt, .ltn, .htm(l) and unknown
    
    # -----------------------------------------------------------------
    # Take care of opening a file for input or output, with appropriate
    # error messages. Input is the complete file path as a QString,
    # the open mode from QIODevice, and the id string for the codec.
    # Allow for an input file that doesn't exist. Return a tuple:
    #   on success, (handles of the open QTextStream of the file)
    #   on failure, (None, None)
    def openSomeFile(self, path, mode, codec):
        filehandle = QFile(path)
        if mode == QIODevice.ReadOnly :
            if not filehandle.exists() :
                return (None, None)
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
    # This is the target of a File menu action based on the name of a recent
    # file. Get the path from the user data field of the event. Make sure we
    # save a modified doc. That done, set the bookFile and do loadFile().
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
                self.bookFile = fname
                self.loadFile()
    
    # -----------------------------------------------------------------
    # File>Open clicked. Make sure to save a working file. Ask the user for a
    # file to open. The starting directory for the dialog is either the 
    # folder for the current book, or '.' if there is no current book.
    # If a path is select, pass it to loadFile().
    def fileOpen(self):
        if not self.ohWaitAreWeDirty():
            return False # dirty doc & user said cancel or save failed
        startdir = (QString(".") if self.bookPath.isEmpty() else self.bookPath)
        bookname = QFileDialog.getOpenFileName(self,
                "PPQT - choose a book file to edit",
                startdir)
        if not bookname.isEmpty(): # user selected a file, we are "go"
            self.bookFile = bookname
            self.loadFile()
            self.addRecentFile(self.bookFile)
    
    # -----------------------------------------------------------------
    # Heart of opening a document: File>Load or File>recent-file-name have
    # loaded self.bookFile with the desired file path. Get that and
    # its related meta, good_words, and bad_words files as text streams
    # and pass them to the editor for loading.
    def loadFile(self):
        # Use Qt's facilities, rather than Pythons os module, to get the
        # absolute path and the directory path.
        finf = QFileInfo(self.bookFile)
        self.bookPath = finf.absolutePath()
        qdir = QDir(self.bookPath)
        # By invoking QFileInfo with a directory path and a filename, we can
        # get info on files without having to know if it's Unix or Windows.
        # !! this has to change: get-codec has to work for these too
        gwinf = QFileInfo(qdir,QString(u"good_words.txt"))
        if not gwinf.exists():
            gwinf = QFileInfo(qdir,QString(u"good_words.utf"))
        # !! this has to change: get-codec has to work for these too
        gwpath = gwinf.absoluteFilePath()
        bwinf = QFileInfo(qdir,QString(u"bad_words.txt"))
        if not bwinf.exists():
            bwinf = QFileInfo(qdir,QString(u"bad_words.utf"))
        bwpath = bwinf.absoluteFilePath()
        self.setWindowTitle("PPQT - loading...")
        (bookStream, bfh) = self.openSomeFile(self.bookFile,
                    QIODevice.ReadOnly, self.codecFromFileSuffix())
        # If the book file at least opened, we can proceed.
        if bookStream is not None :
            (metaStream, mfh) = self.openSomeFile(self.bookFile + u".meta",
                        QIODevice.ReadOnly, "UTF-8")
            # !!!! This has to change, codec from contents
            (goodStream, gfh) =self.openSomeFile(gwpath,QIODevice.ReadOnly,"UTF-8")
            # !!!! This has to change, codec from contents
            (badStream, xfh) = self.openSomeFile(bwpath,QIODevice.ReadOnly,"UTF-8")
            # emit signal to any panels that care before the edit window changes.
            self.emit(SIGNAL("docWillChange"),self.bookFile)
            # tell the editor to clear itself in preparation for loading.
            self.editor.clear()
            try:
                self.editor.load(bookStream, metaStream, goodStream, badStream)
                self.setWindowTitle(u"PPQT - {0}[*]".format(finf.fileName()))
                IMC.bookPath = self.bookPath
                IMC.bookType = finf.suffix()
            except (IOError, OSError), e:
                pqMsgs.warningMsg(u"Error during load: {0}".format(e))
                self.setWindowTitle(u"PPQT - new file[*]")
            finally:
                bfh.close()
                if metaStream is not None: mfh.close()
                if goodStream is not None: gfh.close()
                if badStream is not None: xfh.close()
                self.emit(SIGNAL("docHasChanged"),self.bookFile)
        # else: we didn't get a book file, so nothing has changed, the editor
        # was not cleared and the window title hasn't changed.

    # -----------------------------------------------------------------
    # File>Save clicked, or this is called from ohWaitAreWeDirty() above.
    # If we don't know a bookFile we must be working on a New: go to Save As
    # (which will recurse to here after it gets a file path).
    # Otherwise, try to open bookFile and bookFile+".meta" for writing,
    # and pass them to the editor to do the save. Trap any errors it gets.
    def fileSave(self):
        if self.bookFile.isEmpty():
            return self.fileSaveAs()
        # !!!! this changes: codec from IMC
        (bookStream, bfh) = self.openSomeFile(self.bookFile,
                    QIODevice.WriteOnly, self.codecFromFileSuffix() )
        (metaStream, mfh) = self.openSomeFile(self.bookFile + ".meta",
                    QIODevice.WriteOnly, "UTF-8")
        if (bookStream is not None) and (metaStream is not None) :
            try:
                self.editor.save(bookStream, metaStream)
                retval = True # success
                self.addRecentFile(self.bookFile)
                IMC.notesEditor.document().setModified(False)
                IMC.needMetadataSave = False
                # the following triggers a signal to setWinModStatus above
                self.editor.document().setModified(False)
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
        startPath = QString(".") if self.bookPath.isEmpty() else self.bookPath
        savename = QFileDialog.getSaveFileName(self,
                "Save book text As", startPath)
        if not savename.isEmpty():
            # !!! need to check encoding versus filename/extension
            self.bookFile = savename
            finf = QFileInfo(savename)
            self.bookPath = finf.path()
            IMC.bookPath = self.bookPath
            self.setWindowTitle("PPQT - {0}[*]".format(finf.fileName()))
            # with file path set up, we can go on to the real Save
            return self.fileSave()
        # oops, user cancelled out of the dialog
        return False

    # -----------------------------------------------------------------
    # File > New comes here. Check for a modified file, then tell the editor
    # to clear, and clear our filepath info.
    def fileNew(self):
        if not self.ohWaitAreWeDirty():
            return False # dirty doc & user said cancel or save failed
        self.emit(SIGNAL("docWillChange"),QString())
        # !!! clear notes doc? clear IMC.needMetaDataSave?
        self.editor.clear()
        self.emit(SIGNAL("docHasChanged"),QString())
        self.bookPath = QString()
        IMC.bookPath = self.bookPath
        self.filePath = QString()
        self.bookFile = QString()
        self.setWindowTitle("PPQT - new file[*]")
    
    # -----------------------------------------------------------------
    # File>Scanno clicked. Ask the user for a file to open and if one is given,
    # store it as self.scannoPath, open it, and use it to load IMC.scannoList.
    # If we know a scannoPath, use that as the starting directory in the
    # dialog. Do not pass a list of file extensions.
        
    def scannoOpen(self):
        startdir = (QString(".") if self.scannoPath.isEmpty() else self.scannoPath)
        sfname = QFileDialog.getOpenFileName(self,
                "PPQT - choose a list of common scannos",
                startdir)
        if not sfname.isEmpty(): # user selected a file, we are "go"
            self.scannoPath = sfname
            self.scannoLoad()

    # -----------------------------------------------------------------
    # Called during initialization and from scannoOpen, check that the
    # scannoPath exists (probably, but perhaps the file was moved between
    # PPQT sessions). Determine its file encoding. Load the list. Before
    # loading the list, turn off the hilites if they are on. Clear the list
    # so as not to get the superset of old and new lists (doh!).
    # If the hilites were on, turn them back on to show new words.
    def scannoLoad(self):
        # !!! this must change to get codec
        scanno_sw = IMC.scannoHiliteSwitch
        (sh, fh) = self.openSomeFile(self.scannoPath,
                QIODevice.ReadOnly, self.codecFromFileSuffix(self.scannoPath))
        if sh is not None:
            if scanno_sw :
                self.viewSetScannos(False)
            IMC.scannoList.clear()
            IMC.scannoList.load(sh)
            fh.close()
            if scanno_sw :
                self.viewSetScannos(True)
        else:
            if scanno_sw :
                # We were showing hilites but the file isn't there
                self.viewSetScannos(False)
                IMC.scannoList.clear()
            self.scannoPath.clear()

    # -----------------------------------------------------------------
    # File> Load Find Buttons clicked. Ask the user for a file to open and
    # if one is given, open it and pass the text stream to the Find panel
    # loadUserButtons method. Start the search in the book folder, as we
    # expect user buttons to be book-related.
    def buttonLoad(self):
        startPath = QString(".") if self.bookPath.isEmpty() else self.bookPath
        bfName = QFileDialog.getOpenFileName(self,
                "PPQT - choose a file of saved user button definitions",
                startPath)
        if not bfName.isEmpty():
            (buttonStream, fh) = self.openSomeFile(bfName,
                                                   QIODevice.ReadOnly, "UTF-8")
            if buttonStream is not None:
                IMC.findPanel.loadUserButtons(buttonStream)
                fh.close()

    # -----------------------------------------------------------------
    # File> Save Find Buttons clicked. Ask the user for a file to open and
    # if one is given, open it for output and pass the stream to the Find
    # panel saveUserButtons method.
    def buttonSave(self):
        startPath = QString(".") if self.bookPath.isEmpty() else self.bookPath
        bfName = QFileDialog.getSaveFileName(self,
                "Save user-defined buttons as:", startPath)
        if not bfName.isEmpty():
            (buttonStream, fh) = self.openSomeFile(bfName,
                                                   QIODevice.WriteOnly, "UTF-8")
            if buttonStream is not None:
                IMC.findPanel.saveUserButtons(buttonStream)
                fh.close()

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
    