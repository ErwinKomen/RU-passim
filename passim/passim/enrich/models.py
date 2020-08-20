from django.db import models
LONG_STRING=255

NOISE_TYPE = ( ('p', 'Plain'), ('n', 'Lombard noise'))

# Models for ENRICH

class Participant(models.Model):

    # [1] The name of the speaker
    name = models.CharField("Name", max_length=LONG_STRING)
    # [0-1] Status of this participant
    status = models.CharField("Status", default="created", max_length=LONG_STRING)

    def __str__(self):
        return self.name


class Speaker(models.Model):

    # [1] The name of the speaker
    name = models.CharField("Name", max_length=LONG_STRING)

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
    count = models.IntegerField("Count", default=0)

    # Many-to-many
    participants = models.ManyToManyField(Participant, related_name="participant_testunits")


    def __str__(self):
        sBack = "{}-{}-{}".format(self.speaker.id, self.sentence.id, self.ntype)
        return sBack
