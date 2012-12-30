# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "1.01.0" # refer to PEP-0008
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
Provide a simple HTML Preview using a QWebView widget. The panel consists
of a Refresh button and a WebView. On Refresh we get the
editor's plain text and stuff it into the webview as HTML. We use the 
loadstarted, loadprogress, and loadended signals as they are intended, to
roll the progress bar. (Note: to date, this has always finished so fast
the progress bar is never really visible. It is quick!)

We also provide a function for getting the plain text from the displayed
web page, this lets us extract the plain text from an HTML document
without having to be a DOM parser! We tell QWebView->QWebPage to select-all,
then return its selectedText, which is plain text stripped of HTML cruft.
(Not clear this will actually be used but it's there.)
'''
from PyQt4.QtCore import ( QChar, QPoint, Qt, QString, QUrl, SIGNAL)
from PyQt4.QtGui import (
    QFont, QFontInfo,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget
)
from PyQt4.QtWebKit import(
    QWebFrame, QWebPage, QWebView, QWebSettings
)    
import pqMsgs

class htmlPreview(QWidget):
    def __init__(self, parent=None ):
        super(htmlPreview, self).__init__(parent)
	hbox = QHBoxLayout()
	self.refreshButton = QPushButton(u"Refresh")
	hbox.addWidget(self.refreshButton,0)
	hbox.addStretch(1)
	self.refreshAndClearButton = QPushButton(u"Refresh + Clear")
	hbox.addWidget(self.refreshAndClearButton)
	vbox = QVBoxLayout()
	vbox.addLayout(hbox,0)
	self.preview = QWebView(self)
	vbox.addWidget(self.preview,1)
	self.setLayout(vbox)
	# make the web preview uneditable
	self.preview.page().setContentEditable(False)
	self.settings = self.preview.settings()
	# Find out the nearest font to Palatino
	qf = QFont()
	qf.setStyleStrategy(QFont.PreferAntialias+QFont.PreferMatch)
	qf.setStyleHint(QFont.Serif)
	qf.setFamily(QString(u'Palatino'))
	qfi = QFontInfo(qf)
	# set the default font to that serif font
	self.settings.setFontFamily(QWebSettings.StandardFont, qfi.family())
	self.settings.setFontSize(QWebSettings.DefaultFontSize, 16)
	self.settings.setFontSize(QWebSettings.MinimumFontSize, 6)
	self.settings.setFontSize(QWebSettings.MinimumLogicalFontSize, 6)
	self.textZoomFactor = 1.0
	self.preview.setTextSizeMultiplier(self.textZoomFactor)
	# Disable everything but bog-standard html, appropriate for PP
	self.settings.setAttribute(QWebSettings.JavascriptEnabled, False)
	self.settings.setAttribute(QWebSettings.JavaEnabled, False)
	self.settings.setAttribute(QWebSettings.PluginsEnabled, False)
	self.settings.setAttribute(QWebSettings.ZoomTextOnly, True)
	# the following causes a hard error in linux
	#self.settings.setAttribute(QWebSettings.SiteSpecificQuirksEnabled, False)
	# hook up the refresh buttons
	self.connect(self.refreshButton, SIGNAL("clicked()"),self.refresh1Click)
	self.connect(self.refreshAndClearButton, SIGNAL("clicked()"),self.refresh2Click)
	# hook up the load status signals
	self.connect(self.preview,SIGNAL("loadStarted()"),self.loadStarts )
	self.connect(self.preview,SIGNAL("loadProgress(int)"),self.loadProgresses )
	self.connect(self.preview,SIGNAL("loadFinished(bool)"),self.loadEnds )
	# here we store the scroll position to return to after reloading
	self.scrollPosition = QPoint(0,0)
	# here save the user's find text for ctl-g use
	self.findText = QString()
	# here store the base URL for the current book.
	self.baseURL = QUrl()
	# save a shortcut reference to the browser history object 
	self.history = self.preview.page().history()
	# we do NOT initialize the preview (e.g. by calling self.refresh)
	# at construction time. It may be many hours before the user wants
	# to preview html. So require an explicit refresh click to do it.	
    
    # Plain Refresh clicked.
    def refresh1Click(self) :
	self.refresh(False)
    # Refresh + Clear clicked.
    def refresh2Click(self) :
	self.refresh(True)

    # One or the other refresh button clicked.
    # Get the current scroll position (a QPoint that reflects the position of the
    # scrollbar "thumb" in the webview) from the QWebFrame that is associated with
    # the QWebPage that is displayed in our QWebView, and save it for use after
    # the loadEnds() signal is received, to restore the previous scroll position.
    # 
    # If Refresh+Clear was clicked, clear the memory cache -- a function that is 
    # strangely located in the web settings object, but whatever -- and then reload
    # the HTML contents from the editor document,
    def refresh(self, clearCache=False ):
	# this could be first refresh for this book file, so set the
	# base URL for its images.
	sep = QChar(u'/')
	qsp = QString(IMC.bookDirPath)
	if not qsp.endsWith(sep):
	    qsp.append(sep)
	self.baseURL = QUrl.fromLocalFile(qsp)
	# this might be the second or nth refresh of the book, note the
	# scroll position so we can restore it in loadEnds below. This
	# means that when you make a little edit at the end of a book, and
	# refresh the preview, you won't have to scroll down to the end
	# for the 500th time to see your changes.
	self.scrollPosition = self.preview.page().mainFrame().scrollPosition()
	if clearCache :
	    self.settings.clearMemoryCaches()
	self.preview.setHtml(IMC.editWidget.toPlainText(),self.baseURL) 

    # handle the load-in-progress signals by running our main window's
    # progress bar
    def loadStarts(self):
	pqMsgs.startBar(100,"Loading HTML")
    def loadProgresses(self,amt):
	pqMsgs.rollBar(amt)
    def loadEnds(self,bool):
	pqMsgs.endBar()
	if bool:
	    # load was ok, reset scroll position now the rendering is finished.
	    self.preview.page().mainFrame().setScrollPosition(self.scrollPosition)
	    # our panel is visible (else how was Refresh clicked?) but it may
	    # not have the keyboard focus. Right after refresh one usually wants
	    # to use keys like page-up/dn, so get the focus to our webview
	    # widget (not the page in it because the webview has the scroll
	    # bars and other mechanism.)
	    self.preview.setFocus(Qt.MouseFocusReason)	    
	else:
	    pqMsgs.warningMsg("Some problem loading html")
		
    
    # Re-implement the parent's keyPressEvent in order to provide a simple
    # find function, font-zoom from ctl-plus/minus, and browser "back".
    # For the font size, we initialize the view at 16 points and
    # the textSizeMultiplier at 1.0. Each time the user hits ctl-minus
    # we deduct 0.0625 from the multiplier, and for each ctl-+ we add 0.0625
    # (1/16) to the multiplier. This ought to cause the view to change up or
    # down by one point. We set a limit of 0.375 (6 points) at the low
    # end and 4.0 (64 points) at the top.
    def keyPressEvent(self, event):
	kkey = int( int(event.modifiers()) & IMC.keypadDeModifier) | int(event.key())
	if (kkey == IMC.ctl_F) or (kkey == IMC.ctl_G) : # ctl/cmd f/g
	    event.accept()
	    self.doFind(kkey)
	elif (kkey in IMC.zoomKeys) : # ctrl-plus/minus
	    zfactor = 0.0625 # zoom in
	    if (kkey == IMC.ctl_minus) :
		zfactor = -zfactor # zoom out
	    zfactor += self.textZoomFactor
	    if (zfactor > 0.374) and (zfactor < 4.0) :
		self.textZoomFactor = zfactor
		self.preview.setTextSizeMultiplier(self.textZoomFactor)
	elif (kkey in IMC.backKeys) :
	    if self.history.canGoBack() :
		self.history.back()
	    else :
		# reload the html of the book text, but don't call refresh
		# because it would capture the scroll position as of now,
		# and that relates to the linked page we are coming back from.
		# The scroll position noted the last time Refresh was clicked
		# will be instantiated in the loadEnds slot.
		self.history.clear()
		self.preview.setHtml(IMC.editWidget.toPlainText(),self.baseURL)
	    
	else: # not a key we support, so,
	    event.ignore()
	    super(htmlPreview, self).keyPressEvent(event)

    # Implement a simple Find/Find-Next, same logic as in pqNotes,
    # but adjusted for our widget being a webview, and it does the
    # wraparound for us.
    def doFind(self,kkey):
	if (kkey == IMC.ctl_F) or (self.findText.isEmpty()) :
	    # ctl+F, or ctl+G but no previous find done, show the find dialog
	    # with a COPY of current selection as pqMsgs might truncate it
	    prepText = QString(self.preview.page().selectedText())
	    (ok, self.findText) = pqMsgs.getFindMsg(self,prepText)
	# dialog or no dialog, we should have some findText now
	if not self.findText.isEmpty() :
	    if not self.preview.page().findText(
	        self.findText, QWebPage.FindWrapsAroundDocument
	    ) :
		pqMsgs.beep()
    
if __name__ == "__main__":
    import sys
    import os
    from PyQt4.QtCore import (Qt,QFile,QIODevice,QFileInfo,QTextStream,QSettings)
    from PyQt4.QtGui import (QApplication,QPlainTextEdit,QFileDialog,QMainWindow)
    import pqIMC
    app = QApplication(sys.argv) # create an app
    IMC = pqIMC.tricorder() # create inter-module communicator
    pqMsgs.IMC = IMC
    IMC.bookType = QString(u"html")
    M = QMainWindow()
    pqMsgs.makeBarIn(M.statusBar())
    utname = QFileDialog.getOpenFileName(M,
                "UNIT TEST DATA FOR FLOW", ".")
    utfile = QFile(utname)
    if not utfile.open(QIODevice.ReadOnly):
        raise IOError, unicode(utfile.errorString())
    utinfo = QFileInfo(utfile)
    IMC.bookDirPath = utinfo.absolutePath()
    utstream = QTextStream(utfile)
    utstream.setCodec("UTF-8")
    utqs = utstream.readAll()
    IMC.editWidget = QPlainTextEdit()
    IMC.editWidget.setPlainText(utqs)
    IMC.editWidget.show()
    W = htmlPreview()
    M.setCentralWidget(W)
    M.show()
    #t = unicode(W.getSimpleText())
    #print(t)
    #W.doneWithText()
    app.exec_()

