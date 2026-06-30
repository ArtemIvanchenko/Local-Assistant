"""Ollama clients: router (Qwen3-1.7B), main (Qwen3.5-4B), embeddings.

Handles model selection, streaming, speculative decoding, and the fallback to
Qwen3-4B-Instruct if Gated DeltaNet is unstable on the local build. (phase 1-2)
"""
