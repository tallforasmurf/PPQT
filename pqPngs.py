# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
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
and passes the filename and path to the load method of QPixMap. The path
comes from the pqMain's docHasChanged signal.

N.B. there is a cryptic comment in the QPixmap doc page that "QPixmaps are
automatically added to the QPixmapCache when loaded from a file." This seems
to mean that it will avoid a second disk load when we revisit a page, and
the performance would indicate this is so.
'''

from PyQt4.QtCore import ( Qt, QFileInfo, QString, QSettings, QVariant, SIGNAL )
from PyQt4.QtGui import (
    QColor, QImage, QPixmap,
    QFrame, QKeyEvent, QLabel, QPalette, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox,
    QHBoxLayout, QVBoxLayout, QWidget)

class pngDisplay(QWidget):
    def __init__(self, parent=None):
        super(pngDisplay, self).__init__(parent)
        # create the label that displays the image - cribbing from the Image
        # Viewer example in the Qt docs.
        self.imLabel = QLabel()
        self.imLabel.setBackgroundRole(QPalette.Base)
        self.imLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.imLabel.setScaledContents(True)
        # Create a gray field to use when no png is available
        self.defaultPM = QPixmap(700,900)
        self.defaultPM.fill(QColor("gray"))
        # Create a scroll area within which to display our imLabel, this
        # enables the creation of horizontal and vertical scroll bars, when
        # the imLabel exceeds the size of the scroll area.
        self.scarea = QScrollArea()
        # The following two lines make sure that page up/dn gets through
        # the scrollarea widget and up to us.
        self.setFocusPolicy(Qt.ClickFocus)
        self.scarea.setFocusProxy(self)
        self.scarea.setBackgroundRole(QPalette.Dark)
        #self.scarea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        #self.scarea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scarea.setWidget(self.imLabel)
        # create the text label that will have the page number in it
        self.txLabel = QLabel(u"No image")
        self.txLabel.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self.txLabel.setFrameStyle(QFrame.Sunken | QFrame.StyledPanel)
        # Create a spinbox to set the zoom from 15 to 200 with a label:
        # (originally a slider, hence the name)
        self.minZoom = 0.15
        self.maxZoom = 2.00
        self.zlider = QSpinBox()
        self.zlider.setRange(int(100*self.minZoom),int(100*self.maxZoom))
        # connect the value change signal to a slot to handle it
        self.connect(self.zlider, SIGNAL("valueChanged(int)"), self.newZoomFactor)
        # create the to-width and to-height zoom buttons
        zoomWidthButton = QPushButton(u'to Width')
        self.connect(zoomWidthButton, SIGNAL("clicked()"), self.zoomToWidth)
        zoomHeightButton = QPushButton(u'to Height')
        self.connect(zoomHeightButton, SIGNAL("clicked()"), self.zoomToHeight)
        # Make an hbox to contain the spinbox and two pushbuttons, with 
        # stretch on left and right to center the group.
        zlabel = QLabel(
            u'&Zoom ' + str(self.zlider.minimum())
            + '-' + str(self.zlider.maximum()) + '%')
        zlabel.setBuddy(self.zlider)
        zhbox = QHBoxLayout()
        zhbox.addStretch(1)
        zhbox.addWidget(zlabel,0,Qt.AlignLeft)
        zhbox.addWidget(self.zlider,0)
        zhbox.addStretch(1)
        zhbox.addWidget(zoomWidthButton)
        zhbox.addWidget(zoomHeightButton)   
        zhbox.addStretch(1)
        # With all the pieces in hand, create our layout basically a
        # vertical stack: scroll area, label, slider box.
        vbox = QVBoxLayout()
        # the image gets a high stretch and default alignment, the text
        # label hugs the bottom and doesn't stretch at all.
        vbox.addWidget(self.txLabel,0,Qt.AlignBottom)
        vbox.addWidget(self.scarea,10)
        vbox.addLayout(zhbox,0)
        self.setLayout(vbox)
        # Initialize assuming no book is open.
        self.ready = False # nothing to display
        # Recover the last-set zoom factor from the settings object, default 1.0
        qv = IMC.settings.value("pngs/zoomFactor",QVariant(1.0))
        self.zoomFactor = qv.toFloat()[0]
        # The following causes entry into newZoomFactor, below, which tests
        # self.ready, hence the latter has to be assigned-to first.
        self.zlider.setValue(int(self.zoomFactor*100))
        self.clear()
        
    # local subroutine to initialize our contents for an empty edit.
    # called from _init_ and from newPosition when we discover the file
    # has been cleared on us. Don't reset the zoomFactor, leave it as
    # the user last set it.
    def clear(self):
        # Variables to speed up our position look-up
        IMC.currentPageNumber = QString() # last page e.g. "002"
        self.lastPage = QString() # last file name e.g. "002.png"
        self.pngPath = QString() # path to the pngs folder
        self.lastIndex = -1 # index of last-used page in pageTable or -1
        IMC.currentPageIndex = None
        self.ready = False
        self.pixmap = QPixmap() # null pixmap
        self.noImage() # show gray image
    
    # local subroutine to show a blank gray frame and "No Image" below.
    # Called from clear() above.
    def noImage(self) :
        self.imLabel.setPixmap(self.defaultPM)
        self.txLabel.setText(u"No image")
    
    # This slot gets the main window's signal shuttingDown.
    # We save our current zoom factor into IMC.settings.
    def shuttingDown(self):
        IMC.settings.setValue("pngs/zoomFactor",QVariant(self.zoomFactor))
        
    # This slot gets pqMain's signal docHasChanged(QString), telling
    # us that a different document has been loaded. This could be for
    # a successful File>Open, or a failed File>Open or File>New.
    # The bookPath is a null QString for File>New, or the full bookPath.
    # If the latter, we convert that into the path to the pngs folder,
    # and see if bookPath/pngs is a directory. If so, we set self.ready
    # to true, indicating it is worthwhile to try opening image files.
    # The next thing to happen will be a  cursorPositionChanged signal.
    def newFile(self, bookPath):
        if not bookPath.isNull(): # this was successful File>Open
            finf = QFileInfo(bookPath)
            self.pngPath = finf.absolutePath().append(u"/pngs/")
            finf = QFileInfo(self.pngPath)
            if finf.exists() and finf.isDir(): # looking good
                self.ready = True
            else:
                # We could inform the user we couldn't find a pngs folder,
                # but you know -- the user is probably already aware of that.
                self.clear() # just put up the gray default image
        else: # It was a File>New
            self.clear()

    # This function is the slot that is connected to the editor's 
    # cursorPositionChanged signal.
    def newPosition(self):
        if not self.ready : # no file loaded or no pngs folder found
            return
        if 0 == len(IMC.pageTable): # no book open, or no pngs with it
            # this could happen on the first call at startup, the first
            # call after a document has been loaded but before the metadata
            # has been built, or after a File>New. Just bail.
            return
        # find our most advanced position in the text
        pos = IMC.editWidget.textCursor().selectionEnd()
        # if that position is above the first page, which can happen if the
        # user has entered some text above the first psep line, show a
        # blank image.
        if pos < IMC.pageTable[0][0].position() :
            self.noImage()
            return
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

    # Display the page indexed by self.lastIndex. This is called when the cursor
    # moves to a new page (newPosition, above), or when the PageUp/Dn keys are used,
    # (keyPressEvent, below) or when the zoom factor changes in any of several ways.
    #
    # Form the image filename as a Qstring, e.g. "025"; then append ".png" and save
    # that as self.lastPage. Form the full path to the image. Load it as a QImage,
    # which will be an indexed-color format (one byte per pixel).
    # Convert that to a QPixmap and install it as the contents of our displayed label,
    # and scale it to the current zoom factor. The pixmap always has RGB32 format,
    # 4 bytes per pixel. However PG pngs are always(?) monochrome, so the only pixels
    # in the Image are 0x00 or 0xff, and in the pixmap are ff000000 or ffffffff.
    def showPage(self):
        self.lastPage = QString(IMC.pageTable[self.lastIndex][1]+u".png")
        pngName = self.pngPath + self.lastPage
        self.image = QImage(pngName,'PNG')
        self.pixmap = QPixmap.fromImage(self.image,Qt.ColorOnly)
        if not self.pixmap.isNull(): # we successfully found and loaded a file
            self.imLabel.setPixmap(self.pixmap)
            self.imLabel.resize( self.zoomFactor * self.pixmap.size() )
            self.txLabel.setText(
            u"{0} - {1}%".format(self.lastPage, int(100*self.zoomFactor))
                                )
        else: # no file was loaded. It's ok if pages are missing
            self.imLabel.setPixmap(self.defaultPM)
            self.txLabel.setText(u"No image")
    
    # Catch the signal from the Zoom spinbox with a new value.
    # Store the new value as a float, and if we have a page, repaint it.
    def newZoomFactor(self,new_value):
        self.zoomFactor = new_value / 100
        if self.ready :
            self.showPage()

    # Catch the click on zoom-to-width and zoom-to height. The job is basically
    # the same for both. 1: Using the QImage that should be in self.image,
    # scan the pixels to find the width (height) of the nonwhite area.
    # 2. Get the ratio of that to our image label's viewport width (height).
    # 4. Set that ratio as the zoom factor and redraw the image. And finally
    # 5. Set the scroll position(s) of our scroll area to left-justify the text.
    #
    # We get access to the pixels using QImage:bits() which gives us a PyQt4
    # "voidptr" that we can index to get byte values.
    #
    def zoomToWidth(self):
        if (not self.ready) or (self.image.isNull()) :
            return # nothing to do here
        # Our QImage, being loaded from an 8-bit monochrome PNG, should be
        # in Format_Indexed8. It might be Format_Mono (1 bit/pixel) or even
        # Format_RGB32. So make it Indexed8, easiest to handle.
        if self.image.format() != QImage.Format_Indexed8 :
            self.image = self.image.convertToFormat(QImage.Format_Indexed8,Qt.ColorOnly)
        # Query the Color look-up table and build a list of the Green values
        # corresponding to each possible pixel value. Probably there are just
        # two colors so colortab is [0,255] but there could be more, depending
        # on how the PNG was defined, 16 or 32 or even 255 grayscale.
        colortab = [ int((self.image.color(c) >> 4) & 255)
                    for c in range(self.image.colorCount()) ]
        ncols = self.image.width() # number of logical pixels across
        stride = (ncols + 3) & (-4) # number of bytes per scanline
        nrows = self.image.height() # number of pixels high
        vptr = self.image.bits() # uchar * bunch-o-pixel-bytes
        vptr.setsize(stride * nrows) # make the pointer indexable
        # Scan in from left and right to find the outermost dark spots.
        # Looking for single pixels yeilds too many false positives, so we
        # look for three adjacent pixels that sum to less than 32.
        left_side = int(ncols/2) # leftmost dark spot seen so far
        offset = 0
        for r in range(nrows) :
            pa, pb = 255, 255 # virtual white outside border
            for c in range(left_side):
                pc = colortab[ ord(vptr[offset + c]) ]
                if (pa + pb + pc) < 32 : # black or dark gray pair
                    left_side = c # new, further-left, left margin
                    break # no need to look further on this line
                pa, pb = pb, pc
            offset += stride
        offset = 0
        right_side = int(ncols/2) # rightmost dark spot seen so far
        for r in range(nrows) :
            pa, pb = 255, 255 # virtual white outside border
            for c in range(ncols-1,right_side,-1) :
                pc = colortab[ ord(vptr[offset + c]) ]
                if (pa + pb + pc) < 32 : # black or dark gray pair
                    right_side = c # new, further-right, right margin
                    break
                pa, pb = pb, pc
            offset += stride
        # The area with color runs from left_side to right_side. How does
        # that compare to the size of our viewport? Scale to that and redraw.
        text_size = right_side - left_side + 2
        port_width = self.scarea.viewport().width()
        self.zoomFactor = max( self.minZoom, min( self.maxZoom, port_width / text_size ) )
        self.zlider.setValue(int(100*self.zoomFactor)) # this signals newZoomFactor
        # Set the scrollbar to show the page from its left margin.
        self.scarea.horizontalScrollBar().setValue(int( left_side * self.zoomFactor) )
        

    def zoomToHeight(self):
        if (not self.ready) or (self.image.isNull()) :
            return # nothing to do here
        # Our QImage, being loaded from an 8-bit monochrome PNG, should be
        # in Format_Indexed8. It might be Format_Mono (1 bit/pixel) or even
        # Format_RGB32. So make it Indexed8, easiest to handle.
        if self.image.format() != QImage.Format_Indexed8 :
            self.image = self.image.convertToFormat(QImage.Format_Indexed8,Qt.ColorOnly)
        # Query the Color look-up table and build a list of the Green values
        # corresponding to each possible pixel value. Probably there are just
        # two colors so colortab is [0,255] but there could be more, depending
        # on how the PNG was defined, 16 or 32 or even 255 grayscale.
        colortab = [ int((self.image.color(c) >> 4) & 255)
                    for c in range(self.image.colorCount()) ]
        ncols = self.image.width() # number of logical pixels across
        stride = (ncols + 3) & (-4) # number of bytes per scanline
        nrows = self.image.height() # number of pixels high
        vptr = self.image.bits() # uchar * bunch-o-pixel-bytes
        vptr.setsize(stride * nrows) # make the pointer indexable
        # Scan in from top and bottom to find the outermost rows with
        # significant pixels.
        top_side = -1 # The uppermost row with a significant spot of black
        offset = 0 # vptr index to the first/next pixel row
        for r in range(nrows) :
            pa, pb = 255, 255 # virtual white outside border
            for c in range(ncols) :
                pc = colortab[ ord(vptr[offset + c]) ]
                if (pa + pb + pc) < 32 : # black or dark gray triplet
                    top_side = r # that's the row,
                    break # ..so stop scanning
                pa, pb = pb, pc
            if top_side >= 0 : # we hit
                break # ..so don't scan down any further
            offset += stride # continue to next row
        # top_side indexes the first row with a significant blot
        if top_side == -1 : # never found one: an all-white page. bug out.
            return
        bottom_side = nrows # The lowest row with a significant blot
        offset = stride * nrows # vptr index to last/next row of pixels
        for r in range(nrows,top_side,-1) :
            offset -= stride
            pa, pb = 255, 255 # virtual white outside border
            for c in range(ncols) :
                pc = colortab[ ord(vptr[offset + c]) ]
                if (pa + pb + pc) < 32 : # black or dark gray triplet
                    bottom_side = r
                    break
                pa, pb = pb, pc
            if bottom_side < nrows : # we hit
                break
        # bottom_side is the lowest row with significant pixels. It must be
        # < nrows, there is at least one row (top_side) with a dot in it.
        # However if the page is mostly white, don't zoom to that extent.
        if bottom_side < (top_side+100) :
            return # seems to be a mostly-white page, give up
        # The text area runs from scanline top_side to bottom_side.
        text_height = bottom_side - top_side + 1
        port_height = self.scarea.viewport().height()
        self.zoomFactor = max( self.minZoom, min( self.maxZoom, port_height / text_height ) )
        self.zlider.setValue(int(100*self.zoomFactor)) # this signals newZoomFactor
        # Set the scrollbar to show the page from its top margin.
        self.scarea.verticalScrollBar().setValue(int( top_side * self.zoomFactor) )

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
        # assume we will not handle this key and clear its accepted flag
        event.ignore()
        # If we are initialized and have displayed some page, look at the key
        if (self.ready) and (IMC.currentPageIndex is not None):
            kkey = int( int(event.modifiers()) & IMC.keypadDeModifier) | int(event.key())
            if kkey in IMC.zoomKeys :
                # ctl/cmd + or -, do the zoom
                event.accept()
                fac = (0.8) if (kkey == IMC.ctl_minus) else (1.25)
                fac *= self.zoomFactor # target zoom factor
                if (fac >= self.minZoom) and (fac <= self.maxZoom): # keep in bounds
                    self.zoomFactor = fac
                    self.zlider.setValue(int(100*fac))
                    self.showPage()
            elif (event.key() == Qt.Key_PageUp) or (event.key() == Qt.Key_PageDown) :
                event.accept() # real pgUp or pgDn, we do it
                fac = 1 if (event.key() == Qt.Key_PageDown) else -1
                fac += self.lastIndex
                if (fac >= 0) and (fac < len(IMC.pageTable)) : 
                    # not off the end of the book, so,
                    self.lastIndex = fac
                    IMC.currentPageIndex = fac
                    self.showPage()
        if not event.isAccepted() : # we don't do those, pass them on
            super(pngDisplay, self).keyPressEvent(event)

if __name__ == "__main__":
    pass
    #import sys
    #from PyQt4.QtCore import (Qt,QSettings,QFileInfo)
    #from PyQt4.QtGui import (QApplication,QFileDialog)
    #import pqIMC
    #IMC = pqIMC.tricorder() # set up a fake IMC for unit test
    #IMC.settings = QSettings()
    #app = QApplication(sys.argv) # create an app
    #widj = pngDisplay()
    #widj.pngPath = QFileDialog.getExistingDirectory(widj,"Pick a Folder of Pngs",".")
    #widj.showPage()
    #widj.show()
    #app.exec_()