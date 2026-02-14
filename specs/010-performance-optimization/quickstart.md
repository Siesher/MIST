# Quickstart: Performance Optimization

**Feature**: 010-performance-optimization
**Date**: 2026-02-03

## Prerequisites

- Python 3.11+
- Ollama running with GLM-4.7-Flash model
- NVIDIA GPU with 8GB+ VRAM
- Existing MITS installation (feature 009 completed)

## Quick Setup

### 1. Install Additional Dependencies

```bash
pip install pynvml psutil matplotlib seaborn
```

### 2. Initialize Database Schema

```bash
python -c "from src.inference.metrics import MetricsCollector; MetricsCollector().initialize_schema()"
```

### 3. Verify Ollama Optimization

```bash
# Check Flash Attention is enabled
ollama show glm-4.7-flash --modelfile | grep -i flash

# Set environment variable if needed
export OLLAMA_FLASH_ATTENTION=1  # Linux/Mac
$env:OLLAMA_FLASH_ATTENTION=1    # PowerShell
```

### 4. Create Few-Shot Examples Directory

```bash
mkdir -p data/few_shot
mkdir -p data/reports
```

### 5. Run Performance Test

```bash
python -c "
from src.inference.cache import TutoringCacheManager
from src.inference.metrics import MetricsCollector

cache = TutoringCacheManager()
metrics = MetricsCollector()

print(f'Cache entries: {cache.get_stats().total_entries}')
print(f'Cache hit rate: {cache.get_stats().hit_rate:.1%}')
print('Performance optimization ready!')
"
```

## Key Features Usage

### Semantic Caching

```python
from src.inference.cache import TutoringCacheManager, CacheQuery

cache = TutoringCacheManager()

# Check cache
result = cache.lookup(CacheQuery(
    query="Как найти производную произведения?",
    topic="derivatives",
    difficulty="medium",
    student_level="intermediate",
    session_id="session_123"
))

if result.hit_type != CacheHitType.MISS:
    print(f"Cache hit! Response: {result.response[:100]}...")
```

### A/B Testing

```python
from src.inference.ab_testing import ABTesting

ab = ABTesting()

# Create experiment
ab.create_experiment(
    experiment_id="cot_test_001",
    name="Chain-of-Thought vs Standard",
    variants=[
        {"id": "control", "config": {"use_cot": False}},
        {"id": "treatment", "config": {"use_cot": True}}
    ],
    allocation_weights=[0.5, 0.5],
    target_metric="success_rate"
)

# Get assignment for session
assignment = ab.get_variant("cot_test_001", "session_456")
print(f"Assigned variant: {assignment.variant_id}")
```

### Context Compression

```python
from src.inference.context_compressor import ContextCompressor

compressor = ContextCompressor()

# Check if compression needed
if compressor.should_compress(conversation, token_threshold=4000):
    compressed = compressor.compress(conversation)
    print(f"Compressed from {compressed.original_tokens} to {compressed.compressed_tokens} tokens")
```

### Few-Shot Retrieval

```python
from src.knowledge.few_shot_bank import FewShotBank

bank = FewShotBank()

# Get relevant examples
examples = bank.retrieve(
    current_problem="Найди производную f(x) = x³ · cos(x)",
    topic="derivatives",
    difficulty="medium",
    count=2
)

for ex in examples:
    print(f"Example: {ex.problem[:50]}...")
```

### Report Generation

```python
from src.logging.report_generator import ReportGenerator
from datetime import datetime, timedelta

generator = ReportGenerator()

# Generate daily report
report = generator.generate(
    report_type="daily",
    period_start=datetime.now() - timedelta(days=1),
    period_end=datetime.now()
)

print(f"Report saved to: {report.export_paths['json']}")
print(f"Charts: {report.chart_paths}")
```

### Resource Monitoring

```python
from src.inference.metrics import ResourceMonitor

monitor = ResourceMonitor()

# Start background monitoring
monitor.start(interval_seconds=30)

# Get current sample
sample = monitor.sample()
print(f"VRAM: {sample.vram_used_mb}MB / {sample.vram_total_mb}MB")
print(f"RAM: {sample.ram_used_mb}MB")

# Stop monitoring
monitor.stop()
```

## Configuration

Key settings in `src/config.py`:

```python
# Cache settings
CACHE_MAX_SIZE = 1000
CACHE_SIMILARITY_THRESHOLD = 0.90
CACHE_TTL_HOURS = 24

# Performance targets
TARGET_RESPONSE_TIME_MS = 2000
TARGET_CACHE_HIT_RATE = 0.20
TARGET_VRAM_MB = 7000

# Context compression
COMPRESSION_TOKEN_THRESHOLD = 4000
RECENT_MESSAGES_TO_KEEP = 10

# Few-shot
FEW_SHOT_COUNT = 2
FEW_SHOT_MIN_SIMILARITY = 0.5

# Resource monitoring
RESOURCE_SAMPLE_INTERVAL_SEC = 30
VRAM_ALERT_THRESHOLD_MB = 7000
RAM_ALERT_THRESHOLD_MB = 14000
```

## Verification

Run the performance test suite:

```bash
pytest tests/integration/test_performance.py -v
```

Expected results:
- Response time < 2 seconds (new requests)
- Response time < 0.5 seconds (cached)
- VRAM usage < 7GB
- No memory leaks over 2-hour session

## Troubleshooting

### High Response Time

1. Check cache hit rate: `cache.get_stats().hit_rate`
2. Verify Ollama settings: `ollama show glm-4.7-flash`
3. Check context size: may need compression

### VRAM Alerts

1. Check model quantization: should be 4-bit
2. Reduce `num_ctx` in config if needed
3. Check for memory leaks with `monitor.get_trend()`

### Cache Miss Rate High

1. Check similarity threshold (may be too high)
2. Verify embeddings are being computed
3. Check if topics match between queries
