import os
import contextlib


@contextlib.contextmanager
def as_handle(handleish, mode="r", **kwargs):
    r"""Context manager to ensure we are using a handle.

    Context manager for arguments that can be passed to SeqIO and AlignIO read, write,
    and parse methods: either file objects or path-like objects (strings, pathlib.Path
    instances, or more generally, anything that can be handled by the builtin 'open'
    function).

    When given a path-like object, returns an open file handle to that path, with provided
    mode, which will be closed when the manager exits.

    All other inputs are returned, and are *not* closed.

    Arguments:
     - handleish  - Either a file handle or path-like object (anything which can be
                    passed to the builtin 'open' function, such as str, bytes,
                    pathlib.Path, and os.DirEntry objects)
     - mode       - Mode to open handleish (used only if handleish is a string)
     - kwargs     - Further arguments to pass to open(...)

    Examples
    --------
    >>> from Bio import File
    >>> import os
    >>> with File.as_handle('seqs.fasta', 'w') as fp:
    ...     fp.write('>test\nACGT')
    ...
    10
    >>> fp.closed
    True

    >>> handle = open('seqs.fasta', 'w')
    >>> with File.as_handle(handle) as fp:
    ...     fp.write('>test\nACGT')
    ...
    10
    >>> fp.closed
    False
    >>> fp.close()
    >>> os.remove("seqs.fasta")  # tidy up

    """
    try:
        with open(handleish, mode, **kwargs) as fp:
            yield fp
    except TypeError:
        yield handleish


