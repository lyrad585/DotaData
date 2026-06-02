import time
from tqdm import tqdm

# Simply wrap any iterable with tqdm()
for i in tqdm(range(100)):
    time.sleep(0.05)  # Simulating work
