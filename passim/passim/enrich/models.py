from django.db import models
from django.urls import reverse
LONG_STRING=255

NOISE_TYPE = ( ('p', 'Natural'), ('n', 'Lombard noise'))

# Models for ENRICH

class Testset(models.Model):
    """One testset contains all tunits for one participant"""

    # [1] The round of this testset (there may be 2-4 rounds)
    round = models.IntegerField("Round", default=0)
    # [1] The number of this testset 
    number = models.IntegerField("Number", default=0)

    def __str__(self):
        return "{}/{}".format(self.round, self.number)

    def get_testset(round, number):
        """Get the testset object for the particular round"""

        obj = Testset.objects.filter(round=round, number=number).first()
        if obj == None:
            obj = Testset.objects.create(round=round, number=number)
        return obj

    def get_testunits(self):
        """Show which testunits I have"""

        html = []
        for tunit in self.testset_testunits.all().order_by('speaker', 'ntype', 'sentence'):
            url = reverse('testunit_details', kwargs={'pk': tunit.id})
            name = "spk {}/ntype {}/snt {}".format(tunit.speaker.name, tunit.get_ntype_display(), tunit.sentence.name)
            html.append("<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url, name))
        # Combine
        sBack = "\n".join(html)
        return sBack


class Participant(models.Model):

    # [1] The name of the speaker
    name = models.CharField("Name", max_length=LONG_STRING)
    # [0-1] Status of this participant
    status = models.CharField("Status", default="created", max_length=LONG_STRING)

    def __str__(self):
        return self.name


class Speaker(models.Model):

    # [1] The name of the speaker
    name = models.CharField("Name or number code", max_length=LONG_STRING)

    def __str__(self):
        return self.name


class Sentence(models.Model):

    # [1] The text of the sentence
    name = models.CharField("Name", max_length=LONG_STRING)

    def __str__(self):
        return self.name


class Testunit(models.Model):
    """A unit to be tested: speaker/sentence/noise condition"""

    # [1] One testunit is the sentence of one speaker
    speaker = models.ForeignKey(Speaker, on_delete=models.CASCADE)
    # [1] And it concerns one of the sentences
    sentence = models.ForeignKey(Sentence, on_delete=models.CASCADE)
    # [1] ANd it is one variant: 'p' (plain) or 'n' (noise)
    ntype = models.CharField("Noise type type", choices=NOISE_TYPE, max_length=5)

    # [0-1] The number of times this testunit has been used by participants
    #       (This field has not been used yet)
    count = models.IntegerField("Count", default=0)

    # Many-to-many
    testsets = models.ManyToManyField(Testset, related_name="testset_testunits", through="TestsetUnit")

    def __str__(self):
        sBack = "{}-{}-{}".format(self.speaker.id, self.sentence.id, self.ntype)
        return sBack

    def get_testsets(self):
        """Show which testsets I am part of"""

        html = []
        for testset in self.testsets.all().order_by('round', 'number'):
            url = reverse('testset_details', kwargs={'pk': testset.id})
            name = "rnd {}/num {}".format(testset.round, testset.number)
            html.append("<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url, name))
        # Combine
        sBack = "\n".join(html)
        return sBack

    def get_filename(self):
        """Construct a filename and return it
        
        Documentation says that the directory structure and file names follow the template: 

            ENRICH/Radboud Lombard Corpus_Dutch/1_Lom/1_F1_Lom.wav
        """

        ntype = "Lom" if self.ntype == "n" else "Nat"
        # We only return the last part of the filename
        sBack = "{}_{}_{}.wav".format(self.speaker.name, self.sentence.name, ntype)
        return sBack

    def get_filename_html(self):
        """Get the filename in a nice HTML look"""

        filename = self.get_filename()
        sBack = "<span class='badge signature gr'>{}</span>".format(filename)
        return sBack

    def get_ntype_html(self):

        ntype = "Lom" if self.ntype == "n" else "Nat"
        cls = "ot" if self.ntype == "n" else "gr"
        sBack = "<span class='signature {}'>{}<span>".format(cls,ntype)
        return sBack


class TestsetUnit(models.Model):
    """This is the 'through' table for combinations of testset/testunit"""

    # [1] Obligatory link to testset
    testset = models.ForeignKey(Testset, related_name="testsetunits", on_delete=models.CASCADE)
    # [1] Obligatory link to testunit
    testunit = models.ForeignKey(Testunit, related_name="testsetunits", on_delete=models.CASCADE)

