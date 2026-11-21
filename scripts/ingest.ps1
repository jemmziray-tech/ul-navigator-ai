# Crawl the official UL seed sources and build/update the index (incremental).
param([int]$MaxPages = 150, [int]$MaxDepth = 2, [switch]$SeedsOnly)
$env:PYTHONPATH = "$PWD\backend;$PWD\ingestion"
$args2 = @("-m", "ul_ingest", "crawl", "--max-pages", $MaxPages, "--max-depth", $MaxDepth)
if ($SeedsOnly) { $args2 += "--seeds-only" }
.\.venv\Scripts\python @args2
