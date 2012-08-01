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
The help consists of a QWebView in read-only mode, whose document
is read from pqHelp.html in the app folder.
'''

from PyQt4.QtCore import ( Qt, QFile, QString, QIODevice, QTextStream)
from PyQt4.QtWebKit import(QWebPage, QWebView, QWebSettings)
from PyQt4.QtGui import (QAction, QKeySequence)
import pqMsgs
import os

# Initialize our only widget, a modified WebView. If you compare this to
# pqView.py it is obviously similar but confusing, because in pqView,
# "self" is a QWidget that contains a QWebView, where here, "self" IS the
# QWebView. So there's one less level of indirection: in pqView, the WebView
# is "self.preview." where here it's "self." except for the web settings,
# because pqView gets a reference "self.settings = self.preview.settings()"
# so in pqView it is "self.settings." and here, "self.settings()."
#

class helpDisplay(QWebView):
    def __init__(self, parent=None ):
        super(helpDisplay, self).__init__(parent)
	# make page unmodifiable
	#self.page().setContentEditable(False)
	# initialize settings (copied from pqView)
	self.settings().setFontFamily(QWebSettings.StandardFont, 'Palatino')
	self.settings().setFontSize(QWebSettings.DefaultFontSize, 16)
	self.settings().setFontSize(QWebSettings.MinimumFontSize, 6)
	self.settings().setFontSize(QWebSettings.MinimumLogicalFontSize, 6)
	self.textZoomFactor = 1.0
	self.setTextSizeMultiplier(self.textZoomFactor)
	self.settings().setAttribute(QWebSettings.JavascriptEnabled, False)
	self.settings().setAttribute(QWebSettings.JavaEnabled, False)
	self.settings().setAttribute(QWebSettings.PluginsEnabled, False)
	self.settings().setAttribute(QWebSettings.ZoomTextOnly, True)
	#self.settings().setAttribute(QWebSettings.SiteSpecificQuirksEnabled, False)
	self.userFindText = QString()
	# Look for pqHelp.html in the app folder and copy its text into
	# a local buffer. If it isn't found, put a message there instead.
	# We need to keep it in order to implement the "back" function.
	helpPath = os.path.join(IMC.appBasePath,u'pqHelp.html')
	helpFile = QFile(helpPath)
	if not helpFile.exists():
	    self.HTMLstring = QString('''<p>Unable to locate pqHelp.html.</p>
	    <p>Looking in {0}'''.format(helpPath)
                            )
	elif not helpFile.open(QIODevice.ReadOnly) :
	    self.HTMLstring = QString('''<p>Unable to open pqHelp.html.</p>
	    <p>Looking in {0}</p><p>Error code {1}</p>'''.format(helpPath,
	                                                helpFile.error())
	                                                 )
	else:
	    helpStream = QTextStream(helpFile)
	    helpStream.setCodec('ISO8859-1')
	    self.HTMLstring = helpStream.readAll()
	self.setHtml(self.HTMLstring)
	
    # Re-implement the parent's keyPressEvent in order to provide a simple
    # find function and font-zoom from ctl-plus/minus. We start the view at
    # 16 points and textSizeMultiplier of 1.0. Each time the user hits ctl-minus
    # we deduct 0.0625 from the multiplier, and for each ctl-+ we add 0.0625
    # (1/16) to the multiplier. This ought to cause the view to change up or
    # down by one point. We set a limit of 0.375 (6 points) at the low
    # end and 4.0 (64 points) at the top.
    def keyPressEvent(self, event):
	kkey = int(event.modifiers())+int(event.key())
	#print('key {0:X}'.format(kkey))
	if (kkey == IMC.ctl_F) or (kkey == IMC.ctl_G) : # ctl/cmd f/g
	    event.accept()
	    self.doFind(kkey)
	elif (kkey in IMC.zoomKeys) : # ctl-plus/minus
	    zfactor = 0.0625 # zoom in
	    if (kkey == IMC.ctl_minus) :
		zfactor = -zfactor # zoom out
	    zfactor += self.textZoomFactor
	    if (zfactor > 0.374) and (zfactor < 4.0) :
		self.textZoomFactor = zfactor
		self.setTextSizeMultiplier(self.textZoomFactor)
	elif (kkey in IMC.backKeys) : # ctl-B/[/left
	    if self.page().history().canGoBack() :
		self.page().history().back()
	    else :
		self.setHtml(self.HTMLstring)
		self.page().history().clear()
	else: # not ctl/cmd f or ctl/cmd-plus/minus, so,
	    event.ignore()
	    super(helpDisplay, self).keyPressEvent(event)

    # Implement a simple Find/Find-Next, same logic as in pqNotes,
    # but adjusted for our widget being a webview, and it does the
    # wraparound for us.
    def doFind(self,kkey):
	if (kkey == IMC.ctl_F) or (self.userFindText.isEmpty()) :
	    # ctl+F, or ctl+G but no previous find done, show the find dialog
	    # with a COPY of current selection as pqMsgs might truncate it
	    prepText = QString(self.page().selectedText())
	    (ok, self.userFindText) = pqMsgs.getFindMsg(self,prepText)
	# We should have some findText now, either left from previous find
	# on a ctl-G, or entered by user. If none, then user cleared dialog.
	if not self.userFindText.isEmpty() :
	    if not self.page().findText(
	        self.userFindText, QWebPage.FindWrapsAroundDocument
	        ) :
		pqMsgs.beep()

if __name__ == "__main__":
    import sys
    from PyQt4.QtCore import (Qt)
    from PyQt4.QtGui import (QApplication)
    import pqIMC
    IMC = pqIMC.tricorder()
    if hasattr(sys, 'frozen') : # bundled by pyinstaller?
	base = os.path.dirname(sys.executable)
    else: # running under normal python e.g. from command line or an IDE
	base = os.path.dirname(__file__)
    IMC.appBasePath = base

    app = QApplication(sys.argv) # create an app
    W = helpDisplay()
    W.show()
    app.exec_()

