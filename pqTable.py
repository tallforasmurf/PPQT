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
Code to implement ascii tables. Table parsing and reformatting
is an extension of reflowing text. This code could be in pqFlow.py,
and is only a separate module for simplicity of editing.

The syntax of table code is

/T optional-specs
table rows as single lines
T/

/TM optional-specs
table rows as multiple lines

separated by blank lines
T/

The optional-specs determine the layout of the table and of columns.
Note this syntax has been considerably simplified and reduced in function
from my original design. Some features could perhaps be added back in future:
  * ability to specify more elaborate cell-border strings than '-'
  * ability to specify junction characters e.g. '+' or a set of box-drawing ones.

Configurable properties of a table as a whole:
    width: minimum count of characters,
            default is None meaning width is the line length after F and R
            indents as set by containing markup (table can be nested in e.g. Q)
    top-border fill character(s)
            default is None, meaning no top border,
            option is - (hyphen)
    right-side vertical border character
            default is None, meaning no right vertical border
            option is | (stile)

Properties of any single column:
    alignment: content alignment within the cell
            options are left, center, right or decimal
            default is left
    decimal-delimiter: when alignment is decimal, a single char that delimits
            the fraction from the integer, e.g. a comma for a german book
            default is .
            (we don't try to query the Locale because the computer Locale is not 
            necessarily the subject book's Locale)
    width: minimum count of characters
            default is None, meaning width is whatever contents require
            specified larger minimum gets space-fill based on the alignment
            specified minimum less than longest token is overridden
    bottom-border fill character
            default is space: no division in a single-line table, in a
                multi-line, bottom of each row is a line of spaces
            option is - (hyphen), bottom of each row is a line of ----
    left-side vertical border character
            default is None, meaning put two spaces to the left of all
                except for leftmost column
            option is | (stile), left side of all cells consists of |

In framing the table, the right vertical border and the bottom border of each
cell are determined by the column spec. The top border of the top row and
the left border of the leftmost column are determined by the table spec.

The optional-spec syntax is:
    [   Table(
        [Width:n]
        [Top:'-']
        [Side:'|']
        )
    ]
    [   Column(
        [Align:Left|Center|Right|Decimal]
        [Decimal:'x'] # decimal delimiter, default period
        [Width:ww[.ff]]
        [Bottom:'-']
        [Side:'|']
        )
    ]
    [
        <1-9>(
        [Align:Left|Center|Right|Decimal]
        [Width:ww[.ff] ]
        [Side:' ']
        ) ...
    ]
In the above, square brackets and lowercase indicate optional items.
The Column() spec sets defaults for all columns. The <number>() spec
sets values for a specific column <number> 1-9. A table may have more than 9
columns, but only columns 1-9 can be explicitly configured with this syntax.
The Width sets the minimum width. When both integer and fraction widths are
given (W:ww.ff) the minimum width is ww+ff+1.

The /T line is not "parsed", items are just recognized using REs. Only the 
initials are looked for. Unrecognized params are simply ignored!

/T T(T:'-' S:'|') Col(B:'-' S:'|') 1(S:' ') 2(A:C) 3(A:R W:8) 4(ALIGN:DECIMAL)
one  two  75  654321
three  @  200  .123456
T/

This should reflow to the following table:
-----------------------------------------    (top row from T(T:'-')
  one   | two |      75 | 654321        |
-----------------------------------------
  three |  @  |     200 |       .123456 |
-----------------------------------------

A constraint of this code is that all inner cells must be represented by content
IN EVERY LINE. Cells on the right can be omitted, but an empty cell or line of
a multi-line cell must filled out with a single @ when there is a non-empty
cell to its right. In HTML conversion, cell data consisting only of
@ is converted to &nbsp;. (If we do a "delete markup" operation for ascii,
it could replace @s with spaces, but they are easy enough to kill manually.)

What is passed to the table function is a textCursor (the one with the undo/redo
macro working) and the slice of the work unit list bounded by the opening and
closing /T[M] markup lines. (This lets us process only nonempty lines, and use
the B:n value to detect row boundaries in a multiline table.)

We define two local classes. A tableProperties instance decodes and stores
the values defined in the /T[M] statement, allowing the code to easily fetch
information about alignment, widths, and borders. For example,
    tp = tableProperties(QString("/T T(T:'-' S:'|') Col(A:R) 3(W:8)")
    tp.isMultiLine() -> False
    tp.columnSideString(1) -> '|' 
    tp.columnWidth(2) -> None
    tp.columnWidth(3) -> 8

A tableCells instance stores the cell values as they are discovered, and
returns them properly formatted when the table is rewritten. The related
tableProperties is used in initializing the tableCells, so it can return
either actual or specified widths,
    tc = tableCells(tp)
    tc.store(rownum,1,QString("one")) # discovering the values of the example
    tc.store(rownum,2,QString("two"))
    tc.store(rownum,3,QString("75"))
    tc.store(rownum,4,QString("654321"))
    tc.columnMinWidth(1) -> 4 based on len("one") + len(tp.cSide(1))

Some would disdain class definitions like these as "singleton factories."
True, only one of each is made in handling a given table, yet I think this is
valid  design for two reasons. One, it allows me to encapsulate all the work of
parsing and recalling the optional-specs in one place, and all of the
work of storing and recalling cell data in another, and to code these separately
and apart from the general issue of scanning and replacing table text. And two,
the identical classes are useful for both ascii and html table processing,
so they are genuine abstractions.
'''
from PyQt4.QtCore import (Qt, QChar, QString, QStringList, QRegExp)
from PyQt4.QtGui import(QTextBlock, QTextCursor, QTextDocument)
import pqMsgs

# Global definitions used and returned by the classes below:
CalignLeft = 0
CalignCenter = 1
CalignRight = 2
CalignDecimal = 4 

SingleLineTable = 0
MultiLineTable = 1

class tableProperties:
    # For instantiation we receive the /T or /TM line as a qstring.
    # We parse it using regexes. This is not a rigorous parse. It does not
    # detect errors! Anything we recognize, we store. Anything that does not
    # match an RE is simply ignored. For example an unclosed paren will not
    # produce an error "hey dummy you didn't close the paren," it will just
    # mean that the whole option group will not be seen. Also we don't look at
    # spelling of keywords beyond the initial, so ALIGN:CENTER is the same as
    # AZIMUTH:CORPOREAL or of course, A:C.
    #
    def __init__(self,tqs,tlnum):
        self.tLineNumber = tlnum # note line number for messages if any
        # set up default table properties
        self.tProps = {'W':None, 'T':None, 'S':None}
        # set up default all-column properties: A:alignment,
        # B:bottom-sring, S:side-string, D:decimalpoint W:width F:Fraction
        self.cProps = {'A':CalignLeft, 'B':None, 'S':None, 'D':'.', 'W':None, 'F':None}
        # explicit properties of specific columns 1-9 stored here if supplied
        self.c1to9Props = {}
        # note if this is multiline: /TM versus /T
        self.isMulti = tqs.startsWith(QString(u'/TM'))
        self.parseRE = QRegExp()
        self.parseRE.setCaseSensitivity(Qt.CaseInsensitive) # ignore case 
        # set minimal so when looking for ), we stop with the first
        # if any of this code changes parseRE.minimal it must save and restore it.
        self.parseRE.setMinimal(True) 
        # get the contents of a Table(something) if it exists
        topts = self.getMainOption(tqs,u'T')
        if topts is not None: # there is T(something), and topts has the something
            # pull a WIDTH:n option out of it if any, ignoring any fraction
            # (fraction is only valid for a column spec)
            (w,f) = self.getWidthOption(topts)
            if w is not None:
                self.tProps['W'] = w
            # pull a TOP:'-' option if any
            s = self.getStringOption(topts, u'T')
            if s is not None:
                if unicode(s) == u'-':
                    self.tProps[u'T'] = s
                else:
                    self.badTableParm(u'Only hyphen suppported for Top option')
            # pull a SIDE:'|' option if any
            s = self.getStringOption(topts, u'S')
            if s is not None:
                if unicode(s) == u'|':
                    self.tProps[u'S'] = s
                else:
                    self.badTableParm(u'Only stile supported for Side option')
        # get the contents of a Column(something) if it exists
        copts = self.getMainOption(tqs,u'C')
        if copts is not None:
            # there is a Column(something) and copts is the something
            # pull default column options out of it, store in self.cProps
            self.getColumnOptions(copts,self.cProps,True)
        # collect specific column options 1()..9() if given
        for cnum in u'123456789':
            copts = self.getMainOption(tqs,cnum)
            if copts is not None:
                # there is a n(something) option, extract bits from it
                # and store in the dictionary.
                self.c1to9Props[cnum] = self.cProps.copy()
                self.getColumnOptions(copts,self.c1to9Props[cnum])

    # get a major option string Xxxx(something) and return the something
    def getMainOption(self,qs,key):
        # set RE pattern of Xxxxx(something)
        self.parseRE.setPattern(key + u'\w*\s*\((.+)\)')
        if -1 < self.parseRE.indexIn(qs) :
            return self.parseRE.cap(1)
        return None
    # get an Align:keyword option string returning the initial or None
    def getAlignOption(self,qs):
        # set RE pattern of Axxxx:Left/Right/Center/Decimal
        self.parseRE.setPattern(u'A\w*\s*\:\s*([LRCD])\w*')
        if -1 < self.parseRE.indexIn(qs) :
            return unicode(self.parseRE.cap(1).toUpper()) # u'L R C or D'
        return None
    # get a Width:www[.fff] option string, returning (None, None) if not found,
    # or (w, None) if not decimal, or (w, f) if decimal given.
    def getWidthOption(self,qs):
        # set RE pattern of Wxxxx:www.fff, greedy to get all digits
        mopt = self.parseRE.isMinimal()
        self.parseRE.setMinimal(False)
        self.parseRE.setPattern(u'W\w*\s*\:\s*(\d+)(\.(\d+))?')
        wval = None
        fval = None
        if -1 < self.parseRE.indexIn(qs):
            # We have a definite hit on W:www, and it may be W:www.fff
            (wval,ok) = self.parseRE.cap(1).toInt() # ok is True
            (fval,ok) = self.parseRE.cap(3).toInt() # ok may be False
            if not ok :
                fval = None # cap(3) was null, no .fff found
            if (wval > 75) or (fval is not None and (74 < wval+fval)) :
                self.badTableParm(u"Widths over 75 not supported in tables")
                wval = None
                fval = None
        self.parseRE.setMinimal(mopt)
        return (wval,fval)
    # Get a Xxxx:'str' or Xxxx:"str" option and convert to a proper literal,
    # returning either None for no option seen, or a one-character QString.
    # Allow single or double quotes, unfortunately QRegExp does not allow
    # back-references inside character classes, e.g. ('|")([^\1]+)\1
    # so we have to run two separate re's. Originally the plan was to allow
    # multiple chars for some options and and someday might, so this is more
    # general than strictly needed. N.B. when QRegExp.indexIn fails, the value
    # of QRegExp.cap(1) is a null QString.
    def getStringOption(self,qs,initial):
        opt = None
        # set pattern for Xxxx:'x'
        self.parseRE.setPattern(initial+u"\w*\s*\:\s*\\\'([^\\\']*)\\\'")
        self.parseRE.indexIn(qs)
        opt = self.parseRE.cap(1)
        if opt.isNull() : # no hit on single quote, try "x"
            # set pattern for Xxxx:"x"
            self.parseRE.setPattern(initial+u'\w*\s*\:\s*\\\"([^\\\"]*)\\\"')
            self.parseRE.indexIn(qs)
            opt = self.parseRE.cap(1)
        if not opt.isNull() :
            if opt.size() > 1 :
                self.badTableParm(
                    u'only single-char delimiters allowed, ignoring '+unicode(qs)
                )
                opt = None
        else:
            opt = None
        return opt
    # Given the "something" from C(something) or <digit>(something), populate or
    # update a dict of properties with Align, Width, Bottom and Side values.
    # main==True signals this is the C(something) where B and S are allowed.
    def getColumnOptions(self,copts,propdic,main=False):
        a = self.getAlignOption(copts)
        if a is not None:
            propdic[u'A'] = {
        'L':CalignLeft,'R':CalignRight,'C':CalignCenter,'D':CalignDecimal
                            }[a]
            if a == u'D': # decimal align, look for a special delimiter
                d = self.getStringOption(copts, u'D')
                if d is not None:
                    propdic[u'D'] = d.at(0) # keep the first char as a QChar
        (w,f) = self.getWidthOption(copts)
        if w is not None:
            propdic['W'] = w
            if f is not None:
                propdic['F'] = f
        if main:
            s = self.getStringOption(copts, u'B')
            if s is not None:
                if unicode(s) == u'-':
                    propdic[u'B'] = s
                else:
                    self.badTableParm(u'Only hyphen suppported for Bottom option')
            s = self.getStringOption(copts, u'S')
            if s is not None:
                if unicode(s) == u'|':
                    propdic[u'S'] = s
                else:
                    self.badTableParm(u'Only stile supported for Side option')
        else : # not C(stuff) but n(stuff), allow S' ' to override
            s = self.getStringOption(copts, u'S')
            if s is not None:
                if unicode(s) == u' ':
                    propdic[u'S'] = None
                else:
                    self.badTableParm(u'Only space supported for Side option')
           
    # Error message to user about a problem with the /T line
    def badTableParm(self,msg):
        pqMsgs.warningMsg(
            u'Problem with Table at line {0}'.format(self.tLineNumber), msg)
    #
    # Here follow all the accessor methods to retrieve the stored properties.
    # This class only returns defined properties, so e.g. width can come back
    # as None. The tableCells class deals in actual data so it returns a
    # width based on data contents at that time.
    #
    def isMultiLine(self):
        return self.isMulti
    def isSingleLine(self):
        return not self.isMulti
    def tableWidth(self):
        return self.tProps[u'W']
    def tableSideString(self):
        return self.tProps[u'S']
    def tableTopString(self):
        return self.tProps[u'T']
    def columnBottomString(self):
        return self.cProps[u'B']
    def columnSideString(self): # will be None or QString('|') reflecting C()
        return self.cProps[u'S']
    # return a column property for a given column: the one specified for that
    # column alone, or the generic one from C(xx) if not.
    def someColumnValue(self,c,key):
        c = unicode(c) # convert integer column to character key
        if c in self.c1to9Props:
            return self.c1to9Props[c][key]
        return self.cProps[key]
    def oneColumnDelimiter(self,c) : # will be None or QString('|') reflecting n()
        return self.someColumnValue(c,u'S')
    def oneColumnSideString(self,c) : # will be QString('  ') or QString('|')
        qs = self.oneColumnDelimiter(c)
        return qs if qs is not None else QString('  ')
    def columnAlignment(self,c):
        return self.someColumnValue(c,u'A')
    def columnFractionWidth(self,c):
        return self.someColumnValue(c,u'F')
    def columnIntegerWidth(self,c):
        return self.someColumnValue(c,u'W')
    def columnWidth(self,c):
        w = self.someColumnValue(c,u'W') # specific width if given
        f = self.someColumnValue(c,u'F') # fraction width if given
        if f is not None:
            # if f was defined, so was w, return the width including decimal
            return w + f +1
        return w # return width or None
    def columnDecimal(self,c):
        return self.someColumnValue(c,u'D')
        

# Oh sigh, how to store cell data for easy retrieval? We are doing the obvious,
# a list, of which each member is a list of the cell data for that row across.
# Each cell is a single QString. In a multi-line table it is the concatenation
# of the values from each line of that cell, with a space between.
#
# While storing content we also save metadata on a per-column basis:
# self.cMinWidths and self.cDecWidths store the necessary minimum width for
# each column, in case that should exceed what the user specified.
# When alignment is R/L/C, cDecWidth is zero and cMinWidth has
# the length of the longest space-delimited token seen in that column, thus
# the minimum width the column must have.
#
# When alignment is Decimal, cMinWidth has the longest nonblank string seen
# left of a decimal point, and cDecWidth has the longest string seen right
# of a decimal point including the point. Thus for all alignments, the 
# required minimum is cMinWidth+cDecWidth.
# Also stored: the "suggested" width, the longest UNtrimmed string seen for
# any cell.
class tableCells:
    def __init__(self,propsObject) :
        self.tProps = propsObject # save a reference to table properties
        self.multi = self.tProps.isMultiLine()
        self.single = not self.multi # save for convenient coding
        # columns are numbered 1..columnsSeen
        self.columnsSeen = 0 # haven't seen any as yet
        # rows are numbered 1..rowsSeen
        self.rowsSeen = 0 # none of those as yet
        # largest single data-chunk width per column, or left of decimal
        self.cMinWidths = []
        # largest string seen right of a decimal incl. the decimal
        self.cDecWidths = []
        # largest actual cell width seen per column
        self.cSugWidths = []
        # list of cell data strings for each row
        self.data = []
        self.lastRowIndex = None # index of current row
        self.row = None # reference to current row's list of data
        # an RE used to find nonblank tokens. We can't assume the tokens
        # are words, hence can't use \b\w+\b, so we have to look for \s*\S+
        self.tokenRE = QRegExp(u'\s*(\S+)')
        self.tokenRE.setMinimal(False) # greedy to get whole token

    # Store the string qs as data for cell r:c. Note the minimum width it
    # implies based on this column's alignment.
    # Also note the "suggested" width, the actual size including whitespace.
    def store(self,r,c,qs):
        if r != self.lastRowIndex: # starting a new row
            if (r > self.rowsSeen) and (r == (len(self.data) + 1)):
                self.rowsSeen = r
                self.data.append([]) # new list of row values
                self.lastRowIndex = r
                # save a reference (not a copy, this is Python) to the row's data
                self.row = self.data[r-1]
            else: # should never happen
                raise ValueError, "major cock-up in storing table rows"
        if c > self.columnsSeen :
            if c != (self.columnsSeen+1) :
                print("minor cock-up storing table columns")
                c = self.columnsSeen+1
            # first data stored for this column  
            self.columnsSeen = c
            # initialize the suggested and minimum widths for this column
            self.cSugWidths.append(0)
            w = self.tProps.columnIntegerWidth(c)
            self.cMinWidths.append(0 if w is None else w)
            f = self.tProps.columnFractionWidth(c)
            self.cDecWidths.append(0 if f is None else f)
        # save the suggested width based on the un.simplified string
        self.cSugWidths[c-1] = max(self.cSugWidths[c-1],qs.size())
        # get a copy of the data with leading & trailing spaces dropped
        # and internal runs of spaces reduced to single spaces. This stripped
        # version is what we save and return.
        qst = qs.simplified()
        if c > len(self.row):
            # first sight of this column in this row, append this datum
            self.row.append(qst)
        else:
            # second or later line of a multi-line cell, append with a space
            self.row[c-1].append(QString(u' '))
            self.row[c-1].append(qst)
        # work out min/dec widths based on alignment
        if CalignDecimal != self.tProps.columnAlignment(c):
            # align L/R/C, save the longest needed width
            if self.single :
                # single-line table, just note trimmed size
                self.cMinWidths[c-1] = max(self.cMinWidths[c-1],qst.size())
            else:
                # multi-line table, data for this cell may already exist
                # Increase the minimum cell width if necessary, based on the
                # longest nonblank token in the new string.
                w = self.cMinWidths[c-1] # widest token seen so far
                j = self.tokenRE.indexIn(qs) # index of first nonblank sequence
                while j > -1:
                    w = max(w, self.tokenRE.cap(1).size()) # note widest token
                    # find next token after the matched one, if any
                    j = self.tokenRE.indexIn(qs,j+self.tokenRE.matchedLength())
                self.cMinWidths[c-1] = w # put possibly-updated width back
        else:
            # Decimal alignment. Not checking if this is the first & only 
            # value for the cell; decimal can be used in a multi-line table,
            # with the numeric value preceded or followed by empty "@" lines.
            d = self.tProps.columnDecimal(c) # period or comma or whatever
            # Find the 0-based index of the rightmost decimal delimiter in the
            # string, and set the string size if it is not found
            j = qst.lastIndexOf(d)
            if j < 0 : j = qst.size()
            # Set cDecWidths based on the position of the decimal point: set
            # to zero if no point was seen, 1 if the point is the last char
            # in the string, else the width of the point and following digits.
            self.cDecWidths[c-1] = max(self.cDecWidths[c-1],qst.size()-j)
            # and set cMinWidths based on the string left of the point
            self.cMinWidths[c-1] = max(self.cMinWidths[c-1],j)

    # Return the highest count of columns stored for any row. Note it is
    # possible for some rows to be short, if one or more columns were omitted.
    # Assumption: this won't be called until all data has been stored and so
    # all columns have been seen.
    def columnCount(self):
        return self.columnsSeen

    # Return the count of rows stored. Again, assume that all data has been
    # collected before this is called.
    def rowCount(self):
        return self.rowsSeen

    # Return the data string for a given cell, given r and c. On the assumption
    # that rows will be read out sequentially, save the row for future use.
    # In the event a row is valid but no column was stored, return an empty
    # QString. This is not necessarily an error, since empty cells on the
    # right can be omitted. But for a row or column beyond what we saw
    # during fetching, or negative, return a null QString and print an error.
    def fetch(self,r,c):
        if r != self.lastRowIndex:
            if (r > len(self.data)) or (r < 1):
                return self.badFetch(r,c)
            self.lastRowIndex = r
            self.row = self.data[r-1]
        if (c <= self.columnsSeen) and (c > 0) :
            # We have stored this column in at least some row
            if c <= len(self.row): 
                # We stored data for this column in this row
                return self.row[c-1]
            else:
                # We seem to have missed this column in this row
                return QString(u'') # return empty (not null) qstring
        return self.badFetch(r,c)

    def badFetch(self,r,c):
        print("Reference to unstored data at "+unicode(r)+"/"+unicode(c))
        return QString()
    def badColumn(self,c):
        print("Reference to unstored column "+unicode(c))
        return 0
    # Return the minimum width of column c. This was initialized from the
    # table properties and updated with actual data.
    def columnMinWidth(self,c):
        if c <= self.columnsSeen:
            return self.cMinWidths[c-1] + self.cDecWidths[c-1]
        return self.badColumn(c)
    # Return the suggested width of column c, the longest actual string
    # (blanks included) that was stored; but never less than the minimum width.
    def columnSugWidth(self,c):
        if c <= self.columnsSeen:
            return max(self.cSugWidths[c-1],self.columnMinWidth(c))
        return self.badColumn(c)
    def columnDecWidth(self,c):
        if c <= self.columnsSeen:
            return self.cDecWidths[c-1]
    # pass-thru of align and decimal values so they can be gotten via a tableCells
    def columnAlignment(self,c):
        return self.tProps.columnAlignment(c)
    def columnDecimal(self,c):
        return self.tProps.columnDecimal(c)

# Reflow a table, based on the sequence of "work units" as developed in
# pqFlow. Arguments are: doc is a QTextDocument, tc is the textCursor over
# it on which a single undo/redo macro has been started. unitList is the
# slice of the pqFlow unitList from the /T[M] line to the T/ line inclusive.
# For reference the relevant elements of a work unit are (see pqFlow for
# the full general list):
# 'T' : type of work unit, specifically
#    'M' markup of type 'T' starts
#    'P' line of table data
#    '/' markup ends
# 'M' : the type of markup starting, in effect, or ending:
#    'T'
# 'A' : text block number of start of the unit (line number)
# 'L' : left margin when markup started (table might conceivably be nested),
# 'R' : right margin indent if in a nested section
# 'B' : the count of blank lines that preceded this unit - used to spot
#       break between rows in a multiline table

# global regex used to split data line on delimiters which are either
# 2+ spaces or a stile with optional spaces.
splitRE = QRegExp(u'( {2,}|\s*\|\s*)')

def tableReflow(tc,doc,unitList):
    # Note the properties of the table including specified width, multiline etc.
    tprops = tableProperties(getLineQs(tc,doc,unitList[0]['A']))
    # If the width wasn't spec'd then develop a target width based on the
    # current max line width less any indents in the first work unit.
    # Take L and R from the first "real"
    # work unit, as the markup-start unit doesn't get the indent.
    targetTableWidth = tprops.tableWidth()
    availableTableWidth = unitList[0]['W'] - unitList[1]['L'] - unitList[1]['R']
    if targetTableWidth is None: # user did not spec T(W:)
        targetTableWidth = availableTableWidth
    else:
        # user did spec it but maybe was too optimistic - use the lesser value
        targetTableWidth = min(targetTableWidth,availableTableWidth)
    # make a table cells storage object
    tcells = tableCells(tprops)
    # note if the table has a hyphenated top line
    topChar = tprops.tableTopString()
    # note if the cells have hyphenated bottom lines
    botChar = tprops.columnBottomString()
    # decide what work units to process. The first and last are the markup
    # start/end units, skip those. If there is a top-line, skip that also.
    work = range(1,len(unitList)-1)
    if topChar is not None:
        qs = getLineQs(tc,doc,unitList[1]['A']) # fetch text of first line
        if qs.size() == qs.count(topChar):
            # top string is spec'd and there is a top string of ---
            del work[0] # don't process it
    r = 1 # current row number 1..
    for u in work:
        unit = unitList[u]
        qs = getLineQs(tc,doc,unit['A'])
        #dbg = unicode(qs)
        if botChar is not None:
            if qs.size() == qs.count(botChar):
                # this line consists entirely of hyphens, treat as blank
                if tprops.isMultiLine():
                    r += 1 # start a new multiline row
                continue # single or multi, ignore the divider line
        # line is not all-hyphens (or botchars not spec'd) (and not all-blank
        # because all-blanks are not included as work units), however if
        # if unit['B'] is nonzero it was preceded by a blank line, and that
        # indicates a new row in a multiline table -- except the first line!
        if (unit['B'] > 0) and tprops.isMultiLine() and u != work[0]:
            r += 1 # start a new multiline row

        # Bust the line into pieces based on spaces and/or stiles, and
        # stow the pieces numbered sequentially as columns. When stiles are
        # used for the outer columns, .split returns null strings which we discard.
        qsl = qs.split(splitRE)
        if qsl[0].isEmpty() :
            qsl.removeAt(0)
        if qsl[qsl.count()-1].isEmpty():
            qsl.removeAt(qsl.count()-1)
        c = 1
        for cqs in qsl:
            #dbg = unicode(cqs)
            tcells.store(r,c,cqs)
            c += 1
        # If this is a single-line table, increment the row number.
        if tprops.isSingleLine():
            r += 1
    # All text lines of the table have been split and stored in their 
    # logical row/column slots. Now figure out how wide to make each column.
    # The input to this is targetTableWidth, developed above for the table as a
    # whole, and targetDataWidth which we are just about to calculate:
    # Initial delimiter is 0 when columns are space-delimited, else 1 for '|'
    totalDelimiterWidths = 0 if tprops.oneColumnDelimiter(1) is None else 1
    # delimiters between columns are 2 for spaces, 1 for stile.
    for c in range(2,tcells.columnCount()+1):
        totalDelimiterWidths += 2 if tprops.oneColumnDelimiter(c) is None else 1
    # add the right side delimiter
    tableSideString = tprops.tableSideString()
    if tableSideString is None:
        tableSideString = QString(u'')
    totalDelimiterWidths += tableSideString.size() # add the stile on the right
    # Now, how much room for column data?
    tableDataWidth = targetTableWidth - totalDelimiterWidths
    # targetDataWidth is how many chars of data we ought to have. How much do
    # we really have? Develop a list of column "suggested" widths, the actual
    # width of the longest string stored in each column, and its total.
    totalSugWidth = 0
    allSugWidths = [9999] # junk 0th element: cols number by 1
    for c in range(1,tcells.columnCount()+1):
        csw = tcells.columnSugWidth(c)
        allSugWidths.append(csw)
        totalSugWidth += csw
    # If the suggested width is greater than available, adjust somehow:
    if totalSugWidth > tableDataWidth:
        if tprops.isMultiLine() :
            # For a multiline table where we can fold cell contents, we can
            # try to adjust sug widths down toward min widths.
            totalMinWidth = 0
            allMinWidths = [9999] # cell 0 ignored
            for c in range(1,tcells.columnCount()+1):
                cmw = tcells.columnMinWidth(c)
                allMinWidths.append(cmw)
                totalMinWidth += cmw
            if totalMinWidth > tableDataWidth:
                # The minimum (longest token) widths exceed the specified 
                # table. We will use the min widths but warn the user.
                warnWideTable(unitList[0]['A'],targetTableWidth,
                              totalMinWidth+totalDelimiterWidths)
                totalSugWidth = totalMinWidth
                allSugWidths = allMinWidths
                targetTableWidth = totalMinWidth+totalDelimiterWidths
            else:
                # totalMinWidth < (or equal) to tableDataWidth. Reduce the columns
                # with the most flexibility (the greatest difference between
                # suggested width and min width) by 1, until
                # totalSugWidth == tableDataWidth.
                spaceRatios = [0.1]
                for c in range(1,tcells.columnCount()+1):
                    spaceRatios.append(allSugWidths[c]/allMinWidths[c])
                while totalSugWidth > tableDataWidth:
                    c = spaceRatios.index(max(spaceRatios))
                    allSugWidths[c] -= 1
                    spaceRatios[c] = allSugWidths[c]/allMinWidths[c]
                    totalSugWidth -= 1
        else: # single-line table, just force the table to what we need
            warnWideTable(unitList[0]['A'],
                          targetTableWidth,totalSugWidth+totalDelimiterWidths)
            tableDataWidth = totalSugWidth
            targetTableWidth = tableDataWidth+totalDelimiterWidths
    # One way or another, totalSugWidth is now <= tableDataWidth. The above
    # labored logic dealt with it being greater. Now, if it is LESS, we will
    # pad the columns until it is equal. Which columns to pad? The columns
    # that don't have specific widths assigned to them. If all columns have
    # specific widths, totalSugWidth will remain < tableDataWidth.
    if totalSugWidth < tableDataWidth :
        colsWithoutSpecWidth = []
        for c in range(1,tcells.columnCount()+1):
            if tprops.columnWidth(c) is None :
                colsWithoutSpecWidth.append(c)
        n = len(colsWithoutSpecWidth)
        if 0 < n :
            x = int((tableDataWidth-totalSugWidth)/n)
            for c in colsWithoutSpecWidth :
                allSugWidths[c] += x
                totalSugWidth += x
            x = tableDataWidth - totalSugWidth
            if x : # fraction left over, dump in the first
                allSugWidths[colsWithoutSpecWidth[0]] += x
                totalSugWidth += x

    # Now, totalSugWidth <= tableDataWidth and allSugWidths is the list of
    # target column widths. Fill the rows, aligning cell values as requested.
    # We will accumulate one whomping QString for the whole table, and
    # finally insert it using textCursor tc replacing the table.
    # flowCell returns a QStringList with one string for each text line needed
    # to fit the cell data in the width, just one string for a single line table.
    tableText = QString() # Accumulates whole table a line at a time    
    # this list holds the cell data for one row at a time as QStringLists
    rowdata = [None]*(tcells.columnCount()+1)
    # set the head of each text line, indent with optional stile
    leftIndent = QString(u' ' * unitList[1]['L']) # indent by L
    lineStart = QString(leftIndent)
    if tprops.oneColumnDelimiter(1) is not None:
        lineStart.append(tprops.oneColumnSideString(1)) # plus optional stile
    # set the right-side delimiter of stile or nothing
    lineEnd = QString(tableSideString)
    # set the between-rows constant of nothing, linebreak, or hyphens+linebreak
    cellBottom = QString() # nothing, for a single-line table with no botChar
    if botChar is not None:
        cellBottom = QString(leftIndent) # divider starts with indent
        cellBottom.append(botChar.repeated(targetTableWidth))
        cellBottom.append(IMC.QtLineDelim)
    else: # even if no botChar, multiline table still needs empty lines
        if tprops.isMultiLine() :            
            cellBottom.append(IMC.QtLineDelim)
    # accumulate the table top delimiter if requested
    if topChar is not None:
        tableText.append(leftIndent)
        tableText.append(topChar.repeated(targetTableWidth))
        tableText.append(IMC.QtLineDelim)
    # process all logical rows in sequence top to bottom
    for r in range(1,tcells.rowCount()+1):
        asciiLines = 0 # counts how many ascii lines in this logical row
        # process all cells in this row, left to right. flowCell() 
        # returns a QStringList of the flowed data for the cell given
        # its width and alignment style.
        for c in range(1,tcells.columnCount()+1):
            rowdata[c] = flowCell(tcells.fetch(r,c), allSugWidths[c],
                tcells.columnAlignment(c), tcells.columnDecimal(c),
                tcells.columnDecWidth(c))
            asciiLines = max(asciiLines,rowdata[c].count())
        # read out each line x of each cell across a text line, with delimiters
        for x in range(asciiLines):
            qsLine = QString(lineStart) # start with a copy of the indent
            for c in range(1,tcells.columnCount()+1):
                if rowdata[c].count() > x: # this cell has data on line x
                    cqs = rowdata[c][x]
                else: # this cell is empty on line x, fill with spaces
                    cqs = QString(u' ' * allSugWidths[c])
                if c < tcells.columnCount() :
                    # add internal cell delimiter of 2 spaces or 1 stile
                    cqs.append(tprops.oneColumnSideString(c))
                qsLine.append(cqs)
            # finish the line: append the stile border, or strip trailing spaces.
            if lineEnd.isEmpty():
                # sadly, QString doesn't support rstrip.
                qsLine = QString(unicode(qsLine).rstrip())
            else:
                qsLine.append(lineEnd)
            #dbg = unicode(qsLine)
            tableText.append(qsLine)
            tableText.append(IMC.QtLineDelim)
        # If this is not the last row, or even if it is and a bottom string
        # is specified, append bottom delimiter string
        if (r < tcells.rowCount()) or (botChar is not None):
            tableText.append(cellBottom) # finish logical row

    # Finally, point the text cursor at the entire span of lines between
    # but not including the /T and T/ lines and replace it with tableText.
    firstTableLine = unitList[1]['A']
    lastTableLine = unitList[-2]['A']
    firstBlock = doc.findBlockByNumber(firstTableLine)
    lastBlock = doc.findBlockByNumber(lastTableLine)
    tc.setPosition(firstBlock.position()) # click
    tc.setPosition(lastBlock.position()+lastBlock.length(),
		               QTextCursor.KeepAnchor) # and shift-click
    tc.insertText(tableText)
    # bye-eeeeee

# Given the data of one cell as a single QString, fold or stretch it into a
# specified width, aligned as specified. Return a QStringList with one 
# QString per ascii line of folded text: 1 for a single line table, 1 or more
# for a multiline table. The problem is similar to the paragraph folder in
# pqFlow but simpler. We are not supporting logical lengths of <i/b/sc> for one
# thing. (That's TBS, for now use the skip button to stop table reflow until the
# markups are gone.) It is more complex in that we may have to center, right,
# or decimal-align, and deal with @ place-holders.
chunkRE = QRegExp()
def flowCell(qs,width,align,decpoint,decwidth):
    qs = expandAt(qs,width,align) # deal with @ tokens
    #dbg = unicode(qs)
    if qs.size() <= width :
        # entire cell data fits in the width, return one-string list
        return QStringList(alignCell(qs,width,align,decpoint,decwidth))
    # string is greater than width -- we assert this cannot occur in a 
    # single-line table. So we will fold qs into multiple strings. Now let us
    # chunk qs into whitespace-delimited chunks up to width in size.
    qs.append(u' ') # ensure terminal space: last good char is at size-2
    chunkRE.setPattern(u'\s*(\S.{,'+str(width-1)+u'})\s')
    qsl = QStringList()
    j = chunkRE.indexIn(qs,0)
    while j > -1 :
        qsl.append(alignCell(chunkRE.cap(1),width,align,decpoint,decwidth))
        j += chunkRE.cap(0).size()
        j = chunkRE.indexIn(qs,j)
    return qsl    

# The user is told to stick in @ as a place-holder in any row where there
# is no real data. However the input process (using splitRE above) strips
# spaces. So if we don't put the spaces back, the @s from successive lines
# get flowed into a single line and then the table can't be flowed twice
# which violates our desire that any markup be re-flowable over and over.
# So, find any @+ sequence and expand it to be width chars long as the
# user presumably wrote it in the first place.
findAtRE = QRegExp(u'\s*@+\s*')
def expandAt(qs,width,align):
    #dbg = unicode(qs)
    j = findAtRE.indexIn(qs,0)
    if j < 0 : return qs # there were no @s
    q2 = QString()
    w = width-1
    while j > -1 :
        if j > 0 :
            q2 = qs.left(j)
        q2.append(QString( (u' '*w)+u'@') )
        qs.remove(0,j+findAtRE.cap(0).size())
        j = findAtRE.indexIn(qs,0)
    #dbg = unicode(q2)
    return q2        
# Given a QString that fits in a width, extend it front a/o back to
# align in that width.
def alignCell(qs,width,align,decpoint,decwidth):
    qs = qs.simplified() # strip off any spaces expandAt may have added
    spaces = width - qs.size()
    if spaces > 0 : 
        lspace = QString(u'')
        rspace = QString(u'')
        onespace = QChar(u' ')
        # There are some spaces to distribute, but on which side?
        if align == CalignLeft :
            rspace.fill(onespace, spaces)
        elif align == CalignRight :
            lspace.fill(onespace, spaces)
        elif align == CalignCenter :
            # centering, put an odd space, if any, on the right
            lspace.fill(onespace, int(spaces/2))
            rspace.fill(onespace, spaces-lspace.size())
        else:
            # decimal alignment: add right spaces sufficient to make the
            # decimal points line up, and left to reach the width.
            j = qs.lastIndexOf(decpoint)
            if j < 0 : j = qs.size()
            rspace.fill(onespace,decwidth-(qs.size()-j))
            lspace.fill(onespace,spaces-rspace.size())
        qs.prepend(lspace)
        qs.append(rspace)
    #dbg = unicode(qs)
    return qs
    
# warn the user a table will be wider than expected/requested
def warnWideTable(lnumber,twidth,awidth):
    pqMsgs.warningMsg(
        u'Data in table at line '+str(lnumber)+
        u' exceeds '+str(twidth),
        u'Actual width to be used is '+str(awidth)
        )

# return the text of a line given its linenumber, as a QString.
# trim any whitespace, esp. the newline (2027).
def getLineQs(tc,doc,lineNumber):
    textBlock = doc.findBlockByNumber(lineNumber)
    tc.setPosition(textBlock.position()) # click..
    tc.setPosition(textBlock.position()+textBlock.length(),QTextCursor.KeepAnchor)
    return tc.selectedText().trimmed()
   
# return the unicode text of a line given its line number. as a byproduct
# sets the text cursor selecting that line's text
def getLineText(tc,doc,lineNumber):
    return unicode(getLineQs(tc,doc,lineNumber))

# OK here we have the much simpler job of converting a /T markup into
# HTML. Parse the /T[M] line as a tableProperties. From this we can pull
# the specified table width and any specified column widths. These are
# converted to percentage values based on the ascii line and inserted as
# style='width:nn%;'
# Then collect all the rows into a tableCells object. Read them out
# row by row and insert them as <tr> and <td> items. Where the column is
# aligned C or R, we insert class='TC' or class='TR' into the <td>.

def tableHTML(tc,doc,unitList):
    tprops = tableProperties(getLineQs(tc,doc,unitList[0]['A']))
    # if the table width was specified, figure its percentage based
    # on the line width in effect (the table might be nested, e.g.).
    twpct = None
    twasc = unitList[0]['W'] - unitList[1]['L'] - unitList[1]['R']
    twidth = twasc
    if tprops.tableWidth() is not None:
        twidth = min(twasc,tprops.tableWidth())
    if twidth != twasc :
        twpct = int(100*twidth/twasc)
    # Get percent widths for any columns that were given a W: spec
    # syntax only supports cols 1-9. Use a dict, not a list, so if the actual
    # data has >9 cols we don't try to test it.
    cwpct = {}
    for c in range(1,10):
        if tprops.columnWidth(c) is not None:
            cwpct[c] = int(100*tprops.columnWidth(c)/twidth)
    # create a tcells object to store column data
    tcells = tableCells(tprops)
    # note if the table has a hyphenated top line or cell dividers
    topChar = tprops.tableTopString()
    botChar = tprops.columnBottomString()
    # decide what work units to process. The first and last are the markup
    # start/end units, skip those. If there is a top-line, skip that also.
    work = range(1,len(unitList)-1)
    if topChar is not None:
        qs = getLineQs(tc,doc,unitList[1]['A']) # fetch text of first line
        if qs.size() == qs.count(QChar(topChar)):
            # top string is spec'd and there is a top string of ---
            del work[0] # don't process it
    r = 1 # current row number 1-n, used to store in tcells
    for u in work:
        unit = unitList[u]
        qs = getLineQs(tc,doc,unit['A'])
        if botChar is not None:
            if qs.size() == qs.count(QChar(botChar)):
                # this line consists entirely of hyphens, treat as blank
                if tprops.isMultiLine():
                    r += 1 # start a new multiline row
                continue # ignoring the divider line
        # line is not all-hyphens (or hyphens not spec'd), and not all-blank
        # because all-blanks are not included as work units, but if unit['B']
        # is nonzero it was preceded by a blank line.
        if tprops.isMultiLine() and (unit['B'] > 0):
            r += 1 # start a new multiline row
        # Bust the line into pieces based on spaces and/or stiles, and
        # stow the pieces numbered sequentially as columns. When stiles are
        # used for the outer columns, .split returns null strings which we discard.
        qsl = qs.split(splitRE)
        if qsl[0] == u'' :
            qsl.removeAt(0)
        if qsl[qsl.count()-1] == u'':
            qsl.removeAt(qsl.count()-1)
        c = 1
        for cqs in qsl:
            tcells.store(r,c,cqs)
            c += 1
        # If this is a single-line table, increment the row number.
        if tprops.isSingleLine():
            r += 1
    # All the cell data are stored, prepare the table text as a big string
    # starting with the <table> or <table style='width:p%;'> line
    if twpct is None:
        t = u'<table>'
    else:
        t = u'<table style="width:{0:d}%;">'.format(twpct)
    tqs = QString(t)
    tqs.append(IMC.QtLineDelim)
    # Build up the table row by row.
    tds = u'    <td{0}{1}>' # template for <td class='Tx' style='width:x%'>
    tdz = QString(u'</td>')  # constant end of table cell
    trz = QString(u'  </tr>')  # constant end of table row
    tac = u' class="c"' # constant for align-center
    tar = u' class="r"' # constant for align-right
    qat = QString(u'@')
    qnb = QString(u'&nbsp;')
    for r in range(1,tcells.rowCount()+1):
        tqr = QString(u'  <tr>') # constant to start a row, indented
        tqr.append(IMC.QtLineDelim) # linebreak before data cells
        #  Build one row cell by cell. Handle alignment with a class,
        # <td> for left, <td class='TR'> or <td class='TC'>.  In the first row,
        # add <style='width:pp%;'> for columns with specified widths.
        for c in range(1,tcells.columnCount()+1):
            al = tprops.columnAlignment(c)
            if al is None: al = CalignLeft
            if al == CalignLeft: al = u''
            elif al == CalignCenter: al = tac
            else: # right or decimal both get right, HTML has no decimal align
                al = tar
            wd = u''
            if (r == 1) and (c in cwpct) :
                wd = u' style="width:{0:d}%;"'.format(cwpct[c])
            # get the data for the cell
            cqs = tcells.fetch(r,c)
            # change any @ to &nbsp;
            cqs.replace(qat,qnb)
            td = tds.format(al,wd) # make <td> with align, width
            tqr.append(QString(td)) # <td...>
            tqr.append(cqs) # ..stuff .. 
            tqr.append(tdz) # </td>
            tqr.append(IMC.QtLineDelim)
        tqr.append(trz) # </tr>
        tqs.append(tqr)
        tqs.append(IMC.QtLineDelim)
    # the </table> was done by realHTML when it saw T/, so replace
    # the whole table except the last line with the text we have
    blockA = doc.findBlockByNumber(unitList[0]['A'])
    blockZ = doc.findBlockByNumber(unitList[-2]['A'])
    tc.setPosition(blockA.position())
    tc.setPosition(blockZ.position()+blockZ.length(),QTextCursor.KeepAnchor)
    tc.insertText(tqs)
    
    
    
    
if __name__ == "__main__":
    import sys
    from PyQt4.QtCore import (Qt)
    from PyQt4.QtGui import (QApplication)
    import pqIMC
    app = QApplication(sys.argv) # create an app
    IMC = pqIMC.tricorder() # set up a fake IMC for unit test
    IMC.fontFamily = QString("Courier")
    import pqMsgs
    pqMsgs.IMC = IMC
    #IMC.editWidget = QPlainTextEdit()
    #IMC.editWidget.setFont(pqMsgs.getMonoFont())

    tp = tableProperties(QString(u"/t T(A:C T:'-' S:'|') Col(B:'-' S:'|') 3(A:R W:8)"),1599)
    print('tw ',tp.tableWidth())
    print('ts ',tp.tableSideString())
    print('tt ',tp.tableTopString())
    print(tp.columnWidth(1))
    print(tp.columnWidth(3))
    tc = tableCells(tp)
    tc.store(1,1,QString(' foobar '))
    tc.store(1,2,QString('    999.99'))
    tc.store(1,3,QString('eh?'))
    tc.store(1,1,QString('Furthermore, !#$@'))
    print('cd 1,1',unicode(tc.fetch(1,1)))
    print('cd 1,2',unicode(tc.fetch(1,2)))
    print('cd 1,3',unicode(tc.fetch(1,3)))
    print('cm 1',tc.columnMinWidth(1))
    print('cm 2',tc.columnMinWidth(2))
    print('cm 3',tc.columnMinWidth(3))
    print('cs 1',tc.columnSugWidth(1))
    print('cs 2',tc.columnSugWidth(2))
    print('cs 3',tc.columnSugWidth(3))
    print('er 1,4',unicode(tc.fetch(1,4)))
    print('er 2,1',unicode(tc.fetch(2,1)))
    print('er s 4',tc.columnSugWidth(4))
    print('er m 4',tc.columnMinWidth(4))
