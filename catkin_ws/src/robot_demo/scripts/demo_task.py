import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("--task")
args = parser.parse_args() 

print("=" * 40) 
print(f"{args.task} started") 
print("=" * 40)

for i in range(5): 
    print(f"[INFO] Executing step {i + 1}/5")
    time.sleep(1) 
    
print("[INFO] Task completed.")