import sys
import asyncio
import importlib
import json
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from Data.ragas_evaluation_script import run_ragas_evaluation
import config

# Define the sweep parameters
elasticsearch_weights = [0.0, 0.3, 0.5, 0.7, 1.0]
semantic_weights = [1.0, 0.7, 0.5, 0.3, 0.0]
modes = [True, False]  # True = hybrid (RRF), False = non-hybrid (simple merge)
rrf_ks = [30, 60, 90]  # Optionally sweep over RRF k values

results = []

async def sweep():
    for mode in modes:
        for k in rrf_ks:
            for es_w, sem_w in zip(elasticsearch_weights, semantic_weights):
                # Patch config in memory
                config.use_rrf_merging = mode
                config.rrf_elasticsearch_weight = es_w
                config.rrf_semantic_weight = sem_w
                config.rrf_k = k

                # Optionally, reload modules that cache config (if needed)
                importlib.reload(config)

                print(f"\nRunning with use_rrf_merging={mode}, es_weight={es_w}, sem_weight={sem_w}, rrf_k={k}")
                result = await run_ragas_evaluation()
                result['config'] = {
                    'use_rrf_merging': mode,
                    'rrf_elasticsearch_weight': es_w,
                    'rrf_semantic_weight': sem_w,
                    'rrf_k': k,
                }
                results.append(result)

                # Save intermediate results
                with open("sweep_results.json", "w") as f:
                    json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(sweep()) 