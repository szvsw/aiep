import streamlit as st
import networkx as nx
from archetypal.idfclass import IDF

from idd import IDD

st.set_page_config(
    page_title="AI-EP",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def load_idf(file):
    with open("tester.idf", "wb") as f:
        f.write(file.read())
    idf = IDF(idfname="tester.idf")
    idd = IDD.from_idf(idf)
    graph = idd.make_graph()
    cat_graph = nx.DiGraph()
    groups = set()
    for node in graph.nodes:
        cat_graph.add_edge(node.header.group, node)
        groups.add(node.header.group)

    return idf, idd, graph, cat_graph, sorted(list(groups))


def render():
    st.title("AIEP")

    with st.expander("Upload", expanded="idf_file" not in st.session_state):
        file = st.file_uploader(label="Upload an IDF", type=".idf", key="idf_file")
    if "cursor" not in st.session_state:
        st.session_state.cursor = "ZONE"
    if file is not None:
        idf, idd, graph, cat_graph, groups = load_idf(file)
        if st.session_state.cursor is None:
            left, right = st.columns(2)
            with left:
                selected_category = st.selectbox(
                    label="Select an object category",
                    options=groups,
                )
                cat_objs = cat_graph.successors(selected_category)
            with right:
                selected_object = st.selectbox(
                    f"{selected_category} Objects",
                    options=cat_objs,
                    format_func=lambda obj: obj.object_type,
                )
            clicked = st.button(
                "Load Object Definition", use_container_width=True, type="primary"
            )
            if clicked:
                st.session_state.cursor = selected_object.object_type
                st.experimental_rerun()

        else:
            clicked = st.button(
                "Back to Object Browser",
                use_container_width=True,
                type="secondary",
            )
            if clicked:
                st.session_state.cursor = None
                st.experimental_rerun()
            root = idd[st.session_state.cursor]
            referenced_by = graph.predecessors(root)

            st.header(f"`{root.object_type}`")
            st.markdown(f"Category: `{root.header.group}`")
            if root.header.extensible is not None:
                st.write(
                    "Extensible",
                    list(root.field_definitions.values())[root.header.extensible].name,
                )
            if root.header.memo:
                st.markdown(f"*{root.header.memo.replace(':', '::')}*")
            metadata_col, ref_tab = st.tabs(["Schema", "Object References"])
            with metadata_col:
                for i, field in enumerate(root):
                    if root.header.extensible is not None:
                        if i > root.header.extensible:
                            continue
                    l, r = st.columns([0.5, 0.5])
                    with l:
                        st.markdown(
                            f"{field.name} `{field.type}`{'*required*' if field.required_field else ''}"
                        )
                        if field.begin_extensible:
                            st.write("(Start of list)")
                    with r:
                        md_str = []
                        if field.default is not None:
                            md_str.append(f"default: `{field.default}`")
                        if field.minimum is not None:
                            md_str.append(f"minimum: `{field.minimum}`")
                        if field.maximum is not None:
                            md_str.append(f"maximum: `{field.maximum}`")
                        if field.key:
                            md_str.append(f"choices: `{'` | `'.join(field.key)}`")

                        if field.reference:
                            md_str.append(
                                f"Reference Categories: `{'` | `'.join(field.reference)}`"
                            )
                        if field.autocalculatable:
                            md_str.append(
                                f"autocalculatable: `{field.autocalculatable}`"
                            )
                        if field.autosizable:
                            md_str.append(f"autosizable: `{field.autosizable}`")
                        if field.object_list is not None:
                            md_str.append(
                                f"references: `{'` | `'.join(field.object_list)}`"
                            )
                        st.markdown(", ".join(md_str))

            with ref_tab:
                ref_to_col, ref_by_col = st.columns(2)
                with ref_to_col:
                    st.subheader("References")
                    for field in root:
                        if field.validobjects:
                            for obj in field.validobjects:
                                clicked = st.button(
                                    f'({field.name}) `{obj.replace(":", "::")}`',
                                    key=f"{root.object_type}-{field.name}-{obj}",
                                    use_container_width=True,
                                )
                                if clicked:
                                    st.session_state.cursor = obj
                                    st.experimental_rerun()
                with ref_by_col:
                    st.subheader("Referenced By")
                    for obj in referenced_by:
                        reference_keys = ", ".join(list(graph[obj][root].keys()))
                        button_txt = (
                            f'`{obj.object_type.replace(":", "::")}`'
                            + "("
                            + reference_keys[:50]
                            + ("..." if len(reference_keys) > 50 else "")
                            + ")"
                        )
                        clicked = st.button(
                            button_txt, type="secondary", use_container_width=True
                        )

                        if clicked:
                            st.session_state.cursor = obj.object_type
                            st.experimental_rerun()


def old_expander():
    with st.expander(label="References", expanded=False):
        for obj in references:
            reference_keys = ", ".join(list(graph[root][obj].keys()))
            l, r = st.columns([0.2, 0.8])
            with l:
                clicked = st.button(
                    obj.object_type,
                )
            with r:
                st.write(
                    reference_keys[:50] + ("..." if len(reference_keys) > 50 else "")
                )
            if clicked:
                st.session_state.cursor = obj.object_type
                st.experimental_rerun()

    with st.expander(label="Referenced By", expanded=False):
        for obj in referenced_by:
            reference_keys = ", ".join(list(graph[obj][root].keys()))
            l, r = st.columns([0.2, 0.8])
            with l:
                clicked = st.button(obj.object_type)
            with r:
                st.write(
                    reference_keys[:50] + ("..." if len(reference_keys) > 50 else "")
                )

            if clicked:
                st.session_state.cursor = obj.object_type
                st.experimental_rerun()


render()
