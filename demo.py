from nexus_mcp.nodes.indexer_node import crawl_and_index
from nexus_mcp.logic.indexer import search_symbols
from nexus_mcp.nodes.worker_node import get_implementation

print("🔧 Building index...")
count = crawl_and_index()
print(f"Indexed {count} symbols\n")

query = "index"
print(f"🔍 Searching for: '{query}'")

results = search_symbols(query)

for i, r in enumerate(results[:5]):
    print(f"{i+1}. {r.symbol_name} ({r.file_path})")

# pick first result
if not results:
    print("No results found")
    exit()

symbol = results[0]

print("\n📂 Fetching implementation...\n")

impl = get_implementation(
    symbol_name=symbol.symbol_name,
    file_path=symbol.file_path,
)

if impl:
    print(f"Function: {impl.symbol_name}")
    print(f"File: {impl.file_path}")
    print(f"Lines: {impl.line_start}-{impl.line_end}")
    print("\n--- CODE ---\n")
    print(impl.code)
else:
    print("Implementation not found")