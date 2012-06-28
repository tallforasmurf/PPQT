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
    QFont,
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
	vbox = QVBoxLayout()
	vbox.addLayout(hbox,0)
	self.preview = QWebView(self)
	vbox.addWidget(self.preview,1)
	self.setLayout(vbox)
	# make the web preview uneditable
	self.preview.page().setContentEditable(False)
	# Set a common available serif font as default
	self.settings = self.preview.settings()
	self.settings.setFontFamily(QWebSettings.StandardFont, 'Palatino')
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
	self.settings.setAttribute(QWebSettings.SiteSpecificQuirksEnabled, False)
	# hook up the refresh button
	self.connect(self.refreshButton, SIGNAL("clicked()"),self.refresh)
	# hook up the load status signals
	self.connect(self.preview,SIGNAL("loadStarted()"),self.loadStarts )
	self.connect(self.preview,SIGNAL("loadProgress(int)"),self.loadProgresses )
	self.connect(self.preview,SIGNAL("loadFinished(bool)"),self.loadEnds )
	self.scrollPosition = QPoint(0,0)
	self.findText = QString()
    
    # refresh button clicked. Get the current scroll position (a QPoint that
    # reflects the position of the scrollbar "thumb" in the webview)
    # from the QWebFrame -- associated with the QWebPage -- displayed in our
    # QWebView -- and save it. See loadEnds() for use.
    # Then reload the HTML contents from the editor.
    def refresh(self):
	self.scrollPosition = self.preview.page().mainFrame().scrollPosition()
	self.setHtml(IMC.editWidget.toPlainText()) # see setHtml below!

    # handle the load-in-progress signals by running our main window's
    # progress bar
    def loadStarts(self):
	pqMsgs.startBar(100,"Loading HTML")
    def loadProgresses(self,amt):
	pqMsgs.rollBar(amt)
    def loadEnds(self,bool):
	pqMsgs.endBar()
	if bool:
	    # load was ok, reset scroll position now the rendering is finished
	    self.preview.page().mainFrame().setScrollPosition(self.scrollPosition)
	else:
	    pqMsgs.warningMsg("Some problem loading html")
		


    # provide simpler access to the web view's setHtml method. Provide a base
    # url which is the file path to where the image subdirectory should be.
    # The path (originally from QFileInfo.absolutePath) lacks a terminal slash
    # and without it, the URL won't work as a base for e.g.  the images folder.
    # So add one. Since it's a URL we are dealing with we don't have to worry
    # about using '\' in windows and '/' in unix, it's '/' always.
    def setHtml(self,qs):
	sep = QChar(u'/')
	qsp = QString(IMC.bookPath)
	if not qsp.endsWith(sep):
	    qsp.append(sep)
	base = QUrl.fromLocalFile(qsp)
	self.preview.setHtml(qs,base)

    ## return a "const" pointer to the plain text of the web page. Since the
    ## point is "const" it is live, if we change the selection, the text 
    ## changes. So we can't just select-all, grab a pointer, and then clear
    ## the selection; the caller would just get an empty string. We select-all
    ## and return the pointer, then when the caller is finished, he calls back
    ## to doneWithText() and we clear the selection.
    #def getSimpleText(self):
	#self.preview.page().triggerAction(QWebPage.SelectAll)
	#return self.preview.page().selectedText()
    ## findText() of a null string clears the selection
    #def doneWithText(self):
	#self.preview.page().findText(QString())
    
    # Re-implement the parent's keyPressEvent in order to provide a simple
    # find function and font-zoom from ctl-plus/minus. We start the view at
    # 16 points and textSizeMultiplier of 1.0. Each time the user hits ctl-minus
    # we deduct 0.0625 from the multiplier, and for each ctl-+ we add 0.0625
    # (1/16) to the multiplier. This ought to cause the view to change up or
    # down by one point. We set a limit of 0.375 (6 points) at the low
    # end and 4.0 (64 points) at the top.
    def keyPressEvent(self, event):
	kkey = int(event.modifiers())+int(event.key())
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
	else: # not ctl/cmd f or ctl/cmd-plus/minus, so,
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
    IMC.bookPath = utinfo.absolutePath()
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

