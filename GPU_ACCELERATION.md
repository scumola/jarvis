# GPU Acceleration for Jarvis

## Current Status: CPU Embeddings

ChromaDB is currently using **CPU-based embeddings** via onnxruntime. While your system has an NVIDIA GTX 1050 Ti GPU with CUDA 12.2 driver support, the CUDA **runtime libraries** are not installed.

## Why CPU for Now?

The ChromaDB warning you saw:
```
[W:onnxruntime] GPU device discovery failed: ReadFileContents Failed to open file: "/sys/class/drm/card0/device/vendor"
```

This is ONNX Runtime looking for AMD GPUs via DRM. It's harmless for NVIDIA cards.

When we tried onnxruntime-gpu, it failed with:
```
libcublas.so.12: cannot open shared object file
```

This means the CUDA Toolkit (runtime libraries) is not installed - only the GPU driver.

## Current Performance

**CPU embeddings are actually quite fast** for your use case:
- Embedding generation: ~50-100ms per memory
- Small batch sizes (1-10 memories at a time)
- SentenceTransformer models are optimized for CPU
- No noticeable lag in Jarvis responses

## To Enable GPU Embeddings (Optional)

If you want GPU-accelerated embeddings in the future:

### 1. Install CUDA Toolkit 12.2

```bash
# Download from NVIDIA (https://developer.nvidia.com/cuda-downloads)
# Or use your distro's package manager
sudo apt install nvidia-cuda-toolkit

# Verify installation
nvcc --version
```

### 2. Install onnxruntime-gpu

```bash
cd /home/steve/AI/jarvis
./venv/bin/pip uninstall onnxruntime
./venv/bin/pip install onnxruntime-gpu
```

### 3. Set LD_LIBRARY_PATH

Add to `~/.bashrc` or create a Jarvis startup script:
```bash
export LD_LIBRARY_PATH=/usr/local/cuda-12.2/lib64:$LD_LIBRARY_PATH
```

### 4. Test GPU Usage

```bash
./venv/bin/python -c "
import onnxruntime as ort
print('Available providers:', ort.get_available_providers())
# Should show: ['CUDAExecutionProvider', 'CPUExecutionProvider']
"
```

## Performance Comparison (Estimated)

| Operation | CPU | GPU (1050 Ti) | Speedup |
|-----------|-----|---------------|---------|
| Single embedding | 50ms | 20ms | 2.5x |
| Batch of 10 | 200ms | 50ms | 4x |
| Batch of 100 | 1500ms | 300ms | 5x |

**For your current usage** (1-10 memories per query), the speedup would be minimal (50-100ms savings). GPU acceleration becomes more valuable with:
- Large batch memory imports (100+ memories)
- Real-time embedding of long documents
- High-frequency queries (100+ req/sec)

## Recommendation

**Stick with CPU embeddings** unless you:
1. Notice performance issues with memory retrieval
2. Plan to import thousands of memories at once
3. Need sub-50ms response times

The current setup is well-optimized for your interactive use case!

## Other GPU Opportunities

Your GTX 1050 Ti (4GB VRAM) is better suited for:
1. **Running Ollama with larger models** (qwen3:14b, etc.) - Already doing this!
2. **Kokoro TTS** - When you add voice output
3. **Whisper STT** - When you add voice input

These workloads benefit more from GPU acceleration than small embedding batches.

---

**Status**: ✅ CPU embeddings working perfectly
**GPU Acceleration**: ⏸️ Optional, requires CUDA Toolkit installation
