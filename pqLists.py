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
Define an interface to store and search through two types of word-lists:
First are simple lists of words stored as Python u'strings', used for
goodwords, badwords, and scannos. The lists are read in and sorted so we can
provide fast lookup using the bisect module of the Python standard lib.
A separate object is instantiated for each list, offering these methods:
  * clear() - empty the list
  * load(stream) - read a QTextStream and populate the list
  * bool active() - a nonempty list exists and can be used
  * bool check(w) - look up one word in the list
  * insert(w) - insert a word into the list
  * load(stream,endmark) - load sorted words from a metadata stream
  * save(stream) - write the list in sequence to a metadata stream
'''

import bisect

from PyQt4.QtCore import (Qt, QFile, QTextStream, QString, QChar)

# Class for simple one-column unicode (usually just Latin-1) word lists
# This class is used for the good_words, bad_words and scanno lists.
class wordList():
    def __init__(self):
        self.clear()

    def clear(self):
        self.wordlist = []
        self.len = 0
    
    def active(self):
        return (self.len > 0)

    def check(self,word):
    	if self.len :
	    i = bisect.bisect_left(self.wordlist,word)
	    if (i != self.len) and (self.wordlist[i] == word):
		return True
        return False

    # Provide for inserting a word to the list. Bisect_left returns the
    # index of word or the highest item < word. If word is higher than
    # anything in the list, the return is the length of the list.
    def insert(self,word):
	i = bisect.bisect_left(self.wordlist,word)
	if (i != self.len) and (self.wordlist[i] == word):
	    return
	self.wordlist.insert(i,word)
	self.len += 1

    # Load up a file of words, assumed one per line. We store them as
    # Python strings, not QStrings, so as to use the bisect module. We do not
    # assume they are in sequence, although likely they are. If this is the
    # first time a file is opened (no metadata) the stream is e.g. good_words.txt
    # and we read it all. Or, it could be a .meta file where we are supposed to
    # read just the part up to the end of our section.
    
    def load(self,stream,endsec=None):
	if endsec is not None : # reading our part of a metadata file
	    while True:
		word = unicode(stream.readLine().trimmed())
		if (word == endsec) or stream.atEnd() : break
		self.wordlist.append(word)
	else : # reading e.g. a good_words.txt file
	    while (not stream.atEnd()):
		word = unicode(stream.readLine().trimmed())
		self.wordlist.append(word)
        self.wordlist.sort()
        self.len = len(self.wordlist)

    # Write all our words to an open .meta text stream.
    def save(self,stream):
	for i in range(self.len):
	    stream << (self.wordlist[i]+"\n")
'''
Second, lists for the character and word censuses of the entire file.
In each case there is a three-column table held as three lists. The first
is an ordered list of QStrings (not Python u'strings'), searched and inserted-to
using a version of the bisect_left function modified to compare QStrings.
The second is an integer count; the third, an integer flag value, either the
unicode property of a character, or a set of flags for a word.
  
The word lists are built by the editor while loading a document, and again
by the refresh function of the word- and char- views. It is queried by the
word- and char views and by the the syntax highligher (for misspelt flags).

The words and chars are stored as QStrings so as to get Unicode comparisons
(we don't trust Python's Unicode support as well as we do Qt's),
so for example a word composed of all-uppercase Greek or Cyrillic would be
correctly seen as an all-cap word. The methods are:

  * clear() - empty the list
  * int size() - return the number of words in the list
  * int lookup(qs) - find word and return its index, or None if not there
  * int count(qs,flag)  - insert, or increment the count of, a word or char
                        and store its flags. Returns the new count;
                        if it is 1, the word/char was new.
  * int getCount(qs) - find a word and return its occurrence count or 0
  * qs  getWord(i)  - return the word at index i, used by pqWords
  * int getFlag(qs)  - find a word and return its category flags or 0
  * (qs, int, int) get(n) - return the word, count, and flags of the word at
                     index n as a tuple, used by pqChar and pqWord to populate
		     their tables.
  * setflags(i,flag) - set the flag value of a word given its index - used
		     to set or clear the misspelled flag value
  * append(qs,count,flag) - add a word with a known count, in sorted order
                     called during load of metadata, and to populate the
		     char census after census taken.
'''
class vocabList():
    def __init__(self):
        self.clear()

    def clear(self):
        self.words = []
        self.counts = []
        self.flags = []
	self.insertPoint = None
        self._size = 0 # can't be same as name of accessor function?

    def size(self):
        return self._size

    # find a word in our vocabulary and return its index, or None if not there
    # use the bisect_left algorithm.
    def lookup(self,qs):
        lo = 0
        hi = self._size
        while lo < hi:
            mid = (lo+hi)//2
            if self.words[mid].compare(qs,Qt.CaseSensitive) < 0 : # words[mid] < qs
                lo = mid+1
            else:
                hi = mid
	self.insertPoint = lo
        if (lo < self._size) : # not empty list
            if (self.words[lo].compare(qs,Qt.CaseSensitive) == 0) : # matched at words[lo]
                return lo
        return None # not there

    # tabulate one use of a word and set its flag on first seeing it
    def count(self,qs,flag):
        i = self.lookup(qs)
        if i is not None :
            self.counts[i] += 1
        else:
	    # new list key - must make a copy to prevent side-effects if the
	    # caller is re-using his qstring.
	    i = self.insertPoint
            self.words.insert(i,QString(qs))
            self.counts.insert(i,1)
            self.flags.insert(i,int(flag))
            self._size += 1
        return self.counts[i]

    # return the count value of a word
    def getCount(self, qs):
        i = self.lookup(qs)
        if i is not None :
            return self.counts[i]
        else:
            return 0

    # Used by pqWords when scanning the table
    def getWord(self,index):
	return self.words[index]

    # return the flag value of a word
    def getFlag(self, qs):
        i = self.lookup(qs)
        if i >= 0 :
            return self.flags[i]
        else:
            return 0

    # This is called when a table widget is populating itself, reading out
    # the list by row number.
    def get(self,index):
        if (index >= 0) and (index < self.size):
            return (self.words[index], self.counts[index], self.flags[index])
        else:
            raise ValueError # naughty naughty

    # Set or change the flags value of an existing word
    def setflags(self, index, newflag):
        if (index >= 0) and (index < self.size):
            self.flags[index] = newflag
        else:
            raise ValueError # tsk tsk

    # This is called from load, where we learn the word and its count
    # and its flags from the metadata file. We assume this is going to
    # come in sorted order, else we will be in big trouble.
    def append(self, qs, cc, ff):
	self.words.append(qs)
	self.counts.append(cc)
	self.flags.append(ff)
	self._size += 1

if __name__ == "__main__":
    import sys
    from PyQt4.QtGui import (QApplication,QFileDialog)
    from PyQt4.QtCore import (QFile, QTextStream, QString)
    vl = vocabList()
    tx = u"could could Could Couldn't couldn't couldn't couldn't couldn't can't Zabriskie"
    wds = tx.split()
    for w in wds:
	vl.count(QString(w),0)
    for i in range(vl.size()):
	(w,n,f) = vl.get(i)
	print(unicode(w),n)
	
    #app = QApplication(sys.argv) # create the app
    #fn = QFileDialog.getOpenFileName(None,"Select a Unit Test File")
    #print(fn)
    #fh = QFile(fn)
    #if not fh.open(QFile.ReadOnly):
        #raise IOError, unicode(fh.errorString())
    #stream = QTextStream(fh)
    #stream.setCodec("UTF-8")
    #print('before active? {0}'.format(wl.active()))
    #wl.load(stream)
    #print('loaded active? {0}'.format(wl.active()))
    #for w in ['frog','cheese','banana','hasaspace', 'notinfile']:
        #print('{0}: {1}'.format(w,wl.check(w)))
    #vl = vocabList()
    #print('vl size {0}'.format(vl.size()) )
    #stream.seek(0)
    #while (not stream.atEnd()):
        #word = stream.readLine().trimmed()
        #j = vl.count(word, 9)
    #for w in ['frog','cheese','banana','hasaspace', 'notinfile']:
        #vl.count(QString(w),0)
        #if i is not None:
            #(ww,cc,ff) = vl.get(i)
            #print('{0}: {1} {2} {3} {4}'.format(w, i, ww, cc, ff))
        #else:
            #print('{0}: not found'.format(w))
    #for i in range(vl.size()):
	#(ww,cc,ff) = vl.get(i)
	#print(i, ww,cc,ff)
    