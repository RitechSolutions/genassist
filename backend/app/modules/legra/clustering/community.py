from typing import List

import igraph as ig
import leidenalg as la

from .base import Clusterer

__all__ = [
    'LeidenClusterer',
    'LouvainClusterer',
]


class LeidenClusterer(Clusterer):
    """
    Community detection via the Leiden algorithm (RB configuration).
    """

    def __init__(self, resolution_parameter: float = 1.0) -> None:
        if resolution_parameter <= 0:
            raise ValueError("resolution_parameter must be > 0")
        self.resolution = resolution_parameter

    def find_partition(self, graph: ig.Graph) -> List[int]:
        """
        Use leidenalg find_partition with RBConfigurationVertexPartition.
        """
        partition = la.find_partition(
            graph,
            la.RBConfigurationVertexPartition,
            resolution_parameter=self.resolution,
        )
        # partition.membership is a list of community membership per node index
        return partition.membership


class LouvainClusterer(Clusterer):
    """
    Community detection via the built-in igraph Louvain algorithm.
    """

    def find_partition(self, graph: ig.Graph) -> List[int]:
        """
        Use igraph's community_multilevel (Louvain) method.
        """
        clustering = graph.community_multilevel()
        # membership: a list where idx → community ID
        return clustering.membership
