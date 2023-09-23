from tqdm.autonotebook import tqdm
from archetypal.idfclass import IDF
import networkx as nx
from eppy.idf_msequence import Idf_MSequence as idfm
from eppy.bunch_subclass import BadEPFieldError
from geomeppy.patches import EpBunch
from pydantic import BaseModel, UUID4, Field
from uuid import uuid4


# TODO: use data from pydantic IDD to setup dynamic object models

# TODO: consider representing non-object entities in a separate graph,
# e.g. supply/demand inlet/outlet nodes

# TODO: consider adding utilities for analyzing orphans, disjoint subgraphs
# etc.


class Node(BaseModel):
    id: UUID4 = Field(..., default_factory=lambda: uuid4())
    name: str
    type: str
    object: EpBunch

    class Config:
        arbitrary_types_allowed = True

    def __hash__(self):
        return hash(self.id.int)


class Edge(BaseModel):
    source: Node
    target: Node
    type: tuple[str, str]
    field: str

    def __hash__(self):
        return hash(f"SOURCE:{self.source}_TARGET:{self.target}_FIELD:{self.field}")


def create_graph(idf: IDF) -> tuple[list[Node], list[Edge], nx.MultiDiGraph]:
    """
    Convert an IDF file to a graph represented as two lists, nodes and edges.

    Each node stores its name, object type, and the original EpBunch object.
    If the IDF object does not have a name (e.g. the 'VERSION' object), it is
    named as the object type followed by an incrementing index.

    Edges store the name of the source and the name of the target, as well as the
    type of the edge, which is a tuple of the source and target object types,
    as well as the field name associated with the connection.  This is useful for
    distinguishing multi-edges, i.e. when a day is used in multiple schedules.

    Args:
        idf (IDF): The IDF to convert

    Returns:
        nodes (list[Node]): A list of the node objects
        edges (list[Edge]): A list of the edge objects
        graph (nx.MultiDiGraph): A multi-edge directed graph representing the IDF file.


    """
    nodes: list[Node] = []
    type_counts: dict[str, int] = {}
    edges: list[Edge] = []

    # iterate over all object types in file
    for objtype in tqdm(idf.idfobjects.keys()):
        # get the associated objects for a particular type
        objs: idfm = idf.idfobjects[objtype]
        for obj in objs:
            # If the object has a name, use it, otherwise
            # use the objects type along with an incrementer
            try:
                name = obj.Name
            except BadEPFieldError as e:
                if objtype in type_counts:
                    type_counts[objtype] += 1
                else:
                    type_counts[objtype] = 0
                name = f"{objtype}_{type_counts[objtype]:03d}"

            # Save the node
            node = Node(
                name=name,
                type=objtype,
                object=obj,
            )
            nodes.append(node)

    # make a hashmap for easy lookup
    nodes_dict = {(obj.type, obj.name): obj for obj in nodes}
    if len(nodes_dict) != len(nodes):
        duped_nodes: list[Node] = []
        node_counts = {}
        for node in nodes:
            if (node.type, node.name) in node_counts:
                duped_nodes.append(node)
                node_counts[node.name] += 1
            else:
                node_counts[node.name] = 1
        for node in duped_nodes:
            print(f"There are multiple nodes with the name {node.name}")

    assert len(nodes_dict) == len(
        nodes
    ), f"There are multiple nodes with the same name!"
    # Iterate over all nodes
    for source in nodes:
        # get the epbunch object
        obj = source.object
        # Iterate over field names
        for field in obj.fieldnames:
            # skip the name field
            if field == "Name":
                continue
            # get the field value
            fieldvalue = obj[field]
            # make sure there's no weirdness...
            assert type(fieldvalue) in [
                str,
                float,
                int,
            ], f"Found a field with an unsupported type: {field},{fieldvalue}"
            # check that the field value is in the hashmap; if so, assume it
            # is a reference to another object.
            if fieldvalue in [
                node_name for (node_type, node_name) in nodes_dict.keys()
            ]:
                # get the referenced object
                # TODO: check the IDD for duplicate name case
                candidate_nodes = list(
                    filter(lambda obj: obj.name == fieldvalue, nodes_dict.values())
                )
                if len(candidate_nodes) > 1:
                    print(
                        f"WARNING: Source Node {source.type}:{source.name} has multiple targets "
                        f"for field:{field}! Candidates:"
                    )
                    for candidate in candidate_nodes:
                        print(candidate)
                    continue

                target = candidate_nodes[0]
                # save the edge
                edge = Edge(
                    source=source,
                    target=target,
                    type=(source.type, target.type),
                    field=field,
                )
                edges.append(edge)

    # Create the multi-digraph
    g = nx.MultiDiGraph()
    for node in nodes:
        g.add_node(node)
    for edge in edges:
        g.add_edge(edge.target, edge.source, edge.field, type=edge.type)

    return nodes, edges, g
