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
and enclosed in a QScrollArea. Below it, a small label to display the current
page number and zoom factor initialized with "No page". Below that, a
spinBox for the current zoom factor and buttons "to Width" and "to Height"
for zoom factor changes. Zooming is done by changing the size hint of the
pixmap; it scales, and the parent scrollarea scrolls.

Reimplements keyPressEvent() to respond to certain keys when the focus
is in this widget:
   ctl-plus/minus zoom the image when an image exists.
   Page Up/Down cause display of a different png.

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
        #dbg
        #self.profiler = cProfile.Profile()
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
        # Clear the page name, used by pqNotes
        IMC.currentPageNumber = None # will be name of last page e.g. "002"
        # Clear the page filename, used in our caption label
        self.lastPage = QString() # last file name e.g. "002.png"
        # Clear the path to the pngs folder, used to fetch image files
        self.pngPath = QString()
        # Clear the index of the last-shown page in the page table
        # -1 means no page is being displayed.
        self.lastIndex = -1
        # Clear the index of the next page to display, normally same as last
        self.nextIndex = -1
        # Set not-ready to indicate no pngs directory available.
        self.ready = False
        # Clear out & release storage of our QImage and QPixmaps
        self.pixmap = QPixmap() # null pixmap
        self.image = QImage()
        self.noImage() # show gray image

    # Display a blank gray frame and "No Image" below.
    # Called from clear() above and from showPage when no valid image.
    def noImage(self) :
        self.imLabel.setPixmap(self.defaultPM)
        self.txLabel.setText(u"No image")
        self.lastIndex = -1 # didn't see a prior page
        self.nextIndex = -1

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
    # At this point the gray image is displayed and previously would remain displayed
    # until the user moved the cursor in some way, generating cursorPositionChanged.
    # That's a minor annoyance, to avoid it we will fake that signal now.
    def newFile(self, bookPath):
        if not bookPath.isNull(): # this was successful File>Open
            finf = QFileInfo(bookPath)
            self.pngPath = finf.absolutePath().append(u"/pngs/")
            finf = QFileInfo(self.pngPath)
            if finf.exists() and finf.isDir(): # looking good
                self.ready = True
                self.newPosition()
            else:
                # We could inform the user we couldn't find a pngs folder,
                # but you know -- the user is probably already aware of that.
                self.clear() # just put up the gray default image
        else: # It was a File>New
            self.clear()

    # This function is the slot that is connected to the editor's
    # cursorPositionChanged signal. Its input is cursor position and
    # the page table. Its output is to set self.nextIndex to the
    # desired next image table row, and to call showPage.
    def newPosition(self):
        if not self.ready :
                # No file loaded or no pngs folder found.
            self.nextIndex = -1
        elif 0 == len(IMC.pageTable):
                # No book open, or no pngs directory with it.
            # This could happen on the first call at startup, the first
            # call after a document has been loaded but before the metadata
            # has been built. No image to show.
            self.nextIndex = -1
        else :
            # We have a book and some pngs. Find the position of the higher end
            # of the current selection.
            pos = IMC.editWidget.textCursor().selectionEnd()
            # if that position is above the first page, which can happen if the
            # user has entered some text above the first psep line, show a
            # blank image.
            if pos < IMC.pageTable[0][0].position() :
                self.nextIndex = -1
            else :
                # here we go with bisect_right to find the lowest page table entry
                # <= to our present position. We know the table is not empty, but
                # after pseps are removed, there can be multiple pages with the
                # same starting offset. In a 500pp book, this might iterate 8 times.
                hi = len(IMC.pageTable)
                lo = 0
                while lo < hi:
                    mid = (lo + hi)//2
                    if pos < IMC.pageTable[mid][0].position(): hi = mid
                    else: lo = mid+1
                # the page at lo-1 is the greatest <= pos. Set that as the page to show.
                lo -= 1
                self.nextIndex = lo
            # One way or another we have set self.nextIndex to the desired
            # page, so display it.
        self.showPage()

    # Display the page indexed by self.nextIndex. This is called when the cursor
    # moves to a new page (newPosition, above), or when the PageUp/Dn keys are used,
    # (keyPressEvent, below) or when the zoom factor changes in any of several ways.
    def showPage(self):
        # If self.lastIndex is different from self.nextIndex, the page has
        # changed, and we need to load a new image.
        if self.lastIndex != self.nextIndex :
            self.lastIndex = self.nextIndex # don't come here again until it changes.
            if self.lastIndex > -1 :
                # Form the image filename as a Qstring, e.g. "025" and save that for
                # use by pqNotes:
                IMC.currentPageNumber = QString(IMC.pageTable[self.lastIndex][1])
                #dbg = unicode(IMC.currentPageNumber)
                # Form the complete filename by appending ".png" and save as
                # self.lastPage for use in forming our caption label.
                self.lastPage = QString(IMC.currentPageNumber).append(QString(u".png"))
                #dbg = unicode(self.lastPage)
                # Form the full path to the image. Try to load it as a QImage.
                pngName = QString(self.pngPath).append(self.lastPage)
                #dbg = unicode(pngName)
                self.image = QImage(pngName,'PNG')
                # If that successfully loaded an image, make sure it is one byte/pixel.
                if not self.image.isNull() \
                   and self.image.format() != QImage.Format_Indexed8 :
                    # It might be Format_Mono (1 bit/pixel) or even Format_RGB32.
                    self.image = self.image.convertToFormat(QImage.Format_Indexed8,Qt.ColorOnly)
                # Convert the image to a pixmap. If it's null, so is the pixmap.
                self.pixmap = QPixmap.fromImage(self.image,Qt.ColorOnly)
            else :
                IMC.currentPageNumber = QString(u"n.a.")
                self.lastPage = QString()
                self.image = QImage()
                self.pixmap = QPixmap()
        if not self.pixmap.isNull():
            # We successfully found and loaded an image and converted it to pixmap.
            # Load it in our label for display, set the zoom factor, and the caption.
            self.imLabel.setPixmap(self.pixmap)
            self.imLabel.resize( self.zoomFactor * self.pixmap.size() )
            self.txLabel.setText(
                u"{0} - {1}%".format(self.lastPage, int(100*self.zoomFactor))
            )
        else: # no file was loaded. It's ok if pages are missing
            self.noImage() # display the gray image.

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
        #self.profiler.enable() #dbg
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
        # Most pages start with many lines of white pixels so in hopes of
        # establishing the outer edge early, we start at the middle, go to
        # the end, then do the top half.
        left_side = int(ncols/2) # leftmost dark spot seen so far
        # scan from the middle down
        for r in xrange(int(nrows/2)*stride, (nrows-1)*stride, stride) :
            pa, pb = 255, 255 # virtual white outside border
            for c in xrange(left_side):
                pc = colortab[ ord(vptr[c + r]) ]
                if (pa + pb + pc) < 32 : # black or dark gray pair
                    left_side = c # new, further-left, left margin
                    break # no need to look further on this line
                pa = pb
                pb = pc
        # scan from the top to the middle, hopefully left_side is small now
        for r in xrange(0, int(nrows/2)*stride, stride) :
            pa, pb = 255, 255 # virtual white outside border
            for c in xrange(left_side):
                pc = colortab[ ord(vptr[c + r]) ]
                if (pa + pb + pc) < 32 : # black or dark gray pair
                    left_side = c # new, further-left, left margin
                    break # no need to look further on this line
                pa = pb
                pb = pc
        # Now do the same for the right margin.
        right_side = int(ncols/2) # rightmost dark spot seen so far
        for r in xrange(int(nrows/2)*stride, (nrows-1)*stride, stride) :
            pa, pb = 255, 255 # virtual white outside border
            for c in xrange(ncols-1,right_side,-1) :
                pc = colortab[ ord(vptr[c + r]) ]
                if (pa + pb + pc) < 32 : # black or dark gray pair
                    right_side = c # new, further-right, right margin
                    break
                pa = pb
                pb = pc
        for r in xrange(0, int(nrows/2)*stride, stride)  :
            pa, pb = 255, 255 # virtual white outside border
            for c in xrange(ncols-1,right_side,-1) :
                pc = colortab[ ord(vptr[c + r]) ]
                if (pa + pb + pc) < 32 : # black or dark gray pair
                    right_side = c # new, further-right, right margin
                    break
                pa = pb
                pb = pc
        # The area with color runs from left_side to right_side. How does
        # that compare to the size of our viewport? Scale to that and redraw.
        #print('ls {0} rs {1} vp {2}'.format(left_side,right_side,self.scarea.viewport().width()))
        text_size = right_side - left_side + 2
        port_width = self.scarea.viewport().width()
        self.zoomFactor = max( self.minZoom, min( self.maxZoom, port_width / text_size ) )
        self.zlider.setValue(int(100*self.zoomFactor)) # this signals newZoomFactor
        # Set the scrollbar to show the page from its left margin.
        self.scarea.horizontalScrollBar().setValue(int( left_side * self.zoomFactor) )
        #self.profiler.disable() #dbg
        #pstats.Stats(self.profiler).print_stats() # dbg


    def zoomToHeight(self):
        if (not self.ready) or (self.image.isNull()) :
            return # nothing to do here
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
        if self.ready:
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
                    self.nextIndex = fac
                    self.showPage()
        if not event.isAccepted() : # we don't do those, pass them on
            super(pngDisplay, self).keyPressEvent(event)

if __name__ == "__main__":
    pass
    import sys
    from PyQt4.QtCore import (Qt,QSettings,QFileInfo,QDir,QStringList)
    from PyQt4.QtGui import (QApplication,QFileDialog,QPlainTextEdit,QTextCursor)
    app = QApplication(sys.argv) # create an app
    import pqIMC
    IMC = pqIMC.tricorder() # set up a fake IMC for unit test
    IMC.settings = QSettings()
    IMC.editWidget = QPlainTextEdit()
    IMC.pageTable=[]
    widj = pngDisplay()
    widj.pngPath = QFileDialog.getExistingDirectory(widj,"Pick a Folder of Pngs",".")
    widj.pngPath.append(u'/')
    #dbg = unicode(widj.pngPath)
    png_dir = QDir(widj.pngPath)
    png_dir.setFilter(QDir.Files | QDir.NoSymLinks)
    png_dir.setSorting(QDir.Name)
    png_dir.setNameFilters(QStringList(QString(u'*.png')))
    for finf in png_dir.entryInfoList():
        fname = finf.baseName()
        #print('{0} : {1}'.format(unicode(fname),IMC.editWidget.textCursor().position()))
        IMC.pageTable.append( [IMC.editWidget.textCursor(),
                          fname,
                          QString(), IMC.FolioRuleAdd1, IMC.FolioFormatArabic, 1] )
        IMC.editWidget.textCursor().insertText(fname)
    widj.lastIndex = -1
    widj.nextIndex = 0
    widj.ready = True
    widj.showPage()
    widj.show()
    #widj.zoomToWidth()
    #pstats.Stats(pr).print_stats()
    app.exec_()
    pass