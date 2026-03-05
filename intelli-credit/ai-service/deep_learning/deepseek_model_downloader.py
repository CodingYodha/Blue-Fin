from huggingface_hub import snapshot_download
import os


save_path = "./models/deepseek-vl2-tiny"
os.makedirs(save_path, exist_ok=True)


snapshot_download(
    repo_id="deepseek-ai/deepseek-vl2-tiny",
    local_dir=save_path,
    local_dir_use_symlinks=False,
    resume_download=True
)

print(f" Downloaded to: {save_path}")
