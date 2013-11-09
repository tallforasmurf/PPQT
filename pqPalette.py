from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *
''' TO DO
ppqt: import and add IMC
pqMain: tabset movable
pqMain: add Palettes submenu to Edit menu
populate from home/extras/*.palettes
document in help
'''
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

import csv
import unicodedata
from PyQt4.QtGui import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QKeyEvent,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout
)
from PyQt4.QtCore import (
    Qt,
    QPoint,
    QRegExp,
    QSize,
    QString,
    QVariant,
    SIGNAL
)

MOD_SHIFT = int(Qt.ShiftModifier) # shift is down
MOD_CTL = int(Qt.ControlModifier) # ctl/cmd is down
MOD_ALT = int(Qt.AltModifier) # alt/opt is down
MOD_STATES = (0,MOD_SHIFT,MOD_CTL,MOD_ALT,
              MOD_SHIFT | MOD_CTL, MOD_SHIFT | MOD_ALT, MOD_CTL | MOD_ALT,
              MOD_SHIFT | MOD_CTL | MOD_ALT)
MOD_MASK = MOD_SHIFT | MOD_CTL | MOD_ALT

# Global size policy used by all key items.
SPOLICY = QSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
# CSS style sheet for all buttons, applied in KeyPalette.
KEY_STYLE = QString('''KeyButton { background-color: gray; color: white; font-size:24px; }
            KeyButton:hover { background-color:silver; } ''')

'''
Class of the "keyboard" buttons. Each is a QLabel that is styled using a CSS
style-sheet (KEY_STYLE, above). The "values" parameter is a dict of Python
strings representing the key's values for each possible modifier state 0..7
(MOD_STATES, above). A value if a python string, or None if nothing was
defined for this key and that mode. The button sets up parallel dicts of
display QStrings and tool-tip QStrings.

The "target" parameter is a reference to the QLineEdit (MagicLineEdit below)
where to insert a value when a key is clicked. (Insertion of the value when
an actual keyboard key is pressed, is handled in MagicLineEdit.)
'''
class KeyButton(QLabel):
    global GLYPH, IDLEPM, HOVERPM
    def __init__(self, values, target, parent=None):
        super(KeyButton, self).__init__(parent)
        # Save the target QLineEdit
        self.target = target
        # save the dictionary of values for each modifier state, and set up
        # parallel dicts of keytop display QStrings and tooltip QStrings.
        # Where a value is None, convert it to an empty QString.
        self.values = values
        self.glyphs = {}
        self.tooltips = {}
        for mode in self.values :
            py_string = self.values[mode]
            if py_string is not None:
                self.glyphs[mode] = QString(py_string)
                tip = QString()
                # A value can have multiple chars, put all in tooltip
                for uc in py_string :
                    if not tip.isEmpty(): tip.append(u'+')
                    tip.append(unicodedata.name(uc))
                self.tooltips[mode] = tip
            else : # value is None, use empty strings
                self.glyphs[mode] = QString()
                self.tooltips[mode] = QString()
        # set constant properties
        self.setAlignment(Qt.AlignCenter) # both horizontal and vertical
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setScaledContents(True)
        # Make our look square, at least 20px, but able to grow
        self.setMinimumSize(QSize(20,20))
        self.setSizePolicy(SPOLICY)
        self.setFrameStyle(QFrame.Panel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(3)
        # initialize with a glyph
        self.shift(0)
    # Slot entered on a signal when the keyboard shift state may have changed.
    # Display the glyph and tooltip for this state.
    def shift(self, mod_state):
        self.setText(self.glyphs[mod_state])
        self.setToolTip(self.tooltips[mod_state])
        self.mod = mod_state
    # Method called to retrieve the value of this button in the current state.
    # This is used by the QLineEdit while handling keystrokes, it gets the
    # value and does its own inserting.
    def fetch(self):
        return self.values[self.mod]
    # Method called when a mouse button is released while the mouse is
    # over this widget. We do not track mousePress events, just release events.
    # That allows the user to press the mouse down and if she has a
    # second thought, to move the mouse away before releasing it.
    def mouseReleaseEvent(self, event):
        v = self.values[self.mod]
        if v is not None:
            self.target.insert(QString(v))
        event.accept()

'''
Class of the KeyPalette, a modeless dialog. Base class is QDialog with no
parent, hence, a modeless dialog. Input to the initializer:

 * a Python file object presumed to be a "palette" configuration file
   defining the contents of the dialog -- e.g. extras/Greek.palette

 * a QString with the name of the dialog (ususally the filename of the
   defining file) e.g. "Greek"

We retrieve our size and position geometry from the app settings using the
dialog name string. On closeEvent we save them again.

The window title is "<name> Text Entry". The main feature is an array of
KeyButton objects (see above) laid out as four staggered rows of 10, 10, 9
and 7, roughly similar to a real keyboard. The positions are indexed by the
keys of a QWERTY keyboard: 1-9,0 in the top row, QWERTYUIOP in the second,
ASDFGHJKL in the third, ZXCVBNM in the fourth. The contents are set from the
palette file. Under the "keyboard" is a row of controls:

  [Insert] [    QlineEdit      ] [Copy] [Clear] (x) Unicode (x) Html

The Clear button empties the lineEdit; the Copy button copies it to the
system clipboard; the Insert button inserts its contents in the edit
document at the cursor. The unicode and html radio set tell whether to
insert unicode characters or html entities (&dddd;)

The contents are normalized (NFKD) before insertion or copy, thus extra
combining characters are merged into single characters when possible.

No close button should be needed as a modeless dialog will have
a "dismiss" control from the host platform. On closeEvent we save our
position and size in the settings.

The CSV file is a UTF-8 file in which each data line has three items:
keyletter, mode, and value

* keyletter is a single character [A-Z0-9] (case ignored) to
  specify the key object

* mode signifies the shift status and is a string of one or more letters
  (again, case ignored):
  - L for lowercase
  - U for up-shift
  - C for Control (or command)
  - A for Alt (or Option)

* value is a string of one or more Unicode characters:
  - a single character is a value for the key in that mode
  - 2 to 5 decimal digits is taken as an Unicode decimal value
  - 2 to 5 characters is taken as a composition, for example
    a Greek Alpha and a Greek Dasia.
  - 6 or more characters is taken as a formal Unicode character
    name "GREEK CAPITAL LETTER ALPHA WITH DASIA" (case-independent)

(See extras/Greek.palette for an example and more documentation.)
Any line that does not match these formats is ignored. This allows for
ad-lib commentary, but few errors are reported either.
'''

# Useful constants for constructing key arrays
KEYS_ALL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
KEYS_ROW0 = '1234567890'
KEYS_ROW1 = 'QWERTYUIOP'
KEYS_ROW2 = ' ASDFGHJKL'
KEYS_ROW3 = ' ZXCVBNM  '

class KeyPalette(QDialog):

    def __init__(self, name_string, definition_file):
        global MOD_STATES, MOD_SHIFT, MOD_CTL, MOD_ALT
        global KEYS_ALL, KEYS_ROW0, KEYS_ROW1, KEYS_ROW2, KEYS_ROW3, KEY_STYLE

        super(KeyPalette, self).__init__(parent=None)

        # Recall (or establish) the dialog geometry from global settings
        self.name = name_string
        # DO WE WANT THE FOLLOWING CONSOLE OUTPUT?
        print('Loading palette "'+unicode(self.name)+'"')

        self.windowTitle = QString(self.name).append(u' Text Entry')
        self.size_key = QString(self.name).append("/size")
        self.pos_key = QString(self.name).append("/position")
        self.resize(IMC.settings.value(self.size_key,
                        QVariant(QSize(800,300))).toSize() )
        self.move(IMC.settings.value(self.pos_key,
                        QPoint(100, 100)).toPoint() )
        #
        # Here we keep track of the keyboard modifier state.
        self.mod_state = 0

        # Create the magic LineEdit which we have to pass to each key.
        # See its class definition below.
        self.the_magic = MagicLineEdit(parent=self)
        # Direct that when keyboard focus enters this dialog in general,
        # that the magic lineEdit gets the focus. All keystroke events
        # are routed through its keyEvent handler.
        self.setFocusProxy(self.the_magic)

        # Build the key objects, saved in a dict keyed by the key letter.
        #
        # Make a dict of 8 values indexed by mod status, initialized to Nones.
        # One of these will be passed to each key object after we load them
        # from the palette file.
        value_dict = dict( (m, None) for m in MOD_STATES )

        # Make one of those for each key object, indexed by key letter
        key_values = dict( (char, value_dict.copy()) for char in KEYS_ALL )

        # Ready to read the CSV file. The csv.reader returns a list of
        # bytestrings. (Python 2.7 - might change in 3!) We need to convert
        # bytes to UTF-8. For some fields, force uppercase. For some, strip
        # possible whitespace and quotes.
        key_rdr = csv.reader(definition_file)
        for row in key_rdr :
            if len(row) != 3 :
                continue # not a valid row, ignore it
            key = row[0].decode('UTF-8')
            if len(key) != 1 :
                continue # not a single-letter key, skip the row
            if key not in KEYS_ALL :
                continue # not a key letter, skip the row
            # Convert second item into 0-7. Bring to Unicode, strip
            # any blanks or quotes (so, "LC" is ok), make uppercase.
            mod_code = row[1].decode('UTF-8').strip(' "').upper()
            # This will just ignore a bad mode-letter. If they are all
            # bad, it defaults to mode 0. Also treats UL as U.
            mod = 0
            if 'U' in mod_code : mod |= MOD_SHIFT
            if 'C' in mod_code : mod |= MOD_CTL
            if 'A' in mod_code : mod |= MOD_ALT
            # Isolate the character value as Unicode, take off any
            # spaces or quotes.
            char_value = row[2].decode('UTF-8').strip(' "')
            char = None
            if char_value.isdigit() :
                # Value is all-decimal-digits, convert to a Unicode character
                try:
                    char = unichr(int(char_value))
                except ValueError:
                    # invalid unicode number, diagnose & leave char as None
                    print('bad unicode number: '+row.__repr__() )
            elif len(char_value) < 6 :
                # take 1-5 non-numeric characters as-is for the key value,
                # assuming one character perhaps with combining diacriticals
                char = char_value
            else :
                # 6 or more characters, assume it is a name like GREEK RHO
                try:
                    char = unicodedata.lookup(char_value)
                except KeyError:
                    # Unknown name, diagnose and leave char as None
                    print('bad unicode name: '+row.__repr__() )
            if char is None :
                continue # could not decode the value, toss the line
            # Stow the value in the key's dict under the mod value
            key_values[key][mod] = char
        # Ready to create the 36 key objects. Connect the .shift slot of
        # each to the ModStateChange signal out of the magic lineedit.
        self.key_objects = {}
        for key in KEYS_ALL:
            key_object = KeyButton(key_values[key], self.the_magic)
            self.key_objects[key] = key_object
            self.connect(self.the_magic, SIGNAL("ModStateChange"), key_object.shift)
        # Style the key-objects. It doesn't work to have each KeyButton set
        # its own style sheet (why??) but this does.
        self.setStyleSheet(KEY_STYLE)

        # Ready to lay the dialog out. It is a stack of things in a VBox.
        # The top 4 things are the rows of the keys.
        layout = QVBoxLayout()
        layout.addLayout(self.keyRow(KEYS_ROW0,0,30),stretch=1)
        layout.addLayout(self.keyRow(KEYS_ROW1,30,0),stretch=1)
        layout.addLayout(self.keyRow(KEYS_ROW2,0,30),stretch=1)
        layout.addLayout(self.keyRow(KEYS_ROW3,0,0),stretch=1)
        # Make the strip of controls for the bottom:
        # Three action buttons:
        btn_insert = QPushButton('Insert')
        btn_clear = QPushButton('Clear')
        btn_copy = QPushButton('Copy')
        # A two-button radio set, [x]Unicode [ ]HTML
        radio_frame = QFrame()
        radio_frame.setFrameStyle(QFrame.StyledPanel)
        radio_frame.setFrameShadow(QFrame.Sunken)
        radio_frame.setLineWidth(3)
        btn_unicode = QRadioButton('Unicode')
        btn_unicode.setChecked(True) #start with unicode selected
        btn_html = QRadioButton('HTML')
        radio_hb = QHBoxLayout()
        radio_hb.addWidget(btn_unicode)
        radio_hb.addWidget(btn_html)
        radio_frame.setLayout(radio_hb)
        # Lay out the bottom section
        hbox = QHBoxLayout()
        hbox.addWidget(btn_insert,stretch=0)
        hbox.addWidget(self.the_magic,stretch=1)
        hbox.addWidget(btn_copy,stretch=0)
        hbox.addWidget(btn_clear,stretch=0)
        hbox.addWidget(radio_frame,stretch=0)
        layout.addLayout(hbox)
        self.setLayout(layout)
        # Save a reference to the HTML radio button so we can query it
        # when doing Insert.
        self.html_button = btn_html
        # Set up signals from the buttons to our methods below
        self.connect(btn_insert, SIGNAL("clicked()"), self.doInsert)
        self.connect(btn_copy, SIGNAL("clicked()"), self.doCopy)
        self.connect(btn_clear, SIGNAL("clicked()"), self.the_magic.clear)

    # Convenience function to put a row of KeyButtons into a horizontal grid,
    # and that into an Hbox with optional spacing on left or right. Where
    # "keys" has a space, insert an empty QLabel.
    def keyRow(self,keys,lspace,rspace):
        global SPOLICY
        grid = QGridLayout()
        for j in range(len(keys)) : # keys in numeric order left to right
            grid.setColumnStretch(j,0) # all columns equal stretch
            key = keys[j]
            if key != ' ' :
                grid.addWidget(self.key_objects[key], 0, j)
            else :
                ql = QLabel(' ')
                ql.setSizePolicy(SPOLICY)
                ql.setMinimumSize(QSize(20,20))
                grid.addWidget(ql,0,j)
        hbox = QHBoxLayout()
        if lspace : # if stagger-right, stick in space on left
            hbox.addSpacing(lspace)
        hbox.addLayout(grid) # put the keys in the middle
        if rspace : # if stagger-left, stick in space on the right
            hbox.addSpacing(rspace)
        return hbox

    # Slot to receive the clicked of the Copy button. Although QLineEdit
    # does have a copy method, it only copies the selected text, not the
    # whole contents. So the user can drag to select part and key ctl-C
    # and get a partial copy but if they click the Copy button we copy it all.
    # Note we do NOT normalize before copy. The user may want to copy the
    # un-normalized text, may even have de-normalized (back-tab).
    def doCopy(self):
        QApplication.clipboard().setText(self.the_magic.text())

    # Slot to receive the clicked of the Insert button:
    # Normalize (NFC, combine) the string, then insert it in the edit document.
    # This does not clear the text. The user has clicked the Insert button
    # and can easily click Clear if she wants to, but might well want to keep
    # the present text and modify it for insertion again, or insert it again
    # but as entities. However see the Enter key handling in MagicLineEdit.
    def doInsert(self):
        self.the_magic.normNFC()
        if self.html_button.isChecked() :
            # user wants Entities, oh yawn.
            py_string = unicode(self.the_magic.text())
            e_string = ''
            pattern = '&{0};'
            for uc in py_string :
                if uc in IMC.namedEntityDict :
                    e_string += pattern.format(IMC.namedEntityDict[uc])
                else :
                    e_string += pattern.format(ord(uc))
            IMC.editWidget.insertPlainText(QString(e_string))
        else:
            IMC.editWidget.insertPlainText(self.the_magic.text())

    # Slot to handle the close event: the user has dismissed this dialog.
    # Save our position and size so when we are recalled we come up the same.
    def closeEvent(self,event):
        IMC.settings.setValue(self.size_key,self.size())
        IMC.settings.setValue(self.pos_key, self.pos())

'''
Class of the QLineEdit in the KeyPalette dialog. It is a standard QLineEdit
except that it receives and analyzes all keystroke events while focus is on
the containing dialog. On focusIn event, the dialog notes the state of key
modifiers, and while it has the focus it sees all changes in the modifiers.
On any change it signals the 36 KeyButtons of the change. They change their
displays to match.

Key Press events are processed as follows.

If the key is [A-Z0-9], get the value of that key object, and if it is not
empty, insert it. Then, if the mod state is not Ctl, .accept the key (it will
not go up the chain to parent). If it is Ctl, .ignore it, and it will go up.
Thus you can use ^C, ^V, ^Z for their customary actions, just put no value on
those modes of C, V, Z. You can still use the other seven modes of those keys
for input.

If the key is Tab, Normalize (NFKC) the string (compact it), and also convert
regex lowercase-sigma\b to terminal-sigma. Then .accept the event.

If the key is Shift-Tab (Back-tab), Normalize (NFD) the string
(expand it) and .accept this event.

If it is the Return key, invoke the dialog's Insert method (normalize and
insert into the editor) and then its Clear method, and .accept the event.
(Clicking Insert only inserts; Return/Enter both inserts and clears.)

If it is ctl-plus or ctl-minus, change our font size and .accept the key.

All other keystrokes (e.g. punctuation) we .ignore the event. Thus any other
key with ascii value (comma, paren, etc) is entered in the lineEdit as itself

'''
# For quick lookup, nothing beats a Python hash table.
KEYSAZ09 = set([
    Qt.Key_A, Qt.Key_B, Qt.Key_C, Qt.Key_D, Qt.Key_E, Qt.Key_F,
    Qt.Key_G, Qt.Key_H, Qt.Key_I, Qt.Key_J, Qt.Key_K, Qt.Key_L,
    Qt.Key_M, Qt.Key_N, Qt.Key_O, Qt.Key_P, Qt.Key_Q, Qt.Key_R,
    Qt.Key_S, Qt.Key_T, Qt.Key_U, Qt.Key_V, Qt.Key_W, Qt.Key_X,
    Qt.Key_Y, Qt.Key_Z, Qt.Key_0, Qt.Key_1, Qt.Key_2, Qt.Key_3,
    Qt.Key_4, Qt.Key_5, Qt.Key_6, Qt.Key_7, Qt.Key_8, Qt.Key_9
    ])
KEYTABRET = set([Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Return, Qt.Key_Enter])
KEYZOOM = set([Qt.Key_Minus, Qt.Key_Plus, Qt.Key_Equal])

class MagicLineEdit(QLineEdit):

    def __init__(self, parent ):
        super(MagicLineEdit, self).__init__(parent)
        # Save a reference to our parent, KeyPalette above, so we can
        # access its key_objects, mod_state, and doInsert.
        self.mamma = parent
        # Set some space above the text so accents show better
        self.setTextMargins(0,8,0,0)
        # Initialize the text font to 16, bigger than default
        f = self.font() # get our font,
        f.setPointSize(16) # start at 16pts
        self.setFont(f) # put the font back
        # The following is a kludge. The lineEdit does not show a cursor
        # line until a selection has been made. Presumably a bug? Recheck
        # if Qt is updated. But now a hairline insertion-cursor does not
        # appear until a selection is made. This puts one space in and selects
        # it, so when the dialog first appears there is one selected blank.
        # The first character typed replaces it, but now a cursor appears.
        self.setText(QString(' '))
        self.home(True)



    # Test a new modifier state and if it differs, emit the signal to
    # tell all 36 key buttons to change their looks. mod_state is the
    # modifiers word from either a key event or the application.
    def testMod(self, mod_state) :
        global MOD_MASK
        mods = int(mod_state) & MOD_MASK
        if mods != self.mamma.mod_state :
            self.mamma.mod_state = mods
            self.emit(SIGNAL("ModStateChange"),mods)

    # Normalize our text with the NFKC, compressing normalization.
    # This is called for the Insert button, Tab key and Enter key.
    # Also use a regex to find greek lowercase sigma before a word
    # boundary and convert it to the word-ending form. This is something
    # applicable only to Greek but we do it regardless. If it turns out
    # to be a problem (who knows, Coptic doesn't want it?) we will have
    # to work out some kind of switch command in the input file format.
    def normNFC(self):
        qre = QRegExp(u'\u03c3\\b')
        qs_normal = self.text().normalized(QString.NormalizationForm_KC)
        qs_normal.replace(qre,QString(u'\u03c2'))
        self.setText(qs_normal)

    # Normalize with NFD, de-compressing combined characters into their parts.
    # This is called only from the back-tab key processing.
    def normNFD(self):
        qs_normal = self.text().normalized(QString.NormalizationForm_KD)
        self.setText(qs_normal)

    # Catch the arrival of focus into our dialog. Get the current state
    # of the modifier keys from the app and if it differs from what
    # we had before, emit the shift signal.
    def focusInEvent(self, event):
        self.testMod(QApplication.keyboardModifiers())

    # Catch each key event and do something with it.

    # For mouse actions, the practice is to act on the release, not the
    # click. It seems however that for key events, Qt acts on the press, not
    # the release. (One reason: auto-repeat produces a sequence of Press
    # events with no Release.) So for key Release we just check the new
    # mod-state, and pass the event on.
    def keyReleaseEvent(self, event):
        # probably no change from last key press, but check it
        self.testMod(event.modifiers())
        event.ignore()
        super(MagicLineEdit, self).keyReleaseEvent(event)

    # For key PRESS we also check the mod state. This is where we find
    # out that Shift, Alt, a/o Control have been pressed and make the
    # keytops change to match. Then take action on certain keys.

    def keyPressEvent(self, event):
        self.testMod(event.modifiers())
        key = event.key()
        if key in KEYSAZ09 :
            py_string = self.mamma.key_objects[unichr(int(key))].fetch()
            # "easy for you to say..."
            if py_string is not None :
                self.insert(QString(py_string))
            if self.mamma.mod_state != MOD_CTL :
                # just a key value, and we have dealt with it
                event.accept()
            else : # ctl-something, pass it along
                event.ignore()
        elif key in KEYTABRET : # tab, shift-tab, return
            if key == Qt.Key_Tab :
                self.normNFC()
            elif key == Qt.Key_Backtab :
                self.normNFD()
            elif (key == Qt.Key_Enter) or (key == Qt.Key_Return) :
                self.mamma.doInsert()
                self.mamma.doClear()
            event.accept() # in all these cases, key is finished.
        elif (key in KEYZOOM) and (self.mamma.mod_state == MOD_CTL) :
            change = (-1) if (key == Qt.Key_Minus) else 1
            points = self.fontInfo().pointSize() + change
            if (points > 4) and (points < 32): # don't let's get ridiculous, hmm?
                f = self.font() # so get our font,
                f.setPointSize(points) # change its point size +/-
                self.setFont(f) # and put the font back
            event.accept()
        else :
            event.ignore()
            super(MagicLineEdit, self).keyPressEvent(event)

if __name__ == "__main__":
    from PyQt4.QtCore import(PYQT_VERSION_STR,QT_VERSION_STR,QSettings)
    from PyQt4.QtGui import (QPlainTextEdit)
    import pqIMC, pqMsgs
    import sys
    import os
    app = QApplication(sys.argv)

    base = os.path.dirname(__file__)
    kfile = open(base+'/extras/Greek.palette','rb')
    IMC = pqIMC.tricorder()
    IMC.editWidget = QPlainTextEdit()
    IMC.fontFamily = QString("Liberation Mono")
    pqMsgs.IMC = IMC
    pqMsgs.getMonoFont()
    IMC.settings = QSettings()
    kbd = KeyPalette('Greek',kfile)
    kbd.show()
    app.exec_()
