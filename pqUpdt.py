# These imports move Python 2.x almost to Python 3.
# They must precede anything except #comments, including even the docstring
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future_builtins import *

__version__ = "0.1.0" # refer to PEP-0008
__author__  = "David Cortesi"
__copyright__ = "Copyright 2012 David Cortesi"
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
This module implements the File > Check for Updates menu command.
In summary it does as follows:

* Makes contact with Github and reads the names and hashcodes of all
  the modules in the "master" branch of PPQT. Makes a 3-column table
  of name (e.g. pqUpdt.py), git-hashcode, local-hashcode (initially None)

* For each name in the table, looks for that module in the app directory
  and gets its git hashcode. This may be speeded by finding the hashes
  already calculated in the file modulehashes.txt.

* Count the modules for which local hashcode != git hashcode. These need
  to be updated. If the count is 0, tell the user and exit.

* For each updated module, read the blob contents from github and save
  in memory. If any error, tell about it and quit.

* For each updated module, verify that it can be opened for writing.
  If not, tell about it and quit.

* Rewrite each updated module with the git blob contents and close the file.
  If any error, tell about the serious error and quit.

* Attempt to write the file modulehashes.txt with the current hashcodes
  of all modules, so the check can go faster next time, but if that fails,
  don't sweat it.

* Tell the user the update is done, restart PPQT to make the changes active.

This scheme works because the .py (and one .html) modules are copied into
memory when the program starts up. They can be changed freely and not affect
the current execution instance. It also works because we are bundling the
app with pyinstaller as a single folder, not a single executable. The
single executable has all the modules hashed in a zip file and couldn't be
updated on the fly.

If an error happens while actually writing a module, the app is in an unknown
state and the user had better just download a whole new copy of the app.
But that is an unlikely case; we pre-verify that we have the data from git
and the files are writable. The only error is an IO error on output, for example
a full disk.

Unit test code is appended.

The following additional features have been considered.

Automating the check, e.g. checking at startup, instead of having the user
ask for a check. Not done because I absolutely detest programs doing that, or
making any other kind of internet access I didn't specifically request. Also,
PPQT should not be internet-dependent at all, should be possible to work a
whole book disconnected. This would add a time-out delay at startup.

Getting commit data from git and offering the user a selection list of bug
fixes to be updated, rather than just bulk updating to the current master level.
This would be extremely complex to implement, because of dependencies between
commits. And scary-complex for the user, probably. If a fix is worth committing
to the master branch, it is at worst harmless for every user to apply (or it
shouldn't have been committed).

Instead of rewriting the changed modules, copy them to a bundle, a zip file
maybe, with a sequence number, so you could have a Back Out Last Update command.
Not infeasible but not worth doing. There would be two reasons for wantint to
back out an update. One, there's a bug in it, but the right way to handle that
is to report it, get a fix, and run another update. Or Two, the update adds
some UI behaviour you don't like. Tough. Because we are not going to support
selective update (see previous paragraph), once you skip one update you can
never update again. If some UI change is intolerable, you are up the creek.

'''
import pqMsgs
import os # for path joining

# The git hash input is b'blob ###\000xx...' where ### is the length of the
# data in ascii decimal, and xx... is that data. Here we create an SHA1 hash
# object initialized to b'blob '. This is cloned each time we need a hash.

import hashlib
initializedSHA1 = hashlib.sha1()
initializedSHA1.update(b'blob ')

import urllib2 # used to read pages from github

# in this module we deal strictly with byte strings. (Raw data from github
# is UTF8 but we assume it only contains Latin-1 characters.) We do NOT want
# to move into the 16-bit Unicode used in by Qt in all the rest of the app.
# So unlike other modules, we here use Python re instead of Qt regex objects.
import re
# RE to find the SHA string that github replaces with "master" in URLs.
# It is the SHA of the latest commit to the master branch, and has to be
# replaced with "master" in the URLs.
reGetMasterSHA = re.compile('data-clipboard-text=\"([0-9a-f]+)\"')

# RE to find the next blob content line in the github CODE display page.
# After a match, the groups are:
# The URL of the blob is 'https:raw.github.com/\1/\2
# The hash id of the blob is \3 (should match the hash of the local file)
# The name of the file is \4, e.g. pqMain.py
reBlobLine = re.compile('''\<td class=\"content\">\s*\<a href=\"(.+?)/blob/([^"]+)\".+?id="([^"]+)\"\s*\>([^<]+)</a></td>''')

# Read the complete text of a single web page given a URL.
# If the operation succeeds, return the UTF byte-string of the page text.
# If it fails for any reason return a null string.
# Appreciation to http://www.voidspace.org.uk/python/articles/urllib2.shtml

def slurp(anurl):
    uf = None
    page = None
    try:
        uf = urllib2.urlopen( anurl , timeout=5 )
    except urllib2.URLError as e:
        if hasattr(e, 'reason'): # e.g. socket error
            print('Unable to reach github, reason: {0}'.format(e.reason))
        elif hasattr(e, 'code'): # HTTP error e.g. 404
            print('Error in the URL: {0}'.format(e.code))
    except Exception: # not a URLError
        print('We have no clue')
    if uf is not None: # then the page is open and needs closing
        try:
            page = uf.read().decode('UTF-8')
        except Exception:
            print('Error reading a web page')
        uf.close()
    return page

# Implement the command File > Check for Updates
def checkForUpdates():
    # Step one, read the code display for the master
    page = slurp('https://github.com/tallforasmurf/PPQT')
    if page is None:
        pqMsgs.warningMsg('Unable to contact Github',
                          'Perhaps try again later?')
        return

    # the embedded URLs usable.
    hit = reGetMasterSHA.search(page)
    if hit is None:
        pqMsgs.warningMsg('Github page format not as expected',
                          'Probable bug, update not available')
        return
    masterSHA = hit.group(1)
    page = re.sub(masterSHA,'master',page)

    # Step three, make a list of all the "blobs" mentioned, which is just
    # all the committed modules, pqXXX.py and pqHelp.html. Ignoring the
    # extras -- the extras folder appears as a "tree" item and we could
    # follow it and list all the blobs extras/* but we are not.
    blobs = reBlobLine.findall(page)
    # blobs is a list of 4-tuples, the (/1, /2, /3, /4) from reBlobLine above
    # Now make a dict with 3-item values,
    # { modname:[ None, masterhash, masterURL] } where None will be filled
    # in with the local hash value shortly.
    blobTab = {}
    for blob in blobs:
        blobURL = u'https://raw.github.com' + blob[0] + u'/' + blob[1]
        blobName = blob[3]
        blobHash = blob[2]
        blobTab[blobName] =[None,blobHash,blobURL]

    # Look for the file modulehash.txt and if it exists, use it to fill
    # in the local hashes it lists. We do not distribute so it doesn't
    # show up in the github listing. We want the local hash to reflect
    # the actual local files, which might have been diddled locally.
    mhPath = os.path.join(IMC.appBasePath,'modulehashes.txt')
    try:
        mhFile = open(mhPath,'r')
        for line in mhFile:
            [modname, localhash] = line.split()
            if modname in blobTab:
                blobTab[modname][0] = localhash
    except:
        # presumably the file doesn't exist
        pass

    # Run through the blobTab and try to get hash values for any
    # modules that don't have a local hash yet (because modulehashes
    # didn't exist -- or didn't list them because they're new to us).
    for modName in blobTab:
        if blobTab[modName][0] is None:
            modPath = os.path.join(IMC.appBasePath,modName)
            try:
                modFile = open(modPath,'r')
                modText = modFile.read()
                hasher = initializedSHA1.copy()
                hasher.update(str(len(modText)))
                hasher.update(b'\000')
                hasher.update(modText)
                blobTab[modName][0] = hasher.hexdigest()
            except:
                # presumably modname doesn't exist (new module?)
                pass

    # Run through the blobTab and make a new table, updaTab, listing
    # the members where localhash differs from master hash.
    updaTab = {}
    for modName in blobTab:
        if blobTab[modName][0] != blobTab[modName][1] :
            updaTab[modName] = blobTab[modName]

    # If there are no names left in the updaTab, the app is up to date!
    if len(updaTab) == 0:
        pqMsgs.infoMsg('PPQT is up to date.')
        return

    # There are one or more modules needing updating. Ask the user
    # if we should proceed.
    ans = pqMsgs.okCancelMsg('{0} module(s) can be updated.'.format(len(updaTab)),
                       'Shall we proceed?')
    if not ans:
        pqMsgs.infoMsg('PPQT remains unchanged.')
        return

    # User said OK to do it. Read the text of the updated modules from
    # github and save it in the updaTab.
    for modName in updaTab:
        page = slurp(updaTab[modName][2])
        if page is None:
            pqMsgs.warningMsg('Some problem reading update modules',
                              'PPQT is unchanged.')
            return
        updaTab[modName].append(page)

    # All update texts read correctly. Now open each for writing,
    # appending the file object to the updaTab entry.
    for modName in updaTab:
        try:
            modPath = os.path.join(IMC.appBasePath,modName)
            modFile = open(modPath, 'w')
            updaTab[modName].append(modFile)
        except Exception:
            pqMsgs.warningMsg('Updated modules are not writable'
                              'PPQT is unchanged.')
            return

    # All files open for writing and text is ready. Write them.
    for modName in updaTab:
        try:
            modFile = updaTab[modName][4]
            modFile.write(updaTab[modName][3])
            modFile.flush()
            os.fsync(modFile.fileno())
            modFile.close()
        except Exception as e:
            # This is the bad case: some amount of writing done but not
            # all of it complete. PPQT is in an inconsistent state.
            pqMsgs.warningMsg('Error writing updated module(s)!',
                              'PPQT is in an inconsistent state\nDownload a complete new copy')
            return

    # All updates complete. Record local hashes in modulehashes.txt
    try:
        mhFile = open(mhPath,'w')
        for modName in blobTab:
            mhFile.write(modName + ' ' + blobTab[modName][1] + '\n')
        mhFile.close()
    except Exception as e:
        pass

    pqMsgs.infoMsg('Updates applied.',
                   'Changes take effect when PPQT is restarted.')
    return

# Unit test code when executed as main. Be sure to have committed and
# pushed all legit changes before running this as it will try to make
# everything match the current master branch. To create a difference for it
# to see, you can edit any module and make a trivial change. Or you can
# edit modulehashes.txt if it exists, and change one or more hashcodes.
if __name__ == "__main__":
    import sys
    from PyQt4.QtGui import (QApplication,QWidget)
    app = QApplication(sys.argv) # create an app
    import pqIMC
    IMC = pqIMC.tricorder()
    IMC.mainWindow = QWidget()
    import os
    IMC.appBasePath = os.path.dirname(__file__) # assume not running bundled
    # test slurp
    # 404 or something like it
    # p = slurp('https://github.com/DoesNotExist/PPQT')
    # turn off airport or pull the ethernet cable to force an error here
    # p = slurp('https://github.com/tallforasmurf/PPQT')
    checkForUpdates()



