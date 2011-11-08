# must precede anything except #comments, including the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
 Define a class that represents an interface to a spellchecker.
 One object is instantiated in the main program and used for
 spell-checking of single words.
 
 Originally we attached aspell via a pipe, using the subprocess
 module of the Python standard library. However Aspell presents several
 problems: hard to bundle with pyinstaller; latest 0.60 version not 
 available on windows, no clear path to programming dictionary selection.
 
 The Enchant package wrapped with pyenchant solves most of these (bundling
 may still be a problem).
 
 Our spell class offers these methods:
    .isUp() true/false if spelling is working
    .check(w) where w can be a python string or a QString
        - returns False if checker is not up or rejects word
        - returns True iff word is accepted
    .terminate() is called from pqMain on shutdown
    .dictList() returns a QStringList with the names (tags, e.g. "en_GB")
        of the available dictionaries
    .setMainDict(tag) switch to tag, e.g. u"fr_CA", as the main, default
        dictionary. Returns true if tag is available, else false and makes
        no change.
    .setAltDict(tag) establish tag as a secondary dictionary, returns true if
        tag is available, else false and makes no change.
    .useAltDict(bool) makes the current alt dict active (True) or returns to
        to default dict (False)
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
from PyQt4.QtCore import (QString,QStringList)
import enchant

class makeSpellCheck():
    def __init__(self):
        # initialize our main dictionary with the last-chosen by the user
        self.mainTag = IMC.settings.value(u"main/spellDictTag",
                                          QString(u"en_US")).toString()
        try:
            self.mainDict = enchant.Dict(unicode(self.mainTag))
        except: # on any error just set None
            # query - worthwhile popping up a message?
            # or - just print a diagnostic to the console?
            self.mainDict = None
        self.altTag = IMC.settings.value(u"main/altDictTag",
                                         QString()).toString()

    def isUp(self):
        return self.mainDict is not None

    # check one word against the main or alt dictionary. aword is a QString.
    # enchant doesn't treat hyphenated words as a phrase so we tokenize the
    # hyphenated string and check the words individually, and-ing the results.

    def check(self,aword,dictag=""):
	d = self.mainDict
	if dictag != "" : # alt dict wanted
	    try:
		d = enchant.Dict(dictag)
	    except:
		d = None
        if d is not None: # we have a dict
            if len(aword.strip()) : # nonempty text
		l = aword.split(u'-')
		b = True
		for w in l:
		    b = b and d.check(w)
                return b
        return False

    # open a pyEnchant "Broker" and ask it for the available dicts.
    # format the list as a QStringList and return.
    def dictList(self):
        b = enchant.Broker()
        l = b.list_languages()
        qsl = QStringList()
        for s in l:
            qsl.append(QString(unicode(s)))
        return qsl

    # set a new main/default dictionary, if the tag is recognized
    def setMainDict(self,tag):
        try:
            d = enchant.Dict(tag)
        except:
            return False
        self.mainTag = tag
        self.mainDict = d
        return True
    
    # When the program terminates, this slot is called. Save the user-set
    # main and alt dictionary tags.
    def terminate(self):
        IMC.settings.setValue(u"main/spellDictTag",self.mainTag)
        IMC.settings.setValue(u"main/altDictTag",self.altTag)

if __name__ == "__main__":
    from PyQt4.QtCore import (QSettings)
    class tricorder():
	def __init__(self):
		pass
    IMC = tricorder()
    IMC.settings = QSettings()
    IMC.spellCheck = makeSpellCheck()
    sp = IMC.spellCheck
    print("spellcheck is up: ",sp.isUp())
    if sp.isUp():
	print("en_US as main: ",sp.setMainDict(u"en_US"))
	print("fr_FR as alt: ",sp.setAltDict(u"fr_FR"))
	wl = ['cheese','bazongas','run-of-the-mill', 'basse-terre', '  ','lait','fraise','bloodyFrench']
	print("Main dict")
	for w in wl:
            if sp.check(QString(w)):
                print(w + " is a word")
            else:
                print(w + " is not")
	sp.useAltDict(True)
	print("Alt dict")
	for w in wl:
	    if sp.check(QString(w)):
                print(w + " is a word")
            else:
                print(w + " is not")
	sp.terminate()

    
