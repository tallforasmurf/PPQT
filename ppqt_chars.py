   
28 = ( Punctuation_Open
29 = ) Punctuation_Close

2d = - Punctuation_Dash

30 = 0 Number_DecimalDigit

41 = A Letter_Uppercase

5b = [ Punctuation_Open

5d = ] Punctuation_Close

61 = a Letter_Lowercase

7b = { Punctuation_Open

7d = } Punctuation_Close

ab = ÃÂ« Punctuation_InitialQuote

bb = ÃÂ» Punctuation_FinalQuote

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

WordHasCap = 0x01
WordHasLower = 0x02
WordHasDigit = 0x04
WordHasHyphen = 0x08
WordHasApostrophe = 0x10
WordMisspelt = 0x80

from PyQt4.QtCore import (QFile, QTextStream, QString, QChar)

#word = QString(u"a0-9\03C3A\u00D1\u0386 fubar")
#flag = 0
#for i in range(word.size()):
    #cat = word.at(i).category()
    #if cat == QChar.Letter_Uppercase : flag |= WordHasCap
    #if cat == QChar.Letter_Lowercase : flag |= WordHasLower
    #if cat == QChar.Number_DecimalDigit : flag |= WordHasDigit
    #if cat == QChar.Punctuation_Dash : flag |= WordHasHyphen
    #print(cat)
    
for x in range(1,126):
    q = QChar(x)
    print('{0:x} = {1} cat {2}'.format(x, QString(q), q.category()) )
