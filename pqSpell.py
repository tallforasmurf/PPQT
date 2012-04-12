# must precede anything except #comments, including the docstring
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
 Define a class that represents an interface to a spellchecker, and
 a class that represents a dictionary for a single language.

 The makeSpellCheck class stores information about the available
 dictionaries and the path to them. It instantiates a main or default
 dictionary object, and can instantiate other, alternate dictionaries
 when requested. It provides a method to spell-check a single word
 in a specified or the default dictionary, returning True for valid.

 This spellcheck is pure Python, 100% Unicode and has no external
 dependencies except on the dictionary and affix files. It uses dictionaries
 that are compatible with Myspell or Hunspell which come as two files,
 tag.dic containing words and tag.aff containing affix rules. Being all
 Python and not cleverly coded it isn't quick. Also it does not support
 the auxiliary functions of the open-source spellcheckers, like suggestions
 or user dictionaries (the good_words list serves that purpose).
 
 The main implementation constraint is that we expect all dictionary files
 to be located on the __file__/dict path, that is, a folder dict at the
 same level as this .py module. Which means, bundled inside our app.

 Historical note: this is our 4th try at spellcheck. First we did it by
 attaching Aspell via a pipe. But Aspell has dubious Unicode support,
 its latest version isn't on Windows, and pyinstaller couldn't bundle it.
 Then we tried pyenchant to Enchant, which solved the Unicode issue but
 was unpredictable as to what checker it would use (didn't use Hunspell
 on Mac OS, for example) and again pyinstaller couldn't handle it. Then
 we got a simple hunspell wrapper and called the Hunspell dylib. But again
 there are issues with bundling and multiplatform support. So screw it,
 let's just write some code to search in a Myspell affix/dict fileset.
 
 ppqt instantiates one object of the makeSpellCheck class which offers
 these methods:

    .isUp() true/false if spelling is working, which is to say, if
        the last-requested main dictionary could be found and loaded.
    
    .dictList() returns a QStringList with the tag-names (e.g. "en_GB")
        of the available dictionaries. This is used from the View
	menu choice Dictionary... , see pqMain.

    .setMainDict(tag) switch to tag, e.g. u"fr_CA", as the main, default
        dictionary. Returns true if tag is available and that dictionary
	could be successfully loaded, else false and makes no change.

    .mainTag is the unicode tag last set, or null

    .check(aword, dicTag=None)
        aword is a Python Unicode string
	dicTag of None means use main/default dictionary
	dicTag of a string is taken as the tag of an alternate dictionary
        - returns False if dicTag=None and no default dict is loaded
	- returns False if an alt. dict. cannot be found or loaded
	- returns False if aword is not found in the specified dictionary
        - returns True iff aword is accepted

    .terminate() is called from pqMain on shutdown, saves the current
        tag of the main dictionary in settings.

    The spellDict class represents access to a Myspell/Hunspell
    dictionary. It is used internally to implement the main and alt dicts.
    It provides only its initializer and the spell(aword) method.

'''
from PyQt4.QtCore import (QRegExp, QString,QStringList)
import pqMsgs
import os
import sys

class makeSpellCheck():
    def __init__(self):
	# nothing loaded yet
	self.altTag = u''
	self.altDict = None
	self.mainTag = u''
	self.mainDict = None
	# tag of a not-found dict so we don't keep repeating a message
	self.errTag = u''
	# populate our list of available dictionaries by finding
	# all the files of the form <tag>.dic and <tag>.aff in the folder
	# passed by the parent module and store the
	# dict tags (file names) into the string list self.listOfDicts.
	self.listOfDicts = QStringList()
	#print('Looking for dicts in:{0}'.format(IMC.dictPath))
	# list all files in that folder. We don't need to sort them, we
	# use the "in" operator to find the X.dic matching an X.aff
	fnames = os.listdir(IMC.dictPath)
	for fn in fnames:
	    if u'.aff' == fn[-4:] :
		# this is a tag.aff file, look for matching tag.dic
		dn = fn[:-4]
		if (dn + u'.dic') in fnames:
		    self.listOfDicts.append(QString(dn))
        # initialize our main dictionary to the one last-chosen by the user
	# with a default of en_US.
	deftag = IMC.settings.value(u"main/spellDictTag",
                                          QString(u"en_US")).toString()
	# try to load the main dictionary
	self.setMainDict(deftag)
	# No alt-dict has been loaded yet

    def isUp(self):
        return (self.mainDict is not None)

    # Return our list of available dictionary tags (used in forming a
    # popup menu for user selection).
    def dictList(self):
        return self.listOfDicts
    
    # When the program terminates, this slot is called. Save the user-set
    # main dictionary tags.
    def terminate(self):
        IMC.settings.setValue(u"main/spellDictTag",self.mainTag)

    # set a new main/default dictionary, if a dict of that tag exists.
    # if we have already gone to the labor of loading that dict, don't
    # repeat the work.
    def setMainDict(self,tag):
	if tag == self.mainTag :
	    return True # already got that one
	elif tag == self.altTag :
	    self.mainTag = self.altTag
	    self.mainDict = self.altDict
	    return True
        dictobj = self.loadDict(tag)
	if dictobj is not None :
	    self.mainDict = dictobj
	    self.mainTag = tag
	    return True
	else:
	    self.mainDict = None
	    self.mainTag = u''
	    return False
    
    # Load a dictionary specified by its tag, if it appears in our list.
    # If it doesn't, or any other problem comes up, trap with a warning
    # message. Only warn about a given dict tag once, not repeatedly.
    # Either returns the dictionary object or None on failure.
    def loadDict(self,tag):
	p = self.listOfDicts.indexOf(tag)
	try:
	    if p > -1 : # the tag is in our list of valid dicts
		fn = unicode(tag) # get qstring to python string
		fa = os.path.join(IMC.dictPath,fn+u'.aff')
		fd = os.path.join(IMC.dictPath,fn+u'.dic')
		obj = spellDict(fd,fa)
		return obj # success
	    else:
		raise LookupError('dictionary tag {0} not found'.format(tag))
        except (LookupError, IOError, OSError) as err:
	    if tag != self.errTag :
		pqMsgs.warningMsg(u'Could not open dictionary',str(err))
		self.errTag = tag
	    return None

    
    # Check one word, a python u-string, against the main or some alt dictionary.
    # If an alt dict is specified, it is likely the same as the last one 
    # requested, but if not, then try to load a dict of the given tag.
    # We treat hyphenated phrases as words, but assume that the spellchecker
    # does not (Aspell did, Myspell didn't), so tokenize the hyphenated string
    # and check the words individually, and-ing the results together.

    def check(self,aword, dicTag = ''):
	if 0 == len(dicTag):
	    d = self.mainDict # which, if we are not up, is None
	else:
	    if dicTag == self.altTag :
		d = self.altDict # same alt as the last one
	    else:
		d = self.loadDict(dicTag)
		if d is not None :
		    self.altDict = d # ok that worked, save alt dict
		    self.altTag = dicTag
        if d is not None: # one way or another we have a dict
            if len(aword.strip()) : # nonempty text
		if (u'-' in aword) and (aword[0] != u'-'):
		    # hyphenated word, check each unit, AND the results
		    l = aword.split(u'-') # list of 1 or more tokens
		    b = True
		    for w in l:
			b = b and d.spell(w)
		    return b
		else:
		    # not hyphenated, or initial-hyphen (assume number)
		    return d.spell(aword) # just spell it
	return False # null word, or main or alt dict not available

'''
Represent access to one Myspell-compatible dictionary.
'''
import codecs

class spellDict():
    ''' Open the dictionary and affix files. Read the affix SET
    statement and set the appropriate codec for reading the dic file.
    Store all the PFX and SFX rules as lists of tuples for use in 
    de-affixing test words. Read the dictionary and store it as
    a big Python dict whose values are the affix-flags for each word.
    Since Python stores dict keys as a hash -- hopefully one that expands
    as tags are added -- this gives us fast hashed lookup for known words.
    '''
    def __init__(self,dicPath,affPath):
	# set up regex for numeric words like 101st, 22nd, 33rd, 44th, 40th
	self.numericWord = QRegExp('(\d*1st)|(\d*2nd)|(\d*3rd)|(\d*[4567890]th)')
	# sadly, python's unicode .isdecimal() doesn't actually recognize
	# signs or decimal points! Not going to attempt scientific notation.
	self.decimalWord = QRegExp(u'(\-|\+)?\d*\.?\d+')
	# open the affix file as Latin-1, and find out how the .dic is encoded.
	# Not that this is certain: the OpenOffice Latin dictionary had
	# SET UTF-8 but the dict was saved in Win CP1251, grrr.
	uaf = codecs.open(affPath,'r','ISO8859-1')
	setCodec = "ISO8859-1"
	for line in uaf:
	    if line[:3] == 'SET' :
		setCodec = line.split()[1]
		break
	# open the .dic file with the codec specified by SET
	udf = codecs.open(dicPath,'r',setCodec)
	# read the affix file and save the PFX and SFX rules. We do not
	# do suggestions so ignore TRY and REP lines. We do not support
	# any Hunspell compounding option lines, either.
	uaf.seek(0) # might have read right to the end, so rewind .aff
	self.pfxRules = self.readAffRules('PFX',uaf)
	uaf.seek(0) # rewind once more; heck, it's all in memory now
	self.sfxRules = self.readAffRules('SFX',uaf)
	# Now read the dictionary and store it. A typical dictionary line
	# would be aardvark/S that is, word-string and an optional
	# /X... where the Xs are the classids of affix rules. The dic
	# is not necessarily sorted. The first line is a number, the size.
	# Just skip it.
	dSize = int(udf.readline().strip())
	# Process the rest of the dictionary into a list of two-ples,
	# ('wordtext', 'affixflags'). Sort the entire list on the word texts.
	# Any encoding errors or i/o errors here will trap up to the 
	# caller's try statement.
	self.dictData = {}
	for line in udf:
	    if len(line) and (line[0].isalnum()): # ignoring nulls, comments
		(word,slash,aflags) = unicode(line).strip().partition(u'/')
		self.dictData[word] = aflags
	# And that is all there is to loading a dictionary!

    '''
    Read all the lines in a tag.aff file and save the PFX or SFX rules
    in a form we use later to strip down words. For reference a PFX
    or SFX line has one of two forms. The first of a class is:
        xxx classid [Y|N] rule-count
    where: classid is a single letter key to a class of related rules
    (we do NOT support the Hunspell multi-char class ids); Y|N refers
    to whether rules can be compounded (we always assume Y, too bad);
    and rule-count is the number of actual rules of this class to follow.
    We ignore this line. Other lines are of the form:
        xxxx classid cstrip cadd test
    where: cstrip is the characters that would be removed before applying
    the affix, with '0' meaning none; cadd is the affix string; and test
    is a form of regex to see if the affix can be used. We store only
    a four-ple (cadd, len(cadd), cstrip, classid). Because we discard the
    test, we get quite a few duplicates which we eliminate with a set.
    Finally, sort the list on the cadd strings (really useful only for PFX)
    '''
    def readAffRules(self,verb,affile):
	keySet = set([])
	rules = []
	for line in affile:
	    line = unicode(line) # let's keep it all Unicode
	    if line[0:3]==verb : # either PFX or SFX
		p = line.split()
		if not p[3].isdigit() : # not first line of a class
		    classid = p[1]
		    cstrip = u'' if p[2] == u'0' else p[2]
		    cadd = p[3]
		    key = cadd+classid+cstrip
		    if not key in keySet :
			keySet.add(key)
			rules.append( (cadd, len(cadd), cstrip, classid) )
	rules.sort(key = lambda fourple : fourple[0])
	return rules

    # Try to find a word by "disarmingly" stripping affixes. Each time
    # we strip an affix we have a new word. Look it up and if it is found,
    # verify that it permits use of the affix classid we used for stripping.
    # If it passes both tests, great, return True.
    # If not, recurse to try some more affixes, until we have tested all
    # the affix rules. Note: with en_US, en_GB it was ok to recurse freely
    # but with fr_FR, there is a recursion loop implicit in the rules for
    # appending e and s, so we have to cut it off at 2.
    def stripAndLookup(self,tw,depth):
	for (cadd,ladd,cstrip,classid) in self.sfxRules:
	    if tw[-ladd:] == cadd : # word has this suffix e.g. 'ed'
		xw = tw[:-ladd]+cstrip
		if (xw in self.dictData) and (classid in self.dictData[xw]) :
		    # shortened word matched and sfx class applies to it
		    return True
		else:
		    if depth < 2 :
			if self.stripAndLookup(xw,depth+1): # try to shorten it more
			    return True # shorter word was a hit
		    # else keep trying suffixes
	# We have run through all the suffixes with no luck; try prefixes
	for (cadd,ladd,cstrip,classid) in self.pfxRules:
	    if tw[:ladd] == cadd: # word has this prefix e.g. 'un'
		xw = cstrip+tw[ladd:]
		if (xw in self.dictData) and (classid in self.dictData[xw]):
		    # shortened word matched and pfx class is applicable
		    return True
		else:
		    if depth < 2 :
			if self.stripAndLookup(xw,depth+1): # try to shorten it more
			    return True # shorter word was a hit
	    elif tw[:ladd] < cadd : # past any applicable prefixes
		break
	return False

    # Try like heck to find some kind of match to this word in our dictionary:
    # 1. Look for the word as-is; if we hit, yippee! Many words should hit.
    # 2. if it starts with a digit, then
    #       if all-digit, it's good
    #       test with a regex for words like "10th" and "23rd"
    #       otherwise, a numeric token is wrong
    # 3. If it is all-lowercase, try stripping affixes.
    # 4. It has some caps, on the assumption it is the first word of a
    #    sentence or and all-cap, try it lowercase, direct and affix-stripped.
    # 5. If it is Title-cased (thank you Python for supplying that test),
    #    try stripping suffixes (no prefix rules are title-cased)
    # The result of this is that a word that is Title-cased in the dictionary
    # must be Title-cased to be found, e.g. dict. 'France' will not match
    # to either FRANCE or france. However a properly Title-cased word
    # will match, e.g. Englishman -> English, Scandanavian -> Scandanavia
    
    def spell(self,tw):
	if len(tw): # null string is not valid
	    if (tw in self.dictData) :
		return True # hopefully the majority of words exit right here
	    if tw[0] in '.-+0123456789' : # starts with a digit
		qtw = QString(tw) # to QString-land for QRegExp tests
		if self.decimalWord.exactMatch(qtw) : # numbers are ok 
		    return True
		else: # check for 1st, 2nd, 3rd, 4th... 1001st...
		    return self.numericWord.exactMatch(qtw)
	    if tw.islower() :
		# all-lowercase, try stripping affixes
		return self.stripAndLookup(tw,0)
	    # word has 1 or more capital letters. 
	    lw = tw.lower()
	    if (lw in self.dictData) :
		return True
	    if self.stripAndLookup(lw,0) : # try stripping the lowercase form
		return True
	    if tw.istitle(): # title-case, try stripping it as-is
		return self.stripAndLookup(tw,0)
	return False # can't say we didn't try...

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
	print("Junk as main: ", sp.setMainDict(u"Foobar"))
	print("en_GB as main: ",sp.setMainDict(u"en_GB"))
	wl = ['-8.7', 'AND','bazongas','101st', 'run-of-the-mill', 'basse-terre', '  ','lait','fraise',
	      'Englishman', 'oiseau', 'oiseaux','Paris']
	print("==Main dict==")
	for w in wl:
            if sp.check(w):
                print(w + " is a word")
            else:
                print(w + " is not")
	print("==Alt dict==")
	for w in wl:
	    if sp.check(w,'fr_FR'):
                print(w + " is a word")
            else:
                print(w + " is not")
	sp.terminate()
