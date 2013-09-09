
This directory contains dictionaries for the hunspell spellchecker.

Files ending in .dic are the dictionaries.
Files ending in .aff are the "affix" rule files associated with each dict.

The names of files ending in .dic appear in the drop-down menu
when you select View > Dictionary…

To add or replace a dictionary, find a Myspell-compatible
(or Hunspell-compatible) dictionary somewhere.
Place the name.dic and name.aff file pair in this folder.
Restart PPQT. The dictionary name should appear in the list.

One source of dictionaries used to be the OpenOffice.org or
LibreOffice.org websites, but now both of these bundle their
dictionaries into ".oxt" extension files.

Mozilla.org has a huge list of language dictionaries for Firefox
at:  https://addons.mozilla.org/en-US/firefox/language-tools/
However again, each is an "add-on" for Firefox. The .dic/.aff
file pair are not easily found. Actually they can be found
in the Firefox "profile" folder. Install the desired dictionary
as a Firefox add-on. Then, on Mac OS, use the Terminal:

 cd ~/Library/Application Support/Firefox/Profiles/*.default/extensions
 find . -name '*.dic'

The name(s) of installed dictionary files will be displayed,
often several folders below the current one.

