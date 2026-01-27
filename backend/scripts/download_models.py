"""Download sentence-transformer models for offline deployment."""

import os
from pathlib import Path
from huggingface_hub import snapshot_download

MODELS = [
    'sentence-transformers/all-MiniLM-L6-v2',
    # 'sentence-transformers/all-mpnet-base-v2',
    # 'sentence-transformers/multi-qa-MiniLM-L6-cos-v1',
    # 'sentence-transformers/all-distilroberta-v1',
    # 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
]

def main():
    # Use HF_HOME if set (Docker), otherwise use huggingface_hub's default (~/.cache/huggingface)
    hf_home = os.getenv('HF_HOME')

    if hf_home:
        cache_dir = f'{hf_home}/huggingface'
        print('=' * 60)
        print('Downloading models for offline deployment (Docker/Production)')
        print('=' * 60)
        print(f'HF_HOME: {hf_home}')
        print(f'Cache directory: {cache_dir}\n')
    else:
        cache_dir = None  # Let huggingface_hub use default location
        default_cache = Path.home() / '.cache' / 'huggingface'
        print('=' * 60)
        print('Downloading models for offline deployment (Local Development)')
        print('=' * 60)
        print(f'Cache directory: {default_cache} (default)\n')

    for i, model in enumerate(MODELS, 1):
        print(f'[{i}/{len(MODELS)}] Downloading {model}...')
        try:
            snapshot_download(
                repo_id=model,
                cache_dir=cache_dir,
                repo_type='model'
            )
            print(f'[{i}/{len(MODELS)}] ✅ Successfully downloaded {model}\n')
        except Exception as e:
            print(f'[{i}/{len(MODELS)}] ❌ Failed to download {model}: {e}')
            raise

    print('=' * 60)
    print('🎉 All models downloaded successfully!')
    print('=' * 60)

if __name__ == '__main__':
    main()