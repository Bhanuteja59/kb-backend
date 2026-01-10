
import os

env_path = ".env"
target_key = "MAIL_FROM"
new_value = "bhanutejareddy59@gmail.com"
lines = []

if os.path.exists(env_path):
    with open(env_path, "r") as f:
        read_lines = f.readlines()
    
    key_found = False
    for line in read_lines:
        if line.startswith(target_key + "="):
            lines.append(f"{target_key}={new_value}\n")
            key_found = True
        else:
            lines.append(line)
    
    if not key_found:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"{target_key}={new_value}\n")
    
    with open(env_path, "w") as f:
        f.writelines(lines)
    print(f"Updated {target_key} to {new_value}")
else:
    print(".env file not found")
