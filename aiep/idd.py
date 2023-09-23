from archetypal.idfclass import IDF
import networkx as nx
from typing import Optional, Annotated, Iterator, Union
from pydantic import BaseModel, Field, BeforeValidator


# TODO: automatically define IDDField rather than
# hardcode it.  see work in notebook about intelligently
# determine the correct configuration for each IDDField attr

# TODO: incorporate idf.idd_index data

# TODO: cast int fields from str to int with a new type alias with beforevalidator, ala boolean


def is_singleton(v):
    if isinstance(v, list):
        if len(v) != 1:
            # There are a few fields like type, units, autosizable, and retaincase
            # which are only ever meant to have a single length list,
            # but occasionally have duplicate values, like units set
            # to ['W', 'W'] or autosizable set to ['', '']
            if all([val == v[0] for val in v]):
                return v[0]
            raise ValueError(f"List length must be equal to 1 item, not {len(v)} items")
        else:
            return v[0]
    else:
        return v


def is_boolean_singleton(v):
    # Boolean yes is always defined with an empty
    # string, otherwise empty
    v = is_singleton(v)
    if v != "":
        raise ValueError(f"Boolean field must be empty string, not '{v}'.")
    else:
        return True


def join_arr_to_str(v):
    return " ".join(v)


# Type Alias for Singleton Lists
ListAsJoinedStr = Optional[Annotated[str, BeforeValidator(join_arr_to_str)]]
ListAsSingletonStr = Optional[Annotated[str, BeforeValidator(is_singleton)]]
ListAsSingletonBoolean = Annotated[bool, BeforeValidator(is_boolean_singleton)]


class IDD(BaseModel, extra="forbid"):
    schemas: dict[str, "IDDObjectSchema"] = {}

    def __len__(self) -> int:
        return len(self.schemas)

    def __getitem__(self, obj_type: str) -> "IDDObjectSchema":
        if obj_type not in self.schemas:
            raise ValueError(
                f"There is no object schema for '{obj_type}' registered in this IDD."
            )
        else:
            return self.schemas[obj_type]

    def __iter__(self) -> Iterator["IDDObjectSchema"]:
        return iter(self.schemas.values())

    def make_graph(self):
        graph = nx.MultiDiGraph()
        for source in self:
            graph.add_node(source)

        for source in self:
            for field in source:
                if field.validobjects is not None:
                    for target in field.validobjects:
                        assert target.upper() in self.schemas
                        target = self.schemas[target.upper()]
                        graph.add_edge(source, target, key=field.name)
        return graph

    @classmethod
    def from_idf(cls, idf: IDF):
        idd = cls()
        for idfobj_schema in idf.idd_info:
            idfobj_type = idfobj_schema[0]["idfobj"]

            header_dict = {
                key: val
                for key, val in idfobj_schema[0].items()
                if "extensible" not in key.lower()
            }
            header = IDDObjectHeader(**header_dict)
            extensible_keys = [
                key for key in idfobj_schema[0] if "extensible" in key.lower()
            ]
            assert (
                (len(extensible_keys) == 1) if len(extensible_keys) > 0 else True
            ), f"An object can only have 1 'extensible:N' key, but {idfobj_type} has multiple: {extensible_keys}"
            if len(extensible_keys) > 0:
                header.extensible = int(extensible_keys[0].split(":")[-1])

            idd_obj_schema = IDDObjectSchema(
                object_type=idfobj_type.upper(),
                header=header,
            )
            idd.schemas[idd_obj_schema.object_type] = idd_obj_schema
            for schema_entry in idfobj_schema:
                if "field" in schema_entry:
                    iddfield = IDDField(**schema_entry)
                    idd_obj_schema.field_definitions[iddfield.name] = iddfield

        return idd


class IDDObjectHeader(BaseModel, extra="forbid"):
    object_type: str = Field(..., alias="idfobj")
    # TODO: dynamically construct group enum type?
    memo: ListAsJoinedStr = None
    unique_object: ListAsSingletonBoolean = Field(default=False, alias="unique-object")
    format: ListAsSingletonStr = None
    group: str
    min_fields: ListAsSingletonStr = Field(default=None, alias="min-fields")
    required_object: ListAsSingletonBoolean = Field(
        default=False, alias="required-object"
    )
    obsolete: ListAsSingletonStr = None
    extensible: Optional[int] = None


class IDDObjectSchema(BaseModel, extra="forbid"):
    object_type: str
    header: IDDObjectHeader
    field_definitions: dict[str, "IDDField"] = {}

    def __hash__(self):
        return hash(self.object_type)

    def __getitem__(self, field_name: str) -> "IDDField":
        if field_name in self.field_definitions:
            return self.field_definitions[field_name]
        else:
            raise KeyError(
                f"IDDObjectSchema:{self.object_type} does not have a field called '{field_name}'.  Available fields: {', '.join(self.fields)}"
            )

    def __iter__(self) -> Iterator["IDDField"]:
        return iter(self.field_definitions.values())

    @property
    def fields(self) -> set[str]:
        return set(self.field_definitions.keys())


class IDDField(BaseModel, extra="forbid"):
    name: Annotated[
        str,
        BeforeValidator(is_singleton),
    ] = Field(..., alias="field")
    default: ListAsSingletonStr = None
    note: ListAsJoinedStr = None
    type: ListAsSingletonStr = None
    key: Optional[list[str]] = None

    minimum: ListAsSingletonStr = None
    maximum: ListAsSingletonStr = None
    minimum_strict: ListAsSingletonStr = Field(default=None, alias="minimum>")
    maximum_strict: ListAsSingletonStr = Field(default=None, alias="maximum<")

    retaincase: ListAsSingletonBoolean = Field(default=False)

    object_list: Optional[list[str]] = Field(default=None, alias="object-list")
    begin_extensible: ListAsSingletonBoolean = Field(
        default=False, alias="begin-extensible"
    )
    validobjects: Optional[list[str]] = None
    required_field: ListAsSingletonBoolean = Field(
        default=False, alias="required-field"
    )
    reference: Optional[list[str]] = None
    units: ListAsSingletonStr = None
    ip_units: ListAsSingletonStr = Field(default=None, alias="ip-units")
    unitsbasedonfield: ListAsSingletonStr = None
    autocalculatable: ListAsSingletonBoolean = Field(default=False)
    reference_class_name: Optional[list[str]] = Field(
        default=None, alias="reference-class-name"
    )
    autosizable: ListAsSingletonBoolean = Field(default=False)
    external_list: ListAsSingletonStr = Field(default=None, alias="external-list")
