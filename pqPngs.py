# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
Display the pngs to match the page being edited.

The object consists of a vertical box layout containing, above,
a QLabel widget initialized with a 700x1000 QPixmap with fill(QColor("gray"))
and enclosed in a QScrollArea, and below, a small label to display the current
page number initialized with "No page"

Reimplements keyPressEvent() copied from the editor, trapping ctl-plus/minus
to zoom the image when an image exists. Zooming is done by just changing
the size hint of the pixmap; it scales, and the parent scrollarea scrolls.

The method cursorMoved() is connect to the cursorPositionChanged signal emitted
by the editor. It gets the current position, looks it up in IMC.pageTable,
gets the filename and IMC.bookPath to give to the load method of QPixMap.

N.B. there is a cryptic comment in the QPixmap doc page that "QPixmaps are
automatically added to the QPixmapCache when loaded from a file." This seems
to mean that it will avoid a second disk load when we revisit a page, and
the performance would indicate this is so.
'''

from PyQt4.QtCore import ( Qt, QFileInfo, QString, QSettings, QVariant )
from PyQt4.QtGui import (
    QColor,
    QFrame, QKeyEvent, QLabel, QPalette, QPixmap,
    QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget)

class pngDisplay(QWidget):
    def __init__(self, parent=None):
        super(pngDisplay, self).__init__(parent)
        # create the label that displays the image - cribbing from the Image
        # Viewer example in the Qt docs.
        self.imLabel = QLabel()
        self.imLabel.setBackgroundRole(QPalette.Base)
        self.imLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.imLabel.setScaledContents(True)
        self.defaultPM = QPixmap(700,900)
        self.defaultPM.fill(QColor("gray"))
        self.scarea = QScrollArea()
        # The following two lines make sure that page up/dn gets through
        # the scrollarea widget and up to us.
        self.setFocusPolicy(Qt.ClickFocus)
        self.scarea.setFocusProxy(self)
        self.scarea.setBackgroundRole(QPalette.Dark)
        self.scarea.setWidget(self.imLabel)
        # create the text label that will have the page number in it
        self.txLabel = QLabel(u"No image")
        self.txLabel.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self.txLabel.setFrameStyle(QFrame.Sunken | QFrame.StyledPanel)
        # create our layout
        vbox = QVBoxLayout()
        # the image gets a high stretch and default alignment, the text
        # label hugs the bottom and doesn't stretch at all.
        vbox.addWidget(self.scarea,10)
        vbox.addWidget(self.txLabel,0,Qt.AlignBottom)
        self.setLayout(vbox)
        qv = IMC.settings.value("pngs/zoomFactor",QVariant(1.0))
        self.zoomFactor = qv.toFloat()[0]
        self.clear()
        
    # local subroutine to initialize our contents for an empty edit.
    # called from _init_ and from newPosition when we discover the file
    # has been cleared on us. Don't reset the zoomFactor, leave it as
    # the user las set it.
    def clear(self):
        self.imLabel.setPixmap(self.defaultPM)
        self.txLabel.setText(u"No image")
        # Variables to speed up our position look-up
        IMC.currentPageNumber = QString() # last page e.g. "002"
        self.lastPage = QString() # last file name e.g. "002.png"
        self.bookName = QString() # name of book we are in
        self.pngPath = QString() # path to the pngs folder
        self.lastIndex = -1 # index of last page in pageTable or -1
        IMC.currentPageIndex = None
        self.ready = False
    
    # this slot gets the main window's signal shuttingDown.
    # we write our current zoom factor into IMC.settings.
    def shuttingDown(self):
        IMC.settings.setValue("pngs/zoomFactor",QVariant(self.zoomFactor))
        
    # This slot gets the main window's signal docHasChanged(QString).
    # The full bookPath is passed and we convert that into the path to
    # the pngs folder, and see if that is a directory. When that is all
    # good we set ready to true. The next thing to happen will be the
    # cursorPositionChanged signal from the editor.
    def newFile(self, bookPath):
        finf = QFileInfo(bookPath)
        if not bookPath.isNull(): # this was File>Open
            self.bookName = finf.fileName() # for cache tags
            self.pngPath = finf.path()
            self.pngPath.append(u"/pngs/")
            finf = QFileInfo(self.pngPath)
            if finf.exists() and finf.isDir(): # looking good
                self.ready = True
            else:
                # we could inform the user we couldn't find the pngs folder,
                # but you know -- the user is probably already aware of that.
                self.clear() # just put up the gray default image
        else: # It was a File>New
            self.clear()

    # This function is the slot that is connected to the editor's 
    # cursorPositionChanged signal.
    def newPosition(self):
        if not self.ready : return # no file loaded or no pngs folder
        if 0 == len(IMC.pageTable): # no book open, or no pngs with it
            # this could happen on the first call at startup, the first
            # call after a document has been loaded but before the metadata
            # has been built, or after a File>New. Just bail.
            return
        else:
            # find our most advanced position in the text
            pos = IMC.editWidget.textCursor().selectionEnd()
            # here we go with bisect_right to find the last page table entry
            # <= to our present position. We know the table is not empty, but
            # after pseps are removed, there can be multiple pages with the
            # same starting offset.
            hi = len(IMC.pageTable)
            lo = 0
            while lo < hi:
                mid = (lo + hi)//2
                if pos < IMC.pageTable[mid][0].position(): hi = mid
                else: lo = mid+1
            # the page at lo-1 is the greatest <= pos. If it is the same as
            # we already displayed then bail out.
            lo -= 1
            if self.lastIndex == (lo) :
                return # nothing to do, we are there
            # On another page, save its index as IMC.currentPageIndex for use
            # by pqNotes and here as lastIndex. Then display it.
            self.lastIndex = lo
            IMC.currentPageIndex = lo
            self.showPage()
    # Display the page indexed by self.lastPage.
    # Get its filename Qstring, e.g. "025", add ".png"
    # and save as self.lastPage. Make full path to the image and load it.
    # Update our image label with the filename and zoom factor.
    def showPage(self):
        self.lastPage = QString(IMC.pageTable[self.lastIndex][1]+u".png")
        png = self.pngPath + self.lastPage
        pxmap = QPixmap(png)
        if not pxmap.isNull(): # successfully got a pixmap from a file
            self.imLabel.setPixmap(pxmap)
            self.imLabel.resize( self.zoomFactor * pxmap.size() )
            self.txLabel.setText(
            u"{0} - {1}%".format(self.lastPage, int(100*self.zoomFactor))
                                )
        else: # no file - it's ok if pages are missing
            self.imLabel.setPixmap(self.defaultPM)
            self.txLabel.setText(u"No image")

    # Re-implement the parent's keyPressEvent in order to provide zoom:
    # ctrl-plus increases the image size by 1.25
    # ctrl-minus decreases the image size by 0.8
    # Also trap pageup/dn and use to walk through images.
    # At this point we do not reposition the editor to match the page viewed.
    # we page up/dn but as soon as focus returns to the editor and the cursor
    # moves, this display will snap back to the edited page. As a user that
    # seems best, come over to Pngs and page ahead to see what's coming, then
    # back to the editor to read or type.
    def keyPressEvent(self, event):
        # If we are initialized and have displayed some page, look at the key
        if (self.ready) and (IMC.currentPageIndex is not None):
            code = int(event.key())
            mods = int(event.modifiers())
            # print('key {0:X} mod {1:X}'.format(code,mods))
            if (mods & Qt.ControlModifier):
                # ctl/cmd-something 
                if (code == Qt.Key_Equal) \
                or (code == Qt.Key_Plus) or (code == Qt.Key_Minus):
                    # ctl/cmd + or -, do the zoom
                    event.accept()
                    fac = (0.8) if (code == Qt.Key_Minus) else (1.25)
                    fac *= self.zoomFactor # target zoom factor
                    if (fac >= 0.2) and (fac <= 3.0): # keep in bounds
                        self.imLabel.resize( fac * self.imLabel.pixmap().size() )
                        self.zoomFactor = fac
                        self.txLabel.setText(
                    u"{0} - {1}%".format(self.lastPage, int(100*self.zoomFactor))
                        )
                else: # control-something but not one of ours
                    event.ignore()
            else: # not ctl/cmd modifier
                if (code == Qt.Key_PageUp) or (code == Qt.Key_PageDown) :
                    # real pgUp or pgDn
                    event.accept()
                    fac = 1 if (code == Qt.Key_PageDown) else -1
                    fac += self.lastIndex
                    if (fac >= 0) and (fac < len(IMC.pageTable)) : 
                        # not off the end of the book, so,
                        self.lastIndex = fac
                        IMC.currentPageIndex = fac
                        self.showPage()
                else: # some other key
                    event.ignore()
        # ignored or accepted, pass the event along.
        super(pngDisplay, self).keyPressEvent(event)

if __name__ == "__main__":
    import sys
    from PyQt4.QtCore import (QSettings)
    from PyQt4.QtGui import (QApplication,QFileDialog)
    class tricorder():
        def __init__(self):
            pass
    IMC = tricorder() # set up a fake IMC for unit test
    IMC.settings = QSettings()
    app = QApplication(sys.argv) # create an app
    widj = pngDisplay()
    apng = QFileDialog.getOpenFileName(widj,"Pick a Png",".","page files (*.png)")
    pm = QPixmap(apng)
    widj.imLabel.setPixmap(pm)
    widj.imLabel.adjustSize()
    widj.show()
    app.exec_()

