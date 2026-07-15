
try:
    import tenacity
    print(f"Tenacity version: {tenacity.__version__}")
except ImportError:
    print("Tenacity NOT installed")
