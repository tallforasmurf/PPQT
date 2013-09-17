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

'''
Defines a class for a Properties dialog, invoked from the
File >Properties menu.

The dialog extracts document info from the IMC and displays it
with a choice of Apply and Cancel buttons. On Apply the dialog
replaces the values of its displayed field in the IMC, with some
validity checking.

The IMC namespace is passed in as an instantiation argument,
instead of the usual hack of inserting it into the file namespace.
'''
from PyQt4.QtCore import ( Qt, QFileInfo, QString, SIGNAL )
from PyQt4.QtGui import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout
    )



class Properties(QDialog) :
    def __init__(self, IMC, parent=None) :
        super(QDialog, self).__init__(parent)
        self.IMC = IMC
        self.setModal(True)
        self.setSizeGripEnabled(True)
        bookinfo = QFileInfo(IMC.bookPath)
        self.setWindowTitle(u"Properties of {0}".format(bookinfo.fileName()))
        # Our layout is a vertical stack of widgets and hboxes
        vlayout = QVBoxLayout()
        # Add the path information field
        fplb = QLabel(u"Path: {0}".format(unicode(bookinfo.path())))
        fplb.setFrameStyle(QFrame.Sunken)
        fplb.setToolTip(QString(u'Full path to document'))
        vlayout.addWidget(fplb)
        # Add the write-encoding choice, setting the buttons to reflect
        # the current value. We build this up from the inside out.
        # Two radio buttons. As they will be exclusive we need connect
        # the toggled() signal from only one of them.
        self.saveEncoding = self.IMC.bookSaveEncoding
        rb_enc_utf = QRadioButton(QString(u'UTF-8'))
        rb_enc_utf.setChecked(self.saveEncoding==rb_enc_utf.text())
        rb_enc_utf.toggled.connect(self.encodingChange)
        rb_enc_ltn = QRadioButton(QString(u'Latin-1'))
        rb_enc_ltn.setChecked(self.saveEncoding!=rb_enc_utf.text())
        # put the buttons in a layout because groupbox doesn't act as one
        hb_enc_btns = QHBoxLayout()
        hb_enc_btns.addWidget(rb_enc_utf)
        hb_enc_btns.addWidget(rb_enc_ltn)
        # add to groupbox to get exclusivity on the buttons
        gb_enc = QGroupBox()
        gb_enc.setLayout(hb_enc_btns)
        # put in horizontal box with descriptive label, and add to the dialog
        hb_enc = QHBoxLayout()
        lb_enc = QLabel(u'Write Encoding')
        lb_enc.setToolTip('Character encoding when writing the document')
        hb_enc.addWidget(lb_enc)
        hb_enc.addWidget(gb_enc)
        vlayout.addLayout(hb_enc)

        # Next get a QStringList of available dicts from pqSpell
        # and create a combobox with that content.
        dictlist = IMC.spellCheck.dictList()
        dictlist.sort()
        self.maintag = self.IMC.bookMainDict
        if self.maintag.isEmpty() :
            self.maintag = self.IMC.spellCheck.mainTag
        current = dictlist.indexOf(QString(self.maintag)) # index of current dict or -1
        self.cb_dic = QComboBox()
        self.cb_dic.addItems(dictlist)
        if current >= 0 : self.cb_dic.setCurrentIndex(current)
        self.cb_dic.activated.connect(self.dictChange)

        hb_dic = QHBoxLayout()
        hb_dic.addWidget(QLabel(u'Main Dictionary'))
        hb_dic.addStretch()
        hb_dic.addWidget(self.cb_dic)
        vlayout.addLayout(hb_dic)

        # create the [ apply cancel ] buttons, but apply == accept
        apply_button = QPushButton("Apply")
        cancel_button = QPushButton("Cancel")
        cancel_button.setDefault(True)
        bbox = QDialogButtonBox()
        bbox.addButton(cancel_button, QDialogButtonBox.RejectRole )
        bbox.addButton(apply_button, QDialogButtonBox.AcceptRole)
        bbox.accepted.connect(self.applyButtonHit )
        bbox.rejected.connect(self.cancelButtonHit )
        vlayout.addWidget(bbox)

        self.setLayout(vlayout)

    # Slot entered when the UTF encoding button toggles state
    def encodingChange(self, checked):
        if checked :
            # UTF button is checked
            self.saveEncoding = QString(u'UTF-8')
        else :
            self.saveEncoding = QString(u'ISO-8859-1')
    def dictChange(self):
        self.maintag = self.cb_dic.currentText()
    # Slot entered on Apply button: Store local items in the IMC, then quit
    def applyButtonHit(self) :
        self.IMC.bookSaveEncoding = self.saveEncoding
        if self.IMC.bookMainDict != self.maintag :
            self.IMC.bookMainDict = self.maintag
            self.IMC.needSpellCheck = True
            self.IMC.spellCheck.setMainDict(self.maintag)
        self.IMC.needMetadataSave |= self.IMC.propertyChanged
        self.accept()
    # Slot entered from Cancel button: just quit
    def cancelButtonHit(self) :
        self.reject()

if __name__ == "__main__":
    import sys, os
    from PyQt4.QtCore import (QSettings)
    from PyQt4.QtGui import (QApplication,QFileDialog)
    app = QApplication(sys.argv) # create an app
    from PyQt4.QtGui import QWidget
    import pqIMC
    IMC = pqIMC.tricorder()
    IMC.settings = QSettings()
    IMC.bookPath = QFileDialog.getOpenFileName(
        IMC.mainWindow,u"Pick a book",os.path.dirname(__file__))
    IMC.bookSaveEncoding = QString('UTF-8')
    IMC.bookMainDict = QString()
    base = os.path.dirname(__file__)
    IMC.dictPath = os.path.join(base,u"dict")
    import pqSpell
    pqSpell.IMC = IMC
    IMC.spellCheck = pqSpell.makeSpellCheck()
    IMC.mainWindow = QWidget()
    pd = Properties(IMC,IMC.mainWindow)
    pd.exec_()

