import os
import re
import subprocess

def run_cmd(cmd, input_data=None):
    print(f"Running: {cmd}")
    p = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE if input_data else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy()
    )
    stdout, stderr = p.communicate(input=input_data)
    if p.returncode != 0:
        return False, stderr.decode()
    return True, stdout.decode()

# Read .env
env_vals = {}
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Matches KEY=VAL, KEY='VAL', KEY="VAL"
            m = re.match(r"^([\w_]+)\s*=\s*['\"]?(.*?)['\"]?$", line)
            if m:
                key, val = m.groups()
                # Clean up any trailing/leading single/double quotes that re might have missed or left
                if val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                elif val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                env_vals[key] = val

# Secrets to create
secrets = {
    "ANTHROPIC_API_KEY": env_vals.get("ANTHROPIC_API_KEY", ""),
    "UPSTASH_VECTOR_REST_URL": env_vals.get("UPSTASH_VECTOR_REST_URL", ""),
    "UPSTASH_VECTOR_REST_TOKEN": env_vals.get("UPSTASH_VECTOR_REST_TOKEN", ""),
    "FLASK_SECRET_KEY": "clinical-ai-flask-secret-key-prod-9988"
}

project = "healthcare-ai-manoj"

# Set environment paths for execution
os.environ["CLOUDSDK_PYTHON"] = "/Users/manojpotharlankavenkatanaga/opt/anaconda3/bin/python3.8"
os.environ["PATH"] = os.environ.get("PATH", "") + ":/Users/manojpotharlankavenkatanaga/Desktop/GCP/google-cloud-sdk/bin"

for secret_name, secret_val in secrets.items():
    if not secret_val:
        print(f"⚠️ Warning: No value found in .env for {secret_name}")
        continue
    
    # Check if secret exists
    check_cmd = f"gcloud secrets describe {secret_name} --project={project}"
    ok, _ = run_cmd(check_cmd)
    if not ok:
        print(f"🔒 Secret {secret_name} does not exist. Creating it...")
        create_cmd = f"gcloud secrets create {secret_name} --replication-policy=automatic --project={project}"
        ok, err = run_cmd(create_cmd)
        if not ok:
            print(f"❌ Failed to create secret {secret_name}: {err}")
            continue
    else:
        print(f"ℹ️ Secret {secret_name} already exists.")
        
    # Add version
    print(f"🔑 Adding new version for {secret_name}...")
    version_cmd = f"gcloud secrets versions add {secret_name} --data-file=- --project={project}"
    ok, err = run_cmd(version_cmd, input_data=secret_val.encode('utf-8'))
    if ok:
        print(f"✅ Successfully updated secret version for {secret_name}")
    else:
        print(f"❌ Failed to update secret version for {secret_name}: {err}")

print("🎉 Secret setup process complete.")
