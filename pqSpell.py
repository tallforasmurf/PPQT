# must precede anything except #comments, including the docstring
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
 Define a class that represents an interface to a spellchecker.
 The makeSpellCheck class stores information about the available
 dictionaries and the paths to them. It instantiates a main or default
 dictionary object, and can instantiate other, alternate dictionaries
 when requested. It provides a method to spell-check a single word
 in the active dictionary or a given alternate, returning True for valid.
 
 Actual spellcheck is done by the Hunspell checker, as used in Open Office,
 LibreOffice, Mac OSX and many others. See note below for provenance.

 ppqt.py instantiates one makeSpellCheck object as IMC.spellCheck,
 from whence it is referenced by pqEdit and pqMain for these methods:
 
    .isUp() True/False if spelling is working, which is to say, if
        hunspell could be set up using the last-requested main dict.

    .dictList() returns a QStringList with the tag-names (e.g. "en_GB")
        of the available dictionaries. This is used from to set up
        the View > Dictionary... menu in pqMain.

    .setMainDict(tag) switch to another tag, e.g. u"fr_CA", as the main
        or default dictionary. Returns True if tag is available and
        hunspell set up with that dict, else False and makes no change.

    .mainTag is the unicode tag last set in setMainDict (or initialized
        from saved settings), or null for none.

    .check(aword, dicTag=None)
        aword is a Python Unicode string (not a QString)
	dicTag of None means use main/default dictionary
	dicTag of a string is taken as the tag of an alternate dictionary
        - returns False if dicTag=None and no default dict is loaded
	- returns False if an alt. dict. cannot be found or loaded
	- returns False if aword is not found in the specified dictionary
        - returns True iff aword is accepted in the specified dictionary

    .terminate() is called from pqMain on shutdown to save the current
        tag of the main dictionary in settings.

 The spellDict class represents access to a single Myspell/Hunspell
 dictionary via a hunspell object. It is used internally to implement the
 main and alt dicts. It provides only its initializer and the spell(aword) method.

 The main implementation constraint is that we expect all dictionary files
 to be located on the __file__/dict path, that is, a folder of dictionaries
 bundled inside our app. We pass the path to the tag.dic and tag.aff files
 to the hunspell instantiation. This means that the only available dict tags
 are those bundled with PPQT, or added by the user to the PPQT/dict folder.

 Historical note: this is our 5th (!) try at spellcheck. First we did it by
 attaching Aspell via a pipe. But Aspell has dubious Unicode support,
 its latest version isn't on Windows, and pyinstaller couldn't bundle it.
 Then we tried pyenchant to Enchant, which solved the Unicode issue but
 was unpredictable as to what checker it would use (didn't use Hunspell
 on Mac OS, for example) and again pyinstaller couldn't handle it. Then
 we got a simple hunspell wrapper and called the Hunspell dylib. But again
 there were issues with bundling and multiplatform support. So 4th try
 I wrote my own checker to search a Myspell-format dictionary, which worked
 pretty well for English and French but failed horribly for German, and was
 rather slow. So now we are back to using a hunspell wrapper from
 https://code.google.com/p/pyhunspell/ which has some issues and is not
 being supported, but seems to work and is wicked fast.
'''
from PyQt4.QtCore import (QRegExp, QString,QStringList)
import pqMsgs
import os
import sys
import hunspell

class makeSpellCheck():
    def __init__(self):
        # Nothing loaded yet
        self.altTag = u''
        self.altDict = None
        self.mainTag = u''
        self.mainDict = None
        # Tag of a not-found dict so we don't keep repeating a message
        self.errTag = u''
        # Populate our list of available dictionaries by finding
        # all the file-pairs of the form <tag>.dic and <tag>.aff in the
        # folder whose path is saved by ppqt in IMC.dictPath.
        # Save the dict tags in the string list self.listOfDicts.
        self.listOfDicts = QStringList()
        # Get a list of all files in that folder. We don't need to sort them,
        # we use the "in" operator to find the X.dic matching an X.aff
        fnames = os.listdir(IMC.dictPath)
        for fn in fnames:
            if u'.aff' == fn[-4:] :
                # this is a tag.aff file, look for a matching tag.dic
                dn = fn[:-4]
                if (dn + u'.dic') in fnames:
                    self.listOfDicts.append(QString(dn))
        # Initialize our main dictionary to the one last-chosen by the user
        # with a default of en_US. The current main dict is saved in the
        # settings during the terminate() method below.
        deftag = IMC.settings.value(u"main/spellDictTag",
                                    QString(u"en_US")).toString()
        # Try to load the main dictionary. Sets self.mainDict/.mainTag.
        self.setMainDict(deftag)
        # No alt-dict has been loaded yet, so self.altDict/.altTag are None.

    # If a main dictionary has been loaded, return True.
    def isUp(self):
        return (self.mainDict is not None)

    # Return our list of available dictionary tags, as needed to populate
    # the View > Dictionary submenu.
    def dictList(self):
        return self.listOfDicts

    # When the program is ending, pqMain calls this slot.
    # Save the user-set main dictionary tag for next time.
    def terminate(self):
        IMC.settings.setValue(u"main/spellDictTag",self.mainTag)

    # Set a new main/default dictionary if a dict of that tag exists.
    # If we have already gone to the labor of loading that dict, don't
    # repeat the work.
    def setMainDict(self,tag):
        if tag == self.mainTag :
            return True # We already loaded that one
        elif tag == self.altTag :
            # We already loaded that tag as an alt, make it Main
            self.mainTag = self.altTag
            self.mainDict = self.altDict
            # and now we don't have an alt any more.
            self.altTag = None
            self.altDict = None
            return True
        # Try to create a hunspell object for that dict/aff pair.
        dictobj = self.loadDict(tag)
        if dictobj is not None :
            # That worked, save it.
            self.mainDict = dictobj
            self.mainTag = tag
            return True
        else:
            # It didn't work. .mainDict/.mainTag are either None,
            # or else they have some earlier successful choice.
            # Leave them as-is.
            return False

    # Set up a spellcheck dictionary by way of our spellDict class.
    def loadDict(self,tag):
        p = self.listOfDicts.indexOf(tag)
        try:
            if p > -1 : # the tag is in our list of valid dicts
                fn = unicode(tag) # get qstring to python string
                aff_path = os.path.join(IMC.dictPath,fn+u'.aff')
                dic_path = os.path.join(IMC.dictPath,fn+u'.dic')
                obj = spellDict( dic_path, aff_path )
                return obj # success
            else:
                raise LookupError('dictionary tag {0} not found'.format(tag))
        except (LookupError, IOError, OSError) as err:
            if tag != self.errTag :
                pqMsgs.warningMsg(u'Could not open dictionary',str(err))
                self.errTag = tag
            return None
        except : # some other error?
            print("unexpected error opening a spell dict")
            return None

    # Check one word, a python u-string, against the main or an alt dictionary.
    # If an alt dict is specified, it is likely the same as the last one 
    # requested, but if not, then try to load a dict of the given tag.
    # We used to split up hyphenated phrases, but Hunspell handles them.
    def check(self, aword, dicTag = ''):
        if 0 == len(dicTag):
            d = self.mainDict # which is None, if we are not up
        else:
            if dicTag == self.altTag :
                d = self.altDict # same alt as the last one
            else:
                # Different alt dictionary, open it
                d = self.loadDict(dicTag)
                if d is not None :
                    self.altDict = d # that worked, save new alt dict
                    self.altTag = dicTag
        if d is not None: # one way or another we have a dict
            return d.spell(aword)
        return False # null word, or main or alt dict not available


# Represent access to one Myspell-compatible dictionary, by way of
# a Hunspell object. Called from within a try block, so make no
# attempt here to trap errors. The Hunspell constructor takes its
# character encoding from the SET statement in the affix file.
# The word to be spell-checked has to be encoded to that encoding
# or it will not be found. No need to get anal about encoding errors;
# if a word has a letter that can't be encoded to match the dictionary,
# obviously the word cannot appear in the dictionary.

class spellDict():
    def __init__(self,dic_path,aff_path):
        self.hobj = hunspell.HunSpell(
            dic_path.encode('ISO-8859-1'),
            aff_path.encode('ISO-8859-1') )
        # Get the encoding Hunspell is using for this dict.
        self.encoding = self.hobj.get_dic_encoding()
    
    def spell(self, aword):
        encword = aword.encode(self.encoding, errors='replace')
        return self.hobj.spell(encword)

if __name__ == "__main__":
    from PyQt4.QtCore import (QSettings)
    from PyQt4.QtGui import (QApplication)
    import sys
    app = QApplication(sys.argv) # create an app in case it pops a warning
    import pqIMC
    IMC = pqIMC.tricorder()
    IMC.settings = QSettings()
    base = os.path.dirname(__file__)
    IMC.dictPath = os.path.join(base,u"dict")
    IMC.spellCheck = makeSpellCheck()
    sp = IMC.spellCheck
    print("spellcheck is up: ",sp.isUp())
    if sp.isUp():
        #print("Junk as main: ", sp.setMainDict(u"Foobar"))
        #print("en_GB as main: ", sp.setMainDict(u"en_GB"))
        #words = '-8.7 AND bazongas 101st run-of-the-mill Englishman Paris'
        #print("fr_FR as main: ", sp.setMainDict(u"fr_FR"))
        #words = 'basse-terre lait oiseau oiseaux Paris fraise'
        print("de_DE as main: ", sp.setMainDict(u"de_DE"))
        words = u'erschien Heldengedicht unbewu\u00dft \u00fcberall \xfcberwinden \xfcberwindende \xfcberwindet \xfcbertragen \xfcbertragenen \xfcberstark \xfcberschreibt \xfcberschreitet \xfcberraschender \xfcberraschend'
        words = words + u' Lateinschule Vaterstadt Kindererz\xe4hlungen Selbstvertrauen Kuchenteig Grundlage Grundverm\xf6gen Dichtkunst Marktstrasse Wohnhaus Heldengedicht'

        wlist = words.split()
        for word in wlist :
            tf = sp.check(word)
            print((' ' if tf else '*'), word ,('is' if tf else "isn't"),'a word')

        adict = 'fr_FR'
        awords = 'basse-terre lait oiseau oiseaux Paris fraise'
        alist = awords.split()
        print("==Alt dict==",adict)
        for aword in alist:
            tf = sp.check(aword, adict)
            print((' ' if tf else '*'), aword ,('is' if tf else "isn't"),'a word')

        sp.terminate()