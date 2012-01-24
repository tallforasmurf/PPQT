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

/t optional-specs
table rows as multiple lines

separated by blank lines
t/

The optional-specs determine the layout of the table and of columns.

Properties of a table as a whole:
    width: minimum count of characters,
            default is None meaning width is whatever is needed
    top-border fill character(s)
            default is None, meaning no top border,
            option is - (hyphen)
    left-side vertical border character
            default is None, meaning no left vertical border
            option is | (stile)

Properties of any single column:
    alignment: contents aligned left, center, right or decimal within the cell
            default is left
    width: minimum count of characters
            default is None, meaning width is whatever contents require
    bottom-border fill character
            default is space, bottom of each row is a line of spaces
            option is - (hyphen), bottom of each row is a line of ----
    right-side vertical border character
            default is two spaces except for rightmost column, null
            option is | (applies to all)

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
sets values for a specific column <number> 1-9 (no others supported)

/t T(T:'-' S:'|') Col(B:'-' S:'|') 3:(A:R W:8)
one  two  75
three  @  200
t/

This should produce the following centered table:
--------------------------    (top row of hyphens from T(T:'-')
| one   | two  |      75 |    (T(S:'|') C(S:'|'))
--------------------------
| three | @    |     200 |
--------------------------

A constraint of this code is that all cells must be represented in the first
row (this is how we find out how many columns there are). After the first row,
data for cells on the right can be omitted. In general it is best to represent
every line of every cell of every row. One way to do this is to provide a
single @ character, as above. In HTML conversion, cell data consisting only of
@ is converted to &nbsp;. (If we do a "delete markup" operation for ascii,
it could replace @s with spaces, but they are easy enough to kill manually.)

A second way to represent an empty cell is to delimit it with stiles. That is,
the regex for a column delimiter is ( *\| *| {2,}) that is, a stile with 
any amount of spaces around it, or a sequence of 2 or more spaces. So the data
row above, "three  @  200" could also be given as "three| |200"

What is passed to the table function is a textCursor (the one with the undo/redo
macro working) and the slice of the work unit list bounded by the opening and
closing /t markup lines. (This lets us process only nonempty lines, and use the
B:n value to detect row boundaries in a multiline table.) The document is
available from IMC.

The code here parses the table. If errors are found it displays warnings and 
returns. When all is well, it develops the finished text and inserts it using
the textCursor.

We define two local classes. A tableProperties instance represents the values
defined in the /t statement, allowing the code to easily fetch information
about alignment, defined width, border and junction characters. For example,
    tp = tableProperties(QString("/T T(A:C T:'-' S:'|') Col(B:'-' S:'|') 3:(A:R W:8)")
    tp.tAlign() -> TalignCenter
    tp.cSide(1) -> '|' 
    tp.cWidth(2) -> None
    tp.cWidth(3) -> 8

A tableCells instance stores the cell values as they are discovered, and
returns them properly formatted when the table is rewritten. The related
tableProperties is part of initializing the tableCells, so it can return
either actual or specified widths,
    tc = tableCells(tp,multiLine=False)
    tc.store(rownum,1,QString("one")) # discovering the values of the example
    tc.store(rownum,2,QString("two"))
    tc.store(rownum,3,QString("75"))
    tc.cWidth(1) -> 4 based on len("one") + len(tp.cSide(1))
    tc.cWidth(2) -> 4 based on len("two") + len(tp.cSide(2))
    tc.cWidth(3) -> 10 based on tp.cWidth(3) + len(tp.cSide(3))

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
#CalignDecimal = 4 fuggedaboudit

SingleLineTable = 0
MultiLineTable = 1

class tableProperties:
    # For instantiation we receive the /T or /M line as a qstring.
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
        # set up default all-column properties
        self.cProps = {'A':CalignLeft, 'W':None, 'B':None, 'S':None}
        self.c1to9Props = {}
        # note if this is multiline: currently /TM versus /T
        self.isMulti = tqs.startsWith(QString(u'/TM'))
        self.parseRE = QRegExp()
        self.parseRE.setCaseSensitivity(Qt.CaseInsensitive) # ignore case 
        self.parseRE.setMinimal(True) # when looking for ) stop with the first
        # get the contents of a Table(something) if it exists
        topts = self.getMainOption(tqs,u'T')
        if topts is not None: # yes there is a Table(something) and topts==something
            w = self.getWidthOption(topts)
            if w is not None:
                self.tProps['W'] = w
            s = self.getStringOption(topts, u'T')
            if s is not None:
                if s == u'-':
                    self.tProps[u'T'] = s
                else:
                    pqMsgs.warningMsg(u'Only hyphen suppported for Top option')
            s = self.getStringOption(topts, u'S')
            if s is not None:
                if s == u'|':
                    self.tProps[u'S'] = s
                else:
                    pqMsgs.warningMsg(u'Only stile supported for Side option')
        # get the contents of a Column(something) if it exists
        copts = self.getMainOption(tqs,u'C')
        if copts is not None:
            # there is a Column(...) option so extract the bits from it
            self.getColumnOptions(copts,self.cProps,True)
        # collect specific column options 1()..9() if given
        for key in u'123456789':
            copts = self.getMainOption(tqs,key)
            if copts is not None:
                # there is a <x>(something) option, extract bits from it
                # and store in the dictionary.
                self.c1to9Props[key] = self.cProps.copy()
                self.getColumnOptions(copts,self.c1to9Props[key])

    # get a major option string Xxxx(something) and return the something
    def getMainOption(self,qs,key):
        dbg = unicode(qs)
        self.parseRE.setPattern(key + u'\w*\s*\((.+)\)')
        dbg2 = unicode(self.parseRE.pattern())
        if -1 < self.parseRE.indexIn(qs) :
            return self.parseRE.cap(1)
        return None
    # get an Align:keyword option string returning the initial or None
    def getAlignOption(self,qs,dAllowed=False):
        #dbg = unicode(qs)
        self.parseRE.setPattern(u'A\w*\s*\:\s*([LRC])\w*')
        if -1 < self.parseRE.indexIn(qs) :
            opt = unicode(self.parseRE.cap(1).toUpper()) # u'L R C or D'
            if (opt == u'D') and (not dAllowed) :
                pqMsgs.warningMsg("ALIGN:DECIMAL not allowed for Table",
                                  "found in " + unicode(qs) )
                return None
            else: return opt
        else: return None
    # get a Width:nnn option string, returning the integer or None
    def getWidthOption(self,qs):
        #dbg = unicode(qs)
        self.parseRE.setPattern(u'W\w*\s*\:\s*(\d+)')
        minimal = self.parseRE.isMinimal()
        self.parseRE.setMinimal(False) # need to suck up all the digits
        wval = None
        if -1 < self.parseRE.indexIn(qs):
            (wval,ok) = self.parseRE.cap(1).toInt()
            # do a sanity check on a large number
            if wval > 75 :
                pqMsgs.warningMsg(u"Lines over 75 not allowed in ASCII etexts",
                    u"Ignoring "+qs)
                wval = None
        self.parseRE.setMinimal(minimal) # restore regex
        return wval
    # Get a Xxxx:'str' or Xxxx:"str" option and convert to a proper literal.
    # Allow single or double quotes, unfortunately QRegExp does not allow
    # back-references inside character classes, e.g. ('|")([^\1]+)\1
    # so we have to run two separate re's. Originally we were going to allow
    # multiple chars and various chars and someday might, so this is more
    # general than strictly needed.
    def getStringOption(self,qs,initial):
        #dbg = unicode(qs)
        opt = None
        self.parseRE.setPattern(initial+u"\w*\s*\:\s*\\\'([^\\\']*)\\\'")
        if -1 < self.parseRE.indexIn(qs) :
            opt = self.parseRE.cap(1)
        else:
            self.parseRE.setPattern(initial+u'\w*\s*\:\s*\\\"([^\\\"]*)\\\"')
            if -1 < self.parseRE.indexIn(qs) :
                opt = self.parseRE.cap(1)
        if opt is not None :
            opt = unicode(opt)
            if len(opt) > 1 :
                pqMsgs.warningMsg(u'only single-char delimiters allowed',
                                  u'Ignoring '+qs)
                opt = None
        return opt
    # Given a Column(something) or <digit>(something), populate or update
    # a dict of properties with Align, Width, Bottom and Side values.
    def getColumnOptions(self,copts,propdic,main=False):
        a = self.getAlignOption(copts,True)
        if a is not None:
            propdic[u'A'] = {'L':CalignLeft,'R':CalignRight,'C':CalignCenter}[a]
        w = self.getWidthOption(copts)
        if w is not None:
            propdic['W'] = w
        if main:
            s = self.getStringOption(copts, u'B')
            if s is not None:
                if s == u'-':
                    propdic[u'B'] = s
                else:
                    pqMsgs.warningMsg(u'Only hyphen suppported for Bottom option')
            s = self.getStringOption(copts, u'S')
            if s is not None:
                if s == u'|':
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
    def columnAlignment(self,c):
        c = unicode(c)
        if c in self.c1to9Props:
            return self.c1to9Props[c][u'A']
        return self.cProps[u'A']
    def columnWidth(self,c):
        c = unicode(c)
        if c in self.c1to9Props:
            return self.c1to9Props[c][u'W']
        return self.cProps[u'W']
    def columnBottomString(self):
        return self.cProps[u'B']
    def columnSideString(self):
        return self.cProps[u'S']

# Oh sigh, how to store cell data for easy retrieval? 
# The obvious is a list of lists, which could be arranged by rows or
# columns, that is, a list of which each member is a list of the cells
# for that row across, or a list of which each member is a list of the
# cells for that column down. (Or of course, a dict where each key is 
# the catenation of r:c values.) All lend themselves about equally to for-loops.
# OK, K.I.S.S., do a list ordered by rows because the data will be read in
# and out by rows.
#
# And, do we need to store metadata as well as string data? Is the record of
# one cell a tuple, or maybe even we need a cellData class?
#
# No, we have metadata PER COLUMN, the minimum width needed and possibly
# the "suggested" width, that is the width between delimiters in the input.
# And PER TABLE, the number of columns and rows. But not per CELL, there the
# only metadata can be derived using len().
class tableCells:
    def __init__(self,propsObject) :
        self.tProps = propsObject
        self.multi = self.tProps.isMultiLine()
        self.single = not self.multi
        self.columnsSeen = 0
        self.rowsSeen = 0
        self.cMinWidths = []
        self.cSugWidths = []
        self.data = []
        self.lastRowIndex = None # index of current row
        self.row = None # reference to current row's list of data
        # an RE used to find nonblank tokens. We can't assume the tokens
        # are words, hence can't use \b\w+\b, so we have to look for \s*\S+
        self.tokenRE = QRegExp(u'\s*(\S+)')

    # Store the string qs as data for cell r/c. Note the minimum width it
    # implies: if single-line, the trimmed length; if multi-line, the length
    # of the longest non-blank token seen so far for that cell.
    # Also note the "suggested" width, the actual size including whitespace.
    def store(self,r,c,qs):
        if r != self.lastRowIndex: # new row
            if r > self.rowsSeen:
                # new row: assert r = len(self.data)+1, i.e. rows start at 1
                # and are only ever incremented by 1 and never skip.
                self.rowsSeen = r
                self.data.append([]) # new list of row values
            self.lastRowIndex = r
            # get a reference (not a copy, this is Python) to this row's data
            self.row = self.data[r-1]
        if c > self.columnsSeen :
            # assuming c goes up sequentially (and maxes out in row 1)
            self.columnsSeen = c
            # initialize the suggested and minimum widths for this column
            self.cSugWidths.append(0)
            w = self.tProps.columnWidth(c)
            self.cMinWidths.append(0 if w is None else w)
        if self.single : 
            # single-line table. assert c = 1+len(row)
            # Get a copy of the data with front & back whitespace trimmed
            qst = qs.trimmed()
            # Store the un-trimmed data in the row at index c-1
            self.row.append(qst)
            # Save minimum width based on trimmed width
            self.cMinWidths[c-1] = max(self.cMinWidths[c-1],qst.size())
        else:
            # multi-line table, c in 1..columnsSeen and data may already exist
            if c > len(self.row):
                # first sight of this column in this row, append this datum
                self.row.append(qs)
            else:
                # second or later line of a multi-line cell, append with a space
                self.row[c-1].append(QString(u' '))
                self.row[c-1].append(qs)
            # Calculate the minimum cell width based on the longest nonblank
            # token in the new string.
            w = 0
            j = self.tokenRE.indexIn(qs) # index of first nonblank sequence
            while j > -1:
                dbg1 = unicode(self.tokenRE.cap(1))
                dbg2 = self.tokenRE.matchedLength()
                w = max(w, self.tokenRE.cap(1).size()) # note widest token
                # find next token after the matched one, if any
                j = self.tokenRE.indexIn(qs,j+self.tokenRE.matchedLength())
            # record longest token seen so far this column
            self.cMinWidths[c-1] = max(self.cMinWidths[c-1],w)
        # for single and multi, save the actual size as suggested width
        self.cSugWidths[c-1] = max(self.cSugWidths[c-1],qs.size())

    # Return the count of columns stored in any row. Note it is possible for
    # the data for a row to be short, if one or more columns were omitted.
    def columnCount(self):
        return self.columnsSeen

    # Return the count of rows stored.
    def rowCount(self):
        return len(self.data)

    # Return the data string for a given cell, given r and c. On the assumption
    # that rows will be read out sequentially, save the row for future use.
    # In the event a row is valid but no column was stored, return an empty
    # QString. This is not necessarily an error.
    # In the event of an unknown cell, return a null QString and print an error.
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
                return QString()
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
            return self.cMinWidths[c-1]
        return self.badColumn(c)
    # Return the suggested width of column c, the longest actual string
    # (blanks included) that was stored; but never less than the minimum width.
    def columnSugWidth(self,c):
        if c <= self.columnsSeen:
            return max(self.cSugWidths[c-1],self.cMinWidths[c-1])
        return self.badColumn(c)

# Reflow a table, based on the sequence of "work units" as developed in
# pqFlow. Arguments are: tc is the textCursor over doc, a QTextDocument,
# on which a single undo/redo macro has been started. unitList is the
# slice of the pqFlow unitList from the /T line to the T/ line inclusive.
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

def tableReflow(tc,doc,unitList):
    # Note the properties of the table including specified width, multiline etc.
    tprops = tableProperties(getLineQs(tc,doc,unitList[0]['A']))
    # If the width wasn't spec'd then develop a target width based on 75 less
    # any indent in the first work unit.
    targetTableWidth = tprops.tableWidth()
    if targetTableWidth is None:
        targetTableWidth = 75 - unitList[0]['F']
    # save regex used to split data line on delimiters which are either
    # 2+ spaces or a stile with optional spaces.
    splitRE = QRegExp(u'( {2,}| *\| *)')
    # make a table cells storage object
    tcells = tableCells(tprops)
    # note if the table has a hyphenated top line
    topChar = tprops.tableTopString()
    if topChar is not None:
        topChar = QChar(topChar)
    # note if the cells have hyphenated bottom lines
    botChar = tprops.columnBottomString()
    if botChar is not None:
        botChar = QChar(botChar)
    # decide what work units to process. The first and last are the markup
    # start/end units, skip those. If there is a top-line, skip that also.
    work = range(1,len(unitList)-1)
    if topChar is not None:
        qs = getLineQs(tc,doc,unitList[1]['A']) # fetch text of first line
        if qs.size() == qs.count(topChar):
            # top string is spec'd and there is a top string of ---
            del work[0] # don't process it
    r = 1 # current row number 1-n
    for u in work:
        unit = unitList[u]
        qs = getLineQs(tc,doc,unit['A'])
        if botChar is not None:
            if qs.size() == qs.count(botChar):
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
            dbg1 = unicode(cqs)
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
    if tprops.columnSideString() is None:
        cellDelimiterString = QString(u'  ') # internal delimiter
    else:
        cellDelimiterString = QString(tprops.columnSideString())
        totalDelimiterWidths += cellDelimiterString.size() # the stile on the left
    # add widths of internal delimiters
    totalDelimiterWidths += cellDelimiterString.size() * (tcells.columnCount() - 1)
    # add the right side delimiter
    if tprops.tableSideString() is None:
        tableSideString = QString()
    else:
        tableSideString = QString(tprops.tableSideString())
        totalDelimiterWidths += tableSideString.size() # the stile on the right
    # Now, how much room for column data?
    tableDataWidth = targetTableWidth - totalDelimiterWidths
    # targetDataWidth is how many chars of data we ought to have. How much do
    # we really have? Develop a list of column "suggested" widths, the actual
    # width of the longest string stored in each column, and its total.
    totalSugWidth = 0
    allSugWidths = [9999] # skip the 0th element, cols number by 1
    for c in range(1,tcells.columnCount()+1):
        csw = tcells.columnSugWidth(c)
        allSugWidths.append(csw)
        totalSugWidth += csw
    # If the suggested width is greater than expected, adjust somehow:
    if totalSugWidth > tableDataWidth:
        if tprops.isMultiLine() :
            # For a multiline table where we can fold cell contents, we can
            # try to adjust sug widths down toward min widths.
            totalMinWidth = 0
            allMinWidths = [9999] # cell 0 ignored
            for c in range(1,tcells.columnCount()+1):
                csw = tcells.columnMinWidth(c)
                allMinWidths.append(csw)
                totalMinWidth += csw
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
    # target column widths. Fill the rows aligning cells as requested.
    # What we are going to do is, develop one whomping QString for the whole
    # table, then finally insert it using textCursor tc replacing the table.
    # flowCell returns a QStringList with one string for each ascii line needed
    # to fit the cell data in the given width -- just one for singleline.
    tableText = QString()
    if topChar is not None: # start with top line of ---s
        tableText.fill(topChar,targetTableWidth)
        tableText.append(IMC.QtLineDelim)
    rowdata = [None]*(tcells.columnCount()+1)
    lineStart = QString() if tprops.columnSideString() is None \
                           else QString(cellDelimiterString)
    lineEnd = QString(tableSideString)
    dbg = unicode(lineEnd)
    cellBottom = QString()
    if botChar is not None:  # Create bottom-string of ---\n
        cellBottom.fill(botChar,targetTableWidth)
        cellBottom.append(IMC.QtLineDelim)
    else:
        if tprops.isMultiLine() :
            # if no bottom string, multi still needs empty line
            cellBottom.append(IMC.QtLineDelim)
    for r in range(1,tcells.rowCount()+1):
        asciiLines = 0
        for c in range(1,tcells.columnCount()+1):
            rowdata[c] = flowCell(
                tcells.fetch(r,c), allSugWidths[c], tprops.columnAlignment(c)
                )
            asciiLines = max(asciiLines,rowdata[c].count())
        for x in range(asciiLines):
            qsLine = QString(lineStart) # making a copy
            for c in range(1,tcells.columnCount()+1):
                if rowdata[c].count() > x:
                    cqs = rowdata[c][x]
                else:
                    cqs = QString(u' ' * allSugWidths[c])
                qsLine.append(cqs)
                if c < tcells.columnCount() :
                    qsLine.append(cellDelimiterString) # add internal delimiter
                dbg = unicode(qsLine)
            # finish the line
            dbg = unicode(qsLine)
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
# QString per ascii line of folded text -- which should be 1 for a single line
# table, or more for a multiline table. The problem is similar to the
# paragraph folder in pqFlow but simpler. We are not supporting logical lengths
# of <i/b/sc> for one thing. Sorry, get rid of those before flowing a table,
# that's what the skip button is for.
# It is more complex in that we may have to center or right-align. (Once we
# had the mad notion to support decimal alignment, but you know? Screw it.
# That would require scanning all rows of a column to find the decimals, and
# anyway, just put in enough @'s to make shit line up.)
chunkRE = QRegExp()
def flowCell(qs,width,align):
    if qs.size() <= width :
        return QStringList(alignCell(qs,width,align))
    # string is greater than width -- we assert this cannot occur in a 
    # single-line table. So we will fold qs into multiple strings. Now let us
    # chunk qs into whitespace-delimited chunks up to width in size.
    dbg1 = unicode(qs)
    qs.append(u' ') # ensure terminal space: last good char is at size-2
    chunkRE.setMinimal(False)
    chunkRE.setPattern(u'\s*(\S.{,'+str(width-1)+u'})\s')
    qsl = QStringList()
    j = chunkRE.indexIn(qs,0)
    while j > -1 :
        dbg2 = unicode(chunkRE.cap(1))
        qsl.append(alignCell(chunkRE.cap(1),width,align))
        j += chunkRE.cap(0).size()
        j = chunkRE.indexIn(qs,j)
    return qsl    
    
# Given a QString that fits in a width, extend it front a/o back to
# align in that width.
def alignCell(qs,width,align):
    spaces = width - qs.size()
    if spaces : 
        # There are some spaces to distribute, but on which side?
        if align == CalignLeft :
            qs.append(u' ' * spaces)
        elif align == CalignRight :
            qs.prepend(u' ' * spaces)
        else :
            # sigh - center it. put the odd space on the right.
            spacesLeft = int(spaces/2)
            spacesRight = spaces - spacesLeft
            qs.prepend(u' ' * spacesLeft)
            qs.append(u' ' * spacesRight)
    dbg = unicode(qs)
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

    tp = tableProperties(u"/t T(A:C T:'-' S:'|') Col(B:'-' S:'|') 3(A:R W:8)")
    print('ta ',tp.tableAlignment())
    print('tw ',tp.tableWidth())
    print('ts ',tp.tableSideString())
    print('tt ',tp.tableTopString())
    print(tp.columnWidth(1))
    print(tp.columnWidth(3))
    tc = tableCells(tp,True)
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
