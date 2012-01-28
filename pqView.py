# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

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
from PyQt4.QtCore import ( QChar, Qt, QString, QUrl, SIGNAL)
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
	settings = QWebSettings.globalSettings()
	settings.setFontFamily(QWebSettings.StandardFont, 'Palatino')
	settings.setFontSize(QWebSettings.DefaultFontSize, 16)
	self.preview = QWebView(self)
	vbox.addWidget(self.preview,1)
	self.setLayout(vbox)
	# make the web preview uneditable
	self.preview.page().setContentEditable(False)
	# hook up the refresh button
	self.connect(self.refreshButton, SIGNAL("clicked()"),self.refresh)
	# hook up the load status signals
	self.connect(self.preview,SIGNAL("loadStarted()"),self.loadStarts )
	self.connect(self.preview,SIGNAL("loadProgress(int)"),self.loadProgresses )
	self.connect(self.preview,SIGNAL("loadFinished(bool)"),self.loadEnds )
    
    # refresh button clicked. Get the current scroll position (a QPoint that
    # reflects the position of the scrollbar "thumb" in the webview)
    # from the QWebFrame associated with the QWebPage displayed in our
    # QWebView. Then reset the HTML and scroll back to the same point.
    def refresh(self):
	scrollpos = self.preview.page().mainFrame().scrollPosition()
	self.setHtml(IMC.editWidget.toPlainText()) # see setHtml below!
	self.preview.page().mainFrame().setScrollPosition(scrollpos)

    # handle the load-in-progress signals by running our main window's
    # progress bar
    def loadStarts(self):
	pqMsgs.startBar(100,"Loading HTML")
    def loadProgresses(self,amt):
	pqMsgs.rollBar(amt)
    def loadEnds(self,bool):
	pqMsgs.endBar()
	if not bool:
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

    # return a "const" pointer to the plain text of the web page. Since the
    # point is "const" it is live, if we change the selection, the text 
    # changes. So we can't just select-all, grab a pointer, and then clear
    # the selection; the caller would just get an empty string. We select-all
    # and return the pointer, then when the caller is finished, he calls back
    # to doneWithText() and we clear the selection.
    def getSimpleText(self):
	self.preview.page().triggerAction(QWebPage.SelectAll)
	return self.preview.page().selectedText()
    # findText() of a null string clears the selection
    def doneWithText(self):
	self.preview.page().findText(QString())
    
    ## Re-implement the parent's keyPressEvent in order to provide a simple
    ## find function only.
    #def keyPressEvent(self, event):
	#kkey = int(event.modifiers())+int(event.key())
	#if kkey == IMC.ctl_F: # ctl/cmd f
	    #event.accept()
	    #self.doFind()
	#else: # not ctl/cmd f so,
	    #event.ignore()
        ## ignored or accepted, pass the event along.
        #super(helpDisplay, self).keyPressEvent(event)

    ## Do a simple find. getFindMsg returns (ok,find-text). This is a VERY
    ## simple find from the present cursor position downward, case-insensitive.
    ## If we get no hit we try once more from the top, thus in effect wrapping.    
    #def doFind(self):
	#(ok, findText) = pqMsgs.getFindMsg(self)
	#if ok and (not findText.isNull()) :
	    #if not self.find(findText): # no hits going down
		#self.moveCursor(QTextCursor.Start) # go to top
		#if not self.find(findText): # still no hit
		    #pqMsgs.beep()

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

