from nexus_mcp.nodes.worker_node import get_implementation

result = get_implementation(
    symbol_name="crawl_and_index",
    file_path="nexus_mcp/nodes/indexer_node.py",
)

if result is None:
    print("Not found")
else:
    print(result.model_dump())
    print("\nCODE:\n")
    print(result.code)