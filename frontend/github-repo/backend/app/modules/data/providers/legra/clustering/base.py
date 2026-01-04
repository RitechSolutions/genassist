from abc import ABC, abstractmethod
from typing import List

import igraph as ig

__all__ = [
    'Clusterer',
]


class Clusterer(ABC):
    """
    Abstract interface for community detection / clustering on an igraph Graph.
    """

    @abstractmethod
    def find_partition(self, graph: ig.Graph) -> List[int]:
        """
        Given an igraph Graph, return a list of community labels, one per vertex
        index.
        """
        raise NotImplementedError
