from django.db import models
from django.urls import reverse
import re, copy
from passim.bible.utils import *

LONG_STRING=255
SPACES = " \t\n\r"
NUMBER = "0123456789"
STANDARD_LENGTH=100
ABBR_LENGTH = 5
BKCHVS_LENGTH = 9       # BBBCCCVVV

BOOK_NAMES = [{"name":"Romans","abbr":"ROM"},{"name":"Rom.","abbr":"ROM"},{"name":"Rom:","abbr":"ROM"},
              {"name":"Revelations","abbr":"REV"},
              {"name":"Ps.","abbr":"PSA"},{"name":"Prv.","abbr":"PRO"},{"name":"Prov.","abbr":"PRO"},
              {"name":"Philippians","abbr":"PHP"},{"name":"Phil.","abbr":"PHP"},{"name":"Os.","abbr":"HOS"},
              {"name":"Mt.","abbr":"MAT"},{"name":"Mt","abbr":"MAT"},{"name":"Matthew","abbr":"MAT"},
              {"name":"Matth.","abbr":"MAT"},{"name":"Matt.","abbr":"MAT"},{"name":"Matt","abbr":"MAT"},
              {"name":"Mat.","abbr":"MAT"},
              {"name":"Mark","abbr":"MRK"},{"name":"Marc.","abbr":"MRK"},{"name":"Luke","abbr":"LUK"},
              {"name":"Lucas","abbr":"LUK"},{"name":"Luc.","abbr":"LUK"},{"name":"Luc","abbr":"LUK"},
              {"name":"1 Lamentations","abbr":"LAM"},
              {"name":"2 Cor.","abbr":"2CO"},
              {"name":"2 Cor","abbr":"2CO"},{"name":"1 Timothy","abbr":"1TI"},{"name":"1 Thess.","abbr":"1TH"},
              {"name":"1 Peter","abbr":"1PE"},{"name":"1 John","abbr":"1JN"},{"name":"I Ioh.","abbr":"1JN"},
              {"name":"1 Cor.","abbr":"1CO"},{"name":"1 Cor","abbr":"1CO"},
              {"name":"Lc.","abbr":"LUK"},{"name":"Lc","abbr":"LUK"},{"name":"Lamentations","abbr":"LAM"},
              {"name":"Lam.","abbr":"LAM"},{"name":"John","abbr":"JHN"},{"name":"Joh.","abbr":"JHN"},
              {"name":"Jo.","abbr":"JHN"},{"name":"James","abbr":"JAS"},{"name":"Isaias","abbr":"ISA"},
              {"name":"Isaiah","abbr":"ISA"},{"name":"Is.","abbr":"ISA"}, {"name":"Ioh.","abbr":"JHN"},
              {"name":"II Petr.","abbr":"2PE"},{"name":"II Cor.","abbr":"2CO"},{"name":"Iac.","abbr":"JAS"},
              {"name":"I Tim.","abbr":"1TI"},{"name":"I Thess.","abbr":"1TH"},{"name":"I Thes.","abbr":"1TH"},
              {"name":"I Mcc","abbr":"1MA"},{"name":"I Cor.","abbr":"1CO"},
              {"name":"Hebr.","abbr":"HEB"},{"name":"Heb.","abbr":"HEB"},{"name":"Gen.","abbr":"GEN"},
              {"name":"Gal.","abbr":"GAL"},{"name":"Ez.","abbr":"EZK"},{"name":"Ephesians","abbr":"EPH"},
              {"name":"Eph:","abbr":"EPH"},{"name":"Eph.","abbr":"EPH"},{"name":"Eccle.","abbr":"ECC"},{"name":"Eccli.","abbr":"SIR"},
              {"name":"Cor.","abbr":"1CO"},{"name":"Col.","abbr":"COL"},{"name":"Canticum Canticorum","abbr":"SNG"},
              {"name":"Apocalypsis","abbr":"REV"},{"name":"Apoc.","abbr":"REV"},{"name":"Acts","abbr":"ACT"},
              {"name":"Act. Apost.","abbr":"ACT"},{"name":"Act.","abbr":"ACT"}
              ]



class Book(models.Model):
    """One book from the Bible"""

    # [1] obligatory name
    name = models.CharField("Name (English)", max_length=STANDARD_LENGTH)
    latname = models.CharField("Name (Latin)", null=True, blank=True, max_length=STANDARD_LENGTH)
    # [1] standard three letter abbreviation
    abbr = models.CharField("Abbreviation (English)", max_length=ABBR_LENGTH)
    # [0-1] standard three letter abbreviation
    latabbr = models.CharField("Abbreviation (Latin)", null=True, blank=True, max_length=STANDARD_LENGTH)
    # [1] the numerical identifier of this book, running from 1-66
    idno = models.IntegerField("Identifier", default=-1)
    # [1] The number of chapters in this book
    chnum = models.IntegerField("Number of chapters", default=-1)

    def __str__(self):
        return self.abbr

    def get_abbr(idno):
        sAbbr = ""
        # Get the abbreviation, given the IDNO of a book
        obj = Book.objects.filter(idno=idno).first()
        if obj != None:
            sAbbr = obj.abbr
        return sAbbr

    def get_idno(abbr):
        abbr_from = ["mt1", "matt.", "luc.", "lc.", "jo."]
        abbr_to = ["mat", "mat", "luk", "luk", "jhn"]

        idno = -1
        # Possibly adapt some abbreviations to be able to understand them
        abbr = abbr.lower()
        idx = next((x for x in abbr_from if x == abbr), -1)
        if idx >= 0:
            abbr = abbr_to[idx]

        # Get the abbreviation, given the IDNO of a book
        obj = Book.objects.filter(abbr__iexact=abbr).first()
        if obj != None:
            idno = obj.idno
        return idno

    def get_chapters(idno):
        chnum = 0
        # Get the abbreviation, given the IDNO of a book
        obj = Book.objects.filter(idno=idno).first()
        if obj != None:
            chnum = obj.chnum
        return chnum
    

class Chapter(models.Model):
    """A chapter in a Bible book"""

    # [1] Each chapter belongs to a book
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="bookchapters")
    # [1] The chapter number
    number = models.IntegerField("Chapter", default = -1)
    # [1] The number of verses in this chapter
    vsnum = models.IntegerField("Number of verses", default = -1)

    def __str__(self):
        sBack = ""
        if self.book != None and self.number > 0:
            sBack = "{} {}".format(self.book.abbr, self.number)
        return sBack

    def get_vss(idno, chn):
        """Get the number of verses for this chapter"""

        vss = 0
        obj = Chapter.objects.filter(book__idno=idno, number=chn).first()
        if obj != None:
            vss = obj.vsnum
        else:
            iStop = 1
        return vss


class BkChVs():
    """Helper class to convert to/from bk/ch/vs"""

    book = ""
    ch = -1
    vs = -1

    def __init__(self, bkchvs):
        """Create an object"""

        # Perform the standard initialization
        response = super(BkChVs, self).__init__()
        # Disentanble bkchvs
        if len(bkchvs) == 9:
            idno = int(bkchvs[0:3])
            self.ch = int(bkchvs[3:3])
            selv.vs = int(bkchvs[6:3])
            # Convert idno into abbreviation
            self.book = Book.get_abbr(idno)

        # Return the response
        return response


class Reference():
    """Convert from and to reference(s)"""

    ref_string = ""     # The reference string
    ref_len = 0         # Length of the reference string
    num_refs = 0        # Number of references gathered
    pos = 0             # Running position within string
    sr = []             # List of scripture reference objects
    sr_idx = -1         # Index of the current item in [sr]
    
    def __init__(self, kwargs=None):
        if kwargs != None:
            self.ref_string = kwargs.pop("bibleref", "")
        if self.ref_string != "":
            self.ref_string = self.ref_string.strip()
            self.ref_len = len(self.ref_string)
            self.pos = 0
        return super(Reference, self).__init__(**kwargs)

    def get_range(self):
        sRange = ""
        # a range from a bk/ch/vs to a bk/ch/vs
        start = self.start
        einde = self.einde
        if len(start) == 9 and len(einde) == 9:
            # Derive the bk/ch/vs of start
            oStart = BkChVs(start)
            oEinde = BkChVs(einde)
            if oStart.book == oEinde.book:
                # Check if they are in the same chapter
                if oStart.ch == oEinde.ch:
                    # Same chapter
                    if oStart.vs == oEinde.vs:
                        # Just one place
                        sRange = "{} {}:{}".format(oStart.book, oStart.ch, oStart.vs)
                    else:
                        # From vs to vs
                        sRange = "{} {}:{}-{}".format(oStart.book, oStart.ch, oStart.vs, oEinde.vs)
                else:
                    # Between different chapters
                    if oStart.vs == 0 and oEinde.vs == 0:
                        # Just two different chapters
                        sRange = "{} {}-{}".format(oStart.book, oStart.ch, oEinde.ch)
                    else:
                        sRange = "{} {}:{}-{}:{}".format(oStart.book, oStart.ch, oStart.vs, oEinde.ch, oEinde.vs)
            else:
                # Between books
                sRange = "{}-{}".format(oStart.book, oEinde.book)
        # Return the total
        return sRange

    def skip_spaces(self):
        while self.pos < self.ref_len and self.ref_string[self.pos] in SPACES: self.pos += 1
        return self.pos

    def skip_char(self, char):
        while self.pos < self.ref_len and self.ref_string[self.pos] in char: self.pos += 1
        return self.pos

    def is_end(self):
        pos_last = self.ref_len-1
        bFinish = (self.pos > pos_last)
        return bFinish

    def is_end_orsemi(self):
        bResult = self.is_end()
        if not bResult:
            bResult = (self.ref_string[self.pos] == ";")
        return bResult

    def get_number(self):
        """Return the number that is here, if there is a number. Otherwise return None"""

        number = None
        pos_start = self.pos
        length = self.ref_len
        while self.pos < length and self.ref_string[self.pos] in NUMBER: self.pos += 1
        # See if we have something
        if self.pos > pos_start:
            # Get the chapter number
            number = int(self.ref_string[pos_start: self.pos]) # - pos_start + 1])
            # Possibly skip following spaces
            while self.pos < self.ref_len and self.ref_string[self.pos] in SPACES: self.pos += 1
        return number

    def get_string(self, lst_string):
        """Try to get one of the strings defined in the list [lst_string]"""

        ln = len(self.ref_string)
        for item in lst_string:
            len_this = len(item)
            if ln >= self.pos + len(item) and self.ref_string[self.pos:self.pos+len_this] == item:
                # Got it
                self.pos += len_this
                self.skip_spaces()
                return item
        return ""

    def get_remainder(self, sUntil = None):
        """Get the remainder as string"""

        sBack = ""
        if not self.is_end():
            if sUntil == None:
                pos_last = len(self.ref_string)
                sBack = self.ref_string[self.pos:pos_last]
            else:
                pos_until = self.ref_string.find(sUntil, self.pos)
                if pos_until >= 0:
                    sBack = self.ref_string[self.pos:pos_until]
                    self.pos = pos_until + 1
        return sBack

    def has_following(self, sChar):
        """Check if this has a following symbol"""

        bFound = False
        if not self.is_end():
            bFound = (sChar in self.ref_string[self.pos:len(self.ref_string)])
        return bFound

    def syntax_error():
        msg = "Cannot interpret at {}: {}".format(self.pos, self.ref_string)
        bStatus = False

    def parse(self):
        """Parse a string into a list of scripture reference objects

        Note: each object consists of:
            intro   - any introductory words like 'cf.' 'or'
            added   - any annotations added to these verses
            reflist - list of references (as strings)
                     
        Syntax (BNF):
            <ScrRef> ::= <BkRef> (SPACE* ";" SPACE* <BkRef>)*
            <BkRef>  ::= <Book> SPACE <ChVsList> || <Book>
            <Book>   ::= (LETTER || "1" || "2") LETTER LETTER
            <ChVsList> ::= <ChVs> (SPACE* ";" SPACE*  <ChVs>)*
            <ChVs>     ::= <Ch> ||
                        <Ch> SPACE* ("-")$ SPACE* <Ch> ||
                        <Ch> ("*") ":" <Vs> (SPACE* "," SPACE* <Vss>)*
            <Vss>      ::= <Vs> ||
                        <Vs> SPACE* ("-")$ SPACE* <Vs> ||
                        <Vs> SPACE* ("-")$ SPACE* <Ch> ":" <Vs>

        Example:  GEN 2:3-4,7,10-12;5;6:8; EXO 6:7-9,22;8-10
                   GEN 9:1-4;10:4,21-5:2
        """

        oErr = ErrHandle()
        bStatus = True
        introducer = ""
        obj = None
        msg = ""
        lst_back = None

        self.pos = 0
        self.num_refs = 0    # Number of references
        self.sr.clear()

        try:

            # Ad-hoc: replace any older book names
            sRange = self.ref_string
            for item in BOOK_NAMES:
                if item['name'] in sRange:
                    sRange = sRange.replace(item['name'], item['abbr'])

            # Make sure we know the length correctly
            self.ref_string = sRange.strip()
            self.ref_len = len(sRange)

            # Sanity check
            if self.ref_len == 0:
                # Just return zero - there is nothing to be done
                return bStatus, "", sr

            # Work on line: 
            # <ScrRef> ::= <BkRef> (SPACE* ";" SPACE* <BkRef>)*
            bFound, bi = self.bnf_BkRef()
            # Continue while there is still space
            while bFound and not self.is_end():
                # Skip spaces
                self.skip_spaces()
                # Expecting a semicolumn to follow
                sNext = self.preview_next()
                if sNext == ";":
                    self.pos += 1
                    self.skip_spaces()
                    bFound, bi = self.bnf_BkRef(bi)
                elif self.has_following(";"):
                    added = self.get_remainder(";")
                    self.add_added(added)
                    self.skip_spaces()
                    bFound, bi = self.bnf_BkRef(bi)
                else:
                    bFound = False
            # Check if we are at the end already
            if not self.is_end():
                # Whatever is left should be 'added'
                added = self.get_remainder()
                self.add_added(added)
                bFound = True
            # Has anything been found?
            if bFound:
                # Copy the list
                lst_back = copy.copy(self.sr)
            else:
                # There was a problem finding it???
                iStop = 1

        except:
            msg = oErr.get_error_message()
            oErr.DoError("Reference/parse")
            bStatus = False
        return bStatus, msg, lst_back

    def bnf_BkRef(self, bi = None):
        """Process <BkRef> line

        BNF code:
            <BkRef>  ::= [ <intro> ] <Book> SPACE$ <ChVsList> || <Book>
            <intro>  ::= "cf." | "or"
            <Book>   ::= (LETTER || [1-9]) LETTER LETTER
            <ChVsList> ::= <ChVs> (SPACE* ";" SPACE*  <ChVs>)*
        """

        bStatus = True
        msg = ""
        oErr = ErrHandle()

        try:
            intro = self.get_string(["cf.", "or"])
            if intro != "":
                self.add_intro(intro)
            # Get the length of the input string
            ln = len(self.ref_string)
            # Is there room enough for the name of the book?
            if ln >= self.pos + 3:
                # Get the book abbreviation in upper case
                bk = self.ref_string[self.pos:self.pos+3].upper()
                # Get the BkNo of the book
                idno = Book.get_idno(bk)
                # If book number cannot be determined: indicate failure
                if idno < 0 and bi == None:
                    bStatus = False
                    msg = "Cannot determine book number for [{}]".format(bk)
                else:
                    if idno >= 0: 
                        bi = idno
                        # Advance 3 positions
                        self.pos += 3
                    # Skip spaces
                    self.skip_spaces()
                    # Check if this is a book as a whole
                    if self.is_end_orsemi():
                        # This is a book in its entirety
                        chnum = Book.get_chapters(idno)
                        for ch in range(1, chnum+1):
                            vsnum = Chapter.get_vss(idno, ch)
                            # Walk all verses
                            for vs in range(1, vsnum+1):
                                # Process this combination
                                self.add_bkchvs(bi, ch, vs)
                    else:
                        # See if there indeed is another <ChVs>
                        bFound = self.bnf_ChVs(bi)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Reference/bnf_BkRef")
            bStatus = False

        # All we return directly is the Status
        return bStatus, bi

    def bnf_ChVs(self, bi):
        """Process <ChVs> line for bnf_BkRefs

        BNF code:
            <ChVs>     ::= <Ch> ||
                            <Ch> SPACE* ("-")$ SPACE* <Ch> ||
                            <Ch> ("*") ":" <Vs> (SPACE* "," SPACE* <Vss>)* ("*")
        """

        oErr = ErrHandle()
        msg = ""
        bStatus = True
        try:
            # There should be at leas one <Ch>
            self.skip_spaces()
            chapter = self.get_number()
            if chapter == None:
                # No number found, so return false
                msg = "No number found"
                bStatus = False
                return bStatus, msg

            # One obligatory space
            self.skip_spaces()

            # Check for end
            if self.is_end():
                # This is a whole chapter
                num_vss = Chapter.get_vss(bi, chapter)
                # Fill the array
                for i in range(num_vss):
                    verse = i+1
                    self.add_bkchvs(bi, chapter, verse)
                # Return positively
                return bStatus, ""

            # Remember the length
            ln = len(self.ref_string)
            # Action depends on what is now following
            sNext = self.ref_string[self.pos]
            if sNext == "-":    #  E.g: EXO 5-7
                # Skip one or more hyphens
                self.skip_char("-")
                # Skip spaces
                self.skip_spaces()
                # Get the second chapter number
                chapter2 = self.get_number()
                if chapter2 == None or chapter2 < chapter:
                    # Produce an error
                    msg = "Second chapter must exist and be higher than first"
                    bStatus = False
                    return bStatus, msg
                # Now we have a range of 2 chapters, e.g. EXO 5-7
                # Iterate over the chapters
                for chnum in range(chapter, chapter2 + 1 ):
                    # Get the number of verses for this chapter
                    num_vss = Chapter.get_vss(bi, chnum)
                    # Fill the array
                    for i in range(num_vss):
                        verse = i+1
                        self.add_bkchvs(bi, chnum, verse)
                    # Adjust the number of references
                    self.num_refs += num_vss
            elif sNext == ":":
                # First try to see if this is e.g: EXO 5:1-6:2
                # Skip the colon
                self.pos += 1
                # Skip spaces
                self.skip_spaces()
                # Look for verses
                bFound = self.bnf_Vss(bi, chapter) 
                # Skip spaces
                self.skip_spaces()
                # Skip at least a comma
                sNext = self.preview_next()
                while sNext == ",":
                    # Reset
                    sNext = None
                    # Skip the comma
                    self.pos += 1
                    # Skip spaces
                    self.skip_spaces()
                    # Find verses
                    bFoundMore = self.bnf_Vss(bi, chapter)
                    if bFoundMore:
                        self.skip_spaces()
                        sNext = self.preview_next()  
            elif re.match("[A-Za-z]", sNext):
                # This must be a chapter named like 2CH, 1TI or so
                bStatus = False
            else:
                # THis is just a whole chapter
                num_vss = Chapter.get_vss(bi, chapter)
                # Fill the array
                for i in range(num_vss):
                    verse = i+1
                    self.add_bkchvs(bi, chapter, verse)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Reference/bnf_BkRef")
            bStatus = False
        return bStatus, msg

    def add_bkchvs(self, bi, chnum, vsnum):
        oErr = ErrHandle()
        try:
            if self.sr_idx < 0:
                # Create the first object
                oScrRef = dict(intro="", added="", scr_refs=[])
                self.sr.append(oScrRef)
                self.sr_idx = 0
            lst_refs = self.sr[self.sr_idx]['scr_refs']
            lst_refs.append("{:0>3d}{:0>3d}{:0>3d}".format(bi, chnum, vsnum))
            self.num_refs += 1
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Reference/add_bkchvs")
        return None

    def add_intro(self, intro):
        """Create a new ScrRef item and add the intro to it"""

        oScrRef = dict(intro=intro, added="", scr_refs=[])
        self.sr.append(oScrRef)
        self.sr_idx = len(self.sr) - 1
        return None

    def add_added(self, added):
        """Add text in [added] to the current ScrRef item"""

        if self.sr_idx >= 0 and self.sr_idx < len(self.sr):
            self.sr[self.sr_idx]['added'] = added
        return None

    def preview_next(self):
        """Get the next character without advancing"""

        if self.is_end():
            sNext = None
        else:
            sNext = self.ref_string[self.pos]
        return sNext

    def preview_string(self, sPreview):
        """Check if [sPreview] is here"""

        bFound = False
        length = len(sPreview)
        if self.pos + length < self.ref_len:
            bFound = (self.ref_string[self.pos:self.pos+length] == sPreview)
        # Return our verdict
        return bFound

    def bnf_Vss(self, bi, ch):
        """ Process <Vss> line for bnf_ChVs proc

        BNF code:
            <Vss>      ::= <Vs> ||
                            <Vs> SPACE* ("-")$ SPACE* <Vs>  ||
                            <Vs> SPACE* ("-")$ SPACE* "end" ||
                            <Vs> SPACE* ("-")$ SPACE* <Ch> ":" <Vs>
        """

        oErr = ErrHandle()
        bStatus = True
        try:
            # Get the first verse number
            verse = self.get_number()
            if verse == None:
                bStatus = False
            else:
                # Skip possible spaces
                self.skip_spaces()
                # Anything left?
                if self.is_end():
                    # Only one verse to store!
                    self.add_bkchvs(bi, ch, verse)
                else:
                    # Find out wha tis coming
                    sNext = self.preview_next()
                    if sNext == "-":
                        # Skip any hyphens
                        self.skip_char("-")
                        # Skip possible spaces
                        self.skip_spaces()
                        # Is the keyword "end" following here?
                        if self.preview_string("end"):
                            # Determin wha the last verse number would be
                            number = Chapter.get_vss(bi, ch)
                            # Make sure to advance past "end"
                            self.pos += 3
                        else:
                            # Read eiher chapter or verse number...
                            number = self.get_number()
                        # Skip spaces
                        self.skip_spaces()
                        # Check if colon is following
                        sNext = self.preview_next()
                        if sNext == ":":
                            # It was a chapter number!
                            # So we have Chn:Vsn "-" <Ch>:<Vs>
                            ch2 = number
                            self.pos += 1
                            self.skip_spaces()
                            # Get the verse number
                            verse2 = self.get_number()
                            # Situation...
                            if ch == ch2:
                                # Chapter numbers are equal, e.g: GEN 4:5-4:6
                                for vs in range(verse, verse2 + 1):
                                    self.add_bkchvs(bi, ch, vs)
                            else:
                                # Get the number of verses for the current chapter [ch]
                                num_vss = Chapter.get_vss(bi, ch)
                                for vs in range(verse, num_vss + 1):
                                    self.add_bkchvs(bi, ch, vs)
                                # Walk all chapters in between
                                for chapter in range(ch+1, ch2):
                                    # Get the number of verses for the current chapter [ch]
                                    num_vss = Chapter.get_vss(bi, chapter)
                                    for vs in range(verse, num_vss + 1):
                                        self.add_bkchvs(bi, ch, vs)
                                # Walk the last chapter
                                for vs in range(1, verse2 + 1):
                                    self.add_bkchvs(bi, ch2, vs)
                        else:
                            # This is a reference to a range
                            # <Vs> SPACE* ("-")$ SPACE* <Vs>
                            for vs in range(verse, number+1):
                                self.add_bkchvs(bi, ch, vs)
                    else:
                        # Only one verse to store!
                        self.add_bkchvs(bi, ch, verse)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Reference/bnf_Vss")
            bStatus = False
        # Return only the status
        return bStatus




