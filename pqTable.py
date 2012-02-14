# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *
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
  * decimal alignment for cell contents.

Properties of a table as a whole:
    width: minimum count of characters,
            default is None meaning width is the line length F and R indents
            applied by any containing markup (table can be nested in e.g. Q)
    top-border fill character(s)
            default is None, meaning no top border,
            option is - (hyphen)
    left-side vertical border character
            default is None, meaning no left vertical border
            option is | (stile)

Properties of any single column:
    alignment: contents aligned left, center, right or decimal within the cell
            default is left
    decimal-delimiter: when alignment is decimal, a single char that delimits
            the fraction from the integer, e.g. a comma for a german book.
            (we don't use the Locale because the computer Locale is not 
            necessarily the subject book's Locale)
    width: minimum count of characters
            default is None, meaning width is whatever contents require
    bottom-border fill character
            default is space: no division in a single-line table, in a
                multi-line, bottom of each row is a line of spaces
            option is - (hyphen), bottom of each row is a line of ----
    right-side vertical border character
            default is None, meaning put two spaces to the right of all
                except for rightmost column
            option is | (stile), right side of all cells consists of |

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
        [Width:n]
        [Bottom:'-']
        [Side:'|']
        )
    ]
    [
        <number>(
        [Align:Left|Center|Right|Decimal]
        [Width:n]
        ) ...
    ]
In the above, square brackets and lowercase indicate optional items. There
is a resemblance to Python dict literals but simplified, no commas, keys not
quoted. The Column() spec sets defaults for all columns. The <number>() spec
sets values for a specific column <number> 1-9. A table may have more than 9
columns, but only columns 1-9 can be explicitly configured with this syntax.

/t T(T:'-' S:'|') Col(B:'-' S:'|') 2(A:C) 3(A:R W:8) 4(ALIGN:DECIMAL)
one  two  75  654321
three  @  200  .123456
t/

This should reflow to the following table:
-----------------------------------------    (top row from T(T:'-')
| one   | two |      75 | 654321        |
-----------------------------------------
| three |  @  |     200 |       .123456 |
-----------------------------------------

A constraint of this code is that all inner cells must be represented IN
EVERY LINE. Cells on the right can be omitted, but an empty cell or line of
a multi-line cell must filled out with a single @ when there is a non-empty
cell to its right. In HTML conversion, cell data consisting only of
@ is converted to &nbsp;. (If we do a "delete markup" operation for ascii,
it could replace @s with spaces, but they are easy enough to kill manually.)

What is passed to the table function is a textCursor (the one with the undo/redo
macro working) and the slice of the work unit list bounded by the opening and
closing /T[M] markup lines. (This lets us process only nonempty lines, and use the
B:n value to detect row boundaries in a multiline table.) The document is
available from IMC.

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

Some would disdain classes like these as "singleton factories." True, only one
of each is made in handling a given table, yet I think this is valid 
design for two reasons. One, it allows me to encapsulate all the work of
parsing and recalling the optional-specs in one place, and all of the
work of storing and recalling cell data in another, considering them separately
and apart from the general issue of scanning and replacing table text. And two,
the identical classes are useful for both ascii and html table processing,
so they are genuine abstractions.
'''
from PyQt4.QtCore import (Qt, QChar, QString, QStringList, QRegExp)
from PyQt4.QtGui import(QTextBlock, QTextCursor, QTextDocument)
import pqMsgs

# Global definitions used and returned by these classes:
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
    def __init__(self,tqs):
        # set up default table properties
        self.tProps = {'W':None, 'T':None, 'S':None}
        # set up default all-column properties: A:alignment,
        # B:bottom-sring, S:side-string, D:decimalpoint W:width F:Fraction
        self.cProps = {'A':CalignLeft, 'B':None, 'S':None, 'D':'.', 'W':None, 'F':None}
        # explicit properties of specific columns 1-9 here if supplied
        self.c1to9Props = {}
        # note if this is multiline: currently /TM versus /T
        self.isMulti = tqs.startsWith(QString(u'/TM'))
        self.parseRE = QRegExp()
        self.parseRE.setCaseSensitivity(Qt.CaseInsensitive) # ignore case 
        # set minimal so when looking for ), we stop with the first
        # if any of this code changes minimal it must save and restore it.
        self.parseRE.setMinimal(True) # when 
        # get the contents of a Table(something) if it exists
        topts = self.getMainOption(tqs,u'T')
        if topts is not None: # there is T(something), and topts has the something
            # pull a WIDTH:n option out of it if any, ignoring any fraction
            (w,f) = self.getWidthOption(topts)
            if w is not None:
                self.tProps['W'] = w
            # pull a TOP:'-' option if any
            s = self.getStringOption(topts, u'T')
            if s is not None:
                if unicode(s) == u'-':
                    self.tProps[u'T'] = s
                else:
                    pqMsgs.warningMsg(u'Only hyphen suppported for Top option')
            # pull a SIDE:'|' option if any
            s = self.getStringOption(topts, u'S')
            if s is not None:
                if unicode(s) == u'|':
                    self.tProps[u'S'] = s
                else:
                    pqMsgs.warningMsg(u'Only stile supported for Side option')
        # get the contents of a Column(something) if it exists
        copts = self.getMainOption(tqs,u'C')
        if copts is not None:
            # there is a Column(something) and copts is the something
            # pull default column options out of it, store in self.cProps
            self.getColumnOptions(copts,self.cProps,True)
        # collect specific column options 1()..9() if given
        for key in u'123456789':
            copts = self.getMainOption(tqs,key)
            if copts is not None:
                # there is a n(something) option, extract bits from it
                # and store in the dictionary.
                self.c1to9Props[key] = self.cProps.copy()
                self.getColumnOptions(copts,self.c1to9Props[key])

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
    # get a Width:nnn option string, returning the integer or None
    def getWidthOption(self,qs):
        # set RE pattern of Wxxxx:nnn, greedy to get all digits
        mopt = self.parseRE.isMinimal()
        self.parseRE.setMinimal(False)
        self.parseRE.setPattern(u'W\w*\s*\:\s*(\d+)(\.(\d+))?')
        wval = None
        fval = None
        if -1 < self.parseRE.indexIn(qs):
            # We have a hit on W:ddd and it may be, W:ddd.ddd
            (wval,ok) = self.parseRE.cap(1).toInt()
            (fval,ok) = self.parseRE.cap(3).toInt()
            if not ok : fval = None
            # however, do a sanity check on a large number
            if wval > 75 or fval > 75 :
                pqMsgs.warningMsg(u"Lines over 75 not allowed in ASCII etexts",
                    u"Ignoring width in "+qs)
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
        if opt.isNull() : # no hit on single quote, try "-"
            # set pattern for Xxxx:"x"
            self.parseRE.setPattern(initial+u'\w*\s*\:\s*\\\"([^\\\"]*)\\\"')
            self.parseRE.indexIn(qs)
            opt = self.parseRE.cap(1)
        if not opt.isNull() :
            if opt.size() > 1 :
                pqMsgs.warningMsg(u'only single-char delimiters allowed',
                                  u'Ignoring '+unicode(qs))
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
                    pqMsgs.warningMsg(u'Only hyphen suppported for Bottom option')
            s = self.getStringOption(copts, u'S')
            if s is not None:
                if unicode(s) == u'|':
                    propdic[u'S'] = s
                else:
                    pqMsgs.warningMsg(u'Only stile supported for Side option')
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
    def columnSideString(self):
        return self.cProps[u'S']
    # return a specific column property is one is coded, else the generic one
    def someColumnValue(self,c,key):
        c = unicode(c) # convert integer column to character key
        if c in self.c1to9Props:
            return self.c1to9Props[c][key]
        return self.cProps[key]
    def columnAlignment(self,c):
        return self.someColumnValue(c,u'A')
    def columnFractionWidth(self,c):
        return self.someColumnValue(c,u'F')
    def columnIntegerWidth(self,c):
        return self.someColumnValue(c,u'W')
    def columnWidth(self,c):
        return self.someColumnValue(c,u'W')+self.someColumnValue(c,u'F')
    def columnDecimal(self,c):
        return self.someColumnValue(c,u'D')
        

# Oh sigh, how to store cell data for easy retrieval? We are doing the obvious,
# a list of which each member is a list of the cell data  for that row across.
# Each cell is a single QString, in a multi-line table we concatenate the
# values from each line of a row with a space between.
#
# While storing we also save metadata on a per-column basis:
# self.cMinWidths and self.cDecWidths store the necessary minimum width for
# each column. When alignment is R/L/C, cDecWidth is zero and cMinWidth has
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
        self.tProps = propsObject
        self.multi = self.tProps.isMultiLine()
        self.single = not self.multi # save for convenient coding
        # columns numbered 1..columnsSeen
        self.columnsSeen = 0
        # rows numbered 1..rowsSeen
        self.rowsSeen = 0
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

    # Store the string qs as data for cell r:c. Note the minimum width it
    # implies based on this column's alignment.
    # Also note the "suggested" width, the actual size including whitespace.
    def store(self,r,c,qs):
        if r != self.lastRowIndex: # starting a new row
            if r > self.rowsSeen:
                # new row: assert r = len(self.data)+1, i.e. rows start at 1
                # and are only ever incremented by 1 and never skip.
                if r == (len(self.data) + 1):
                    self.rowsSeen = r
                    self.data.append([]) # new list of row values
                else: # should never happen
                    raise ValueError, "cock-up in storing rows"
            self.lastRowIndex = r
            # get a reference (not a copy, this is Python) to this row's data
            self.row = self.data[r-1]
        dbg = unicode(qs)
        if c > self.columnsSeen :
            # assuming c goes up sequentially 
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
            # Set cDecWidths based on the position of the decimal point, this
            # is zero if no point was seen, 1 if the point is the last char
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

    # Return the count of rows stored.
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
# 'B' : the count of blank lines that preceded this unit - used to spot
#       break between rows in a multiline table

# global regex used to split data line on delimiters which are either
# 2+ spaces or a stile with optional spaces.
splitRE = QRegExp(u'( {2,}| *\| *)')

def tableReflow(tc,doc,unitList):
    # Note the properties of the table including specified width, multiline etc.
    tprops = tableProperties(getLineQs(tc,doc,unitList[0]['A']))
    # If the width wasn't spec'd then develop a target width based on 75 less
    # any indent in the first work unit.
    targetTableWidth = tprops.tableWidth()
    if targetTableWidth is None:
        targetTableWidth = 75 - unitList[0]['F']
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
        if botChar is not None:
            if qs.size() == qs.count(botChar):
                # this line consists entirely of hyphens, treat as blank
                if tprops.isMultiLine():
                    r += 1 # start a new multiline row
                continue # single or multi, ignore the divider line
        # line is not all-hyphens (or hyphens not spec'd), and not all-blank
        # because all-blanks are not included as work units, but if unit['B']
        # is nonzero it was preceded by a blank line.
        if tprops.isMultiLine() and (unit['B'] > 0):
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
            tcells.store(r,c,cqs)
            c += 1
        # If this is a single-line table, increment the row number.
        if tprops.isSingleLine():
            r += 1
    # All text lines of the table have been split and stored in their 
    # logical row/column slots. Now figure out how wide to make each column.
    # The input to this is targetTableWidth, developed above for the table as a
    # whole, and targetDataWidth which we are just about to calculate:
    totalDelimiterWidths = 0
    cellDelimiterString = tprops.columnSideString()
    if cellDelimiterString is None:
        # no side stiles, delimit cells with 2 spaces
        cellDelimiterString = QString(u'  ') # internal delimiter
    else:
        # include the width of the left-edge stile in the delimiters
        totalDelimiterWidths = cellDelimiterString.size()
    # add widths of internal delimiters
    totalDelimiterWidths += cellDelimiterString.size() * (tcells.columnCount() - 1)
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
                # with the most flexibility until totalSugWidth == tableDataWidth.
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
    # labored logic dealt with it being greater. Now, if it is LESS, we need
    # to pad the columns until it is equal. Pad the smallest
    # leftmost columns first, simply because that is easier to calculate!
    # N.B. if you don't like these automatic adjustments, just specify the
    # table and column widths you want.
    while totalSugWidth < tableDataWidth:
        c = allSugWidths.index(min(allSugWidths))
        allSugWidths[c] += 1
        totalSugWidth += 1
    # Now, totalSugWidth == tableDataWidth and allSugWidths is the list of
    # target column widths. Fill the rows, aligning cell values as requested.
    # What we are going to do is, develop one whomping QString for the whole
    # table, then finally insert it using textCursor tc replacing the table.
    # flowCell returns a QStringList with one string for each ascii line needed
    # to fit the cell data in the given width -- just one for singleline.
    tableText = QString()
    if topChar is not None: # start with top line of ---s
        tableText.fill(topChar.at(0),targetTableWidth)
        tableText.append(IMC.QtLineDelim)
    # this list holds the cell data for one row at a time as QStringLists
    rowdata = [None]*(tcells.columnCount()+1)
    # set the left-side delimiter of stile or nothing
    lineStart = QString() if tprops.columnSideString() is None \
                           else cellDelimiterString
    # set the right-side delimiter of stile or nothing
    lineEnd = tableSideString
    # set the between-rows constant of nothing, linebreak, or hyphens+linebreak
    cellBottom = QString()
    if botChar is not None:
        cellBottom.fill(botChar.at(0),targetTableWidth)
        cellBottom.append(IMC.QtLineDelim)
    else:
        if tprops.isMultiLine() :
            # if no bottom string, multi still needs empty line
            cellBottom.append(IMC.QtLineDelim)
    # process all logical rows in sequence top to bottom
    for r in range(1,tcells.rowCount()+1):
        asciiLines = 0 # counts how many ascii lines in this logical row
        # process all cells in this row, left to right -- note if Python
        # had #include that's how flowCell would be coded- nested includes
        for c in range(1,tcells.columnCount()+1):
            rowdata[c] = flowCell(tcells.fetch(r,c), allSugWidths[c],
                tcells.columnAlignment(c), tcells.columnDecimal(c),
                tcells.columnDecWidth(c))
            asciiLines = max(asciiLines,rowdata[c].count())
        for x in range(asciiLines):
            # read out line x of each cell across a line, with delimiters
            qsLine = QString(lineStart) # making a copy
            for c in range(1,tcells.columnCount()+1):
                if rowdata[c].count() > x:
                    cqs = rowdata[c][x]
                else:
                    cqs = QString(u' ' * allSugWidths[c])
                qsLine.append(cqs)
                if c < tcells.columnCount() :
                    qsLine.append(cellDelimiterString) # add internal delimiter
            # finish the line
            qsLine.append(lineEnd)
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
# thing. That's TBS, for now use the skip button to stop table reflow until the
# markups are gone.) It is more complex in that we may have to center, right,
# or decimal-align.
chunkRE = QRegExp()
def flowCell(qs,width,align,decpoint,decwidth):
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
    
# Given a QString that fits in a width, extend it front a/o back to
# align in that width.
def alignCell(qs,width,align,decpoint,decwidth):
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
        dbg = unicode(qs)
        qs.prepend(lspace)
        qs.append(rspace)
        dbg2 = unicode(qs)
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
    twasc = 75 - unitList[0]['F']
    if tprops.tableWidth() is not None:
        twpct = int(100*tprops.tableWidth()/twasc)
    # Get percent widths for any columns that were given a W: spec
    # syntax only supports cols 1-9. Use a dict, not a list, so if the actual
    # data has >9 cols we don't try to test it.
    cwpct = {}
    for c in range(1,10):
        if tprops.columnWidth(c) is not None:
            cwpct[c] = int(100*tprops.columnWidth(c)/twasc)
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
    # Build up the table row by row. Handle alignment with a class,
    # <td> for left, <td class='r'> or <td class='c'>.  In the first row,
    # add <style='width:pp%;'> for columns with specified widths.
    tds = u'<td{0}{1}>'
    for r in range(1,tcells.rowCount()+1):
        tqr = QString(u'<tr>')
        for c in range(1,tcells.columnCount()+1):
            al = tprops.columnAlignment(c)
            if al is None: al = CalignLeft
            if al == CalignLeft: al = u''
            elif al == CalignRight: al = u' class="r"'
            else: al = u' class="c"'
            wd = u''
            if (r == 1) and (c in cwpct) :
                wd = u' style="width:{0:d}%;"'.format(cwpct[c])
            cqs = tcells.fetch(r,c)
            td = tds.format(al,wd)
            tqr.append(QString(td))
            tqr.append(cqs)
            tqr.append(QString(u'</td>'))
        tqr.append(QString(u'</tr>'))
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

    tp = tableProperties(QString(u"/t T(A:C T:'-' S:'|') Col(B:'-' S:'|') 3(A:R W:8)"))
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
