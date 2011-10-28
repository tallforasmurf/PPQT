# must precede anything except #comments, including the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

'''
 Define a class that represents an interface to Aspell.
 One object is instantiated in the main program and used for
 spell-checking of single words.
 
 At present we are attaching aspell via a pipe, using the subprocess
 module of the Python standard library. Thus to check a word means
 one pipe-write and at least two pipe-reads. If this becomes too slow
 (or turns out not to work for UTF-8!) 
 we will have to obtain a python wrapper for the C api to Aspell.
 
 The makeAspell class offers these methods:
    .isUp() true/false if spelling is working
    .check(w) where w can be a python string or a QString, returns True
        if aspell approves of the word
    .checkLine(w) passes the line to aspell and returns zero or more
        characters of response, * for a good word, # for a bad one.
    .terminate() which actually isn't called, but could be e.g. from
        a shuttingDown signal from pqMain.

 Aspell commands can be sent over the pipe, as follows:
    *word	Add a word to the personal dictionary 
    @word	Accept the word, but leave it out of the dictionary 
    $$cs option,value e.g. $$cs master en_GB
 We could use these features to provide an add-word method or a
 change-dict method but have not done so.
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

import subprocess
from PyQt4.QtCore import (QString)

class makeAspell():
    def __init__(self):
        aspellOptions = '-a --dont-suggest --run-together --run-together-min 1 --encoding utf-8'
        self.ok = False
        try:
            self.ap = subprocess.Popen('aspell '+aspellOptions,
                                     shell=True,stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
            self.ok = True
            junk = self.ap.stdout.readline() # absorb the first line
        except:
            pass
     
    def isUp(self):
        return self.ok

    # When the program terminates, this slot is called. However sometimes the
    # message "Exception AttributeError: "'NoneType' object has no attribute
    # 'error'" in <bound method Popen.__del__ of <subprocess.Popen object at
    # 0x1036c3510>> ignored". That doesn't happen if we have a debug stop on the 
    # terminate call. So the fix would seem to be to introduce a delay before
    # going out of scope. But putting this call before all other termination
    # code didnt help, even introducting a qWait of 5 seconds (!) didn't do it.
    # It would seem this is Python issue 5099, http://bugs.python.org/issue5099
    # and is fixed by a patch that I don't have.
    def terminate(self):
        self.ap.terminate()

    # Attached as a pipe, Aspell expects a line with zero or more words,
    # and returns a separate LINE of output for each WORD it sees, with
    # '*\n' for correct, '#\n' for not-found, followed by a null line.
    # We assume that we are checking a single word and will get just the two
    # two lines '*\n\n', but trust no-one: Our caller might send in an
    # all-blank line, or a hyphenated string like mother-in-law, so we
    # might see just '\n' or '*\n*\n*\n\n', '*\n#\n*\n\n'. So we read until we
    # see the null line, and return the and-product over asterisks.
    #
    # If Aspell has a problem of any kind, it just goes away and we find out
    # when a pipe read gets an OSError for broken pipe. If that happens we
    # just set our ok flag and .isUp returns false thereafter.
    #
    def check(self,aword):
        if aword.trimmed().size() : # nonempty text
            try:
                self.ap.stdin.write( aword.toUtf8() + '\n')
                ans = self.ap.stdout.readline()
            except: # guard against broken pipe?
                ans = '' # this spell check failed..
                self.ok = False # ..and no more will work
            ok = (len(ans) > 1) # initialize &-reduction of stars
            while len(ans) > 1:
                ok = ok and ('*' == ans[0])
                ans = self.ap.stdout.readline()
            return ok
        return False

    def checkLine(self,aline):
        try:
            self.ap.stdin.write(aline+'\n')
            ans = self.ap.stdout.readline()
        except:
            ans = ''
            self.ok = False
        ret = ''
        while len(ans) > 1:
            ret = ret+ans[0] # collect successive * and # 
            ans = self.ap.stdout.readline()
        return ret

if __name__ == "__main__":
    aspell = makeAspell()
    print(aspell.isUp())
    if aspell.isUp():
        for w in ['cheese','bzongas', 'run-of-the-mill', '  ']:
            if aspell.check(QString(w)):
                print(w + " is a word")
            else:
                print(w + " is not")
        print (aspell.checkLine('cheese bzongas run-of-the-mill'))
        polish = u"g\xc5\xbceg\xc5\xbc\xc3\xb3\xc5\x82ka"
        print(polish, aspell.check(QString(polish)) )

    
