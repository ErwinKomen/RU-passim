import BaseTree

class Tree(BaseTree.Tree):
    """Newick Tree object."""

    def __init__(self, root=None, rooted=False, id=None, name=None, weight=1.0):
        """Initialize parameters for a Newick tree object."""
        BaseTree.Tree.__init__(
            self, root=root or Clade(), rooted=rooted, id=id, name=name
        )
        self.weight = weight


class Clade(BaseTree.Clade):
    """Newick Clade (sub-tree) object."""

    def __init__(
        self, branch_length=None, name=None, clades=None, confidence=None, comment=None
    ):
        """Initialize parameters for a Newick Clade object."""
        BaseTree.Clade.__init__(
            self,
            branch_length=branch_length,
            name=name,
            clades=clades,
            confidence=confidence,
        )
        self.comment = comment
