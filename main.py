import asyncio
from typing import Hashable

import httpx
import networkx as nx
from networkx import DiGraph
from pyvis.network import Network


async def fetch_package(client, package_name):
    """Fetches package metadata from the npm registry."""
    url = f"https://registry.npmjs.org/{package_name}/latest"
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


async def build_graph(root_package, max_depth=3):
    """Builds a NetworkX Directed Graph of dependencies."""
    graph = nx.DiGraph()
    visited = set()
    queue = asyncio.Queue()

    # 1. Explicitly initialize the root node with its attributes
    graph.add_node(root_package, level=0, group=0, title=f"<b>{root_package}</b><br>Level: 0")
    await queue.put((root_package, 0))

    async with httpx.AsyncClient() as client:
        while not queue.empty():
            pkg_name, depth = await queue.get()

            if pkg_name in visited or depth > max_depth:
                queue.task_done()
                continue

            visited.add(pkg_name)
            data = await fetch_package(client, pkg_name)

            if not data:
                queue.task_done()
                continue

            dependencies = data.get("dependencies", {})

            for dep_name in dependencies.keys():
                # 2. Add the dependency node WITH its depth attributes before drawing the edge.
                # Because this is BFS, the first time we see a node is its shallowest depth.
                if dep_name not in graph:
                    graph.add_node(dep_name, level=depth + 1, group=depth + 1,
                                   title=f"<b>{dep_name}</b><br>Level: {depth + 1}")

                # Now it's safe to draw the edge
                graph.add_edge(pkg_name, dep_name)
                await queue.put((dep_name, depth + 1))

            queue.task_done()

    return graph


async def print_levels(g: DiGraph[Hashable]):
    # --- 1. Console Output of Levels ---
    print("\n--- Dependency Tree by Level ---")
    nodes_by_level = {}
    for node, data in g.nodes(data=True):
        lvl = data.get('level', 0)
        nodes_by_level.setdefault(lvl, []).append(node)

    for lvl in sorted(nodes_by_level.keys()):
        pkgs = nodes_by_level[lvl]
        print(f"Level {lvl} ({len(pkgs)} packages):")
        # Truncate terminal output if a level has massive amounts of packages
        if len(pkgs) > 10:
            print(f"  {', '.join(pkgs[:10])} ... and {len(pkgs) - 10} more")
        else:
            print(f"  {', '.join(pkgs)}")
    print("--------------------------------\n")


async def print_graph(g: DiGraph[Hashable]):
    # --- 2. PyVis Visualization ---
    print("Generating interactive HTML visualization...")
    net = Network(height="800px", width="100%", directed=True, bgcolor="#222222", font_color="white")
    net.from_nx(g)

    # Inject vis.js options for hierarchical layout and selection styling
    net.set_options("""
    var options = {
      "configure": {
        "enabled": true,
        "filter": "layout, physics"
      },
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "LR",
          "sortMethod": "directed",
          "nodeSpacing": 100,
          "levelSeparation": 250
        }
      },
      "nodes": {
        "color": {
          "highlight": {
            "background": "#ff2a2a", 
            "border": "#ffffff"
          }
        },
        "font": { "size": 16 }
      },
      "edges": {
        "color": {
          "color": "#555555",
          "highlight": "#ff2a2a"
        },
        "smooth": { "type": "cubicBezier", "forceDirection": "horizontal" }
      },
      "interaction": {
        "selectConnectedEdges": true
      }
    }
    """)

    output_file = "npm_dependencies.html"
    net.save_graph(output_file)
    print(f"Visualization saved to '{output_file}'.")


async def main():
    target_pkg = "express"
    print(f"Building dependency graph for '{target_pkg}'...")

    g = await build_graph(target_pkg, max_depth=2)
    print(f"Graph built: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

    await print_levels(g)

    await print_graph(g)





if __name__ == "__main__":
    asyncio.run(main())